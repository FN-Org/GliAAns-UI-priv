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

try:
    from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                 QLabel, QSlider, QPushButton, QFileDialog, QSpinBox,
                                 QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                                 QStatusBar, QMessageBox, QProgressDialog, QGridLayout,
                                 QSplitter, QFrame, QSizePolicy, QCheckBox, QComboBox, QScrollArea, QDialog, QLineEdit,
                                 QListWidget, QDialogButtonBox, QListWidgetItem, QGroupBox)
    from PyQt6.QtCore import Qt, QPointF, QTimer, QThread, pyqtSignal, QSize, QCoreApplication, QRectF
    from PyQt6.QtGui import (QPixmap, QImage, QPainter, QColor, QPen, QPalette,
                             QBrush, QResizeEvent, QMouseEvent, QTransform)
    from matplotlib.figure import Figure

    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    log.error("PyQt6 not available. Install with: pip install PyQt6")
    sys.exit(1)
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.cm as cm


_t = QtCore.QCoreApplication.translate



# Numba
from numba import njit, prange


@njit(parallel=True)
def compute_mask_numba_mm(img, x0, y0, z0, radius_mm, voxel_sizes,
                          seed_intensity, diff,
                          x_min, x_max, y_min, y_max, z_min, z_max):
    mask = np.zeros(img.shape, dtype=np.uint8)
    r2 = radius_mm * radius_mm
    vx, vy, vz = voxel_sizes  # mm per asse

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
    h, w, c = rgba_image.shape
    for y in prange(h):
        for x in range(w):
            if overlay_mask[y, x]:
                for ch in range(3):
                    # solo RGB
                    if overlay_color[ch] != 0:
                        rgba_image[y, x, ch] = min(1.0, rgba_image[y, x, ch] + overlay_intensity[y, x] * overlay_color[ch])
                    else:
                        rgba_image[y, x, ch] *= (1.0 - overlay_intensity[y, x])
    return rgba_image


class NiftiViewer(QMainWindow):
    """Enhanced NIfTI viewer application with triplanar display and 4D support"""

    def __init__(self, context=None):
        super().__init__()

        self.threads = []
        self.context = context

        self.progress_dialog = None
        self.setWindowTitle(_t("NIfTIViewer","NIfTI Image Viewer"))
        self.setMinimumSize(1000, 700)
        self.resize(1400, 1000)

        # Data variables
        self.img_data = None
        self.affine = None
        self.dims = None
        self.is_4d = False
        self.current_slices = [0, 0, 0]  # axial, coronal, sagittal
        self.current_time = 0
        self.current_coordinates = [0, 0, 0]  # x, y, z in image space
        self.file_path = None
        self.stretch_factors = {}
        self.voxel_sizes = None

        # Overlay data
        self.overlay_data = None
        self.overlay_dims = None
        self.overlay_alpha = 0.7  # Default overlay transparency
        self.overlay_threshold = 0.1  # Only show overlay values above this threshold
        self.overlay_enabled = False
        self.overlay_file_path = None

        # Planes
        self.plane_labels = None

        # Status bar
        self.status_bar = None
        self.slice_info_label = None
        self.value_label = None
        self.coord_label = None

        # Color mapping
        self.colormap ='gray'
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

        # UI components
        self.views = []
        self.scenes = []
        self.pixmap_items = []
        self.slice_sliders = []
        self.slice_spins = []
        self.slice_labels = []
        self.coord_displays = []

        # Time things for 4D data
        self.time_slider = None
        self.time_spin = None
        self.time_checkbox = None
        self.time_plot_figure = None
        self.time_plot_canvas = None

        # Other
        self.file_info_label = None
        self.slice_navigation_label = None
        self.time_point_label = None
        self.colormap_combo = None
        self.overlay_threshold_slider = None
        self.display_options_label = None
        self.overlay_alpha_slider = None
        self.overlay_info_label = None

        # Automatic Drawing
        self.automaticROIbtn = None
        self.automaticROI = None
        self.automaticROI_radius_slider = None
        self.automaticROI_radius_label = None
        self.automaticROI_diff_label = None
        self.AutomaticROI_diff_slider = None
        self.automaticROI_sliders_group = None
        self.automaticROI_seed_coordinates = None
        self.automaticROI_save_btn = None
        self.automaticROI_overlay = None

        # Initialize UI
        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        """Initialize the user interface"""
        # Central widget with splitter for responsive design
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main horizontal splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        central_widget.layout = QHBoxLayout(central_widget)
        central_widget.layout.setContentsMargins(5, 5, 5, 5)
        central_widget.layout.addWidget(main_splitter)

        # Left control panel
        self.create_control_panel(main_splitter)

        # Right image display area
        self.create_image_display(main_splitter)

        # Set splitter proportions
        main_splitter.setSizes([300, 1100])
        main_splitter.setStretchFactor(0, 0)  # Control panel fixed width
        main_splitter.setStretchFactor(1, 1)  # Image area stretches

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Status bar (solo messaggio iniziale)
        self.coord_label = QLabel(_t("NIfTIViewer", "Coordinates: (-, -, -)"))
        self.value_label = QLabel(_t("NIfTIViewer", "Value: -"))
        self.slice_info_label = QLabel(_t("NIfTIViewer", "Slice: -/-"))

        # Aggiungi solo il messaggio iniziale
        self.status_bar.showMessage(_t("NIfTIViewer", "Ready - Open a NIfTI file to begin"))

    def create_control_panel(self, parent):
        """Create the left control panel"""
        # 🌟 Scroll area wrapper
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # 🌟 Control panel content widget
        control_content = QWidget()
        # Imposta la larghezza massima per prevenire scroll orizzontale
        control_content.setMaximumWidth(340)
        layout = QVBoxLayout(control_content)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)  # Margini ridotti

        # File operations
        file_group = QFrame()
        file_layout = QVBoxLayout(file_group)
        file_layout.setContentsMargins(5, 5, 5, 5)

        self.open_btn = QPushButton(_t("NIfTIViewer", "📁 Open NIfTI"))
        self.open_btn.setMinimumHeight(35)
        self.open_btn.setMaximumHeight(40)
        self.open_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Imposta tooltip per testo completo
        self.open_btn.setToolTip(_t("NIfTIViewer", "Open NIfTI File"))
        file_layout.addWidget(self.open_btn)

        self.file_info_label = QLabel(_t("NIfTIViewer", "No file loaded"))
        self.file_info_label.setWordWrap(True)
        self.file_info_label.setStyleSheet("font-size: 10px;")
        self.file_info_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        # Imposta larghezza massima per prevenire espansione
        self.file_info_label.setMaximumWidth(320)
        self.file_info_label.setMinimumHeight(40)
        file_layout.addWidget(self.file_info_label)

        layout.addWidget(file_group)

        # Slice controls
        slice_group = QFrame()
        slice_layout = QVBoxLayout(slice_group)
        slice_layout.setContentsMargins(5, 5, 5, 5)

        self.slice_navigation_label = QLabel(_t("NIfTIViewer", "Slice Navigation:"))
        self.slice_navigation_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.slice_navigation_label.setMaximumWidth(320)
        self.slice_navigation_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        slice_layout.addWidget(self.slice_navigation_label)

        plane_names = [_t("NIfTIViewer", "Axial (Z)"), _t("NIfTIViewer", "Coronal (Y)"),
                       _t("NIfTIViewer", "Sagittal (X)")]

        self.plane_labels = []

        for i, plane_name in enumerate(plane_names):
            # Plane label
            label = QLabel(plane_name)
            self.plane_labels.append(label)
            label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            slice_layout.addWidget(label)
            self.slice_labels.append(label)

            # Slider and spinbox container
            controls_widget = QWidget()
            controls_layout = QHBoxLayout(controls_widget)
            controls_layout.setContentsMargins(0, 0, 0, 0)
            controls_layout.setSpacing(5)

            # Slider
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(100)
            slider.setValue(50)
            slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            controls_layout.addWidget(slider, stretch=3)

            # Spinbox
            spinbox = QSpinBox()
            spinbox.setMinimum(0)
            spinbox.setMaximum(100)
            spinbox.setValue(50)
            spinbox.setMaximumWidth(60)
            spinbox.setMinimumWidth(50)
            spinbox.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            controls_layout.addWidget(spinbox, stretch=0)

            # Coordinate display
            coord_label = QLabel("(-, -)")
            coord_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 10px;")
            coord_label.setMinimumWidth(45)
            coord_label.setMaximumWidth(60)
            coord_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            controls_layout.addWidget(coord_label, stretch=0)

            controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            slice_layout.addWidget(controls_widget)

            self.slice_sliders.append(slider)
            self.slice_spins.append(spinbox)
            self.coord_displays.append(coord_label)

        layout.addWidget(slice_group)

        # 4D Time controls
        self.time_group = QFrame()
        time_layout = QVBoxLayout(self.time_group)
        time_layout.setContentsMargins(5, 5, 5, 5)

        self.time_checkbox = QCheckBox(_t("NIfTIViewer", "Enable 4D Time Navigation"))
        self.time_checkbox.setChecked(False)
        self.time_checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        time_layout.addWidget(self.time_checkbox)

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

        self.time_point_label = QLabel(_t("NIfTIViewer", "Time Point:"))
        self.time_point_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.time_point_label.setMaximumWidth(320)
        self.time_point_label.setStyleSheet("font-size: 11px;")
        time_layout.addWidget(self.time_point_label)

        time_controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        time_layout.addWidget(time_controls_widget)

        self.time_group.setVisible(False)
        layout.addWidget(self.time_group)

        # Display options
        display_group = QFrame()
        display_layout = QVBoxLayout(display_group)
        display_layout.setContentsMargins(5, 5, 5, 5)

        self.display_options_label = QLabel(_t("NIfTIViewer", "Display Options:"))
        self.display_options_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.display_options_label.setMaximumWidth(320)
        self.display_options_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        display_layout.addWidget(self.display_options_label)

        # Colormap selection - Layout compatto
        colormap_widget = QWidget()
        colormap_layout = QVBoxLayout(colormap_widget)  # Cambiato a verticale
        colormap_layout.setContentsMargins(0, 0, 0, 0)
        colormap_layout.setSpacing(3)

        self.colormap_label = QLabel(_t("NIfTIViewer", "Colormap:"))
        self.colormap_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.colormap_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        colormap_layout.addWidget(self.colormap_label)

        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(
            [_t("NIfTIViewer", 'gray'), _t("NIfTIViewer", 'viridis'), _t("NIfTIViewer", 'plasma'),
             _t("NIfTIViewer", 'inferno'), _t("NIfTIViewer", 'magma'), _t("NIfTIViewer", 'hot'),
             _t("NIfTIViewer", 'cool'), _t("NIfTIViewer", 'bone')])
        self.colormap_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.colormap_combo.setMaximumHeight(25)
        colormap_layout.addWidget(self.colormap_combo)

        colormap_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        display_layout.addWidget(colormap_widget)

        layout.addWidget(display_group)

        # Automatic ROI
        self.automaticROI_group = QFrame()
        automaticROI_layout = QVBoxLayout(self.automaticROI_group)
        automaticROI_layout.setContentsMargins(5, 5, 5, 5)

        automaticROIbtns_group = QFrame()
        automaticROIbtns_layout = QVBoxLayout(automaticROIbtns_group)  # Cambiato a verticale
        automaticROIbtns_layout.setContentsMargins(0, 0, 0, 0)
        automaticROIbtns_layout.setSpacing(3)

        self.automaticROIbtn = QPushButton(_t("NIfTIViewer", "Auto ROI"))
        self.automaticROIbtn.setEnabled(False)
        self.automaticROIbtn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.automaticROIbtn.setMaximumHeight(30)
        self.automaticROIbtn.setToolTip(_t("NIfTIViewer", "Automatic ROI Drawing"))
        automaticROIbtns_layout.addWidget(self.automaticROIbtn)

        self.automaticROI_save_btn = QPushButton(_t("NIfTIViewer", "Save ROI"))
        self.automaticROI_save_btn.setEnabled(False)
        self.automaticROI_save_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.automaticROI_save_btn.setMaximumHeight(30)
        self.automaticROI_save_btn.setToolTip(_t("NIfTIViewer", "Save ROI Drawing"))
        automaticROIbtns_layout.addWidget(self.automaticROI_save_btn)

        automaticROIbtns_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        automaticROI_layout.addWidget(automaticROIbtns_group)

        self.automaticROI_sliders_group = QFrame()
        automaticROI_sliders_layout = QVBoxLayout(self.automaticROI_sliders_group)
        automaticROI_sliders_layout.setContentsMargins(0, 0, 0, 0)

        self.automaticROI_radius_label = QLabel(_t("NIfTIViewer", "Radius:"))
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

        self.automaticROI_diff_label = QLabel(_t("NIfTIViewer", "Difference:"))
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

        layout.addWidget(self.automaticROI_group)

        # Overlay controls
        overlay_group = QFrame()
        overlay_layout = QVBoxLayout(overlay_group)
        overlay_layout.setContentsMargins(5, 5, 5, 5)

        self.overlay_control_label = QLabel(_t("NIfTIViewer", "Overlay Controls:"))
        self.overlay_control_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.overlay_control_label.setMaximumWidth(320)
        self.overlay_control_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        overlay_layout.addWidget(self.overlay_control_label)

        # Overlay file button
        self.overlay_btn = QPushButton(_t("NIfTIViewer", "Load Overlay"))
        self.overlay_btn.setMinimumHeight(30)
        self.overlay_btn.setMaximumHeight(35)
        self.overlay_btn.setEnabled(False)  # Enable only when base image is loaded
        self.overlay_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.overlay_btn.setToolTip(_t("NIfTIViewer", "Load NIfTI Overlay"))
        overlay_layout.addWidget(self.overlay_btn)

        # Overlay enable/disable checkbox
        self.overlay_checkbox = QCheckBox(_t("NIfTIViewer", "Show Overlay"))
        self.overlay_checkbox.setEnabled(False)
        self.overlay_checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        overlay_layout.addWidget(self.overlay_checkbox)

        # Overlay alpha slider
        self.alpha_overlay_label = QLabel(_t("NIfTIViewer", "Overlay Transparency:"))
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
        self.overlay_threshold_label = QLabel(_t("NIfTIViewer", "Overlay Threshold:"))
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
        self.overlay_info_label = QLabel(_t("NIfTIViewer", "No overlay loaded"))
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

        # 🔁 Imposta il contenuto nel QScrollArea
        scroll_area.setWidget(control_content)

        # 🔁 Imposta dimensioni per eliminare scroll orizzontale
        scroll_area.setMinimumWidth(240)
        scroll_area.setMaximumWidth(340)

        # ✅ Connessioni signal/slot per sincronizzare slider e spinbox

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

        # ✅ Aggiungi lo scroll area al parent
        parent.addWidget(scroll_area)

    # Funzione helper per formattare il testo senza causare scroll orizzontale
    def format_info_text(self, text, max_line_length=35):
        """
        Formatta il testo per prevenire scroll orizzontale nel control panel

        Args:
            text (str): Testo da formattare
            max_line_length (int): Lunghezza massima per riga

        Returns:
            str: Testo formattato con a-capo appropriati
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
        """Create the main image display area with three anatomical views"""
        display_widget = QWidget()
        display_layout = QGridLayout(display_widget)
        display_layout.setSpacing(5)

        # Create three views in a 2x2 grid layout
        view_positions = [(0, 0), (0, 1), (1, 0)]
        view_titles = [_t("NIfTIViewer","Axial"),_t("NIfTIViewer","Coronal"),_t("NIfTIViewer","Sagittal")]

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

        self.fourth_title = QLabel(_t("NIfTIViewer","Image Information"))
        self.fourth_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fourth_title.setStyleSheet("font-weight: bold; padding: 4px;")
        fourth_layout.addWidget(self.fourth_title)

        # Container for switching between info and plot
        self.fourth_content = QWidget()
        self.fourth_content_layout = QVBoxLayout(self.fourth_content)

        # Info text widget
        self.info_text = QLabel(_t("NIfTIViewer","No image loaded"))
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
        """Setup crosshairs for all views"""
        for view in self.views:
            view.setup_crosshairs()

    def setup_connections(self):
        """Setup signal-slot connections"""
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
        if is_overlay:
            result = NiftiFileDialog.get_files(
                self,
                self.context["workspace_path"],
                allow_multiple=False,
                has_existing_func=False,
                label=None,
                forced_filters={"search": "derivatives"}
            )
        else:
            result = NiftiFileDialog.get_files(
                self,
                self.context["workspace_path"],
                allow_multiple=False,
                has_existing_func=False,
                label=None
            )
        if result:
            self.open_file(result[0], is_overlay=is_overlay)



    def open_file(self, file_path=None, is_overlay = False):
        """Open a NIfTI file with progress dialog
        Args:
            is_overlay: (bool, optional): true if a overlay file is opening
            file_path (str, optional): Path to the file to open. If None, shows file dialog.
        """
        if is_overlay and self.img_data is None:
            QMessageBox.warning(
                self,
                _t("NIfTIViewer", "Warning"),
                _t("NIfTIViewer", "Please load a base image first!")
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
                _t("NIfTIViewer", "Loading NIfTI file..."),
                _t("NIfTIViewer", "Cancel"), 0, 100, self
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
        """Handle successful file loading"""
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
                _t("NIfTIViewer", "Dimensions") +
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
                _t("NIfTIViewer", "Overlay loaded") + f":{filename}"
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
                info_text = _t("NIfTIViewer", "File") + f":{filename}\n" + _t("NIfTIViewer",
                                                                              "Dimensions") + f":{dims[0]}×{dims[1]}×{dims[2]}×{dims[3]}\n" + _t(
                    "NIfTIViewer", "4D Time Series")
                self.time_group.setVisible(True)
                self.time_checkbox.setChecked(True)
                self.time_checkbox.setEnabled(True)
                self.setup_time_series_plot()
            else:
                info_text = _t("NIfTIViewer", "File") + f":{filename}\n" + _t("NIfTIViewer",
                                                                              "Dimensions") + f":{dims[0]}×{dims[1]}×{dims[2]}\n" + _t(
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
        """Handle file loading errors"""
        self.progress_dialog.close()
        QMessageBox.critical(self, _t("NIfTIViewer","Error Loading File"), _t("NIfTIViewer","Failed to load NIfTI file") + f":\n{error_message}")
        log.critical(f"Error loading NIftI file: {error_message}")
        thread_to_cancel = self.sender()
        if thread_to_cancel in self.threads:
            self.threads.remove(thread_to_cancel)

    def on_load_canceled(self, canceled=True):
        self.threads[-1].terminate()
        self.threads.pop()


    def initialize_display(self):
        """Initialize display parameters and update all views"""
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
        """Toggle overlay display on/off - VERSIONE MIGLIORATA"""
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
        """Update overlay transparency - CON CONTROLLI MIGLIORATI"""
        self.overlay_alpha = value / 100.0
        if (self.overlay_enabled and
                hasattr(self, 'overlay_data') and
                self.overlay_data is not None):
            self.update_all_displays()

    def update_overlay_threshold(self, value):
        """Update overlay threshold - CON CONTROLLI MIGLIORATI"""
        self.overlay_threshold = value / 100.0
        if (self.overlay_enabled and
                hasattr(self, 'overlay_data') and
                self.overlay_data is not None):
            self.update_all_displays()

    def update_overlay_settings(self):
        """Update overlay settings from UI controls - VERSIONE MIGLIORATA"""
        if hasattr(self, 'overlay_alpha_slider') and hasattr(self, 'overlay_threshold_slider'):
            self.overlay_alpha = self.overlay_alpha_slider.value() / 100.0
            self.overlay_threshold = self.overlay_threshold_slider.value() / 100.0

            # Aggiorna visualizzazione solo se overlay è abilitato e dati esistono
            if self.overlay_enabled and hasattr(self, 'overlay_data') and self.overlay_data is not None:
                self.update_all_displays()

    def slice_changed(self, plane_idx, value):
        """Handle slice navigation"""
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
        """Handle time point changes for 4D data"""
        self.current_time = value
        self.time_slider.setValue(value)
        self.time_spin.setValue(value)
        self.update_all_displays()

    def toggle_time_controls(self, enabled):
        """Enable/disable time controls"""
        value = enabled and self.is_4d
        self.time_slider.setVisible(value)
        self.time_slider.setEnabled(value)
        self.time_spin.setVisible(value)
        self.time_spin.setEnabled(value)
        self.time_point_label.setVisible(value)

    def colormap_changed(self, colormap_name):
        """Handle colormap changes"""
        self.colormap = colormap_name
        self.update_all_displays()

    def handle_click_coordinates(self, view_idx, x, y):
        """Handle mouse clicks to update coordinates and cross-view synchronization"""
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
        """Convert screen coordinates to 3D image coordinates"""
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
        """Update coordinate display from mouse movement"""
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

            self.coord_label.setText(_t("NIfTIViewer","Coordinates")+f": ({img_coords[0]}, {img_coords[1]}, {img_coords[2]})")
            self.value_label.setText(_t("NIfTIViewer","Value")+f": {value:.2f}")

        except (IndexError, ValueError):
            pass

    def update_coordinate_displays(self):
        """Update coordinate displays next to sliders"""
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
        self.coord_label.setText(_t("NIfTIViewer","Coordinates")+f": ({coords[0]}, {coords[1]}, {coords[2]})")

        try:
            if self.is_4d:
                value = self.img_data[coords[0], coords[1], coords[2], self.current_time]
            else:
                value = self.img_data[coords[0], coords[1], coords[2]]
            self.value_label.setText(_t("NIfTIViewer","Value")+ f": {value:.2f}")
        except (IndexError, ValueError):
            self.value_label.setText(_t("NIfTIViewer","Value")+f": -")

    def update_cross_view_lines(self):
        """Update crosshair lines across all views to show current position"""
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
        """Update a specific plane display with matplotlib-style rendering in mm scale"""
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
            normalized_data = self.normalize_data_matplotlib_style(slice_data)
            rgba_image = self.apply_colormap_matplotlib(normalized_data, self.colormap)
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

    def normalize_data_matplotlib_style(self, data):
        """Normalize data using matplotlib's approach for clear image display"""
        if data.size == 0:
            return data

        # Remove NaN and infinite values
        valid_data = data[np.isfinite(data)]
        if valid_data.size == 0:
            return np.zeros_like(data)

        # Use robust percentile normalization like matplotlib
        vmin, vmax = np.percentile(valid_data, [2, 98])

        # Avoid division by zero
        if vmax <= vmin:
            vmax = vmin + 1

        # Normalize to [0, 1]
        normalized = np.clip((data - vmin) / (vmax - vmin), 0, 1)

        return normalized

    def setup_time_series_plot(self):
        """Setup time series plot for 4D data"""
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
        self.fourth_title.setText(_t("NIfTIViewer","Tracer Concentration Curve"))
        self.fourth_content_layout.addWidget(self.time_plot_canvas)

    def hide_time_series_plot(self):
        """Hide time series plot for 3D data"""
        if self.time_plot_canvas is not None:
            # Rimuovi dal layout per evitare che rimanga "sporco"
            self.fourth_content_layout.removeWidget(self.time_plot_canvas)
            self.time_plot_canvas.setParent(None)
            self.time_plot_canvas.deleteLater()
            self.time_plot_canvas = None
            self.time_plot_axes = None
            self.time_plot_figure = None

        self.fourth_title.setText(_t("NIfTIViewer", "Image Information"))
        self.info_text.show()

    def update_time_series_plot(self):
        """Update the time series plot with current voxel data"""

        if not self.is_4d or self.time_plot_canvas is None or self.img_data is None:
            return

        try:
            coords = self.current_coordinates
            bool_in_mask = False
            if self.overlay_data is not None and self.overlay_enabled:
                # Normalizza overlay_data in modo coerente
                overlay_norm = self.normalize_data_matplotlib_style(self.overlay_data)

                # Calcola mask thresholded
                overlay_max = np.max(overlay_norm) if np.max(overlay_norm) > 0 else 1
                threshold_value = self.overlay_threshold * overlay_max
                threshold_mask = overlay_norm > threshold_value

                if threshold_mask[coords[0], coords[1], coords[2]]:
                    bool_in_mask = True
                    # Usa il mask thresholded per la ROI
                    roi_voxels = self.img_data[threshold_mask, :]  # shape: (N_voxels, T)

                    time_series = roi_voxels.mean(axis=0)
                    std_series = roi_voxels.std(axis=0)
                else:
                    # Voxel singolo fuori soglia, prendi la serie singola
                    time_series = self.img_data[coords[0], coords[1], coords[2], :]
                    std_series = None
            else:
                # Caso overlay non abilitato o non disponibile
                time_series = self.img_data[coords[0], coords[1], coords[2], :]
                std_series = None

            time_points = np.arange(self.dims[3])

            # Clear and plot
            self.time_plot_axes.clear()
            self.time_plot_axes.set_facecolor('black')

            # Plot time series
            self.time_plot_axes.plot(time_points, time_series, 'c-', linewidth=2, label=_t("NIfTIViewer",'Concentration'))
            if std_series is not None:
                self.time_plot_axes.fill_between(time_points, time_series - std_series, time_series + std_series, alpha=0.2, color='c')

            # Add current time indicator
            self.time_indicator_line = self.time_plot_axes.axvline(
                x=self.current_time, color='yellow', linewidth=2, alpha=0.8, label=_t("NIfTIViewer",'Current Time')
            )

            # Styling
            self.time_plot_axes.set_xlabel(_t("NIfTIViewer","Time Point"), color='white')
            self.time_plot_axes.set_ylabel(_t("NIfTIViewer","Signal Intensity"), color='white')
            if bool_in_mask:
                self.time_plot_axes.set_title(f'Mean in overlay mask', color='white')
            else:
                self.time_plot_axes.set_title(f'Voxel ({coords[0]}, {coords[1]}, {coords[2]})', color='white')
            self.time_plot_axes.tick_params(colors='white')
            self.time_plot_axes.legend()

            # Grid
            self.time_plot_axes.grid(True, alpha=0.3, color='gray')

            self.time_plot_canvas.draw()

        except Exception as e:
            log.error(f"Error updating time series plot: {e}")

    def apply_colormap_matplotlib(self, data, colormap_name):
        """Apply colormap using matplotlib and return QImage"""
        try:
            # Get matplotlib colormap
            cmap = cm.get_cmap(colormap_name)

            # Apply colormap
            colored_data = cmap(data)

            return colored_data

        except Exception as e:
            log.error(f"Error applying colormap: {e}")
            return None

    def update_all_displays(self):
        """Update all plane displays"""
        for i in range(3):
            self.update_display(i)

        # Update time series plot if available
        if self.is_4d:
            self.update_time_series_plot()

        # Update slice info in status bar
        if self.img_data is not None:
            spatial_dims = self.dims[:3] if self.is_4d else self.dims
            slice_info = _t("NIfTIViewer","Slices")+f": {self.current_slices[0] + 1}/{spatial_dims[2]} | {self.current_slices[1] + 1}/{spatial_dims[1]} | {self.current_slices[2] + 1}/{spatial_dims[0]}"
            if self.is_4d:
                slice_info += f" | "+_t("NIfTIViewer","Time")+f": {self.current_time + 1}/{self.dims[3]}"
            self.slice_info_label.setText(slice_info)

    def create_overlay_composite(self, rgba_image, overlay_slice, colormap):
        """Create a composite image with colormap base and red overlay."""
        try:

            rgba_image_float = rgba_image.astype(np.float64)  # (H,W,4)

            if overlay_slice.size > 0:
                overlay_normalized = self.normalize_data_matplotlib_style(overlay_slice)

                overlay_max = np.max(overlay_normalized) if np.max(overlay_normalized) > 0 else 1
                threshold_value = self.overlay_threshold * overlay_max
                overlay_mask = overlay_normalized > threshold_value

                if np.any(overlay_mask):
                    overlay_intensity = overlay_normalized * self.overlay_alpha

                    overlay_color = self.overlay_colors.get(self.colormap,np.array([0.0, 1.0, 0.0]))
                    rgba_image_float = apply_overlay_numba(rgba_image, overlay_mask, overlay_intensity, overlay_color)

            rgba_image_overlay = np.clip(rgba_image_float, 0, 1)

            return rgba_image_overlay

        except Exception as e:
            log.error(f"Error creating overlay composite: {e}")
            # Fallback to regular colormap
            return rgba_image

    def resizeEvent(self, event: QResizeEvent):
        """Handle window resize to maintain aspect ratios"""

        super().resizeEvent(event)
        # Refit all views after a short delay
        QTimer.singleShot(100, self.fit_all_views)

    def fit_all_views(self):
        """Fit all views to their scenes while maintaining aspect ratio"""

        for view in self.views:
            if view.scene():
                view.fitInView(view.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def update_automaticROI(self):
        if self.overlay_enabled and self.automaticROI_overlay:
            self.automaticROI_drawing()
            self.update_all_displays()

    def automaticROI_clicked(self):

        self.automaticROI_seed_coordinates = self.current_coordinates

        # Maximum radius in mm
        # Calcola le dimensioni reali (in mm) dell'immagine lungo X, Y, Z
        dims_voxel = self.dims[:3]  # numero di voxel lungo X, Y, Z
        dims_mm = dims_voxel * self.voxel_sizes  # dimensioni reali in mm
        # Trova il lato più corto in mm e lo dimezza per avere il raggio massimo
        max_radius_mm = np.min(dims_mm) / 2
        # Imposta il massimo dello slider (in mm)
        self.automaticROI_radius_slider.setMaximum(int(max_radius_mm))

        self.automaticROI_radius_slider.setValue(
            32 if not self.automaticROI_overlay else self.automaticROI_radius_slider.value()
        )

        max_diff = int((self.img_data.max() - self.img_data.min()) / 2)
        self.automaticROI_diff_slider.setMaximum(max_diff)
        self.automaticROI_diff_slider.setValue(
            int(max_diff * (16 / 100)) if not self.automaticROI_overlay else self.automaticROI_diff_slider.value()
        )
        self.automaticROI_sliders_group.setVisible(True)
        self.automaticROI_sliders_group.setEnabled(True)
        self.automaticROIbtn.setText("Reset Origin")
        self.automaticROI_overlay = True
        self.automaticROI_save_btn.setEnabled(True)

        self.automaticROI_drawing()

        self.overlay_info_label.setText(
            f"Overlay:"+ _t("NIfTIViewer", "Automatic ROI Drawing"))

        self.toggle_overlay(True)
        self.overlay_checkbox.setChecked(True)
        self.overlay_checkbox.setEnabled(True)

        self.update_all_displays()

    def automaticROI_drawing(self):
        radius_mm = self.automaticROI_radius_slider.value()  # già in mm
        difference = self.automaticROI_diff_slider.value()
        x0, y0, z0 = self.automaticROI_seed_coordinates

        img_data = self.img_data[..., self.current_time] if self.is_4d else self.img_data

        # Intensità al punto di origine
        seed_intensity = img_data[x0, y0, z0]

        # Estensione in voxel per asse, convertendo il raggio mm
        rx_vox = int(np.ceil(radius_mm / self.voxel_sizes[0]))
        ry_vox = int(np.ceil(radius_mm / self.voxel_sizes[1]))
        rz_vox = int(np.ceil(radius_mm / self.voxel_sizes[2]))

        x_min, x_max = max(0, x0 - rx_vox), min(img_data.shape[0], x0 + rx_vox + 1)
        y_min, y_max = max(0, y0 - ry_vox), min(img_data.shape[1], y0 + ry_vox + 1)
        z_min, z_max = max(0, z0 - rz_vox), min(img_data.shape[2], z0 + rz_vox + 1)

        # Calcolo parallelo con numba
        mask = compute_mask_numba_mm(img_data, x0, y0, z0,
                                     radius_mm, self.voxel_sizes,
                                     seed_intensity, difference,
                                     x_min, x_max, y_min, y_max, z_min, z_max)

        self.overlay_data = mask

    def automaticROI_save(self):
        if not self.automaticROI_overlay or self.overlay_data is None:
            return

        radius = self.automaticROI_radius_slider.value()
        difference = self.automaticROI_diff_slider.value()

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

        relative_path = os.path.relpath(original_path, workspace_path)
        parts = relative_path.split(os.sep)
        try:
            subject = next(part for part in parts if part.startswith("sub-"))
        except StopIteration:
            QMessageBox.critical(self, "Error", "Could not determine subject from path.")
            log.error("Could not determine subject from path.")
            return

        filename = os.path.basename(original_path)
        base_name = filename.replace(".nii.gz", "").replace(".nii", "")
        new_base = f"{base_name}_r{radius:02d}_d{difference:02d}_mask"
        new_name = f"{new_base}.nii.gz"

        save_dir = os.path.join(workspace_path, "derivatives", "manual_masks", subject, "anat")
        full_save_path = os.path.join(save_dir, new_name)
        json_save_path = os.path.join(save_dir, f"{new_base}.json")

        # Mostra dialog di conferma
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
            return  # Annullato

        os.makedirs(save_dir, exist_ok=True)
        self.threads.append(SaveNiftiThread(self.overlay_data, self.affine,full_save_path,json_save_path,relative_path,radius,difference))
        self.threads[-1].success.connect(self._on_automaticROI_saved)
        self.threads[-1].error.connect(self._on_automaticROI_error)
        self.threads[-1].start()


    def _on_automaticROI_saved(self,path,json_path):
        QMessageBox.information(self,
                                "ROI Saved",
                                f"ROI saved in:{path} and metadata saved in:{json_path} successfully!")
        log.info(f"ROI saved in:{path} and metadata saved in:{json_path} successfully!")
    def _on_automaticROI_error(self,error):
        QMessageBox.critical(
            self,
            "Error when saving ROI",
            f"Error when saving: {error}"
        )
        log.critical(f"Error when saving ROI: {error}")
    def closeEvent(self, event):
        """Clean up on application exit"""
        # Clean up any running threads
        if hasattr(self, 'threads'):
            for t in self.threads:
                if t.isRunning():
                    t.terminate()
                    t.wait()
                t.deleteLater()
            self.threads.clear()

        # Clear image data to free memory
        self.img_data = None
        self.overlay_data = None


        gc.collect()

        event.accept()

    def reset_overlay(self):
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
            f"Overlay:\n" +
            _t("NIfTIViewer", "Dimensions")
        )


    def pad_volume_to_shape(self,volume, target_shape, constant_value=0):
        """Pad a 3D volume (numpy array) to match target_shape."""
        current_shape = volume.shape
        pads = []

        for cur, tgt in zip(current_shape, target_shape):
            diff = max(tgt - cur, 0)
            pad_before = diff // 2
            pad_after = diff - pad_before
            pads.append((pad_before, pad_after))

        return np.pad(volume, pads, mode="constant", constant_values=constant_value)

    def _retranslate_ui(self):
        self.setWindowTitle(_t("NIfTIViewer", "NIfTI Image Viewer"))

        self.status_bar.showMessage(_t("NIfTIViewer", "Ready - Open a NIfTI file to begin"))

        self.coord_label.setText(_t("NIfTIViewer", "Coordinates: (-, -, -)"))
        self.value_label.setText(_t("NIfTIViewer", "Value: -"))
        self.slice_info_label.setText(_t("NIfTIViewer", "Slice: -/-"))

        self.open_btn.setText(_t("NIfTIViewer", "📁 Open NIfTI File"))

        self.file_info_label.setText(_t("NIfTIViewer","No file loaded"))

        plane_names = [_t("NIfTIViewer", "Axial (Z)"), _t("NIfTIViewer", "Coronal (Y)"),
                       _t("NIfTIViewer", "Sagittal (X)")]
        for i,name in enumerate(plane_names):
            self.plane_labels[i].setText(_t("NIfTIViewer", name))

        self.time_checkbox.setText(_t("NIfTIViewer", "Enable 4D Time Navigation"))

        self.time_point_label.setText(_t("NIfTIViewer", "Time Point:"))

        self.display_options_label.setText(_t("NIfTIViewer", "Display Options:"))

        colormap_names = ['gray', 'viridis','plasma', 'inferno','magma','hot','cool','bone']

        for i,name in enumerate(colormap_names):
            self.colormap_combo.setItemText(i, name)

        self.colormap_label.setText(_t("NIfTIViewer", "Colormap:"))
        self.overlay_control_label.setText(_t("NIfTIViewer", "Overlay Controls:"))

        self.overlay_btn.setText(_t("NIfTIViewer", "Load NIfTI Overlay"))

        self.overlay_checkbox.setText(_t("NIfTIViewer", "Show Overlay"))

        self.alpha_overlay_label.setText(_t("NIfTIViewer", "Overlay Transparency:"))

        self.overlay_threshold_label.setText(_t("NIfTIViewer", "Overlay Threshold:"))

        self.overlay_info_label.setTetx(_t("NIfTIViewer", "No overlay loaded"))

        view_titles = [_t("NIfTIViewer", "Axial"), _t("NIfTIViewer", "Coronal"), _t("NIfTIViewer", "Sagittal")]
        for i,title in enumerate(view_titles):
            self.view_titles_labels[i].setText(title)

        self.fourth_title.setText(_t("NIfTIViewer", self.fourth_title.text()))
        self.info_text.setText(_t("NIfTIViewer", "No image loaded"))

        filename = os.path.basename(self.file_path)
        dims = self.dims
        if self.is_4d:
            info_text = _t("NIfTIViewer","File")+ f":{filename}\n"+_t("NIfTIViewer","Dimensions") + f":{dims[0]}×{dims[1]}×{dims[2]}×{dims[3]}\n" + _t("NIfTIViewer","4D Time Series")

        else:
            info_text = _t("NIfTIViewer","File")+ f":{filename}\n" + _t("NIfTIViewer","Dimensions") + f":{dims[0]}×{dims[1]}×{dims[2]}\n"+ _t("NIfTIViewer","3D Volume")

        self.file_info_label.setText(info_text)
        self.info_text.setText(info_text)

        #if self.overlay_data is not None