import sys
import os
import gc
import json
import numpy as np
import nibabel as nib

from components.crosshair_graphic_view import CrosshairGraphicsView
from components.nifti_file_selector import NiftiFileDialog
from logger import get_logger
from threads.nifti_utils_threads import ImageLoadThread, SaveNiftiThread

log = get_logger()

from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QFileDialog,
    QSpinBox, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QStatusBar, QMessageBox,
    QProgressDialog, QGridLayout, QSplitter, QFrame, QSizePolicy, QCheckBox, QComboBox,
    QScrollArea, QDialog, QLineEdit, QListWidget, QDialogButtonBox, QListWidgetItem, QGroupBox
)
from PyQt6.QtCore import Qt, QPointF, QTimer, QThread, pyqtSignal, QSize, QCoreApplication, QRectF
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QPalette, QBrush, QResizeEvent, QMouseEvent, QTransform

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib
matplotlib.use('Agg')
import matplotlib.cm as cm

from numba import njit, prange


@njit(parallel=True)
def compute_mask_numba_mm(img, x0, y0, z0, radius_mm, voxel_sizes,
                          seed_intensity, diff,
                          x_min, x_max, y_min, y_max, z_min, z_max):
    """
    Compute a binary mask using a spherical region-growing algorithm.

    This function uses Numba for fast parallel execution.
    It identifies voxels within a given radius (in millimeters)
    from a seed point whose intensity differs from the seed intensity
    by less than a specified threshold.

    Args:
        img (np.ndarray): Input 3D image array.
        x0, y0, z0 (int): Seed voxel coordinates.
        radius_mm (float): Spherical radius in millimeters.
        voxel_sizes (tuple): Size of each voxel (mm_x, mm_y, mm_z).
        seed_intensity (float): Intensity value of the seed voxel.
        diff (float): Allowed intensity difference threshold.
        x_min, x_max, y_min, y_max, z_min, z_max (int): Subregion bounds.

    Returns:
        np.ndarray: Binary mask (same shape as `img`) with 1s where voxels meet the criteria.
    """
    mask = np.zeros(img.shape, dtype=np.uint8)
    r2 = radius_mm * radius_mm
    vx, vy, vz = voxel_sizes

    for x in prange(x_min, x_max):
        for y in range(y_min, y_max):
            for z in range(z_min, z_max):
                dx_mm = (x - x0) * vx
                dy_mm = (y - y0) * vy
                dz_mm = (z - z0) * vz
                if dx_mm * dx_mm + dy_mm * dy_mm + dz_mm * dz_mm <= r2:
                    val = img[x, y, z]
                    if abs(val - seed_intensity) <= diff:
                        mask[x, y, z] = 1
    return mask


@njit(parallel=True)
def apply_overlay_numba(rgba_image, overlay_mask, overlay_intensity, overlay_color):
    """
    Apply an overlay color to a base RGBA image using Numba for performance.

    Args:
        rgba_image (np.ndarray): Base RGBA image.
        overlay_mask (np.ndarray): Binary mask (2D) indicating where to apply the overlay.
        overlay_intensity (np.ndarray): Per-pixel overlay intensity map.
        overlay_color (np.ndarray): RGB color (3,) to apply (values 0.0–1.0).

    Returns:
        np.ndarray: RGBA image with overlay applied.
    """
    h, w, c = rgba_image.shape
    for y in prange(h):
        for x in range(w):
            if overlay_mask[y, x]:
                for ch in range(3):
                    if overlay_color[ch] != 0:
                        rgba_image[y, x, ch] = min(1.0, rgba_image[y, x, ch] + overlay_intensity[y, x] * overlay_color[ch])
                    else:
                        rgba_image[y, x, ch] *= (1.0 - overlay_intensity[y, x])
    return rgba_image


class NiftiViewer(QMainWindow):
    """
    Enhanced NIfTI viewer application with triplanar display and 4D support.

    This class provides a PyQt-based GUI for visualizing medical NIfTI images,
    allowing multi-slice navigation, overlay display, and region-of-interest (ROI) operations.
    """

    def __init__(self, context=None):
        """
        Initialize the NIfTI Viewer window.

        Args:
            context (dict, optional): Shared context or signals for inter-component communication.
        """
        super().__init__()
        self.threads = []
        self.context = context
        self.progress_dialog = None

        self.setWindowTitle(QtCore.QCoreApplication.translate("NIfTIViewer", "NIfTI Image Viewer"))
        self.setMinimumSize(1000, 700)
        self.resize(1400, 1000)

        # Core data containers
        self.img_data = None
        self.affine = None
        self.dims = None
        self.is_4d = False
        self.current_slices = [0, 0, 0]
        self.current_time = 0
        self.current_coordinates = [0, 0, 0]
        self.file_path = None
        self.voxel_sizes = None

        # Overlay parameters
        self.overlay_data = None
        self.overlay_dims = None
        self.overlay_alpha = 0.7
        self.overlay_threshold = 0.1
        self.overlay_enabled = False
        self.overlay_file_path = None

        # GUI elements (placeholders for setup)
        self.status_bar = None
        self.slice_info_label = None
        self.value_label = None
        self.coord_label = None

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

        # Initialize user interface
        self.init_ui()
        self.setup_connections()

        # Translation setup
        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def init_ui(self):
        """
        Initialize and configure the main user interface.

        Creates a horizontal splitter layout dividing the control panel
        (left) and the visualization area (right), and sets up the status bar.
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        central_widget.layout = QHBoxLayout(central_widget)
        central_widget.layout.setContentsMargins(5, 5, 5, 5)
        central_widget.layout.addWidget(main_splitter)

        # Left and right UI sections
        self.create_control_panel(main_splitter)
        self.create_image_display(main_splitter)

        # Adjust splitter proportions
        main_splitter.setSizes([300, 1100])

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.coord_label = QLabel("Coordinates: (-, -, -)")
        self.value_label = QLabel("Value: -")
        self.slice_info_label = QLabel("Slice: -/-")
        self.status_bar.showMessage("Ready - Open a NIfTI file to begin")

    def create_control_panel(self, parent):
        """
        Create the **left-side control panel** for the NIfTI Viewer interface.

        This panel is embedded in a scrollable container and contains all UI controls
        for navigation, visualization, overlays, and ROI tools.

        Structure Overview:
            1. **File Operations** — open and display NIfTI file info
            2. **Slice Navigation** — control 3D slice position (X, Y, Z)
            3. **4D Time Navigation** — enable time-based navigation for 4D images
            4. **Display Options** — choose colormaps and visual styles
            5. **Automatic ROI Tools** — enable and adjust automatic region of interest (ROI) drawing
            6. **Overlay Controls** — load, toggle, and adjust overlay transparency and thresholds

        Args:
            parent (QLayout): Parent layout (typically a `QVBoxLayout`) to which this
                control panel (wrapped in a `QScrollArea`) is added.
        """

        # Create a scrollable container to hold the entire control panel
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Content widget inside scroll area
        control_content = QWidget()
        control_content.setMaximumWidth(340)  # Prevent horizontal overflow
        layout = QVBoxLayout(control_content)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ----------------------------------------------------------------------
        # FILE OPERATIONS GROUP — Open NIfTI and show file info
        # ----------------------------------------------------------------------
        file_group = QFrame()
        file_layout = QVBoxLayout(file_group)
        file_layout.setContentsMargins(5, 5, 5, 5)

        self.open_btn = QPushButton(QtCore.QCoreApplication.translate("NIfTIViewer", "📁 Open NIfTI"))
        self.open_btn.setMinimumHeight(35)
        self.open_btn.setMaximumHeight(40)
        self.open_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.open_btn.setToolTip(QtCore.QCoreApplication.translate("NIfTIViewer", "Open NIfTI File"))
        file_layout.addWidget(self.open_btn)

        self.file_info_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "No file loaded"))
        self.file_info_label.setWordWrap(True)
        self.file_info_label.setStyleSheet("font-size: 10px;")
        self.file_info_label.setMaximumWidth(320)
        self.file_info_label.setMinimumHeight(40)
        file_layout.addWidget(self.file_info_label)

        layout.addWidget(file_group)

        # ----------------------------------------------------------------------
        # SLICE NAVIGATION — 3D (X, Y, Z) sliders with coordinates
        # ----------------------------------------------------------------------
        slice_group = QFrame()
        slice_layout = QVBoxLayout(slice_group)
        slice_layout.setContentsMargins(5, 5, 5, 5)

        self.slice_navigation_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Slice Navigation:"))
        self.slice_navigation_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        slice_layout.addWidget(self.slice_navigation_label)

        # Define names for the three planes
        plane_names = [
            QtCore.QCoreApplication.translate("NIfTIViewer", "Axial (Z)"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Coronal (Y)"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Sagittal (X)")
        ]

        self.plane_labels = []

        for i, plane_name in enumerate(plane_names):
            # Plane title label
            label = QLabel(plane_name)
            label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            slice_layout.addWidget(label)
            self.plane_labels.append(label)
            self.slice_labels.append(label)

            # Slider + Spinbox + Coordinate readout
            controls_widget = QWidget()
            controls_layout = QHBoxLayout(controls_widget)
            controls_layout.setContentsMargins(0, 0, 0, 0)
            controls_layout.setSpacing(5)

            # Slice slider
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(50)
            controls_layout.addWidget(slider, stretch=3)

            # Slice index spinbox
            spinbox = QSpinBox()
            spinbox.setRange(0, 100)
            spinbox.setValue(50)
            spinbox.setMaximumWidth(60)
            controls_layout.addWidget(spinbox)

            # Coordinate label
            coord_label = QLabel("(-, -)")
            coord_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 10px;")
            coord_label.setMinimumWidth(45)
            controls_layout.addWidget(coord_label)

            slice_layout.addWidget(controls_widget)

            self.slice_sliders.append(slider)
            self.slice_spins.append(spinbox)
            self.coord_displays.append(coord_label)

        layout.addWidget(slice_group)

        # ----------------------------------------------------------------------
        # TIME NAVIGATION — Optional 4D volume control
        # ----------------------------------------------------------------------
        self.time_group = QFrame()
        time_layout = QVBoxLayout(self.time_group)
        time_layout.setContentsMargins(5, 5, 5, 5)

        # Checkbox to enable/disable 4D controls
        self.time_checkbox = QCheckBox(QtCore.QCoreApplication.translate("NIfTIViewer", "Enable 4D Time Navigation"))
        time_layout.addWidget(self.time_checkbox)

        # Time navigation controls
        time_controls_widget = QWidget()
        time_controls_layout = QHBoxLayout(time_controls_widget)
        time_controls_layout.setContentsMargins(0, 0, 0, 0)
        time_controls_layout.setSpacing(5)

        # Time slider + spinbox
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, 0)
        self.time_slider.setEnabled(False)
        time_controls_layout.addWidget(self.time_slider, stretch=3)

        self.time_spin = QSpinBox()
        self.time_spin.setRange(0, 0)
        self.time_spin.setEnabled(False)
        time_controls_layout.addWidget(self.time_spin)

        self.time_point_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Time Point:"))
        time_layout.addWidget(self.time_point_label)

        time_layout.addWidget(time_controls_widget)
        self.time_group.setVisible(False)
        layout.addWidget(self.time_group)

        # ----------------------------------------------------------------------
        # DISPLAY OPTIONS — Colormap and visualization controls
        # ----------------------------------------------------------------------
        display_group = QFrame()
        display_layout = QVBoxLayout(display_group)
        display_layout.setContentsMargins(5, 5, 5, 5)

        self.display_options_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Display Options:"))
        self.display_options_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        display_layout.addWidget(self.display_options_label)

        # Colormap selector
        colormap_widget = QWidget()
        colormap_layout = QVBoxLayout(colormap_widget)
        colormap_layout.setContentsMargins(0, 0, 0, 0)
        colormap_layout.setSpacing(3)

        self.colormap_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Colormap:"))
        self.colormap_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        colormap_layout.addWidget(self.colormap_label)

        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems([
            'gray', 'viridis', 'plasma', 'inferno', 'magma', 'hot', 'cool', 'bone'
        ])
        self.colormap_combo.setMaximumHeight(25)
        colormap_layout.addWidget(self.colormap_combo)
        display_layout.addWidget(colormap_widget)

        layout.addWidget(display_group)

        # ----------------------------------------------------------------------
        # AUTOMATIC ROI — Configure radius and intensity difference
        # ----------------------------------------------------------------------
        self.automaticROI_group = QFrame()
        automaticROI_layout = QVBoxLayout(self.automaticROI_group)
        automaticROI_layout.setContentsMargins(5, 5, 5, 5)

        # ROI action buttons
        self.automaticROIbtn = QPushButton(QtCore.QCoreApplication.translate("NIfTIViewer", "Auto ROI"))
        self.automaticROIbtn.setToolTip(QtCore.QCoreApplication.translate("NIfTIViewer", "Automatic ROI Drawing"))
        automaticROI_layout.addWidget(self.automaticROIbtn)

        self.automaticROI_save_btn = QPushButton(QtCore.QCoreApplication.translate("NIfTIViewer", "Save ROI"))
        self.automaticROI_save_btn.setToolTip(QtCore.QCoreApplication.translate("NIfTIViewer", "Save ROI Drawing"))
        automaticROI_layout.addWidget(self.automaticROI_save_btn)

        # ROI sliders (radius + difference)
        self.automaticROI_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.automaticROI_radius_slider.setRange(0, 9999)
        self.automaticROI_radius_spin = QSpinBox()
        self.automaticROI_radius_spin.setRange(0, 9999)

        self.automaticROI_diff_slider = QSlider(Qt.Orientation.Horizontal)
        self.automaticROI_diff_slider.setRange(0, 99999)
        self.automaticROI_diff_spin = QSpinBox()
        self.automaticROI_diff_spin.setRange(0, 99999)

        automaticROI_layout.addWidget(QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Radius:")))
        automaticROI_layout.addWidget(self.automaticROI_radius_slider)
        automaticROI_layout.addWidget(self.automaticROI_radius_spin)
        automaticROI_layout.addWidget(QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Difference:")))
        automaticROI_layout.addWidget(self.automaticROI_diff_slider)
        automaticROI_layout.addWidget(self.automaticROI_diff_spin)

        layout.addWidget(self.automaticROI_group)

        # ----------------------------------------------------------------------
        #  OVERLAY CONTROLS — Load and adjust overlay transparency/threshold
        # ----------------------------------------------------------------------
        overlay_group = QFrame()
        overlay_layout = QVBoxLayout(overlay_group)
        overlay_layout.setContentsMargins(5, 5, 5, 5)

        self.overlay_control_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Controls:"))
        self.overlay_control_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        overlay_layout.addWidget(self.overlay_control_label)

        self.overlay_btn = QPushButton(QtCore.QCoreApplication.translate("NIfTIViewer", "Load Overlay"))
        self.overlay_btn.setToolTip(QtCore.QCoreApplication.translate("NIfTIViewer", "Load NIfTI Overlay"))
        overlay_layout.addWidget(self.overlay_btn)

        self.overlay_checkbox = QCheckBox(QtCore.QCoreApplication.translate("NIfTIViewer", "Show Overlay"))
        overlay_layout.addWidget(self.overlay_checkbox)

        self.overlay_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.overlay_alpha_slider.setRange(10, 100)
        self.overlay_alpha_spin = QSpinBox()
        self.overlay_alpha_spin.setRange(10, 100)
        overlay_layout.addWidget(QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Transparency:")))
        overlay_layout.addWidget(self.overlay_alpha_slider)
        overlay_layout.addWidget(self.overlay_alpha_spin)

        self.overlay_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.overlay_threshold_slider.setRange(0, 100)
        self.overlay_threshold_spin = QSpinBox()
        self.overlay_threshold_spin.setRange(0, 100)
        overlay_layout.addWidget(QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Threshold:")))
        overlay_layout.addWidget(self.overlay_threshold_slider)
        overlay_layout.addWidget(self.overlay_threshold_spin)

        self.overlay_info_label = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer", "No overlay loaded"))
        self.overlay_info_label.setWordWrap(True)
        overlay_layout.addWidget(self.overlay_info_label)

        layout.addWidget(overlay_group)

        # ----------------------------------------------------------------------
        # Final Setup: spacing, signals, and integration
        # ----------------------------------------------------------------------
        layout.addStretch()
        scroll_area.setWidget(control_content)
        scroll_area.setMinimumWidth(240)
        scroll_area.setMaximumWidth(340)

        # Connect sliders ↔ spinboxes for synchronization
        self.automaticROI_radius_slider.valueChanged.connect(self.automaticROI_radius_spin.setValue)
        self.automaticROI_radius_spin.valueChanged.connect(self.automaticROI_radius_slider.setValue)
        self.automaticROI_diff_slider.valueChanged.connect(self.automaticROI_diff_spin.setValue)
        self.automaticROI_diff_spin.valueChanged.connect(self.automaticROI_diff_slider.setValue)
        self.overlay_alpha_slider.valueChanged.connect(self.overlay_alpha_spin.setValue)
        self.overlay_alpha_spin.valueChanged.connect(self.overlay_alpha_slider.setValue)
        self.overlay_threshold_slider.valueChanged.connect(self.overlay_threshold_spin.setValue)
        self.overlay_threshold_spin.valueChanged.connect(self.overlay_threshold_slider.setValue)

        # Add final scrollable panel to parent layout
        parent.addWidget(scroll_area)

    # Funzione helper per formattare il testo senza causare scroll orizzontale
    def format_info_text(self, text, max_line_length=35):
        """
        Format informational text to prevent horizontal scrolling in the control panel.

        This helper function wraps long lines and adds indentation
        for improved readability in narrow UI areas.

        Args:
            text (str): The text to format.
            max_line_length (int): Maximum number of characters per line.

        Returns:
            str: Nicely wrapped text with line breaks and indentation.
        """
        import textwrap

        lines = text.split('\n')
        formatted_lines = []

        for line in lines:
            if len(line) <= max_line_length:
                formatted_lines.append(line)
            else:
                # Cerca di spezzare in punti logici (dopo :, spazi, ecc.)
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts[0]) <= max_line_length:
                        formatted_lines.append(parts[0] + ':')
                        # Wrap la seconda parte
                        wrapped = textwrap.fill(parts[1].strip(), width=max_line_length - 2)
                        formatted_lines.append('  ' + wrapped.replace('\n', '\n  '))
                    else:
                        wrapped = textwrap.fill(line, width=max_line_length)
                        formatted_lines.append(wrapped)
                else:
                    wrapped = textwrap.fill(line, width=max_line_length)
                    formatted_lines.append(wrapped)

        return '\n'.join(formatted_lines)

    def create_image_display(self, parent):
        """
        Create the main image display area showing three anatomical planes.

        This method builds a grid layout with:
            - Axial, Coronal, and Sagittal `CrosshairGraphicsView` widgets
            - A fourth panel for image info or time series (for 4D images)

        Args:
            parent (QSplitter): The parent splitter in which the display is inserted.
        """
        display_widget = QWidget()
        display_layout = QGridLayout(display_widget)
        display_layout.setSpacing(5)

        # Create three views in a 2x2 grid layout
        view_positions = [(0, 0), (0, 1), (1, 0)]
        view_titles = [QtCore.QCoreApplication.translate("NIfTIViewer","Axial"),QtCore.QCoreApplication.translate("NIfTIViewer","Coronal"),QtCore.QCoreApplication.translate("NIfTIViewer","Sagittal")]

        self.view_titles_labels = []
        for i, (row, col) in enumerate(view_positions):
            # View container with title
            view_container = QFrame()
            view_container.setFrameStyle(QFrame.Shape.StyledPanel)
            container_layout = QVBoxLayout(view_container)
            container_layout.setContentsMargins(2, 2, 2, 2)

            # Title label
            title_label = QLabel(view_titles[i])
            self.view_titles_labels.append(title_label)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("font-weight: bold; padding: 4px;")
            container_layout.addWidget(title_label)

            # Graphics view
            view = CrosshairGraphicsView(i, self)
            view.setMinimumSize(200, 200)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            # Scene
            scene = QGraphicsScene()
            view.setScene(scene)

            # Pixmap item
            pixmap_item = QGraphicsPixmapItem()
            scene.addItem(pixmap_item)

            container_layout.addWidget(view)

            # Add to grid
            display_layout.addWidget(view_container, row, col)

            # Store references
            self.views.append(view)
            self.scenes.append(scene)
            self.pixmap_items.append(pixmap_item)

        # Add time series plot panel to bottom right (for 4D data) or info panel (for 3D data)
        self.fourth_widget = QFrame()
        self.fourth_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        fourth_layout = QVBoxLayout(self.fourth_widget)

        self.fourth_title = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer","Image Information"))
        self.fourth_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fourth_title.setStyleSheet("font-weight: bold; padding: 4px;")
        fourth_layout.addWidget(self.fourth_title)

        # Container for switching between info and plot
        self.fourth_content = QWidget()
        self.fourth_content_layout = QVBoxLayout(self.fourth_content)

        # Info text widget
        self.info_text = QLabel(QtCore.QCoreApplication.translate("NIfTIViewer","No image loaded"))
        self.info_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.info_text.setStyleSheet("color: #cccccc; font-size: 11px; padding: 10px;")
        self.info_text.setWordWrap(True)
        self.fourth_content_layout.addWidget(self.info_text)

        # Time series plot widget (will be created when needed)
        self.time_plot_widget = None
        self.time_plot_canvas = None
        self.time_indicator_line = None

        fourth_layout.addWidget(self.fourth_content)
        display_layout.addWidget(self.fourth_widget, 1, 1)

        parent.addWidget(display_widget)

        # Setup crosshairs after views are created
        QTimer.singleShot(100, self.setup_crosshairs)


    def setup_crosshairs(self):
        """
        Initialize crosshair overlays for all anatomical views.

        Crosshairs are used to show the current coordinate position
        across the Axial, Coronal, and Sagittal views.
        """
        for view in self.views:
            view.setup_crosshairs()

    def setup_connections(self):
        """
        Connect all UI controls to their corresponding signal handlers.

        This includes:
            - File opening and overlay toggles
            - Slice and time navigation
            - Automatic ROI (region of interest) controls
            - Colormap selection
            - Mouse movement and coordinate updates
        """
        # File operations
        self.open_btn.clicked.connect(lambda: self.open_file())
        self.overlay_btn.clicked.connect(lambda: self.open_file(is_overlay=True))
        self.overlay_checkbox.toggled.connect(self.toggle_overlay)
        self.overlay_alpha_slider.valueChanged.connect(self.update_overlay_alpha)
        self.overlay_threshold_slider.valueChanged.connect(self.update_overlay_threshold)

        # Slice controls
        for i, (slider, spinbox) in enumerate(zip(self.slice_sliders, self.slice_spins)):
            slider.valueChanged.connect(lambda value, idx=i: self.slice_changed(idx, value))
            spinbox.valueChanged.connect(lambda value, idx=i: self.slice_changed(idx, value))

        # Automatic ROI Drawing
        self.automaticROIbtn.clicked.connect(self.automaticROI_clicked)
        self.automaticROI_diff_slider.valueChanged.connect(self.update_automaticROI)
        self.automaticROI_radius_slider.valueChanged.connect(self.update_automaticROI)
        self.automaticROI_save_btn.clicked.connect(self.automaticROI_save)
        # Time controls
        self.time_checkbox.toggled.connect(self.toggle_time_controls)
        self.time_slider.valueChanged.connect(self.time_changed)
        self.time_spin.valueChanged.connect(self.time_changed)

        # Colormap
        self.colormap_combo.currentTextChanged.connect(self.colormap_changed)

        # View coordinate changes
        for view in self.views:
            view.coordinate_changed.connect(self.update_coordinates)

    def show_workspace_nii_dialog(self, is_overlay=False):
        """
        Show a file selection dialog for loading a NIfTI file from the workspace.

        Args:
            is_overlay (bool): If True, restricts the search to derivative folders
                and loads the selected file as an overlay.

        Returns:
            None
        """
        if is_overlay:
            result = NiftiFileDialog.get_files(
                self.context,
                allow_multiple=False,
                has_existing_func=False,
                label=None,
                forced_filters={"search": "derivatives"}
            )
        else:
            result = NiftiFileDialog.get_files(
                self.context,
                allow_multiple=False,
                has_existing_func=False,
                label=None
            )
        if result:
            self.open_file(result[0], is_overlay=is_overlay)



    def open_file(self, file_path=None, is_overlay=False):
        """
        Open a NIfTI file and start an asynchronous loading thread.

        A progress dialog is displayed while loading.
        Supports both base images and overlay images.

        Args:
            file_path (str, optional): Path to the NIfTI file. If None, a file dialog is shown.
            is_overlay (bool, optional): Whether this file is an overlay. Defaults to False.
        """
        if is_overlay and self.img_data is None:
            QMessageBox.warning(
                self,
                QtCore.QCoreApplication.translate("NIfTIViewer", "Warning"),
                QtCore.QCoreApplication.translate("NIfTIViewer", "Please load a base image first!")
            )
            log.warning("No base image")
            return
        # If no file path provided, show file dialog
        if file_path is None:
            file_path = self.show_workspace_nii_dialog(is_overlay=is_overlay)
            if not file_path:  # User canceled the dialog
                return

        # Proceed with file loading
        if file_path:
            # Show progress dialog
            self.progress_dialog = QProgressDialog(
                QtCore.QCoreApplication.translate("NIfTIViewer", "Loading NIfTI file..."),
                QtCore.QCoreApplication.translate("NIfTIViewer", "Cancel"), 0, 100, self
            )
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setMinimumDuration(0)

            # Start loading thread
            self.threads.append(ImageLoadThread(file_path,is_overlay))
            self.threads[-1].finished.connect(self.on_file_loaded)
            self.threads[-1].error.connect(self.on_load_error)
            self.threads[-1].progress.connect(self.progress_dialog.setValue)
            self.threads[-1].start()

            self.progress_dialog.canceled.connect(self.on_load_canceled)

            if is_overlay:
                self.overlay_file_path = file_path
            else:
                self.file_path = file_path

    def on_file_loaded(self, img_data, dims, affine, is_4d, is_overlay):
        """
        Handle successful NIfTI file loading.

        This method updates the display, initializes slice controls,
        handles overlays, and populates file information in the UI.

        Args:
            img_data (np.ndarray): Loaded image data array.
            dims (tuple): Image dimensions.
            affine (np.ndarray): Affine transformation matrix.
            is_4d (bool): True if the image has a time dimension.
            is_overlay (bool): True if the loaded file is an overlay.
        """
        self.progress_dialog.canceled.disconnect()
        self.progress_dialog.close()
        thread_to_cancel = self.sender()
        self.threads.remove(thread_to_cancel)
        if is_overlay:
            # Salva overlay
            self.overlay_data = img_data
            self.overlay_dims = dims

            # Se le dimensioni non combaciano, applica padding
            if hasattr(self, "dims") and self.overlay_data.shape[:3] != self.dims[:3]:
                QMessageBox.warning(
                    self,
                    "Dimensions mismatch!",
                    f"The main image has dimensions {self.dims[:3]} and the overlay has dimensions {self.overlay_data.shape[:3]}."
                )
                self.overlay_data = self.pad_volume_to_shape(self.overlay_data, self.dims[:3])


            # Disabilita controlli Automatic ROI
            self.automaticROI_overlay = False
            self.automaticROI_save_btn.setEnabled(False)
            self.automaticROI_sliders_group.setEnabled(False)
            self.automaticROI_sliders_group.setVisible(False)

            # Aggiorna label info overlay
            filename = os.path.basename(self.overlay_file_path)
            self.overlay_info_label.setText(
                f"Overlay: {filename}\n" +
                QtCore.QCoreApplication.translate("NIfTIViewer", "Dimensions") +
                f":{self.overlay_dims}"
            )

            # Attiva overlay in UI
            self.toggle_overlay(True)
            self.overlay_checkbox.setChecked(True)
            self.overlay_checkbox.setEnabled(True)

            # Aggiorna visualizzazione
            self.update_overlay_settings()
            self.update_all_displays()

            # Messaggio nella status bar
            self.status_bar.showMessage(
                QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay loaded") + f":{filename}"
            )
        else:
            # Automatic ROI and Overlay resetting
            self.reset_overlay()
            self.img_data = img_data
            self.dims = dims
            self.affine = affine
            self.is_4d = is_4d
            self.voxel_sizes = np.sqrt((self.affine[:3, :3] ** 2).sum(axis=0))  # mm/voxel

            # Update file info
            filename = os.path.basename(self.file_path)
            if is_4d:
                info_text = QtCore.QCoreApplication.translate("NIfTIViewer", "File") + f":{filename}\n" + QtCore.QCoreApplication.translate("NIfTIViewer",
                                                                              "Dimensions") + f":{dims[0]}×{dims[1]}×{dims[2]}×{dims[3]}\n" + QtCore.QCoreApplication.translate(
                    "NIfTIViewer", "4D Time Series")
                self.time_group.setVisible(True)
                self.time_checkbox.setChecked(True)
                self.time_checkbox.setEnabled(True)
                self.setup_time_series_plot()
            else:
                info_text = QtCore.QCoreApplication.translate("NIfTIViewer", "File") + f":{filename}\n" + QtCore.QCoreApplication.translate("NIfTIViewer",
                                                                              "Dimensions") + f":{dims[0]}×{dims[1]}×{dims[2]}\n" + QtCore.QCoreApplication.translate(
                    "NIfTIViewer", "3D Volume")
                self.time_group.setVisible(False)
                self.time_checkbox.setChecked(False)
                self.time_checkbox.setEnabled(False)
                self.hide_time_series_plot()

            self.status_bar.clearMessage()
            self.status_bar.addWidget(self.coord_label)
            self.status_bar.addPermanentWidget(self.slice_info_label)
            self.status_bar.addPermanentWidget(self.value_label)

            self.automaticROIbtn.setEnabled(True)
            self.automaticROIbtn.setText("Automatic ROI")

            self.file_info_label.setText(info_text)
            self.info_text.setText(info_text)

            self.initialize_display()



    def on_load_error(self, error_message):
        """
        Handle errors that occur during file loading.

        Displays an error message dialog and logs the issue.

        Args:
            error_message (str): Description of the error.
        """
        self.progress_dialog.canceled.disconnect()
        self.progress_dialog.close()
        QMessageBox.critical(self, QtCore.QCoreApplication.translate("NIfTIViewer","Error Loading File"), QtCore.QCoreApplication.translate("NIfTIViewer","Failed to load NIfTI file") + f":\n{error_message}")
        log.critical(f"Error loading NIftI file: {error_message}")
        thread_to_cancel = self.sender()
        if thread_to_cancel in self.threads:
            self.threads.remove(thread_to_cancel)

    def on_load_canceled(self):
        """
        Cancel an ongoing file loading operation.

        Terminates the most recently started loading thread.
        """
        self.threads[-1].terminate()
        self.threads.pop()


    def initialize_display(self):
        """
        Initialize all display settings after an image is loaded.

        Sets up slice sliders, time controls (if 4D), and coordinates.
        Also enables overlay controls and refreshes all anatomical views.
        """
        if self.img_data is None:
            return

        # Set up slice controls for spatial dimensions
        spatial_dims = self.dims[:3][::-1] if self.is_4d else self.dims[::-1]

        for i in range(3):
            max_slice = spatial_dims[i] - 1
            self.slice_sliders[i].setMaximum(max_slice)
            self.slice_spins[i].setMaximum(max_slice)
            self.current_slices[i] = max_slice // 2  # Start in middle
            self.slice_sliders[i].setValue(self.current_slices[i])
            self.slice_spins[i].setValue(self.current_slices[i])

        # Set up time controls for 4D data
        if self.is_4d:
            max_time = self.dims[3] - 1
            self.time_slider.setMaximum(max_time)
            self.time_spin.setMaximum(max_time)
            self.current_time = 0
            self.time_slider.setValue(0)
            self.time_spin.setValue(0)
            self.toggle_time_controls(self.time_checkbox.isChecked())

        # Initialize coordinate display
        self.current_coordinates = [
            self.current_slices[2],  # X (sagittal slice)
            self.current_slices[1],  # Y (coronal slice)
            self.current_slices[0]  # Z (axial slice)
        ]

        self.update_all_displays()
        self.update_coordinate_displays()

        # Enable overlay controls when base image is loaded
        self.overlay_btn.setEnabled(True)

    def toggle_overlay(self, enabled):
        """
        Enable or disable overlay visualization.

        Args:
            enabled (bool): True to show overlay, False to hide it.
        """
        self.overlay_enabled = enabled

        # Abilita/disabilita controlli
        if hasattr(self, 'overlay_alpha_slider'):
            self.overlay_alpha_slider.setEnabled(enabled)
        if hasattr(self, 'overlay_alpha_spin'):
            self.overlay_alpha_spin.setEnabled(enabled)
        if hasattr(self, 'overlay_threshold_slider'):
            self.overlay_threshold_slider.setEnabled(enabled)
        if hasattr(self, 'overlay_threshold_spin'):
            self.overlay_threshold_spin.setEnabled(enabled)

        # Aggiorna visualizzazione solo se abbiamo dati overlay
        if hasattr(self, 'overlay_data') and self.overlay_data is not None:
            self.update_all_displays()
            if hasattr(self, 'update_time_series_plot'):
                self.update_time_series_plot()

    def update_overlay_alpha(self, value):
        """
        Update overlay transparency based on the slider value.

        Args:
            value (int): Alpha transparency (0–100).
        """
        self.overlay_alpha = value / 100.0
        if (self.overlay_enabled and
                hasattr(self, 'overlay_data') and
                self.overlay_data is not None):
            self.update_all_displays()

    def update_overlay_threshold(self, value):
        """
        Update overlay threshold based on the slider value.

        Args:
            value (int): Threshold percentage (0–100).
        """
        self.overlay_threshold = value / 100.0
        if (self.overlay_enabled and
                hasattr(self, 'overlay_data') and
                self.overlay_data is not None):
            self.update_all_displays()

    def update_overlay_settings(self):
        """
        Synchronize overlay alpha and threshold values from UI controls.

        Updates all views if overlay is enabled and overlay data is available.
        """
        if hasattr(self, 'overlay_alpha_slider') and hasattr(self, 'overlay_threshold_slider'):
            self.overlay_alpha = self.overlay_alpha_slider.value() / 100.0
            self.overlay_threshold = self.overlay_threshold_slider.value() / 100.0

            # Aggiorna visualizzazione solo se overlay è abilitato e dati esistono
            if self.overlay_enabled and hasattr(self, 'overlay_data') and self.overlay_data is not None:
                self.update_all_displays()

    def slice_changed(self, plane_idx, value):
        """
        Handle slice change events from sliders or spinboxes.

        Args:
            plane_idx (int): Index of the anatomical plane (0=axial, 1=coronal, 2=sagittal).
            value (int): New slice index value.
        """
        self.current_slices[plane_idx] = value

        # Update corresponding controls
        self.slice_sliders[plane_idx].setValue(value)
        self.slice_spins[plane_idx].setValue(value)

        # Update coordinates based on slice change
        if plane_idx == 0:  # Axial
            self.current_coordinates[2] = value
        elif plane_idx == 1:  # Coronal
            self.current_coordinates[1] = value
        elif plane_idx == 2:  # Sagittal
            self.current_coordinates[0] = value

        self.update_display(plane_idx)
        self.update_coordinate_displays()
        self.update_cross_view_lines()

    def time_changed(self, value):
        """
        Handle time slider or spinbox changes for 4D data.

        Args:
            value (int): Current time index.
        """
        self.current_time = value
        self.time_slider.setValue(value)
        self.time_spin.setValue(value)
        self.update_all_displays()

    def toggle_time_controls(self, enabled):
        """
        Enable or disable visibility of time navigation controls.

        Args:
            enabled (bool): True to show controls, False to hide them.
        """
        value = enabled and self.is_4d
        self.time_slider.setVisible(value)
        self.time_slider.setEnabled(value)
        self.time_spin.setVisible(value)
        self.time_spin.setEnabled(value)
        self.time_point_label.setVisible(value)

    def colormap_changed(self, colormap_name):
        """
        Update the active colormap for image display.

        Args:
            colormap_name (str): Name of the selected Matplotlib colormap.
        """
        self.colormap = colormap_name
        self.update_all_displays()

    def handle_click_coordinates(self, view_idx, x, y):
        """
        Handle user mouse clicks on any anatomical view.

        Updates the 3D coordinates and crosshair position across all views.

        Args:
            view_idx (int): Index of the clicked view.
            x (float): X coordinate in scene space.
            y (float): Y coordinate in scene space.
        """
        if self.img_data is None:
            return

        # Convert screen coordinates to image coordinates
        img_coords = self.screen_to_image_coords(view_idx, x, y)
        if img_coords is None:
            return

        # Update current coordinates
        self.current_coordinates = img_coords

        # Update slice positions based on clicked coordinates
        self.current_slices[0] = img_coords[2]  # Axial (Z)
        self.current_slices[1] = img_coords[1]  # Coronal (Y)
        self.current_slices[2] = img_coords[0]  # Sagittal (X)

        # Update slice controls
        for i in range(3):
            self.slice_sliders[i].setValue(self.current_slices[i])
            self.slice_spins[i].setValue(self.current_slices[i])

        # Update all displays and coordinate displays
        self.update_all_displays()
        self.update_coordinate_displays()
        self.update_cross_view_lines()

    def screen_to_image_coords(self, view_idx, x, y):
        """
        Convert 2D screen (view) coordinates to 3D voxel coordinates.

        Args:
            view_idx (int): Index of the view (0=axial, 1=coronal, 2=sagittal).
            x (float): X coordinate in screen space.
            y (float): Y coordinate in screen space.

        Returns:
            list[int] | None: Corresponding [x, y, z] voxel coordinates,
                or None if conversion fails.
        """
        if self.img_data is None:
            return None

        stretch_x, stretch_y = self.stretch_factors.get(view_idx, (1.0, 1.0))

        # Streching compensation
        x = x / stretch_x
        y = y / stretch_y

        # Get current data shape
        if self.is_4d:
            shape = self.img_data.shape[:3]
        else:
            shape = self.img_data.shape

        # Convert based on view orientation
        if view_idx == 0:  # Axial (XY plane)
            # In axial view: x=X, y=Y, z=current slice
            img_x = min(max(x, 0), shape[0] - 1)
            img_y = min(max(shape[1] - 1 - y, 0), shape[1] - 1)  # Flip Y
            img_z = self.current_slices[0]
        elif view_idx == 1:  # Coronal (XZ plane)
            # In coronal view: x=X, y=Z, z=current slice
            img_x = min(max(x, 0), shape[0] - 1)
            img_y = self.current_slices[1]
            img_z = min(max(shape[2] - 1 - y, 0), shape[2] - 1)  # Flip Z
        elif view_idx == 2:  # Sagittal (YZ plane)
            # In sagittal view: x=Y, y=Z, z=current slice
            img_x = self.current_slices[2]
            img_y = min(max(x, 0), shape[1] - 1)
            img_z = min(max(shape[2] - 1 - y, 0), shape[2] - 1)  # Flip Z
        else:
            return None

        return [int(img_x), int(img_y), int(img_z)]

    def update_coordinates(self, view_idx, x, y):
        """
        Update coordinate and intensity labels during mouse movement.

        Args:
            view_idx (int): Index of the view where the mouse moved.
            x (float): X coordinate.
            y (float): Y coordinate.
        """
        if self.img_data is None:
            return

        img_coords = self.screen_to_image_coords(view_idx, x, y)
        if img_coords is None:
            return

        # Get voxel value
        try:
            if self.is_4d:
                value = self.img_data[img_coords[0], img_coords[1], img_coords[2], self.current_time]
            else:
                value = self.img_data[img_coords[0], img_coords[1], img_coords[2]]

            self.coord_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer","Coordinates")+f": ({img_coords[0]}, {img_coords[1]}, {img_coords[2]})")
            self.value_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer","Value")+f": {value:.2f}")

        except (IndexError, ValueError):
            pass

    def update_coordinate_displays(self):
        """
        Update coordinate and intensity labels beside sliders and in the status bar.

        Displays the current voxel coordinates and intensity value.
        """
        if self.img_data is None:
            return

        # Update coordinate labels for each plane
        coords = self.current_coordinates

        # Axial view: shows X, Y coordinates
        self.coord_displays[0].setText(f"({coords[0]}, {coords[1]})")

        # Coronal view: shows X, Z coordinates
        self.coord_displays[1].setText(f"({coords[0]}, {coords[2]})")

        # Sagittal view: shows Y, Z coordinates
        self.coord_displays[2].setText(f"({coords[1]}, {coords[2]})")

        # Update status bar
        self.coord_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer","Coordinates")+f": ({coords[0]}, {coords[1]}, {coords[2]})")

        try:
            if self.is_4d:
                value = self.img_data[coords[0], coords[1], coords[2], self.current_time]
            else:
                value = self.img_data[coords[0], coords[1], coords[2]]
            self.value_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer","Value")+ f": {value:.2f}")
        except (IndexError, ValueError):
            self.value_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer","Value")+f": -")

    def update_cross_view_lines(self):
        """
        Refresh crosshair positions across all views
        to reflect the current 3D coordinate selection.
        """
        if self.img_data is None:
            return

        coords = self.current_coordinates

        for i, view in enumerate(self.views):
            # Se il fattore di stretch non esiste ancora, usa (1.0, 1.0)
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
        """
        Redraw a single anatomical plane (Axial, Coronal, or Sagittal).

        Handles slice extraction, optional overlay blending,
        and pixel scaling according to voxel dimensions.

        Args:
            plane_idx (int): Index of the plane to update (0=axial, 1=coronal, 2=sagittal).
        """
        if self.img_data is None:
            return

        try:
            # Get current data (3D or 4D)
            if self.is_4d:
                current_data = self.img_data[..., self.current_time]
            else:
                current_data = self.img_data

            slice_idx = self.current_slices[plane_idx]

            if plane_idx == 0:  # Axial (XY)
                slice_data = current_data[:, :, slice_idx].T
                slice_data = np.flipud(slice_data)
                pixel_spacing = self.voxel_sizes[0:2]  # X, Y
            elif plane_idx == 1:  # Coronal (XZ)
                slice_data = current_data[:, slice_idx, :].T
                slice_data = np.flipud(slice_data)
                pixel_spacing = (self.voxel_sizes[0], self.voxel_sizes[2])  # X, Z
            elif plane_idx == 2:  # Sagittal (YZ)
                slice_data = current_data[slice_idx, :, :].T
                slice_data = np.flipud(slice_data)
                pixel_spacing = self.voxel_sizes[1:3]  # Y, Z
            else:
                return

            # Overlay
            overlay_slice = None
            if self.overlay_enabled and self.overlay_data is not None:
                if plane_idx == 0:
                    overlay_slice = self.overlay_data[:, :, slice_idx].T
                    overlay_slice = np.flipud(overlay_slice)
                elif plane_idx == 1:
                    overlay_slice = self.overlay_data[:, slice_idx, :].T
                    overlay_slice = np.flipud(overlay_slice)
                elif plane_idx == 2:
                    overlay_slice = self.overlay_data[slice_idx, :, :].T
                    overlay_slice = np.flipud(overlay_slice)


            # Create composite
            height, width = slice_data.shape
            rgba_image = self.apply_colormap_matplotlib(slice_data, self.colormap)
            if self.overlay_enabled and overlay_slice is not None:
                rgba_image = self.create_overlay_composite(rgba_image, overlay_slice, self.colormap)

            rgba_data_uint8 = (rgba_image * 255).astype(np.uint8)
            qimage = QImage(rgba_data_uint8.data, width, height, width * 4, QImage.Format.Format_RGBA8888)

            if qimage is not None:
                img_w, img_h = qimage.width(), qimage.height()

                # Applica il ridimensionamento in mm
                qimage_scaled = qimage.scaled(
                    int(img_w),
                    int(img_h * (pixel_spacing[1] / pixel_spacing[0])),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

                self.stretch_factors[plane_idx] = (1.0, pixel_spacing[1] / pixel_spacing[0])
                self.pixmap_items[plane_idx].setPixmap(QPixmap.fromImage(qimage_scaled))
                self.scenes[plane_idx].setSceneRect(0, 0, qimage_scaled.width(), qimage_scaled.height())
                self.views[plane_idx].fitInView(self.scenes[plane_idx].sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)



        except Exception as e:
            log.error(f"Error updating display {plane_idx}: {e}")


    def setup_time_series_plot(self):
        """
        Create and initialize a time series plot for 4D image data.

        Displays a dynamic tracer concentration curve
        (intensity vs. time) for the current voxel.
        """
        if self.time_plot_canvas is not None:
            return  # Already setup

        # Hide info text and show plot
        self.info_text.hide()


        self.time_plot_figure = Figure(figsize=(3, 3), facecolor='black')
        self.time_plot_figure.set_tight_layout(True)

        self.time_plot_canvas = FigureCanvas(self.time_plot_figure)
        self.time_plot_axes = self.time_plot_figure.add_subplot(111)
        self.time_plot_axes.set_facecolor('black')

        # Update title and add canvas
        self.fourth_title.setText(QtCore.QCoreApplication.translate("NIfTIViewer","Tracer Concentration Curve"))
        self.fourth_content_layout.addWidget(self.time_plot_canvas)

    def hide_time_series_plot(self):
        """
        Hide and clean up the time series plot when switching from 4D to 3D data.

        Restores the default "Image Information" panel instead of the plot.
        """
        if self.time_plot_canvas is not None:
            # Rimuovi dal layout per evitare che rimanga "sporco"
            self.fourth_content_layout.removeWidget(self.time_plot_canvas)
            self.time_plot_canvas.setParent(None)
            self.time_plot_canvas.deleteLater()
            self.time_plot_canvas = None
            self.time_plot_axes = None
            self.time_plot_figure = None

        self.fourth_title.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Image Information"))
        self.info_text.show()

    def update_time_series_plot(self):
        """
        Update the time series plot with current voxel or ROI data.

        This function updates the time series plot (in 4D mode) using either:
        - The average signal within the thresholded overlay mask (if enabled and voxel is inside mask), or
        - The single voxel time series (if no overlay or voxel is outside threshold).

        It also updates the plot style, labels, and the current time indicator line.
        """
        if not self.is_4d or self.time_plot_canvas is None or self.img_data is None:
            return

        try:
            coords = self.current_coordinates
            bool_in_mask = False

            if self.overlay_data is not None and self.overlay_enabled:
                # Compute thresholded mask based on overlay intensity
                overlay_max = np.max(self.overlay_data) if np.max(self.overlay_data) > 0 else 1
                threshold_value = self.overlay_threshold * overlay_max
                threshold_mask = self.overlay_data > threshold_value

                # Check if current voxel is inside threshold mask
                if threshold_mask[coords[0], coords[1], coords[2]]:
                    bool_in_mask = True

                    # Mean and std across mask voxels
                    roi_voxels = self.img_data[threshold_mask, :]
                    time_series = roi_voxels.mean(axis=0)
                    std_series = roi_voxels.std(axis=0)
                else:
                    # Single voxel time series (outside mask)
                    time_series = self.img_data[coords[0], coords[1], coords[2], :]
                    std_series = None
            else:
                # No overlay enabled
                time_series = self.img_data[coords[0], coords[1], coords[2], :]
                std_series = None

            time_points = np.arange(self.dims[3])

            # Clear and re-draw the plot
            self.time_plot_axes.clear()
            self.time_plot_axes.set_facecolor('black')
            self.time_plot_axes.plot(
                time_points,
                time_series,
                'c-',
                linewidth=2,
                label=QtCore.QCoreApplication.translate("NIfTIViewer", 'Concentration')
            )

            if std_series is not None:
                # Draw standard deviation band
                self.time_plot_axes.fill_between(
                    time_points,
                    time_series - std_series,
                    time_series + std_series,
                    alpha=0.2,
                    color='c'
                )

            # Draw current time indicator
            self.time_indicator_line = self.time_plot_axes.axvline(
                x=self.current_time,
                color='yellow',
                linewidth=2,
                alpha=0.8,
                label=QtCore.QCoreApplication.translate("NIfTIViewer", 'Current Time')
            )

            # Axis labels and style
            self.time_plot_axes.set_xlabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Time Point"),
                                           color='white')
            self.time_plot_axes.set_ylabel(QtCore.QCoreApplication.translate("NIfTIViewer", "Signal Intensity"),
                                           color='white')

            # Dynamic title based on context
            if bool_in_mask:
                self.time_plot_axes.set_title('Mean in overlay mask', color='white')
            else:
                self.time_plot_axes.set_title(f'Voxel ({coords[0]}, {coords[1]}, {coords[2]})', color='white')

            self.time_plot_axes.tick_params(colors='white')
            self.time_plot_axes.legend()
            self.time_plot_axes.grid(True, alpha=0.3, color='gray')

            # Render updated plot
            self.time_plot_canvas.draw()

        except Exception as e:
            log.error(f"Error updating time series plot: {e}")

    def apply_colormap_matplotlib(self, data, colormap_name):
        """
        Apply a matplotlib colormap to data and return the RGBA array.

        Args:
            data (np.ndarray): Normalized grayscale data (0–1).
            colormap_name (str): Name of matplotlib colormap.

        Returns:
            np.ndarray: RGBA array (H, W, 4) or None if error occurs.
        """
        try:
            cmap = cm.get_cmap(colormap_name)
            colored_data = cmap(data)
            return colored_data
        except Exception as e:
            log.error(f"Error applying colormap: {e}")
            return None

    def update_all_displays(self):
        """
        Refresh all image planes (axial, coronal, sagittal) and the time series plot.

        This ensures UI consistency after any data update, such as:
        - Slice changes
        - Overlay toggling
        - Time navigation
        """
        for i in range(3):
            self.update_display(i)

        if self.is_4d:
            self.update_time_series_plot()

        if self.img_data is not None:
            spatial_dims = self.dims[:3] if self.is_4d else self.dims
            slice_info = (
                    QtCore.QCoreApplication.translate("NIfTIViewer", "Slices") +
                    f": {self.current_slices[0] + 1}/{spatial_dims[2]} | "
                    f"{self.current_slices[1] + 1}/{spatial_dims[1]} | "
                    f"{self.current_slices[2] + 1}/{spatial_dims[0]}"
            )
            if self.is_4d:
                slice_info += (
                        " | " +
                        QtCore.QCoreApplication.translate("NIfTIViewer", "Time") +
                        f": {self.current_time + 1}/{self.dims[3]}"
                )
            self.slice_info_label.setText(slice_info)

    def create_overlay_composite(self, rgba_image, overlay_slice, colormap):
        """
        Combine a base RGBA image with a thresholded overlay.

        The overlay is alpha-blended using a user-defined threshold and color.

        Args:
            rgba_image (np.ndarray): Base colormapped image (H, W, 4).
            overlay_slice (np.ndarray): Overlay slice (H, W).
            colormap (str): Colormap name (unused but kept for consistency).

        Returns:
            np.ndarray: RGBA composite image.
        """
        try:
            rgba_image_float = rgba_image.astype(np.float64)
            if overlay_slice.size > 0:
                overlay_max = np.max(overlay_slice) if np.max(overlay_slice) > 0 else 1
                threshold_value = self.overlay_threshold * overlay_max
                overlay_mask = overlay_slice > threshold_value

                if np.any(overlay_mask):
                    overlay_intensity = overlay_slice * self.overlay_alpha
                    overlay_color = self.overlay_colors.get(self.colormap, np.array([0.0, 1.0, 0.0]))
                    rgba_image_float = apply_overlay_numba(rgba_image, overlay_mask, overlay_intensity, overlay_color)

            return np.clip(rgba_image_float, 0, 1)

        except Exception as e:
            log.error(f"Error creating overlay composite: {e}")
            return rgba_image

    def resizeEvent(self, event: QResizeEvent):
        """Ensure views remain correctly scaled when window size changes."""
        super().resizeEvent(event)
        QTimer.singleShot(100, self.fit_all_views)

    def fit_all_views(self):
        """Fit each view to its content maintaining aspect ratio."""
        for view in self.views:
            if view.scene():
                view.fitInView(view.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def update_automaticROI(self):
        """Automatically update ROI overlay when parameters change."""
        if self.overlay_enabled and self.automaticROI_overlay:
            self.automaticROI_drawing()
            self.update_all_displays()

    def automaticROI_clicked(self):
        """
        Initialize automatic ROI drawing.

        Sets up seed point, radius, and difference sliders, enabling overlay
        visualization for interactive segmentation.
        """
        self.automaticROI_seed_coordinates = self.current_coordinates
        dims_voxel = self.dims[:3]
        dims_mm = dims_voxel * self.voxel_sizes
        max_radius_mm = np.min(dims_mm) / 2

        self.automaticROI_radius_slider.setMaximum(int(max_radius_mm))
        self.automaticROI_radius_slider.setValue(
            32 if not self.automaticROI_overlay else self.automaticROI_radius_slider.value()
        )

        self.automaticROI_diff_slider.setMaximum(1000)
        self.automaticROI_diff_slider.setValue(
            int(1000 * (16 / 100)) if not self.automaticROI_overlay else self.automaticROI_diff_slider.value()
        )

        self.automaticROI_sliders_group.setVisible(True)
        self.automaticROI_sliders_group.setEnabled(True)
        self.automaticROIbtn.setText("Reset Origin")
        self.automaticROI_overlay = True
        self.automaticROI_save_btn.setEnabled(True)

        self.automaticROI_drawing()
        self.overlay_info_label.setText(
            f"Overlay:" + QtCore.QCoreApplication.translate("NIfTIViewer", "Automatic ROI Drawing")
        )

        self.toggle_overlay(True)
        self.overlay_checkbox.setChecked(True)
        self.overlay_checkbox.setEnabled(True)
        self.update_all_displays()

    def automaticROI_drawing(self):
        """
        Compute and display an automatic ROI mask around the seed voxel.

        Uses intensity similarity and distance thresholds to determine which
        voxels belong to the region.
        """
        radius_mm = self.automaticROI_radius_slider.value()
        difference = self.automaticROI_diff_slider.value() / 1000
        x0, y0, z0 = self.automaticROI_seed_coordinates
        img_data = self.img_data[..., self.current_time] if self.is_4d else self.img_data
        seed_intensity = img_data[x0, y0, z0]

        # Compute bounding box for ROI
        rx_vox = int(np.ceil(radius_mm / self.voxel_sizes[0]))
        ry_vox = int(np.ceil(radius_mm / self.voxel_sizes[1]))
        rz_vox = int(np.ceil(radius_mm / self.voxel_sizes[2]))

        x_min, x_max = max(0, x0 - rx_vox), min(img_data.shape[0], x0 + rx_vox + 1)
        y_min, y_max = max(0, y0 - ry_vox), min(img_data.shape[1], y0 + ry_vox + 1)
        z_min, z_max = max(0, z0 - rz_vox), min(img_data.shape[2], z0 + rz_vox + 1)

        # Parallel computation (Numba)
        mask = compute_mask_numba_mm(
            img_data, x0, y0, z0,
            radius_mm, self.voxel_sizes,
            seed_intensity, difference,
            x_min, x_max, y_min, y_max, z_min, z_max
        )

        self.overlay_data = mask

    def automaticROI_save(self):
        """
        Save the automatically generated ROI mask to disk as a NIfTI file and metadata JSON.

        This method:
        - Builds the output filename based on current subject, radius, and difference.
        - Asks user for confirmation before saving.
        - Starts a background thread (`SaveNiftiThread`) to write the NIfTI and JSON files.
        """
        if not self.automaticROI_overlay or self.overlay_data is None:
            return

        radius = self.automaticROI_radius_slider.value()
        difference = self.automaticROI_diff_slider.value() / 10

        original_path = self.file_path
        if not original_path:
            QMessageBox.critical(self, "Error", "No file loaded.")
            log.critical("No file loaded")
            return

        workspace_path = self.context.get("workspace_path")
        if not workspace_path:
            QMessageBox.critical(self, "Error", "Workspace path is not set.")
            log.critical("Workspace path not set")
            return

        # Extract subject name from BIDS-like folder structure
        relative_path = os.path.relpath(original_path, workspace_path)
        parts = relative_path.split(os.sep)
        try:
            subject = next(part for part in parts if part.startswith("sub-"))
        except StopIteration:
            QMessageBox.critical(self, "Error", "Could not determine subject from path.")
            log.error("Could not determine subject from path.")
            return

        # Compose filenames and output paths
        filename = os.path.basename(original_path)
        base_name = filename.replace(".nii.gz", "").replace(".nii", "")
        new_base = f"{base_name}_r{radius:02d}_d{difference}%_mask"
        new_name = f"{new_base}.nii.gz"
        save_dir = os.path.join(workspace_path, "derivatives", "manual_masks", subject, "anat")
        full_save_path = os.path.join(save_dir, new_name)
        json_save_path = os.path.join(save_dir, f"{new_base}.json")

        # Confirmation dialog
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Confirm Save")
        msg.setText("Do you want to save the automatic ROI?")
        msg.setInformativeText(
            f"File will be saved as:\n\n{new_name}\n\n"
            f"Location:\n{save_dir}\n\n"
            f"Radius: {radius}\nDifference: {difference}"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        response = msg.exec()

        if response != QMessageBox.StandardButton.Yes:
            return  # User cancelled

        # Create directories and start save thread
        os.makedirs(save_dir, exist_ok=True)
        self.threads.append(SaveNiftiThread(
            self.overlay_data,
            self.affine,
            full_save_path,
            json_save_path,
            relative_path,
            radius,
            difference
        ))

        # Connect callbacks
        self.threads[-1].success.connect(self._on_automaticROI_saved)
        self.threads[-1].error.connect(self._on_automaticROI_error)
        self.threads[-1].start()

    def _on_automaticROI_saved(self, path, json_path):
        """
        Callback executed after a successful ROI save.

        Displays a confirmation dialog and logs success.
        """
        QMessageBox.information(
            self,
            "ROI Saved",
            f"ROI saved in: {path}\nMetadata saved in: {json_path}"
        )
        log.info(f"ROI saved in: {path} and metadata saved in: {json_path} successfully!")

    def _on_automaticROI_error(self, error):
        """
        Callback executed if an error occurs while saving the ROI.

        Displays an error dialog and logs the failure.
        """
        QMessageBox.critical(
            self,
            "Error when saving ROI",
            f"Error when saving: {error}"
        )
        log.critical(f"Error when saving ROI: {error}")

    def closeEvent(self, event):
        """
        Clean up application resources and threads before exit.

        - Terminates and deletes running threads.
        - Clears large arrays (img_data, overlay_data).
        - Forces garbage collection to free memory.
        """
        if hasattr(self, 'threads'):
            for t in self.threads:
                if t.isRunning():
                    t.terminate()
                    t.wait()
                t.deleteLater()
            self.threads.clear()

        self.img_data = None
        self.overlay_data = None
        gc.collect()
        event.accept()

    def reset_overlay(self):
        """
        Reset the overlay system to its default (disabled) state.

        This clears:
        - Current overlay data and dimensions
        - Sliders and buttons
        - Overlay information labels
        """
        self.automaticROI_overlay = False
        self.automaticROI_save_btn.setEnabled(False)
        self.overlay_data = None
        self.overlay_dims = None
        self.overlay_file_path = None
        self.automaticROI_sliders_group.setVisible(False)
        self.automaticROI_sliders_group.setEnabled(False)
        self.toggle_overlay(False)
        self.overlay_checkbox.setChecked(False)
        self.overlay_checkbox.setEnabled(False)
        self.overlay_info_label.setText(
            f"Overlay:\n" + QtCore.QCoreApplication.translate("NIfTIViewer", "Dimensions")
        )

    def pad_volume_to_shape(self, volume, target_shape, constant_value=0):
        """
        Pad a 3D volume to match a target shape.

        Args:
            volume (np.ndarray): Input 3D image (X, Y, Z).
            target_shape (tuple[int, int, int]): Desired output shape.
            constant_value (float): Padding value (default 0).

        Returns:
            np.ndarray: Padded volume centered within the new shape.
        """
        current_shape = volume.shape
        pads = []

        for cur, tgt in zip(current_shape, target_shape):
            diff = max(tgt - cur, 0)
            pad_before = diff // 2
            pad_after = diff - pad_before
            pads.append((pad_before, pad_after))

        return np.pad(volume, pads, mode="constant", constant_values=constant_value)

    def _translate_ui(self):
        """
        Translate all text elements of the user interface.

        This method supports dynamic language switching at runtime using Qt’s
        translation system (`QCoreApplication.translate`).
        """
        self.setWindowTitle(QtCore.QCoreApplication.translate("NIfTIViewer", "NIfTI Image Viewer"))
        self.status_bar.showMessage(
            QtCore.QCoreApplication.translate("NIfTIViewer", "Ready - Open a NIfTI file to begin"))

        self.coord_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Coordinates: (-, -, -)"))
        self.value_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Value: -"))
        self.slice_info_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Slice: -/-"))
        self.open_btn.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "📁 Open NIfTI File"))
        self.file_info_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "No file loaded"))

        plane_names = [
            QtCore.QCoreApplication.translate("NIfTIViewer", "Axial (Z)"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Coronal (Y)"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Sagittal (X)")
        ]
        for i, name in enumerate(plane_names):
            self.plane_labels[i].setText(name)

        self.time_checkbox.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Enable 4D Time Navigation"))
        self.time_point_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Time Point:"))
        self.display_options_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Display Options:"))

        colormap_names = ['gray', 'viridis', 'plasma', 'inferno', 'magma', 'hot', 'cool', 'bone']
        for i, name in enumerate(colormap_names):
            self.colormap_combo.setItemText(i, name)

        self.colormap_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Colormap:"))
        self.overlay_control_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Controls:"))
        self.overlay_btn.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Load NIfTI Overlay"))
        self.overlay_checkbox.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Show Overlay"))
        self.alpha_overlay_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Transparency:"))
        self.overlay_threshold_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "Overlay Threshold:"))
        self.overlay_info_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "No overlay loaded"))

        view_titles = [
            QtCore.QCoreApplication.translate("NIfTIViewer", "Axial"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Coronal"),
            QtCore.QCoreApplication.translate("NIfTIViewer", "Sagittal")
        ]
        for i, title in enumerate(view_titles):
            self.view_titles_labels[i].setText(title)

        self.fourth_title.setText(QtCore.QCoreApplication.translate("NIfTIViewer", self.fourth_title.text()))
        self.info_text.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "No image loaded"))

        if self.file_path:
            filename = os.path.basename(self.file_path)
            dims = self.dims
            if self.is_4d:
                info_text = (
                        QtCore.QCoreApplication.translate("NIfTIViewer", "File") + f": {filename}\n" +
                        QtCore.QCoreApplication.translate("NIfTIViewer",
                                                          "Dimensions") + f": {dims[0]}×{dims[1]}×{dims[2]}×{dims[3]}\n" +
                        QtCore.QCoreApplication.translate("NIfTIViewer", "4D Time Series")
                )
            else:
                info_text = (
                        QtCore.QCoreApplication.translate("NIfTIViewer", "File") + f": {filename}\n" +
                        QtCore.QCoreApplication.translate("NIfTIViewer",
                                                          "Dimensions") + f": {dims[0]}×{dims[1]}×{dims[2]}\n" +
                        QtCore.QCoreApplication.translate("NIfTIViewer", "3D Volume")
                )

            self.file_info_label.setText(info_text)
            self.info_text.setText(info_text)
        else:
            # Default text when no file is loaded
            self.file_info_label.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "No file loaded"))
            self.info_text.setText(QtCore.QCoreApplication.translate("NIfTIViewer", "No image loaded"))
