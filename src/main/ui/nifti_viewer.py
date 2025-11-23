import re
import sys
import os
import gc
import json

import numpy as np
import nibabel as nib

from components.crosshair_graphic_view import CrosshairGraphicsView
from components.nifti_file_dialog import NiftiFileDialog
from logger import get_logger
from threads.nifti_utils_threads import ImageLoadThread, SaveNiftiThread

log = get_logger()

from PyQt6 import QtCore

# Attempt to import all required PyQt6 modules and fallback gracefully if not available
try:
    from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                 QLabel, QSlider, QPushButton, QFileDialog, QSpinBox,
                                 QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                                 QStatusBar, QMessageBox, QProgressDialog, QGridLayout,
                                 QSplitter, QFrame, QSizePolicy, QCheckBox, QComboBox, QScrollArea, QDialog, QLineEdit,
                                 QListWidget, QDialogButtonBox, QListWidgetItem, QGroupBox)
    from PyQt6.QtCore import Qt, QPointF, QTimer, QThread, pyqtSignal, QSize, QCoreApplication, QRectF
    from PyQt6.QtGui import (QPixmap, QImage, QPainter, QColor, QPen, QPalette,
                             QBrush, QResizeEvent, QMouseEvent, QTransform, QFont)
    from matplotlib.figure import Figure

    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    log.error("PyQt6 not available. Install with: pip install PyQt6")
    sys.exit(1)

# Configure matplotlib to use a non-interactive backend (for thread-safe rendering)
import matplotlib
matplotlib.use('Agg')
import matplotlib.cm as cm

# JIT optimization for numerical computations
from numba import njit, prange


@njit(parallel=True)
def compute_mask_numba_mm(img, x0, y0, z0, radius_mm, voxel_sizes,
                          seed_intensity, diff,
                          x_min, x_max, y_min, y_max, z_min, z_max):
    """
    Compute a binary spherical mask around a seed point in millimeter space.

    This function is compiled with Numba for high-performance execution and
    performs voxel-wise checks to include all voxels within a given radius
    (in mm) and within a specified intensity difference from a seed value.

    Args:
        img (np.ndarray): Input 3D image array.
        x0, y0, z0 (int): Coordinates of the seed voxel.
        radius_mm (float): Radius of the spherical mask in millimeters.
        voxel_sizes (tuple[float, float, float]): Physical voxel sizes along each axis.
        seed_intensity (float): Intensity value at the seed voxel.
        diff (float): Maximum allowed intensity difference from the seed.
        x_min, x_max, y_min, y_max, z_min, z_max (int): Bounding box limits in voxel space.

    Returns:
        np.ndarray: Binary mask (uint8) with 1 where the voxel meets the criteria.
    """
    mask = np.zeros(img.shape, dtype=np.uint8)
    r2 = radius_mm * radius_mm
    vx, vy, vz = voxel_sizes  # voxel dimensions in mm

    for x in prange(x_min, x_max):
        for y in range(y_min, y_max):
            for z in range(z_min, z_max):
                dx_mm = (x - x0) * vx
                dy_mm = (y - y0) * vy
                dz_mm = (z - z0) * vz
                if dx_mm * dx_mm + dy_mm * dy_mm + dz_mm * dz_mm <= r2:
                    if abs(img[x, y, z] - seed_intensity) <= diff:
                        mask[x, y, z] = 1
    return mask


@njit(parallel=True)
def apply_overlay_numba(rgba_image, overlay_mask, overlay_intensity, overlay_color):
    """
    Apply a semi-transparent overlay to an RGBA image.

    This function adds colorized overlay regions based on the provided mask and
    intensity map, applying blending only on RGB channels.

    Args:
        rgba_image (np.ndarray): Base image (H, W, 3) in float format (0–1 range).
        overlay_mask (np.ndarray): Binary mask (H, W) specifying overlay pixels.
        overlay_intensity (np.ndarray): Intensity weight map (H, W) for overlay blending.
        overlay_color (tuple[float, float, float]): RGB overlay color (0–1 range).

    Returns:
        np.ndarray: Modified RGBA image with overlay applied.
    """
    h, w, c = rgba_image.shape
    for y in prange(h):
        for x in range(w):
            if overlay_mask[y, x]:
                for ch in range(3):
                    # Apply color to RGB channels only
                    if overlay_color[ch] != 0:
                        rgba_image[y, x, ch] = min(1.0, rgba_image[y, x, ch] + overlay_intensity[y, x] * overlay_color[ch])
                    else:
                        rgba_image[y, x, ch] *= (1.0 - overlay_intensity[y, x])
    return rgba_image


def _slice(data, plane_idx, slice_idx):
    slice = None
    if plane_idx == 0:
        slice = data[:, :, slice_idx].T
        slice = np.flipud(slice)
    elif plane_idx == 1:
        slice = data[:, slice_idx, :].T
        slice = np.flipud(slice)
    elif plane_idx == 2:
        slice = data[slice_idx, :, :].T
        slice = np.flipud(slice)
    else:
        log.warning(f"Invalid plane_idx {plane_idx}")
    return slice

class NiftiViewer(QMainWindow):
    """
    Main application window for viewing and interacting with NIfTI images.

    This class provides a complete NIfTI image viewer with:
      - Triplanar slice visualization (axial, coronal, sagittal)
      - Support for 4D volumes (time series)
      - Overlay support for mask visualization
      - Interactive ROI drawing and threshold-based segmentation
      - Threaded image loading/saving

    Attributes:
        context (dict): Optional shared context for multi-component communication.
        img_data (np.ndarray): Loaded image data.
        overlay_data (np.ndarray): Optional overlay volume.
        affine (np.ndarray): Image affine transformation matrix.
        voxel_sizes (tuple[float]): Voxel dimensions (mm).
        current_slices (list[int]): Current indices for each viewing plane.
        current_time (int): Current time frame (for 4D data).
        overlay_alpha (float): Overlay transparency level.
        overlay_threshold (float): Intensity threshold for overlay visibility.
        colormap (str): Current colormap name used for visualization.
    """

    def __init__(self, context=None):
        """
        Initialize the NIfTI Viewer window and prepare all internal components.

        Args:
            context (dict, optional): Shared context for language translation and inter-component signaling.
        """
        super().__init__()


        self.threads = []
        self.context = context

        self.progress_dialog = None
        self.setWindowTitle(QtCore.QCoreApplication.translate("NIfTIViewer", "NIfTI Image Viewer"))
        self.setMinimumSize(1000, 700)
        self.resize(1400, 1000)

        # === Image data variables ===
        self.img_data = None
        self.affine = None
        self.dims = None
        self.is_4d = False
        self.current_slices = [0, 0, 0]  # axial, coronal, sagittal slice indices
        self.current_time = 0
        self.current_coordinates = [0, 0, 0]  # x, y, z voxel coordinates
        self.file_path = None
        self.stretch_factors = {}
        self.voxel_sizes = None

        # === Overlay-related attributes ===
        self.overlay_data = None
        self.overlay_dims = None
        self.overlay_alpha = 0.7
        self.overlay_threshold = 0.1
        self.overlay_enabled = False
        self.overlay_file_path = None
        self.overlay_max = 0
        self.overlay_thresholded_data = None

        # === UI element placeholders ===
        self.info_text = None
        self.plane_labels = None
        self.status_bar = None
        self.slice_info_label = None
        self.value_label = None
        self.coord_label = None

        # === Visualization color configuration ===
        self.colormap = 'gray'
        self.overlay_colors = {
            "gray": np.array([1.0, 0.0, 0.0]),
            "viridis": np.array([1.0, 0.0, 0.0]),
            "plasma": np.array([0.0, 1.0, 0.0]),
            "inferno": np.array([0.0, 1.0, 1.0]),
            "magma": np.array([0.0, 1.0, 1.0]),
            "hot": np.array([0.0, 1.0, 1.0]),
            "cool": np.array([1.0, 1.0, 0.0]),
            "bone": np.array([1.0, 0.0, 0.0])
        }

        # === Viewer components ===
        self.views = []
        self.scenes = []
        self.pixmap_items = []
        self.slice_sliders = []
        self.slice_spins = []
        self.slice_labels = []
        self.coord_displays = []

        # === Time-series visualization (for 4D data) ===
        self.time_slider = None
        self.time_spin = None
        self.time_checkbox = None
        self.time_plot_figure = None
        self.time_plot_canvas = None

        # === Additional UI components ===
        self.file_info_label = None
        self.slice_navigation_label = None
        self.time_point_label = None
        self.colormap_combo = None
        self.overlay_threshold_slider = None
        self.display_options_label = None
        self.overlay_alpha_slider = None
        self.overlay_info_label = None

        # === Automatic ROI drawing ===
        self.automaticROI_data = None
        self.automatic_ROI_label = None
        self.automaticROIbtn = None
        self.automaticROI_overlay = False
        self.automaticROI_radius_slider = None
        self.automaticROI_radius_label = None
        self.automaticROI_diff_label = None
        self.AutomaticROI_diff_slider = None
        self.automaticROI_sliders_group = None
        self.automaticROI_seed_coordinates = None
        self.ROI_save_btn = None
        self.automaticROI_overlay = None

        self.incrementalROI_data = None
        self.incrementalROI_checkbox = None
        self.incrementalROI_enabled = False
        self.addOrigin_btn = None
        self.cancelROI_btn = None
        self.incrementalROI_origins = []

        # === Initialize and connect the UI ===
        self.init_ui()
        self.setup_connections()

        # === Translation setup ===
        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def init_ui(self):
        """
        Initialize the main user interface of the NIfTI Viewer.

        This method builds the primary application layout, including:
        - A central widget that contains a horizontal splitter.
        - A left control panel for user interactions (file operations, display options, etc.).
        - A right area dedicated to image visualization.
        - A status bar for displaying real-time information (coordinates, intensity values, slice index).

        The layout uses a responsive design with adjustable proportions between
        the control panel and the image display area.

        Raises:
            Exception: Propagates exceptions from widget creation or layout setup.
        """
        # Create the central widget that will contain the main splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create a horizontal splitter for side-by-side layout (control panel + image display)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        central_widget.layout = QHBoxLayout(central_widget)
        central_widget.layout.setContentsMargins(5, 5, 5, 5)
        central_widget.layout.addWidget(main_splitter)

        # Initialize and attach the left control panel to the splitter
        self.create_control_panel(main_splitter)

        # Initialize and attach the right image display area to the splitter
        self.create_image_display(main_splitter)

        # Define relative sizes and resizing behavior of the splitter sections
        main_splitter.setSizes([300, 1100])  # Default size proportions
        main_splitter.setStretchFactor(0, 0)  # Fix the control panel width
        main_splitter.setStretchFactor(1, 1)  # Allow image display to stretch

        # Create and set up the status bar at the bottom of the window
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Initialize status bar labels for dynamic coordinate and voxel value display
        self.coord_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Coordinates: (-, -, -)"))
        self.value_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Value: -"))
        self.slice_info_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Slice: -/-"))

        # Display initial status message when the viewer is ready
        self.status_bar.showMessage(
            QtCore.QCoreApplication.translate("NIfTIViewer", "Ready - Open a NIfTI file to begin")
        )

    def create_control_panel(self, parent):
        """
        Create the left-side control panel for the NIfTI Viewer interface.

        This method builds an interactive, scrollable control panel that allows
        the user to:
          - Open and display NIfTI files.
          - Navigate through 2D slices in axial, coronal, and sagittal planes.
          - Control time navigation for 4D datasets.
          - Adjust visualization parameters such as colormap and display options.
          - Perform automatic ROI (Region of Interest) generation.
          - Manage overlay images (load, transparency, threshold, enable/disable).

        Args:
            parent (QSplitter): The parent splitter widget where the control panel is added.

        Raises:
            Exception: Propagates exceptions from any UI creation or layout step.
        """

        # Scroll area wrapper (enables vertical scrolling for the control panel)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Control panel main content widget and layout
        control_content = QWidget()
        control_content.setMaximumWidth(340)  # Prevent horizontal scrolling
        layout = QVBoxLayout(control_content)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ========================
        # File Operations Group
        # ========================
        file_group = QFrame()
        file_layout = QVBoxLayout(file_group)
        file_layout.setContentsMargins(5, 5, 5, 5)

        # Button to open NIfTI files
        self.open_btn = QPushButton(QtCore.QCoreApplication.translate("NIfTIViewer", "📁 Open NIfTI"))
        self.open_btn.setMinimumHeight(35)
        self.open_btn.setMaximumHeight(40)
        self.open_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.open_btn.setToolTip(QtCore.QCoreApplication.translate("NIfTIViewer", "Open NIfTI File"))
        file_layout.addWidget(self.open_btn)

        # Label displaying currently loaded file info
        self.file_info_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "No file loaded"))
        self.file_info_label.setWordWrap(True)
        self.file_info_label.setStyleSheet("font-size: 10px;")
        self.file_info_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.file_info_label.setMaximumWidth(320)
        self.file_info_label.setMinimumHeight(40)
        file_layout.addWidget(self.file_info_label)
        layout.addWidget(file_group)

        # =====================
        # Slice Navigation
        # =====================
        slice_group = QFrame()
        slice_layout = QVBoxLayout(slice_group)
        slice_layout.setContentsMargins(5, 5, 5, 5)

        # Section label
        self.slice_navigation_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Slice Navigation:"))
        self.slice_navigation_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.slice_navigation_label.setMaximumWidth(320)
        self.slice_navigation_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        slice_layout.addWidget(self.slice_navigation_label)

        plane_names = [
            QtCore.QCoreApplication.translate("NIfTIViewer", "Axial (Z)"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Coronal (Y)"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Sagittal (X)")
        ]
        self.plane_labels = []

        # Create controls for each anatomical plane
        for i, plane_name in enumerate(plane_names):
            # Label for plane name
            label = QLabel(plane_name)
            self.plane_labels.append(label)
            label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            slice_layout.addWidget(label)
            self.slice_labels.append(label)

            # Container for slider + spinbox + coordinates
            controls_widget = QWidget()
            controls_layout = QHBoxLayout(controls_widget)
            controls_layout.setContentsMargins(0, 0, 0, 0)
            controls_layout.setSpacing(5)

            # Slice slider
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(100)
            slider.setValue(50)
            slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            controls_layout.addWidget(slider, stretch=3)

            # Spinbox to match slider
            spinbox = QSpinBox()
            spinbox.setMinimum(0)
            spinbox.setMaximum(100)
            spinbox.setValue(50)
            spinbox.setMaximumWidth(60)
            spinbox.setMinimumWidth(50)
            spinbox.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            controls_layout.addWidget(spinbox, stretch=0)

            # Coordinate label display
            coord_label = QLabel("(-, -)")
            coord_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 10px;")
            coord_label.setMinimumWidth(45)
            coord_label.setMaximumWidth(60)
            coord_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            controls_layout.addWidget(coord_label, stretch=0)

            controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            slice_layout.addWidget(controls_widget)

            # Store references
            self.slice_sliders.append(slider)
            self.slice_spins.append(spinbox)
            self.coord_displays.append(coord_label)

        layout.addWidget(slice_group)

        # ===================
        # ️ 4D Time Controls
        # ===================
        self.time_group = QFrame()
        time_layout = QVBoxLayout(self.time_group)
        time_layout.setContentsMargins(5, 5, 5, 5)

        # Enable time navigation
        self.time_checkbox = QCheckBox(QtCore.QCoreApplication.translate("NIfTIViewer", "Enable 4D Time Navigation"))
        self.time_checkbox.setChecked(False)
        self.time_checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        time_layout.addWidget(self.time_checkbox)

        # Slider + spinbox controls for time navigation
        time_controls_widget = QWidget()
        time_controls_layout = QHBoxLayout(time_controls_widget)
        time_controls_layout.setContentsMargins(0, 0, 0, 0)
        time_controls_layout.setSpacing(5)

        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(0)
        self.time_slider.setValue(0)
        self.time_slider.setEnabled(False)
        self.time_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        time_controls_layout.addWidget(self.time_slider, stretch=3)

        self.time_spin = QSpinBox()
        self.time_spin.setMinimum(0)
        self.time_spin.setMaximum(0)
        self.time_spin.setValue(0)
        self.time_spin.setEnabled(False)
        self.time_spin.setMaximumWidth(80)
        self.time_spin.setMinimumWidth(60)
        self.time_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        time_controls_layout.addWidget(self.time_spin, stretch=0)

        self.time_point_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Time Point:"))
        self.time_point_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.time_point_label.setMaximumWidth(320)
        self.time_point_label.setStyleSheet("font-size: 11px;")
        time_layout.addWidget(self.time_point_label)
        time_controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        time_layout.addWidget(time_controls_widget)

        self.time_group.setVisible(False)
        layout.addWidget(self.time_group)

        # ======================
        #  Display Options
        # ======================
        display_group = QFrame()
        display_layout = QVBoxLayout(display_group)
        display_layout.setContentsMargins(5, 5, 5, 5)

        self.display_options_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Display Options:"))
        self.display_options_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.display_options_label.setMaximumWidth(320)
        self.display_options_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        display_layout.addWidget(self.display_options_label)

        # Colormap selection dropdown
        colormap_widget = QWidget()
        colormap_layout = QVBoxLayout(colormap_widget)
        colormap_layout.setContentsMargins(0, 0, 0, 0)
        colormap_layout.setSpacing(3)

        self.colormap_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Colormap:"))
        self.colormap_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.colormap_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        colormap_layout.addWidget(self.colormap_label)

        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(
            ['gray', 'viridis', 'plasma',
             'inferno', 'magma', 'hot',
             'cool', 'bone'])

        self.colormap_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.colormap_combo.setMaximumHeight(25)
        colormap_layout.addWidget(self.colormap_combo)
        colormap_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        display_layout.addWidget(colormap_widget)
        layout.addWidget(display_group)

        # ==========================
        # Automatic ROI Controls
        # ==========================
        # Automatic ROI
        self.automaticROI_group = QFrame()
        automaticROI_layout = QVBoxLayout(self.automaticROI_group)
        automaticROI_layout.setContentsMargins(5, 5, 5, 5)

        self.automatic_ROI_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Automatic ROI:"))
        self.automatic_ROI_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.automatic_ROI_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        automaticROI_layout.addWidget(self.automatic_ROI_label)

        automaticROIbtns_group = QFrame()
        automaticROIbtns_layout = QVBoxLayout(automaticROIbtns_group)  # Cambiato a verticale
        automaticROIbtns_layout.setContentsMargins(0, 0, 0, 0)
        automaticROIbtns_layout.setSpacing(3)

        self.automaticROIbtn = QPushButton(QtCore.QCoreApplication.translate("NIfTIViewer", "Automatic ROI"))
        self.automaticROIbtn.setEnabled(False)
        self.automaticROIbtn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.automaticROIbtn.setMaximumHeight(30)
        self.automaticROIbtn.setToolTip(QtCore.QCoreApplication.translate("NIfTIViewer", "Automatic ROI Drawing"))
        automaticROIbtns_layout.addWidget(self.automaticROIbtn)

        self.addOrigin_btn = QPushButton(QtCore.QCoreApplication.translate("NIfTIViewer", "Fix ROI and add new Origin"))
        self.addOrigin_btn.setEnabled(False)
        self.addOrigin_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.addOrigin_btn.setMaximumHeight(30)
        self.addOrigin_btn.setToolTip(QtCore.QCoreApplication.translate("NIfTIViewer", "Increment the current incremental ROI with the current ROI drawing"))
        automaticROIbtns_layout.addWidget(self.addOrigin_btn)

        automaticROIbtns_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        automaticROI_layout.addWidget(automaticROIbtns_group)

        # Incremental ROI checkbox
        self.incrementalROI_checkbox = QCheckBox(
            QtCore.QCoreApplication.translate("NIfTIViewer", "Show incremental ROI"))
        self.incrementalROI_checkbox.setEnabled(False)
        self.incrementalROI_checkbox.setVisible(False)
        self.incrementalROI_checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        automaticROI_layout.addWidget(self.incrementalROI_checkbox)

        # Overlay enable/disable checkbox
        self.automaticROI_checkbox = QCheckBox(QtCore.QCoreApplication.translate("NIfTIViewer", "Show automatic ROI"))
        self.automaticROI_checkbox.setEnabled(False)
        self.automaticROI_checkbox.setVisible(False)
        self.automaticROI_checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        automaticROI_layout.addWidget(self.automaticROI_checkbox)

        self.automaticROI_sliders_group = QFrame()
        automaticROI_sliders_layout = QVBoxLayout(self.automaticROI_sliders_group)
        automaticROI_sliders_layout.setContentsMargins(0, 0, 0, 0)

        self.automaticROI_radius_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Radius:"))
        self.automaticROI_radius_label.setStyleSheet("font-size: 10px;")
        self.automaticROI_radius_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        automaticROI_sliders_layout.addWidget(self.automaticROI_radius_label)

        # Radius slider and spinbox container
        radius_controls_widget = QWidget()
        radius_controls_layout = QHBoxLayout(radius_controls_widget)
        radius_controls_layout.setContentsMargins(0, 0, 0, 0)
        radius_controls_layout.setSpacing(5)

        self.automaticROI_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.automaticROI_radius_slider.setMinimum(0)
        self.automaticROI_radius_slider.setMaximum(9999)  # Valore sufficientemente alto per gestire tutti i casi
        self.automaticROI_radius_slider.setValue(32)
        self.automaticROI_radius_slider.setEnabled(True)
        self.automaticROI_radius_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        radius_controls_layout.addWidget(self.automaticROI_radius_slider, stretch=3)

        self.automaticROI_radius_spin = QSpinBox()
        self.automaticROI_radius_spin.setMinimum(0)
        self.automaticROI_radius_spin.setMaximum(9999)  # Valore sufficientemente alto per gestire tutti i casi
        self.automaticROI_radius_spin.setValue(32)
        self.automaticROI_radius_spin.setMaximumWidth(60)
        self.automaticROI_radius_spin.setMinimumWidth(50)
        self.automaticROI_radius_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        radius_controls_layout.addWidget(self.automaticROI_radius_spin, stretch=0)

        radius_controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        automaticROI_sliders_layout.addWidget(radius_controls_widget)

        self.automaticROI_diff_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Difference:"))
        self.automaticROI_diff_label.setStyleSheet("font-size: 10px;")
        self.automaticROI_diff_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        automaticROI_sliders_layout.addWidget(self.automaticROI_diff_label)

        # Difference slider and spinbox container
        diff_controls_widget = QWidget()
        diff_controls_layout = QHBoxLayout(diff_controls_widget)
        diff_controls_layout.setContentsMargins(0, 0, 0, 0)
        diff_controls_layout.setSpacing(5)

        self.automaticROI_diff_slider = QSlider(Qt.Orientation.Horizontal)
        self.automaticROI_diff_slider.setMinimum(0)
        self.automaticROI_diff_slider.setMaximum(99999)  # Valore molto alto per gestire qualsiasi range di intensità
        self.automaticROI_diff_slider.setValue(16)
        self.automaticROI_diff_slider.setEnabled(True)
        self.automaticROI_diff_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        diff_controls_layout.addWidget(self.automaticROI_diff_slider, stretch=3)

        self.automaticROI_diff_spin = QSpinBox()
        self.automaticROI_diff_spin.setMinimum(0)
        self.automaticROI_diff_spin.setMaximum(99999)  # Valore molto alto per gestire qualsiasi range di intensità
        self.automaticROI_diff_spin.setValue(16)
        self.automaticROI_diff_spin.setMaximumWidth(60)
        self.automaticROI_diff_spin.setMinimumWidth(50)
        self.automaticROI_diff_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        diff_controls_layout.addWidget(self.automaticROI_diff_spin, stretch=0)

        diff_controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        automaticROI_sliders_layout.addWidget(diff_controls_widget)

        self.automaticROI_sliders_group.setVisible(False)
        self.automaticROI_sliders_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        automaticROI_layout.addWidget(self.automaticROI_sliders_group)

        automaticROI_bottom_btns_group = QFrame()
        automaticROIb_bottom_btns_layout = QVBoxLayout(automaticROI_bottom_btns_group)  # Cambiato a verticale
        automaticROIb_bottom_btns_layout.setContentsMargins(0, 0, 0, 0)
        automaticROIb_bottom_btns_layout.setSpacing(3)


        self.ROI_save_btn = QPushButton(QtCore.QCoreApplication.translate("NIfTIViewer", "Save ROI"))
        self.ROI_save_btn.setStyleSheet("""
                    QPushButton {
                    font-weight: bold;
                    color:#27ae60 }
                    QPushButton:disabled {
                    color:none;
                    font-weight: normal
                    }""")
        self.ROI_save_btn.setEnabled(False)
        self.ROI_save_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ROI_save_btn.setMaximumHeight(30)
        self.ROI_save_btn.setToolTip(QtCore.QCoreApplication.translate("NIfTIViewer", "Save ROI Drawing"))
        automaticROIb_bottom_btns_layout.addWidget(self.ROI_save_btn)


        self.cancelROI_btn = QPushButton(QtCore.QCoreApplication.translate("NIfTIViewer", "Cancel ROI"))
        self.cancelROI_btn.setEnabled(False)
        self.cancelROI_btn.setStyleSheet("""
                            QPushButton {
                            font-weight: bold;
                            color:#c0392b }
                            QPushButton:disabled {
                            color:none;
                            font-weight: normal
                            }""")
        self.cancelROI_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.cancelROI_btn.setMaximumHeight(30)
        self.cancelROI_btn.setToolTip(QtCore.QCoreApplication.translate("NIfTIViewer", "Cancel ROI Drawing"))
        automaticROIb_bottom_btns_layout.addWidget(self.cancelROI_btn)

        automaticROI_layout.addWidget(automaticROI_bottom_btns_group)

        layout.addWidget(self.automaticROI_group)

        # Overlay controls
        overlay_group = QFrame()
        overlay_layout = QVBoxLayout(overlay_group)
        overlay_layout.setContentsMargins(5, 5, 5, 5)

        self.overlay_control_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Controls:"))
        self.overlay_control_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.overlay_control_label.setMaximumWidth(320)
        self.overlay_control_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        overlay_layout.addWidget(self.overlay_control_label)

        # Overlay file button
        self.overlay_btn = QPushButton(QtCore.QCoreApplication.translate("NIfTIViewer", "Load Overlay"))
        self.overlay_btn.setMinimumHeight(30)
        self.overlay_btn.setMaximumHeight(35)
        self.overlay_btn.setEnabled(False)  # Enable only when base image is loaded
        self.overlay_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.overlay_btn.setToolTip(QtCore.QCoreApplication.translate("NIfTIViewer", "Load NIfTI Overlay"))
        overlay_layout.addWidget(self.overlay_btn)

        # Overlay enable/disable checkbox
        self.overlay_checkbox = QCheckBox(QtCore.QCoreApplication.translate("NIfTIViewer", "Show Overlay"))
        self.overlay_checkbox.setEnabled(False)
        self.overlay_checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        overlay_layout.addWidget(self.overlay_checkbox)

        # Overlay alpha slider
        self.alpha_overlay_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Transparency:"))
        self.alpha_overlay_label.setStyleSheet("font-size: 10px;")
        self.alpha_overlay_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        overlay_layout.addWidget(self.alpha_overlay_label)

        # Alpha slider and spinbox container
        alpha_controls_widget = QWidget()
        alpha_controls_layout = QHBoxLayout(alpha_controls_widget)
        alpha_controls_layout.setContentsMargins(0, 0, 0, 0)
        alpha_controls_layout.setSpacing(5)

        self.overlay_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.overlay_alpha_slider.setMinimum(10)
        self.overlay_alpha_slider.setMaximum(100)
        self.overlay_alpha_slider.setValue(70)
        self.overlay_alpha_slider.setEnabled(False)
        self.overlay_alpha_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        alpha_controls_layout.addWidget(self.overlay_alpha_slider, stretch=3)

        self.overlay_alpha_spin = QSpinBox()
        self.overlay_alpha_spin.setMinimum(10)
        self.overlay_alpha_spin.setMaximum(100)
        self.overlay_alpha_spin.setValue(70)
        self.overlay_alpha_spin.setEnabled(False)
        self.overlay_alpha_spin.setMaximumWidth(60)
        self.overlay_alpha_spin.setMinimumWidth(50)
        self.overlay_alpha_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        alpha_controls_layout.addWidget(self.overlay_alpha_spin, stretch=0)

        alpha_controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        overlay_layout.addWidget(alpha_controls_widget)

        # Overlay threshold slider
        self.overlay_threshold_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Threshold:"))
        self.overlay_threshold_label.setStyleSheet("font-size: 10px;")
        self.overlay_threshold_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        overlay_layout.addWidget(self.overlay_threshold_label)

        # Threshold slider and spinbox container
        threshold_controls_widget = QWidget()
        threshold_controls_layout = QHBoxLayout(threshold_controls_widget)
        threshold_controls_layout.setContentsMargins(0, 0, 0, 0)
        threshold_controls_layout.setSpacing(5)

        self.overlay_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.overlay_threshold_slider.setMinimum(0)
        self.overlay_threshold_slider.setMaximum(100)
        self.overlay_threshold_slider.setValue(10)
        self.overlay_threshold_slider.setEnabled(False)
        self.overlay_threshold_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        threshold_controls_layout.addWidget(self.overlay_threshold_slider, stretch=3)

        self.overlay_threshold_spin = QSpinBox()
        self.overlay_threshold_spin.setMinimum(0)
        self.overlay_threshold_spin.setMaximum(100)
        self.overlay_threshold_spin.setValue(10)
        self.overlay_threshold_spin.setEnabled(False)
        self.overlay_threshold_spin.setMaximumWidth(60)
        self.overlay_threshold_spin.setMinimumWidth(50)
        self.overlay_threshold_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        threshold_controls_layout.addWidget(self.overlay_threshold_spin, stretch=0)

        threshold_controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        overlay_layout.addWidget(threshold_controls_widget)

        # Overlay info
        self.overlay_info_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "No overlay loaded"))
        self.overlay_info_label.setWordWrap(True)
        self.overlay_info_label.setStyleSheet("font-size: 10px;")
        self.overlay_info_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        # Imposta larghezza massima per prevenire espansione
        self.overlay_info_label.setMaximumWidth(320)
        self.overlay_info_label.setMinimumHeight(20)
        overlay_layout.addWidget(self.overlay_info_label)

        layout.addWidget(overlay_group)

        # Add stretch to push everything to top
        layout.addStretch()

        # Set the content inside the QScrollArea
        scroll_area.setWidget(control_content)

        # Set dimensions to eliminate horizontal scrolling
        scroll_area.setMinimumWidth(240)
        scroll_area.setMaximumWidth(340)

        # Signal/slot connections to synchronize slider and spinbox

        # Automatic ROI - Radius
        self.automaticROI_radius_slider.valueChanged.connect(self.automaticROI_radius_spin.setValue)
        self.automaticROI_radius_spin.valueChanged.connect(self.automaticROI_radius_slider.setValue)

        # Automatic ROI - Difference
        self.automaticROI_diff_slider.valueChanged.connect(self.automaticROI_diff_spin.setValue)
        self.automaticROI_diff_spin.valueChanged.connect(self.automaticROI_diff_slider.setValue)

        # Overlay - Alpha/Transparency
        self.overlay_alpha_slider.valueChanged.connect(self.overlay_alpha_spin.setValue)
        self.overlay_alpha_spin.valueChanged.connect(self.overlay_alpha_slider.setValue)

        # Overlay - Threshold
        self.overlay_threshold_slider.valueChanged.connect(self.overlay_threshold_spin.setValue)
        self.overlay_threshold_spin.valueChanged.connect(self.overlay_threshold_slider.setValue)

        # Add scroll area to parent
        parent.addWidget(scroll_area)

    def format_info_text(self, text, max_line_length=35):
        """
        Format text to prevent horizontal scrolling in the control panel.

        This helper function ensures that long lines of information (such as
        NIfTI file metadata) are wrapped neatly to fit within the UI, avoiding
        horizontal overflow. It also attempts to break lines at logical points
        (e.g., after colons or spaces) for improved readability.

        Args:
            text (str): The text to be formatted.
            max_line_length (int, optional): Maximum number of characters per line
                before wrapping. Defaults to 35.

        Returns:
            str: The formatted text with inserted line breaks for better layout.
        """
        import textwrap

        # Split text into lines to process them individually
        lines = text.split('\n')
        formatted_lines = []

        for line in lines:
            # If the line fits within limit, keep it unchanged
            if len(line) <= max_line_length:
                formatted_lines.append(line)
            else:
                # Try to split logically around ':' if possible
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts[0]) <= max_line_length:
                        # Add the first part and indent the continuation
                        formatted_lines.append(parts[0] + ':')
                        wrapped = textwrap.fill(parts[1].strip(), width=max_line_length - 2)
                        formatted_lines.append('  ' + wrapped.replace('\n', '\n  '))
                    else:
                        # If even the key part is long, wrap entire line
                        wrapped = textwrap.fill(line, width=max_line_length)
                        formatted_lines.append(wrapped)
                else:
                    # Wrap normally if no logical split point found
                    wrapped = textwrap.fill(line, width=max_line_length)
                    formatted_lines.append(wrapped)

        # Join all formatted lines back into a single string
        return '\n'.join(formatted_lines)

    def create_image_display(self, parent):
        """
        Create the main image display panel with three anatomical views.

        This function builds the right-hand visualization area of the NIfTI viewer,
        which displays axial, coronal, and sagittal image slices. It also prepares
        a fourth panel for displaying image information or time-series plots
        (depending on whether the dataset is 3D or 4D).

        Args:
            parent (QSplitter): The parent splitter widget where the display
                area is added.

        Components:
            - Three synchronized image views with crosshairs.
            - A fourth panel for displaying image metadata or 4D time plots.
            - Dynamically initialized graphics scenes and pixmap items.

        Raises:
            Exception: Propagates initialization errors in UI creation.
        """
        # Create base container and grid layout for the 2x2 view grid
        display_widget = QWidget()
        display_layout = QGridLayout(display_widget)
        display_layout.setSpacing(5)

        # Define positions for the three main anatomical views
        view_positions = [(0, 0), (0, 1), (1, 0)]
        view_titles = [
            QtCore.QCoreApplication.translate("NIfTIViewer", "Axial"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Coronal"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Sagittal")
        ]

        self.view_titles_labels = []

        # Iterate through each anatomical plane and create a visualization frame
        for i, (row, col) in enumerate(view_positions):
            # Create container with border style
            view_container = QFrame()
            view_container.setFrameStyle(QFrame.Shape.StyledPanel)
            container_layout = QVBoxLayout(view_container)
            container_layout.setContentsMargins(2, 2, 2, 2)

            # Title label (Axial, Coronal, Sagittal)
            title_label = QLabel(view_titles[i])
            self.view_titles_labels.append(title_label)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("font-weight: bold; padding: 4px;")
            container_layout.addWidget(title_label)

            # Initialize graphics view for image rendering
            view = CrosshairGraphicsView(i, self)
            view.setMinimumSize(200, 200)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            # Create graphics scene for the view
            scene = QGraphicsScene()
            view.setScene(scene)

            # Create pixmap item (the actual displayed image)
            pixmap_item = QGraphicsPixmapItem()
            scene.addItem(pixmap_item)

            # Add view to its container layout
            container_layout.addWidget(view)

            # Place container in grid layout
            display_layout.addWidget(view_container, row, col)

            # Keep references for later updates/redraws
            self.views.append(view)
            self.scenes.append(scene)
            self.pixmap_items.append(pixmap_item)

        # ==============================
        #  Fourth Panel (Info / Plot)
        # ==============================
        # Bottom-right panel for metadata or time-series visualization
        self.fourth_widget = QFrame()
        self.fourth_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        fourth_layout = QVBoxLayout(self.fourth_widget)

        # Section title
        self.fourth_title = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Image Information"))
        self.fourth_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fourth_title.setStyleSheet("font-weight: bold; padding: 4px;")
        fourth_layout.addWidget(self.fourth_title)

        # Content container allows swapping between info text and plots
        self.fourth_content = QWidget()
        self.fourth_content_layout = QVBoxLayout(self.fourth_content)

        # Default info label (shown when no image is loaded)
        self.info_text = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "No image loaded"))
        self.info_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.info_text.setStyleSheet("color: #cccccc; font-size: 11px; padding: 10px;")
        self.info_text.setWordWrap(True)
        self.fourth_content_layout.addWidget(self.info_text)

        # Placeholders for 4D time-series plotting (initialized later)
        self.time_plot_widget = None
        self.time_plot_canvas = None
        self.time_indicator_line = None

        # Add dynamic content area to layout
        fourth_layout.addWidget(self.fourth_content)

        # Add the fourth widget to the main grid (bottom-right cell)
        display_layout.addWidget(self.fourth_widget, 1, 1)

        # Attach the full display grid to the parent splitter
        parent.addWidget(display_widget)

        # Delay setup of interactive crosshairs until UI is ready
        QTimer.singleShot(100, self.setup_crosshairs)

    def setup_crosshairs(self):
        """
        Initialize and configure crosshair overlays for all active image views.

        This method ensures that each anatomical view (axial, coronal, sagittal)
        has its own interactive crosshair layer properly initialized.

        Purpose:
            - Enables visual reference lines for voxel coordinates.
            - Synchronizes navigation across views.

        Returns:
            None
        """
        # Iterate over all graphics views and initialize their crosshairs
        for view in self.views:
            view.setup_crosshairs()

    def setup_connections(self):
        """
        Establish all signal-slot connections for the viewer interface.

        This method binds user interface widgets (buttons, sliders, spin boxes, checkboxes)
        to their respective event handlers to enable interactive control over the
        visualization and processing of NIfTI images.

        Connections include:
            - File operations (open base and overlay images)
            - Slice navigation (sliders and spinboxes)
            - ROI (Region of Interest) automation controls
            - Time series navigation (for 4D datasets)
            - Colormap and overlay adjustments
            - Coordinate updates between synchronized views

        Returns:
            None
        """
        # ----------------------------
        # File-related connections
        # ----------------------------
        self.open_btn.clicked.connect(lambda: self.open_file())
        self.overlay_btn.clicked.connect(lambda: self.open_file(is_overlay=True))
        self.overlay_checkbox.toggled.connect(self.toggle_overlay)
        self.overlay_alpha_slider.valueChanged.connect(self.update_overlay_alpha)
        self.overlay_threshold_slider.valueChanged.connect(self.update_overlay_threshold)

        # ----------------------------
        # Slice navigation connections
        # ----------------------------
        # Connect slice sliders and spinboxes for all anatomical planes
        for i, (slider, spinbox) in enumerate(zip(self.slice_sliders, self.slice_spins)):
            slider.valueChanged.connect(lambda value, idx=i: self.slice_changed(idx, value))
            spinbox.valueChanged.connect(lambda value, idx=i: self.slice_changed(idx, value))

        # ----------------------------
        # Automatic ROI Drawing controls
        # ----------------------------
        self.automaticROIbtn.clicked.connect(self.automaticROI_clicked)
        self.automaticROI_diff_slider.valueChanged.connect(self.update_automaticROI)
        self.automaticROI_radius_slider.valueChanged.connect(self.update_automaticROI)
        self.ROI_save_btn.clicked.connect(self.ROI_save)
        self.automaticROI_checkbox.toggled.connect(self.toggle_automaticROI)
        self.addOrigin_btn.clicked.connect(self.addOrigin_clicked)
        self.incrementalROI_checkbox.toggled.connect(self.toggle_incrementalROI)
        self.cancelROI_btn.clicked.connect(self.resetROI)
        # ----------------------------
        # Time-series control connections (for 4D images)
        # ----------------------------
        self.time_checkbox.toggled.connect(self.toggle_time_controls)
        self.time_slider.valueChanged.connect(self.time_changed)
        self.time_spin.valueChanged.connect(self.time_changed)

        # ----------------------------
        # Colormap control
        # ----------------------------
        self.colormap_combo.currentTextChanged.connect(self.colormap_changed)

        # ----------------------------
        # Coordinate synchronization across views
        # ----------------------------
        for view in self.views:
            view.coordinate_changed.connect(self.update_coordinates)

    def show_workspace_nii_dialog(self, is_overlay=False):
        """
        Open a workspace-aware file selection dialog for NIfTI files.

        Depending on the mode (`is_overlay`), this dialog either selects
        a base anatomical image or a secondary overlay image from the user’s workspace.

        Args:
            is_overlay (bool, optional): Whether the dialog is for selecting an overlay file.
                Defaults to False.

        Returns:
            None: If a file is selected, it triggers `open_file()` automatically.
        """
        # ----------------------------
        # Select file using NiftiFileDialog, filtering appropriately
        # ----------------------------
        if is_overlay:
            result = NiftiFileDialog.get_files(
                self.context,
                allow_multiple=False,
                has_existing_func=False,
                label=None,
                forced_filters=None
            )
        else:
            result = NiftiFileDialog.get_files(
                self.context,
                allow_multiple=False,
                has_existing_func=False,
                label=None
            )

        # ----------------------------
        # Open file if a valid selection was made
        # ----------------------------
        if result:
            self.open_file(result[0], is_overlay=is_overlay)

    def open_file(self, file_path=None, is_overlay=False):
        """
        Load a NIfTI file (base or overlay) using a background thread.

        This method either opens a file dialog for selecting a NIfTI file
        or loads a specified path directly. The loading process runs in a
        separate thread to keep the UI responsive, with progress reported
        via a modal progress dialog.

        Args:
            file_path (str, optional): Path to the NIfTI file to load. If None,
                a file dialog will be displayed.
            is_overlay (bool, optional): Whether the file being opened is an overlay
                (requires a base image to be already loaded). Defaults to False.

        Raises:
            RuntimeError: If the overlay is loaded without a base image.
        """
        # ----------------------------
        # Prevent overlay loading without a base image
        # ----------------------------
        if is_overlay and self.img_data is None:
            QMessageBox.warning(
                self,
                QtCore.QCoreApplication.translate("NIfTIViewer", "Warning"),
                QtCore.QCoreApplication.translate("NIfTIViewer", "Please load a base image first!")
            )
            log.warning("No base image")
            return

        # ----------------------------
        # Show file dialog if no path is provided
        # ----------------------------
        if file_path is None:
            file_path = self.show_workspace_nii_dialog(is_overlay=is_overlay)
            if not file_path:  # User canceled the dialog
                return

        # ----------------------------
        # Start file loading process
        # ----------------------------
        if file_path:
            # Create and configure progress dialog
            self.progress_dialog = QProgressDialog(
                QtCore.QCoreApplication.translate("NIfTIViewer", "Loading NIfTI file..."),
                QtCore.QCoreApplication.translate("NIfTIViewer", "Cancel"), 0, 100, self
            )
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setMinimumDuration(0)

            # Launch threaded image loading
            self.threads.append(ImageLoadThread(file_path, is_overlay))
            self.threads[-1].finished.connect(self.on_file_loaded)
            self.threads[-1].error.connect(self.on_load_error)
            self.threads[-1].progress.connect(self.progress_dialog.setValue)
            self.threads[-1].start()

            # Allow user to cancel the loading process
            self.progress_dialog.canceled.connect(self.on_load_canceled)

            # Save file path to appropriate variable
            if is_overlay:
                self.overlay_file_path = file_path
            else:
                self.file_path = file_path

    def on_file_loaded(self, img_data, dims, affine, is_4d, is_overlay):
        """
        Handle successful completion of a NIfTI file loading operation.

        This method is called when the background loading thread finishes without errors.
        It manages both base image and overlay image loading results.

        Args:
            img_data (numpy.ndarray): Loaded image data array.
            dims (tuple): Dimensions of the loaded image (e.g., (X, Y, Z) or (X, Y, Z, T)).
            affine (numpy.ndarray): Affine transformation matrix defining voxel-to-world mapping.
            is_4d (bool): Whether the loaded image is a 4D time series.
            is_overlay (bool): Whether the loaded file is an overlay rather than a base image.

        Returns:
            None
        """
        log.debug("Loading NIfTI image...")
        # Disconnect progress dialog cancel signal and close it
        self.progress_dialog.canceled.disconnect()
        self.progress_dialog.close()
        log.debug("Remove the finished thread")
        # Remove the finished thread from active threads list
        thread_to_cancel = self.sender()
        self.threads.remove(thread_to_cancel)

        # ---------------------------------------------------
        # Handle overlay image loading
        # ---------------------------------------------------
        if is_overlay:
            # Store overlay data and its dimensions
            self.overlay_data = img_data
            self.overlay_dims = dims

            # Check for dimension mismatch and apply padding if necessary
            if hasattr(self, "dims") and self.overlay_data.shape[:3] != self.dims[:3]:
                QMessageBox.warning(
                    self,
                    "Dimensions mismatch!",
                    f"The main image has dimensions {self.dims[:3]} and the overlay has dimensions {self.overlay_data.shape[:3]}."
                )
                self.overlay_data = self.pad_volume_to_shape(self.overlay_data, self.dims[:3])

            self.overlay_max = np.max(self.overlay_data) if np.max(self.overlay_data) > 0 else 1

            # Update overlay information label
            filename = os.path.basename(self.overlay_file_path)
            self.overlay_info_label.setText(
                f"Overlay: {filename}\n" +
                QtCore.QCoreApplication.translate("NIfTIViewer", "Dimensions") +
                f":{self.overlay_dims}"
            )
            log.debug("Activate the UI")
            # Enable and activate overlay in UI
            self.toggle_overlay(True,update_all=False)
            log.debug("Update overlay threshold")
            self.update_overlay_threshold(self.overlay_threshold_slider.value(),update_all=False)
            log.debug("Update display settings")
            # Refresh display with updated overlay settings
            self.update_overlay_settings(update_all=False)
            log.debug("Update all displays")
            self.update_all_displays()
            log.debug("Finished loading NIfTI image, updating checkbox")

            self.overlay_checkbox.setChecked(True)
            self.overlay_checkbox.setEnabled(True)
            log.debug("Updating status bar")
            # Update status bar message
            self.status_bar.showMessage(
                QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay loaded") + f":{filename}"
            )

        # ---------------------------------------------------
        # Handle base image loading
        # ---------------------------------------------------
        else:
            # Reset any existing overlay and ROI tools
            self.reset_overlay()

            # Store loaded base image attributes
            self.img_data = img_data
            self.dims = dims
            self.affine = affine
            self.is_4d = is_4d
            self.voxel_sizes = np.sqrt((self.affine[:3, :3] ** 2).sum(axis=0))  # Compute voxel size in mm

            # Compose file information text
            filename = os.path.basename(self.file_path)
            if is_4d:
                # 4D image information
                info_text = QtCore.QCoreApplication.translate("NIfTIViewer", "File") + f":{filename}\n" + \
                            QtCore.QCoreApplication.translate("NIfTIViewer", "Dimensions") + \
                            f":{dims[0]}×{dims[1]}×{dims[2]}×{dims[3]}\n" + \
                            QtCore.QCoreApplication.translate("NIfTIViewer", "4D Time Series")

                # Enable time-series group and plot setup
                self.time_group.setVisible(True)
                self.time_checkbox.setChecked(True)
                self.time_checkbox.setEnabled(True)
                self.setup_time_series_plot()
            else:
                # 3D volume information
                info_text = QtCore.QCoreApplication.translate("NIfTIViewer", "File") + f":{filename}\n" + \
                            QtCore.QCoreApplication.translate("NIfTIViewer", "Dimensions") + \
                            f":{dims[0]}×{dims[1]}×{dims[2]}\n" + \
                            QtCore.QCoreApplication.translate("NIfTIViewer", "3D Volume")

                # Disable time controls for 3D data
                self.time_group.setVisible(False)
                self.time_checkbox.setChecked(False)
                self.time_checkbox.setEnabled(False)
                self.hide_time_series_plot()

            # Update status bar layout and messages
            self.status_bar.clearMessage()
            self.status_bar.addWidget(self.coord_label)
            self.status_bar.addPermanentWidget(self.slice_info_label)
            self.status_bar.addPermanentWidget(self.value_label)

            # Enable ROI controls
            self.automaticROIbtn.setEnabled(True)

            self.automaticROIbtn.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Automatic ROI"))

            # Update information panel
            self.file_info_label.setText(info_text)
            self.info_text.setText(info_text)

            # Initialize visual display of loaded data
            self.initialize_display()

            self.resetROI()
            self.reset_overlay()

    def on_load_error(self, error_message):
        """
        Handle errors during NIfTI file loading.

        Displays an error message, logs the issue, and cleans up any pending thread.

        Args:
            error_message (str): Error message returned by the worker thread.

        Returns:
            None
        """
        # Disconnect cancel signal and close progress dialog
        self.progress_dialog.canceled.disconnect()
        self.progress_dialog.close()

        # Display critical error dialog
        QMessageBox.critical(
            self,
            QtCore.QCoreApplication.translate("NIfTIViewer", "Error Loading File"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Failed to load NIfTI file") + f":\n{error_message}"
        )

        # Log the critical error message
        log.critical(f"Error loading NIfTI file: {error_message}")

        # Remove failed thread from thread list
        thread_to_cancel = self.sender()
        if thread_to_cancel in self.threads:
            self.threads.remove(thread_to_cancel)

    def on_load_canceled(self):
        """
        Handle manual cancellation of the NIfTI file loading process.

        Terminates the most recent loading thread and removes it from
        the active thread list to prevent resource leakage.

        Returns:
            None
        """
        self.threads[-1].terminate()
        self.threads.pop()

    def initialize_display(self):
        """
        Initialize and configure the viewer display after a NIfTI file is loaded.

        Sets up slice navigation controls, initializes time-series sliders for 4D data,
        updates current coordinates, and enables overlay controls.

        Returns:
            None
        """
        if self.img_data is None:
            return

        # Determine spatial dimension order (reverse for display consistency)
        spatial_dims = self.dims[:3][::-1] if self.is_4d else self.dims[::-1]

        # Configure slice sliders and spin boxes
        for i in range(3):
            max_slice = spatial_dims[i] - 1
            self.slice_sliders[i].setMaximum(max_slice)
            self.slice_spins[i].setMaximum(max_slice)
            self.current_slices[i] = max_slice // 2  # Start in the middle slice
            self.slice_sliders[i].setValue(self.current_slices[i])
            self.slice_spins[i].setValue(self.current_slices[i])

        # Configure time slider and spinbox for 4D datasets
        if self.is_4d:
            max_time = self.dims[3] - 1
            self.time_slider.setMaximum(max_time)
            self.time_spin.setMaximum(max_time)
            self.current_time = 0
            self.time_slider.setValue(0)
            self.time_spin.setValue(0)
            self.toggle_time_controls(self.time_checkbox.isChecked())

        # Initialize coordinate tracking
        self.current_coordinates = [
            self.current_slices[2],  # X coordinate
            self.current_slices[1],  # Y coordinate
            self.current_slices[0]  # Z coordinate
        ]

        # Update all displays and coordinate readouts
        self.update_all_displays()
        self.update_coordinate_displays()

        # Enable overlay loading button after successful image load
        self.overlay_btn.setEnabled(True)

    def toggle_overlay(self, enabled,update_all=True):
        """
        Enable or disable the overlay display on top of the base image.

        Args:
            enabled (bool): Whether to enable (True) or disable (False) the overlay display.

        Behavior:
            - Toggles transparency and threshold controls.
            - Refreshes all active views if overlay data exists.

        Returns:
            None
        """
        # Update internal overlay state
        self.overlay_enabled = enabled

        # Enable or disable overlay-related UI controls
        self.overlay_alpha_slider.setEnabled(enabled or self.automaticROI_overlay or self.incrementalROI_enabled)
        self.overlay_alpha_spin.setEnabled(enabled or self.automaticROI_overlay or self.incrementalROI_enabled)
        self.overlay_threshold_slider.setEnabled(enabled or self.automaticROI_overlay or self.incrementalROI_enabled)
        self.overlay_threshold_spin.setEnabled(enabled or self.automaticROI_overlay or self.incrementalROI_enabled)
        self.ROI_save_btn.setEnabled(enabled or self.automaticROI_overlay or self.incrementalROI_enabled)


        if update_all:
            # Redraw display if overlay data is available
            log.debug("Update all display.")
            self.update_all_displays()
            log.debug("Update time series plot")
            # Update time series plot if available
            self.update_time_series_plot()

    def update_overlay_alpha(self, value,update_all=True):
        """
        Update overlay transparency (alpha blending).

        Args:
            value (int): Slider value representing overlay opacity (0–100).

        Notes:
            Converts the integer slider value to a float ratio (0.0–1.0) and
            refreshes the display only if the overlay is active and data is loaded.
        """
        self.overlay_alpha = value / 100.0
        if (self.overlay_enabled or self.automaticROI_overlay or self.incrementalROI_enabled) and update_all:
            self.update_all_displays()

    def update_overlay_threshold(self, value,update_all=True):
        """
        Update overlay intensity threshold.

        Args:
            value (int): Slider value representing overlay threshold (0–100).

        Notes:
            Adjusts visibility cutoff for overlay voxels and refreshes display
            when overlay is active and data is present.
        """
        self.overlay_threshold = value / 100.0
        if self.overlay_enabled and self.overlay_data is not None and self.overlay_max is not None:
            # Determine overlay threshold
            threshold_value = self.overlay_threshold * self.overlay_max
            # Create boolean mask of overlay pixels above threshold
            self.overlay_thresholded_data = self.overlay_data > threshold_value
            if update_all:
                self.update_all_displays()

    def update_overlay_settings(self,update_all=True):
        """
        Synchronize overlay alpha and threshold values from the UI controls.

        Notes:
            Reads the slider positions for alpha and threshold,
            updates their internal numeric equivalents, and refreshes
            the image view if the overlay is active.
        """
        if hasattr(self, 'overlay_alpha_slider') and hasattr(self, 'overlay_threshold_slider'):
            self.overlay_alpha = self.overlay_alpha_slider.value() / 100.0
            self.overlay_threshold = self.overlay_threshold_slider.value() / 100.0

            # Update visualization only if overlay is active and available
            if self.overlay_enabled and hasattr(self, 'overlay_data') and self.overlay_data is not None and update_all:
                self.update_all_displays()

    def slice_changed(self, plane_idx, value):
        """
        Handle slice navigation events from sliders or spinboxes.

        Args:
            plane_idx (int): Index of the anatomical plane (0=axial, 1=coronal, 2=sagittal).
            value (int): New slice index within the volume.

        Notes:
            Updates the current slice, synchronizes the corresponding slider and spinbox,
            recalculates coordinates, and refreshes the associated 2D view.
        """
        self.current_slices[plane_idx] = value

        # Keep slider and spinbox synchronized
        self.slice_sliders[plane_idx].setValue(value)
        self.slice_spins[plane_idx].setValue(value)

        # Update coordinate system based on selected plane
        if plane_idx == 0:  # Axial
            self.current_coordinates[2] = value
        elif plane_idx == 1:  # Coronal
            self.current_coordinates[1] = value
        elif plane_idx == 2:  # Sagittal
            self.current_coordinates[0] = value

        # Refresh the corresponding view and UI indicators
        self.update_display(plane_idx)
        self.update_coordinate_displays()
        self.update_cross_view_lines()

    def time_changed(self, value,update_all=True):
        """
        Handle time slider or spinbox change for 4D data.

        Args:
            value (int): New time index.

        Notes:
            Updates the current time frame and refreshes all views.
        """
        self.current_time = value
        self.time_slider.setValue(value)
        self.time_spin.setValue(value)
        if update_all:
            self.update_all_displays()

    def toggle_time_controls(self, enabled):
        """
        Enable or disable time navigation controls based on data dimensionality.

        Args:
            enabled (bool): Whether to show and enable time controls.

        Notes:
            Time controls are visible only when both 4D data is loaded and
            the toggle checkbox is active.
        """
        value = enabled and self.is_4d
        self.time_slider.setVisible(value)
        self.time_slider.setEnabled(value)
        self.time_spin.setVisible(value)
        self.time_spin.setEnabled(value)
        self.time_point_label.setVisible(value)

    def colormap_changed(self, colormap_name,update_all=True):
        """
        Handle colormap selection change from the dropdown.

        Args:
            colormap_name (str): Name of the selected colormap.

        Notes:
            Updates the active colormap for display and refreshes all views.
        """
        self.colormap = colormap_name
        if update_all:
            self.update_all_displays()

    def handle_click_coordinates(self, view_idx, x, y):
        """
        Handle user mouse clicks within a 2D slice view.

        Args:
            view_idx (int): Index of the view where the click occurred (0=axial, 1=coronal, 2=sagittal).
            x (float): X coordinate in screen space.
            y (float): Y coordinate in screen space.

        Notes:
            Converts screen coordinates to image voxel coordinates,
            updates slice positions accordingly, and synchronizes all views.
        """
        if self.img_data is None:
            return

        # Convert click from display to image coordinate space
        img_coords = self.screen_to_image_coords(view_idx, x, y)
        if img_coords is None:
            return

        # Update global coordinates
        self.current_coordinates = img_coords

        # Update slice positions based on clicked voxel
        self.current_slices[0] = img_coords[2]  # Axial (Z)
        self.current_slices[1] = img_coords[1]  # Coronal (Y)
        self.current_slices[2] = img_coords[0]  # Sagittal (X)

        # Synchronize controls for all planes
        for i in range(3):
            self.slice_sliders[i].setValue(self.current_slices[i])
            self.slice_spins[i].setValue(self.current_slices[i])

        # Refresh display and coordinate info
        self.update_all_displays()
        self.update_coordinate_displays()
        self.update_cross_view_lines()

    def screen_to_image_coords(self, view_idx, x, y):
        """
        Convert 2D screen coordinates from a slice view into 3D voxel coordinates.

        Args:
            view_idx (int): View index (0=axial, 1=coronal, 2=sagittal).
            x (float): X coordinate in view space.
            y (float): Y coordinate in view space.

        Returns:
            list[int] | None: Image-space voxel indices [x, y, z] or None if invalid.

        Notes:
            Applies stretch factor correction, flips orientation for proper display,
            and clamps coordinates to valid volume bounds.
        """
        if self.img_data is None:
            return None

        # Compensate for view stretching
        stretch_x, stretch_y = self.stretch_factors.get(view_idx, (1.0, 1.0))
        x = x / stretch_x
        y = y / stretch_y

        # Determine image dimensions (ignore time axis if 4D)
        shape = self.img_data.shape[:3] if self.is_4d else self.img_data.shape

        # Map view-specific coordinates to image indices
        if view_idx == 0:  # Axial (XY plane)
            img_x = min(max(x, 0), shape[0] - 1)
            img_y = min(max(shape[1] - 1 - y, 0), shape[1] - 1)  # Flip Y-axis
            img_z = self.current_slices[0]
        elif view_idx == 1:  # Coronal (XZ plane)
            img_x = min(max(x, 0), shape[0] - 1)
            img_y = self.current_slices[1]
            img_z = min(max(shape[2] - 1 - y, 0), shape[2] - 1)  # Flip Z-axis
        elif view_idx == 2:  # Sagittal (YZ plane)
            img_x = self.current_slices[2]
            img_y = min(max(x, 0), shape[1] - 1)
            img_z = min(max(shape[2] - 1 - y, 0), shape[2] - 1)  # Flip Z-axis
        else:
            return None

        return [int(img_x), int(img_y), int(img_z)]

    def update_coordinates(self, view_idx, x, y):
        """
        Update displayed voxel coordinates and value from mouse movement.

        Args:
            view_idx (int): Index of the active view.
            x (float): X mouse position.
            y (float): Y mouse position.

        Notes:
            Displays current voxel indices and intensity in the status bar
            as the user moves the mouse across an image slice.
        """
        if self.img_data is None:
            return

        img_coords = self.screen_to_image_coords(view_idx, x, y)
        if img_coords is None:
            return

        # Retrieve voxel value safely
        try:
            if self.is_4d:
                value = self.img_data[img_coords[0], img_coords[1], img_coords[2], self.current_time]
            else:
                value = self.img_data[img_coords[0], img_coords[1], img_coords[2]]

            # Update coordinate and voxel value display
            self.coord_label.setText(QtCore.QCoreApplication.translate(
                "NIfTIViewer", "Coordinates") + f": ({img_coords[0]}, {img_coords[1]}, {img_coords[2]})")
            self.value_label.setText(QtCore.QCoreApplication.translate(
                "NIfTIViewer", "Value") + f": {value:.2f}")
        except (IndexError, ValueError):
            log.exception("Failed to update coordinates")

    def update_coordinate_displays(self):
        """
        Update coordinate display labels beside each view and in the status bar.

        Notes:
            Shows current voxel positions (X, Y, Z) and value, ensuring real-time
            synchronization with slice sliders and mouse navigation.
        """
        if self.img_data is None:
            return

        coords = self.current_coordinates

        # Update per-view coordinate readouts
        self.coord_displays[0].setText(f"({coords[0]}, {coords[1]})")  # Axial
        self.coord_displays[1].setText(f"({coords[0]}, {coords[2]})")  # Coronal
        self.coord_displays[2].setText(f"({coords[1]}, {coords[2]})")  # Sagittal

        # Update global coordinate display in status bar
        self.coord_label.setText(QtCore.QCoreApplication.translate(
            "NIfTIViewer", "Coordinates") + f": ({coords[0]}, {coords[1]}, {coords[2]})")

        # Update value label safely
        try:
            if self.is_4d:
                value = self.img_data[coords[0], coords[1], coords[2], self.current_time]
            else:
                value = self.img_data[coords[0], coords[1], coords[2]]
            self.value_label.setText(QtCore.QCoreApplication.translate(
                "NIfTIViewer", "Value") + f": {value:.2f}")
        except (IndexError, ValueError):
            self.value_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Value") + f": -")

    def update_cross_view_lines(self):
        """
        Update crosshair positions across all views to indicate current voxel location.

        Notes:
            Crosshair lines are synchronized in all 2D projections (axial, coronal, sagittal),
            taking into account stretching factors and coordinate flipping.
        """
        if self.img_data is None:
            return

        coords = self.current_coordinates

        for i, view in enumerate(self.views):
            # Retrieve stretch correction factors (default to 1.0)
            stretch_x, stretch_y = self.stretch_factors.get(i, (1.0, 1.0))

            if i == 0:  # Axial view
                x = coords[0] * stretch_x
                y = (self.img_data.shape[1] - 1 - coords[1]) * stretch_y
                view.set_crosshair_position(x, y)

            elif i == 1:  # Coronal view
                x = coords[0] * stretch_x
                y = (self.img_data.shape[2] - 1 - coords[2]) * stretch_y
                view.set_crosshair_position(x, y)

            elif i == 2:  # Sagittal view
                x = coords[1] * stretch_x
                y = (self.img_data.shape[2] - 1 - coords[2]) * stretch_y
                view.set_crosshair_position(x, y)

    def update_display(self, plane_idx):
        """Update a specific plane display with matplotlib-style rendering in mm scale"""
        if self.img_data is None:
            return

        try:
            log.debug(f"Update display: {plane_idx}")
            # Select current 3D volume (for 4D data, use the selected time frame)
            if self.is_4d:
                current_data = self.img_data[..., self.current_time]
            else:
                current_data = self.img_data

            # Get current slice index for the selected plane
            slice_idx = self.current_slices[plane_idx]

            # Extract the corresponding slice depending on the plane
            if plane_idx == 0:  # Axial (XY plane)
                slice_data = current_data[:, :, slice_idx].T  # transpose to match orientation
                slice_data = np.flipud(slice_data)  # flip vertically for correct visualization
                pixel_spacing = self.voxel_sizes[0:2]  # spacing in X and Y directions

            elif plane_idx == 1:  # Coronal (XZ plane)
                slice_data = current_data[:, slice_idx, :].T
                slice_data = np.flipud(slice_data)
                pixel_spacing = (self.voxel_sizes[0], self.voxel_sizes[2])  # X and Z spacing

            elif plane_idx == 2:  # Sagittal (YZ plane)
                slice_data = current_data[slice_idx, :, :].T
                slice_data = np.flipud(slice_data)
                pixel_spacing = self.voxel_sizes[1:3]  # Y and Z spacing

            else:
                log.error("Plane index out of range")
                return  # Invalid plane index

            automaticROI_slice = _slice(self.automaticROI_data, plane_idx, slice_idx) if self.automaticROI_overlay and self.automaticROI_data is not None else None

            # Prepare overlay if available and enabled
            overlay_slice = _slice(self.overlay_thresholded_data,plane_idx, slice_idx)  if self.overlay_enabled and self.overlay_data is not None and self.overlay_thresholded_data is not None else None

            incrementalROI_slice = _slice(self.incrementalROI_data,plane_idx, slice_idx) if self.incrementalROI_enabled and self.incrementalROI_data is not None else None

            # Prepare RGBA composite for display
            height, width = slice_data.shape
            rgba_image = self.apply_colormap_matplotlib(slice_data, self.colormap)

            if automaticROI_slice is not None:
                rgba_image = self.create_overlay_composite(rgba_image, automaticROI_slice, self.colormap)

            if overlay_slice is not None:
                rgba_image = self.create_overlay_composite(rgba_image, overlay_slice, self.colormap)

            if incrementalROI_slice is not None:
                rgba_image = self.create_overlay_composite(rgba_image, incrementalROI_slice, self.colormap)

            # Convert RGBA data to 8-bit format for QImage
            rgba_data_uint8 = (rgba_image * 255).astype(np.uint8)
            qimage = QImage(rgba_data_uint8.data, width, height, width * 4, QImage.Format.Format_RGBA8888)

            if qimage is not None:
                img_w, img_h = qimage.width(), qimage.height()

                # Scale the image according to voxel size ratio (convert to mm scale)
                qimage_scaled = qimage.scaled(
                    int(img_w),
                    int(img_h * (pixel_spacing[1] / pixel_spacing[0])),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

                # Store stretch factors for coordinate conversion later
                self.stretch_factors[plane_idx] = (1.0, pixel_spacing[1] / pixel_spacing[0])

                # Update QGraphicsScene and QGraphicsView with new image
                self.pixmap_items[plane_idx].setPixmap(QPixmap.fromImage(qimage_scaled))
                self.scenes[plane_idx].setSceneRect(0, 0, qimage_scaled.width(), qimage_scaled.height())
                self.views[plane_idx].fitInView(self.scenes[plane_idx].sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            log.debug("Updated display ended")
        except Exception as e:
            # Log any display update errors (e.g. shape mismatch or memory issue)
            log.error(f"Error updating display {plane_idx}: {e}")

    def setup_time_series_plot(self):
        """Setup time series plot for 4D data"""
        if self.time_plot_canvas is not None:
            return  # Skip if plot is already initialized

        # Hide static info text to make room for plot
        self.info_text.hide()

        # Initialize matplotlib figure for time series
        self.time_plot_figure = Figure(figsize=(3, 3), facecolor='black')
        self.time_plot_figure.set_layout_engine('tight')

        # Embed matplotlib canvas inside PyQt interface
        self.time_plot_canvas = FigureCanvas(self.time_plot_figure)
        self.time_plot_axes = self.time_plot_figure.add_subplot(111)
        self.time_plot_axes.set_facecolor('black')

        # Update section title and add canvas widget to layout
        self.fourth_title.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Tracer Concentration Curve"))
        self.fourth_content_layout.addWidget(self.time_plot_canvas)

    def hide_time_series_plot(self):
        """Hide time series plot for 3D data"""
        if self.time_plot_canvas is not None:
            # Clean up plot canvas from layout and delete
            self.fourth_content_layout.removeWidget(self.time_plot_canvas)
            self.time_plot_canvas.setParent(None)
            self.time_plot_canvas.deleteLater()
            self.time_plot_canvas = None
            self.time_plot_axes = None
            self.time_plot_figure = None

        # Restore title and info text for non-4D files
        self.fourth_title.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Image Information"))
        self.info_text.show()

    def update_time_series_plot(self):
        """Update the time series plot with current voxel or ROI data"""
        if not self.is_4d or self.time_plot_canvas is None or self.img_data is None:
            return

        try:
            coords = self.current_coordinates
            bool_in_mask = False

            # Check if overlay is active and apply ROI-based averaging
            if self.overlay_data is not None and self.overlay_enabled:
                overlay_max = np.max(self.overlay_data) if np.max(self.overlay_data) > 0 else 1
                threshold_value = self.overlay_threshold * overlay_max
                threshold_mask = self.overlay_data > threshold_value

                # If current voxel is inside the thresholded ROI mask
                if threshold_mask[coords[0], coords[1], coords[2]]:
                    bool_in_mask = True
                    roi_voxels = self.img_data[threshold_mask, :]  # extract time series from ROI voxels
                    time_series = roi_voxels.mean(axis=0)  # mean intensity over ROI
                    std_series = roi_voxels.std(axis=0)  # standard deviation for shaded region
                else:
                    # Outside mask: show only single voxel time series
                    time_series = self.img_data[coords[0], coords[1], coords[2], :]
                    std_series = None
            else:
                # If overlay is not enabled, show voxel intensity over time
                time_series = self.img_data[coords[0], coords[1], coords[2], :]
                std_series = None

            # X-axis values = time points
            time_points = np.arange(self.dims[3])

            # Clear previous plot content
            self.time_plot_axes.clear()
            self.time_plot_axes.set_facecolor('black')

            # Plot time series curve
            self.time_plot_axes.plot(time_points, time_series, 'c-', linewidth=2,
                                     label=QtCore.QCoreApplication.translate("NIfTIViewer", 'Concentration'))

            # Optional shaded error region (ROI variability)
            if std_series is not None:
                self.time_plot_axes.fill_between(time_points, time_series - std_series,
                                                 time_series + std_series, alpha=0.2, color='c')

            # Add vertical yellow line showing current time index
            self.time_indicator_line = self.time_plot_axes.axvline(
                x=self.current_time, color='yellow', linewidth=2, alpha=0.8,
                label=QtCore.QCoreApplication.translate("NIfTIViewer", 'Current Time')
            )

            # Set axis labels and title
            self.time_plot_axes.set_xlabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Time Point"),
                                           color='white')
            self.time_plot_axes.set_ylabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Signal Intensity"),
                                           color='white')

            # Title reflects whether inside ROI or single voxel
            if bool_in_mask:
                self.time_plot_axes.set_title(f'Mean in overlay mask', color='white')
            else:
                self.time_plot_axes.set_title(f'Voxel ({coords[0]}, {coords[1]}, {coords[2]})', color='white')

            # Style axes and legend
            self.time_plot_axes.tick_params(colors='white')
            self.time_plot_axes.legend()
            self.time_plot_axes.grid(True, alpha=0.3, color='gray')

            # Redraw updated plot on canvas
            self.time_plot_canvas.draw()

        except Exception as e:
            # Log error if plotting fails (e.g., index error)
            log.error(f"Error updating time series plot: {e}")

    def apply_colormap_matplotlib(self, data, colormap_name):
        """Apply colormap using matplotlib and return QImage"""
        try:
            # Retrieve selected colormap from matplotlib
            cmap = matplotlib.colormaps.get_cmap(colormap_name)

            # Apply colormap to normalized image data
            colored_data = cmap(data)

            return colored_data

        except Exception as e:
            # Log errors (e.g., invalid colormap name)
            log.error(f"Error applying colormap: {e}")
            return None

    def update_all_displays(self):
        """Update all plane displays"""
        # Loop over all 3 orthogonal views (axial, coronal, sagittal)
        for i in range(3):
            self.update_display(i)

        # If data is 4D, also update the time-series plot
        if self.is_4d:
            self.update_time_series_plot()

        # Update slice information label in the status bar
        if self.img_data is not None:
            spatial_dims = self.dims[:3] if self.is_4d else self.dims
            # Construct slice position string for each plane (1-based indexing)
            slice_info = QtCore.QCoreApplication.translate("NIfTIViewer", "Slices") + \
                         f": {self.current_slices[0] + 1}/{spatial_dims[2]} | " \
                         f"{self.current_slices[1] + 1}/{spatial_dims[1]} | " \
                         f"{self.current_slices[2] + 1}/{spatial_dims[0]}"
            # Add current time info if applicable
            if self.is_4d:
                slice_info += f" | " + QtCore.QCoreApplication.translate("NIfTIViewer", "Time") + \
                              f": {self.current_time + 1}/{self.dims[3]}"
            self.slice_info_label.setText(slice_info)

    def create_overlay_composite(self, rgba_image, overlay_slice, colormap):
        """Create a composite image with colormap base and red overlay."""
        try:
            # Convert RGBA base image to float for blending
            rgba_image_float = rgba_image.astype(np.float64)  # shape (H, W, 4)

            if overlay_slice.size > 0:

                if np.any(overlay_slice):
                    # Apply transparency scaling (based on user alpha)
                    overlay_intensity = overlay_slice * self.overlay_alpha

                    # Retrieve overlay color from dictionary or default (green)
                    overlay_color = self.overlay_colors.get(colormap, np.array([0.0, 1.0, 0.0]))

                    log.debug("Blending overlay color into base image")
                    # Blend overlay into base image using a numba-accelerated function
                    rgba_image_float = apply_overlay_numba(rgba_image, overlay_slice,
                                                           overlay_intensity, overlay_color)
                    log.debug("Blended overlay color into base image")
            log.debug("Clipping values to a valid range")
            # Clip values to valid range [0, 1]
            rgba_image_overlay = np.clip(rgba_image_float, 0, 1)

            return rgba_image_overlay

        except Exception as e:
            # Log errors and return unmodified base image as fallback
            log.error(f"Error creating overlay composite: {e}")
            return rgba_image

    def resizeEvent(self, event: QResizeEvent):
        """Handle window resize to maintain aspect ratios"""
        # Call parent resize handler
        super().resizeEvent(event)
        # Refit all 2D slice views after short delay to prevent flickering
        QTimer.singleShot(100, self.fit_all_views)

    def fit_all_views(self):
        """Fit all views to their scenes while maintaining aspect ratio"""
        for view in self.views:
            if view.scene():
                # Adjust zoom to fit entire image in view with correct aspect ratio
                view.fitInView(view.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def update_automaticROI(self):
        """Update the automatic ROI overlay dynamically when parameters change"""
        if self.automaticROI_overlay:
            self.automaticROI_drawing()
            self.update_all_displays()

    def automaticROI_clicked(self):
        """Handle click on 'Automatic ROI' button to start or reset the ROI tool"""
        # Save current voxel coordinates as ROI seed point
        self.automaticROI_seed_coordinates = self.current_coordinates

        # Compute the maximum allowed ROI radius in millimeters
        dims_voxel = self.dims[:3]  # voxel counts along X, Y, Z
        dims_mm = dims_voxel * self.voxel_sizes  # real-world dimensions in mm
        max_radius_mm = np.min(dims_mm) / 2  # use half of shortest image dimension
        self.automaticROI_radius_slider.setMaximum(int(max_radius_mm))

        # Initialize radius slider (32 mm default for new ROI)
        self.automaticROI_radius_slider.setValue(
            32 if not self.automaticROI_overlay else self.automaticROI_radius_slider.value()
        )

        # Initialize difference (intensity tolerance) slider
        self.automaticROI_diff_slider.setMaximum(1000)
        self.automaticROI_diff_slider.setValue(
            int(1000 * (16 / 100)) if not self.automaticROI_overlay else self.automaticROI_diff_slider.value()
        )

        # Show and enable ROI parameter controls
        self.automaticROI_sliders_group.setVisible(True)
        self.automaticROI_sliders_group.setEnabled(True)
        self.automaticROIbtn.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Reset Origin"))
        self.automaticROI_overlay = True
        self.ROI_save_btn.setEnabled(True)
        self.addOrigin_btn.setEnabled(True)
        self.cancelROI_btn.setEnabled(True)

        # Generate initial automatic ROI mask
        self.automaticROI_drawing()

        self.automaticROI_checkbox.setVisible(True)
        self.automaticROI_checkbox.setEnabled(True)
        # Ensure overlay display is active
        self.toggle_automaticROI(True)
        #self.overlay_checkbox.setChecked(True)
        #self.overlay_checkbox.setEnabled(True)

        # Refresh all displays
        self.update_all_displays()


    def toggle_automaticROI(self, enabled,update_all=True):
        """
        Enable or disable the overlay for the automatic ROI on top of the base image.

        Args:
            enabled (bool): Whether to enable (True) or disable (False) the overlay display.

        Behavior:
            - Toggles transparency and threshold controls.
            - Refreshes all active views if overlay data exists.

        Returns:
            None
        """

        self.automaticROI_checkbox.setChecked(enabled)
        # Update internal overlay state
        self.automaticROI_overlay = enabled
        # Enable or disable overlay-related UI controls
        self.overlay_alpha_slider.setEnabled(enabled or self.overlay_enabled or self.incrementalROI_enabled)
        self.overlay_alpha_spin.setEnabled(enabled or self.overlay_enabled or self.incrementalROI_enabled)
        self.overlay_threshold_slider.setEnabled(enabled or self.overlay_enabled or self.incrementalROI_enabled)
        self.overlay_threshold_spin.setEnabled(enabled or self.overlay_enabled or self.incrementalROI_enabled)
        self.ROI_save_btn.setEnabled(enabled or self.overlay_enabled or self.incrementalROI_enabled)

        self.automaticROI_sliders_group.setEnabled(enabled)
        self.automaticROIbtn.setEnabled(enabled)

        if update_all:
            # Redraw display if overlay data is available
            self.update_all_displays()

            # Update time series plot if available
            self.update_time_series_plot()

    def automaticROI_drawing(self):
        """Generate automatic ROI mask around selected seed voxel"""
        radius_mm = self.automaticROI_radius_slider.value()  # ROI radius in mm
        difference = self.automaticROI_diff_slider.value() / 1000  # intensity tolerance
        x0, y0, z0 = self.automaticROI_seed_coordinates  # seed voxel coordinates

        # Select proper 3D volume if data is 4D
        img_data = self.img_data[..., self.current_time] if self.is_4d else self.img_data

        # Intensity value at the seed voxel
        seed_intensity = img_data[x0, y0, z0]

        # Convert radius in mm to radius in voxel units per axis
        rx_vox = int(np.ceil(radius_mm / self.voxel_sizes[0]))
        ry_vox = int(np.ceil(radius_mm / self.voxel_sizes[1]))
        rz_vox = int(np.ceil(radius_mm / self.voxel_sizes[2]))

        # Compute subvolume limits (ROI bounding box)
        x_min, x_max = max(0, x0 - rx_vox), min(img_data.shape[0], x0 + rx_vox + 1)
        y_min, y_max = max(0, y0 - ry_vox), min(img_data.shape[1], y0 + ry_vox + 1)
        z_min, z_max = max(0, z0 - rz_vox), min(img_data.shape[2], z0 + rz_vox + 1)

        # Compute ROI mask using parallelized Numba function
        mask = compute_mask_numba_mm(img_data, x0, y0, z0,
                                     radius_mm, self.voxel_sizes,
                                     seed_intensity, difference,
                                     x_min, x_max, y_min, y_max, z_min, z_max)

        # Store result as overlay for visualization
        self.automaticROI_data = mask

    def ROI_save(self):
        """Save the automatically generated ROI mask to disk"""
        log.debug("Saving ROI mask to disk")
        original_path = self.file_path
        if not original_path:
            QMessageBox.critical(self, "Error", "No file loaded.")
            log.critical("No file loaded")
            return
        # Retrieve workspace path from context
        workspace_path = self.context.get("workspace_path")
        if not workspace_path:
            QMessageBox.critical(self, "Error", "Workspace path is not set.")
            log.critical("Workspace path not set")
            return

        # Try to infer subject identifier (sub-XX) from relative file path
        relative_path = os.path.relpath(original_path, workspace_path)
        parts = relative_path.split(os.sep)
        try:
            subject = next(part for part in parts if part.startswith("sub-"))
        except StopIteration:
            QMessageBox.critical(self, "Error", "Could not determine subject from path.")
            log.error("Could not determine subject from path.")
            return


        save_dir = os.path.join(workspace_path, "derivatives", "manual_masks", subject, "anat")
        log.debug(f"Save dir: {save_dir}")
        filename = os.path.basename(original_path)
        base_name = filename.replace(".nii.gz", "").replace(".nii", "")
        log.debug(f"Base filename: {base_name}")
        # Prepare filenames and output paths
        id = self._get_next_file_id(save_dir)
        log.debug(f"Obtained version: {id}")
        new_base = f"{base_name}_ROI_v{id}_mask"
        new_name = f"{new_base}.nii.gz"

        log.debug("Show confirmation dialog")
        # Show confirmation dialog before saving
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Confirm Save")
        msg.setText("Do you want to save the automatic ROI?")
        msg.setInformativeText(
            f"File will be saved as:\n\n{new_name}\n\n"
            f"Location:\n{save_dir}\n\n"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)

        # Wait for user response
        response = msg.exec()
        if response != QMessageBox.StandardButton.Yes:
            return  # User canceled

        log.debug("Make dir")
        os.makedirs(save_dir, exist_ok=True)
        full_save_path = os.path.join(save_dir, new_name)
        json_save_path = os.path.join(save_dir, f"{new_base}.json")

        origin_dict = {}

        total_ROI = np.zeros(self.dims)
        if self.overlay_data is not None and self.overlay_enabled and self.overlay_thresholded_data is not None:
            total_ROI = np.logical_or(self.overlay_thresholded_data, total_ROI).astype(np.uint8)
            origin_dict["Original overlay"] = self.overlay_file_path
            origin_dict["Original overlay threshold"] = self.overlay_threshold
            
        if self.incrementalROI_data is not None and self.incrementalROI_enabled:
            total_ROI = np.logical_or(self.incrementalROI_data,total_ROI).astype(np.uint8)
            origin_dict["Automatic drawing parameters"] = self.incrementalROI_origins

        if self.automaticROI_data is not None and self.automaticROI_overlay:
            total_ROI = np.logical_or(self.automaticROI_data, total_ROI).astype(np.uint8)
            new_params = {
                "Seed": list(self.automaticROI_seed_coordinates),  # assicurati che sia JSON-safe
                "Radius": self.automaticROI_radius_slider.value(),
                "Difference": self.automaticROI_diff_slider.value(),
            }
            if "Automatic drawing parameters" in origin_dict:
                origin_dict["Automatic drawing parameters"].append(new_params)
            else:
                origin_dict["Automatic drawing parameters"] = [new_params]

        log.debug("Start thread")
        # Start threaded save operation
        self.threads.append(SaveNiftiThread(total_ROI, self.affine,
                                            full_save_path, json_save_path,
                                            relative_path, origin_dict))
        self.threads[-1].success.connect(self._on_ROI_saved)
        self.threads[-1].error.connect(self._on_ROI_saving_error)
        self.threads[-1].start()

    def _on_ROI_saved(self, path, json_path):
        """Callback executed when ROI save completes successfully"""
        QMessageBox.information(self,
                                "ROI Saved",
                                f"ROI saved in:{path} and metadata saved in:{json_path} successfully!")
        log.info(f"ROI saved in:{path} and metadata saved in:{json_path} successfully!")

    def _on_ROI_saving_error(self, error):
        """Callback executed when ROI saving fails"""
        QMessageBox.critical(
            self,
            "Error when saving ROI",
            f"Error when saving: {error}"
        )
        log.critical(f"Error when saving ROI: {error}")

    def _get_next_file_id(self,folder_path):
        """
        Generates the next available numeric ID based on the files present in the folder.

        Looks for files with names matching the pattern 'something_idNUM_other.extension'
        (where NUM is an integer), and returns the next available number.

        Args:
            folder_path (str): Path to the folder to scan.

        Returns:
            int: The next available numeric ID.
        """
        pattern = re.compile(r"_v(\d+)_")
        ids = []
        log.debug("Searching versions")
        if os.path.exists(folder_path):
            for name in os.listdir(folder_path):
                if os.path.isfile(os.path.join(folder_path, name)):
                    match = pattern.search(name)
                    if match:
                        ids.append(int(match.group(1)))

            next_id = max(ids) + 1 if ids else 1
            log.debug(f"Next v: {next_id}")
            return next_id
        else:
            return 1
    def addOrigin_clicked(self):
        self.incrementalROI_data = self.incrementalROI_data if self.incrementalROI_data is not None else np.zeros(self.dims)

        if self.automaticROI_overlay and self.automaticROI_data is not None:
            self.incrementalROI_data = np.logical_or(self.incrementalROI_data, self.automaticROI_data).astype(np.uint8)

        #if self.overlay_enabled and self.overlay_data is not None:
        #    self.incrementalROI_data = np.logical_or(self.incrementalROI_data, self.overlay_data).astype(np.uint8)
        self.incrementalROI_checkbox.setVisible(True)
        self.incrementalROI_checkbox.setEnabled(True)
        self.toggle_incrementalROI(True)

        new_params = {
            "Seed": list(self.automaticROI_seed_coordinates),
            "Radius": self.automaticROI_radius_slider.value(),
            "Difference": self.automaticROI_diff_slider.value(),
        }

        # Mantieni lista incrementale
        self.incrementalROI_origins.append(new_params)

    def toggle_incrementalROI(self,enabled,update_all=True):

        self.incrementalROI_enabled = enabled
        self.incrementalROI_checkbox.setChecked(enabled)

        # Enable or disable overlay-related UI controls
        self.overlay_alpha_slider.setEnabled(enabled or self.automaticROI_overlay or self.overlay_enabled)
        self.overlay_alpha_spin.setEnabled(enabled or self.automaticROI_overlay or self.overlay_enabled)
        self.overlay_threshold_slider.setEnabled(enabled or self.automaticROI_overlay or self.overlay_enabled)
        self.overlay_threshold_spin.setEnabled(enabled or self.automaticROI_overlay or self.overlay_enabled)
        self.ROI_save_btn.setEnabled(enabled or self.automaticROI_overlay or self.overlay_enabled)

        if update_all:
            # Redraw display if overlay data is available
            self.update_all_displays()

            # Update time series plot if available
            self.update_time_series_plot()

    def closeEvent(self, event):
        """Clean up on application exit"""
        # Stop and delete all active threads
        if hasattr(self, 'threads'):
            for t in self.threads:
                if t.isRunning():
                    t.terminate()
                    t.wait()
                t.deleteLater()
            self.threads.clear()

        # Clear large data arrays to release memory
        self.img_data = None
        self.overlay_data = None

        # Trigger garbage collection
        gc.collect()

        # Accept the close event to exit
        event.accept()

    def reset_overlay(self):
        """Reset all overlay-related UI elements and internal variables."""
        # Disable the automatic ROI overlay mode
        self.automaticROI_overlay = False
        # Disable the "Save ROI" button since there’s no active overlay
        self.ROI_save_btn.setEnabled(False)
        # Clear all overlay-related data
        self.automaticROI_data = None
        self.overlay_data = None
        self.overlay_dims = None
        self.overlay_file_path = None
        # Hide and disable the overlay parameter sliders group (radius/difference)
        self.automaticROI_sliders_group.setVisible(False)
        self.automaticROI_sliders_group.setEnabled(False)
        # Ensure overlay visualization is turned off
        self.toggle_overlay(False,update_all=False)
        # Disable and uncheck the overlay checkbox in UI
        self.overlay_checkbox.setChecked(False)
        self.overlay_checkbox.setEnabled(False)
        # Reset overlay info label to default text
        self.overlay_info_label.setText(
            f"Overlay:\n" +
            QtCore.QCoreApplication.translate("NIfTIViewer", "Dimensions")
        )

    def resetROI(self):
        """Reset all ROI-related UI elements and internal variables."""
        self.ROI_save_btn.setEnabled(False)
        self.cancelROI_btn.setEnabled(False)
        self.addOrigin_btn.setEnabled(False)

        self.toggle_incrementalROI(False,update_all=False)
        self.incrementalROI_checkbox.setEnabled(False)
        self.incrementalROI_checkbox.setVisible(False)

        self.toggle_automaticROI(False,update_all=False)
        self.automaticROI_checkbox.setEnabled(False)
        self.automaticROI_checkbox.setVisible(False)

        self.incrementalROI_data = None
        self.automaticROI_data = None

        self.automaticROI_sliders_group.setVisible(False)
        self.automaticROI_sliders_group.setEnabled(False)

        self.automaticROIbtn.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Automatic ROI"))

        self.automaticROIbtn.setEnabled(True)

        self.incrementalROI_origins = []



    def pad_volume_to_shape(self, volume, target_shape, constant_value=0):
        """
        Pad a 3D volume (NumPy array) symmetrically to match a desired target shape.

        Args:
            volume (np.ndarray): Input 3D volume to pad.
            target_shape (tuple[int]): Desired (X, Y, Z) dimensions after padding.
            constant_value (int or float, optional): Value used for padding. Defaults to 0.

        Returns:
            np.ndarray: The padded 3D array with dimensions matching target_shape.
        """
        current_shape = volume.shape
        pads = []  # Store pad widths for each axis

        # Compute symmetric padding for each axis
        for cur, tgt in zip(current_shape, target_shape):
            diff = max(tgt - cur, 0)  # Calculate missing voxels along this axis
            pad_before = diff // 2  # Padding before the data
            pad_after = diff - pad_before  # Padding after the data
            pads.append((pad_before, pad_after))  # Add as (before, after) pair

        # Apply constant padding and return result
        return np.pad(volume, pads, mode="constant", constant_values=constant_value)

    def handle_scroll(self,plane_idx,delta):
        if plane_idx == 0:  # Axial (XY plane)
            if delta>0:
                self.current_coordinates[2] = min(self.current_coordinates[2] + delta,self.dims[2]-1)
                self.current_slices[0]= min(self.current_slices[0] + delta,self.dims[2]-1)
            elif delta<0:
                self.current_coordinates[2] = max(self.current_coordinates[2] + delta,0)
                self.current_slices[0] = max(self.current_slices[0] + delta,0)
            else:
                return
        elif plane_idx == 1:  # Coronal (XZ plane)
            if delta>0:
                self.current_coordinates[1] = min(self.current_coordinates[1] + delta,self.dims[1]-1)
                self.current_slices[1] = min(self.current_slices[1] + delta,self.dims[1]-1)
            elif delta<0:
                self.current_coordinates[1] = max(self.current_coordinates[1] + delta,0)
                self.current_slices[1] = max(self.current_slices[1] + delta,0)
            else:
                return
        elif plane_idx == 2:  # Sagittal (YZ plane)
            if delta>0:
                self.current_coordinates[0] = min(self.current_coordinates[0] + delta,self.dims[0]-1)
                self.current_slices[2] = min(self.current_slices[2] + delta,self.dims[0]-1)
            elif delta<0:
                self.current_coordinates[0] = max(self.current_coordinates[0] + delta,0)
                self.current_slices[2] = max(self.current_slices[2] + delta,0)
            else:
                return
        else:
            log.error("Plane index out of range")
            return
            # Synchronize controls for all planes
        for i in range(3):
            self.slice_sliders[i].setValue(self.current_slices[i])
            self.slice_spins[i].setValue(self.current_slices[i])
        self.update_cross_view_lines()
        self.update_coordinate_displays()


    def _translate_ui(self):
        """
        Update all UI texts for internationalization (i18n).

        This function ensures that all interface elements are dynamically translated
        using Qt’s translation system. It is typically called when initializing
        or changing the application language.
        """
        # Set the main window title
        self.setWindowTitle(QtCore.QCoreApplication.translate("NIfTIViewer", "NIfTI Image Viewer"))

        # Status bar initial message
        self.status_bar.showMessage(
            QtCore.QCoreApplication.translate("NIfTIViewer", "Ready - Open a NIfTI file to begin"))

        # Initialize coordinate and value display labels
        self.coord_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Coordinates: (-, -, -)"))
        self.value_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Value: -"))
        self.slice_info_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Slice: -/-"))

        # File open button label
        self.open_btn.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "📁 Open NIfTI File"))

        # Default file information message
        self.file_info_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "No file loaded"))

        # Plane labels for orthogonal slice views
        plane_names = [
            QtCore.QCoreApplication.translate("NIfTIViewer", "Axial (Z)"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Coronal (Y)"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Sagittal (X)")
        ]
        for i, name in enumerate(plane_names):
            self.plane_labels[i].setText(QtCore.QCoreApplication.translate("NIfTIViewer", name))

        # Time navigation controls
        self.time_checkbox.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Enable 4D Time Navigation"))
        self.time_point_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Time Point:"))

        # Display options section label
        self.display_options_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Display Options:"))

        # Populate color map combo box options
        colormap_names = ['gray', 'viridis', 'plasma', 'inferno', 'magma', 'hot', 'cool', 'bone']
        for i, name in enumerate(colormap_names):
            self.colormap_combo.setItemText(i, name)

        # Label for colormap and overlay control sections
        self.colormap_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Colormap:"))
        self.overlay_control_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Controls:"))

        # Overlay loading and visibility controls
        self.overlay_btn.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Load NIfTI Overlay"))
        self.overlay_checkbox.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Show Overlay"))
        self.alpha_overlay_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Transparency:"))
        self.overlay_threshold_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Threshold:"))
        self.overlay_info_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "No overlay loaded"))

        # Titles for image view panels
        view_titles = [
            QtCore.QCoreApplication.translate("NIfTIViewer", "Axial"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Coronal"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Sagittal")
        ]
        for i, title in enumerate(view_titles):
            self.view_titles_labels[i].setText(title)

        # Update fourth view title and general info text
        self.fourth_title.setText(QtCore.QCoreApplication.translate("NIfTIViewer", self.fourth_title.text()))
        self.info_text.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "No image loaded"))

        # If an image file is already loaded, update the displayed metadata
        if self.file_path:
            filename = os.path.basename(self.file_path)
            dims = self.dims
            # Distinguish between 3D and 4D datasets
            if self.is_4d:
                info_text = (
                        QtCore.QCoreApplication.translate("NIfTIViewer", "File") + f": {filename}\n" +
                        QtCore.QCoreApplication.translate("NIfTIViewer", "Dimensions") +
                        f": {dims[0]}×{dims[1]}×{dims[2]}×{dims[3]}\n" +
                        QtCore.QCoreApplication.translate("NIfTIViewer", "4D Time Series")
                )
            else:
                info_text = (
                        QtCore.QCoreApplication.translate("NIfTIViewer", "File") + f": {filename}\n" +
                        QtCore.QCoreApplication.translate("NIfTIViewer", "Dimensions") +
                        f": {dims[0]}×{dims[1]}×{dims[2]}\n" +
                        QtCore.QCoreApplication.translate("NIfTIViewer", "3D Volume")
                )

            # Update file info labels and sidebar text
            self.file_info_label.setText(info_text)
            self.info_text.setText(info_text)
        else:
            # Fallback text shown when no NIfTI file is loaded
            self.file_info_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "No file loaded"))
            self.info_text.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "No image loaded"))