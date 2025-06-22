"""
Enhanced NIfTI Medical Image Viewer with matplotlib-style rendering,
cross-view synchronization, and 4D support
"""

import sys
import os
import gc
import numpy as np
import nibabel as nib
from nibabel.orientations import io_orientation, axcodes2ornt, ornt_transform, apply_orientation

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QSlider, QPushButton, QFileDialog, QSpinBox,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                             QStatusBar, QMessageBox, QProgressDialog, QGridLayout,
                             QSplitter, QFrame, QSizePolicy, QCheckBox, QComboBox, QApplication)
from PyQt6.QtCore import Qt, QPointF, QTimer, QThread, pyqtSignal, QSize
from PyQt6.QtGui import (QPixmap, QImage, QPainter, QColor, QPen, QPalette,
                         QBrush, QResizeEvent, QMouseEvent)
import matplotlib

matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.cm as cm


class ImageLoadThread(QThread):
    """Thread for loading large NIfTI files without blocking the UI"""
    finished = pyqtSignal(object, object, object, bool)  # img_data, dims, affine, is_4d
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit(10)

            # Load NIfTI file with memory mapping for efficiency
            img = nib.load(self.file_path, mmap='c')
            self.progress.emit(30)

            if not isinstance(img, (nib.Nifti1Image, nib.Nifti2Image)):
                raise ValueError("Not a valid NIfTI file")

            # Get dimensions and affine
            dims = img.header.get_data_shape()
            affine = img.affine
            is_4d = len(dims) == 4
            self.progress.emit(50)

            # Load full data
            img_data = np.asarray(img.dataobj)

            self.progress.emit(80)

            # Ensure proper orientation (RAS+)
            if not is_4d:
                img_data = self._reorient_to_ras(img_data, affine)
            else:
                # For 4D data, reorient each volume
                reoriented_data = np.zeros_like(img_data)
                for t in range(dims[3]):
                    reoriented_data[..., t] = self._reorient_to_ras(img_data[..., t], affine)
                img_data = reoriented_data

            self.progress.emit(100)

            self.finished.emit(img_data, dims, affine, is_4d)

        except Exception as e:
            self.error.emit(str(e))

    def _reorient_to_ras(self, data, affine):
        """Reorient image data to RAS+ orientation"""
        try:
            # Get current orientation
            ornt = io_orientation(affine)
            # Convert to RAS+
            ras_ornt = axcodes2ornt("RAS")
            # Calculate transformation
            transform = ornt_transform(ornt, ras_ornt)
            # Apply transformation
            data = apply_orientation(data, transform)
            return data
        except Exception:
            # If reorientation fails, return original data
            return data


class CrosshairGraphicsView(QGraphicsView):
    """Custom QGraphicsView with crosshair support and coordinate capture"""

    coordinate_changed = pyqtSignal(int, int, int)  # view_idx, x, y
    slice_changed = pyqtSignal(int, int)  # view_idx, new_slice

    def __init__(self, view_idx, parent=None):
        super().__init__(parent)
        self.view_idx = view_idx
        self.parent_viewer = parent
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        # Crosshair lines
        self.crosshair_h = None
        self.crosshair_v = None
        self.crosshair_visible = False

        # Set rendering hints for smooth display
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )

    def setup_crosshairs(self):
        """Initialize crosshair lines"""
        if self.scene():
            pen = QPen(QColor(255, 255, 0, 180), 1)
            self.crosshair_h = self.scene().addLine(0, 0, 0, 0, pen)
            self.crosshair_v = self.scene().addLine(0, 0, 0, 0, pen)
            self.crosshair_h.setVisible(False)
            self.crosshair_v.setVisible(False)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse movement for coordinate display and crosshairs"""
        if self.scene() and self.parent_viewer and self.parent_viewer.img_data is not None:
            pos = self.mapToScene(event.pos())
            x, y = int(pos.x()), int(pos.y())

            # Check bounds
            scene_rect = self.scene().sceneRect()
            if (0 <= x < scene_rect.width() and 0 <= y < scene_rect.height()):
                # Update crosshairs
                self.update_crosshairs(x, y)
                # Emit coordinate change
                self.coordinate_changed.emit(self.view_idx, x, y)

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse clicks for coordinate selection and slice navigation"""
        if (event.button() == Qt.MouseButton.LeftButton and
                self.scene() and self.parent_viewer and
                self.parent_viewer.img_data is not None):

            pos = self.mapToScene(event.pos())
            x, y = int(pos.x()), int(pos.y())

            # Check bounds
            scene_rect = self.scene().sceneRect()
            if (0 <= x < scene_rect.width() and 0 <= y < scene_rect.height()):
                # Update clicked coordinates and trigger cross-view updates
                self.parent_viewer.handle_click_coordinates(self.view_idx, x, y)

        super().mousePressEvent(event)

    def update_crosshairs(self, x, y):
        """Update crosshair position"""
        if self.crosshair_h and self.crosshair_v and self.scene():
            scene_rect = self.scene().sceneRect()

            # Horizontal line
            self.crosshair_h.setLine(0, y, scene_rect.width(), y)
            # Vertical line
            self.crosshair_v.setLine(x, 0, x, scene_rect.height())

            if not self.crosshair_visible:
                self.crosshair_h.setVisible(True)
                self.crosshair_v.setVisible(True)
                self.crosshair_visible = True

    def set_crosshair_position(self, x, y):
        """Set crosshair position from external call"""
        if self.crosshair_h and self.crosshair_v and self.scene():
            scene_rect = self.scene().sceneRect()
            if (0 <= x < scene_rect.width() and 0 <= y < scene_rect.height()):
                self.crosshair_h.setLine(0, y, scene_rect.width(), y)
                self.crosshair_v.setLine(x, 0, x, scene_rect.height())
                self.crosshair_h.setVisible(True)
                self.crosshair_v.setVisible(True)
                self.crosshair_visible = True

    def leaveEvent(self, event):
        """Hide crosshairs when mouse leaves the view"""
        if self.crosshair_h and self.crosshair_v:
            self.crosshair_h.setVisible(False)
            self.crosshair_v.setVisible(False)
            self.crosshair_visible = False
        super().leaveEvent(event)


class NiftiViewer(QWidget):
    """Enhanced NIfTI viewer application with triplanar display and 4D support"""

    def __init__(self):
        super().__init__()
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

        # Color mapping
        self.colormap = 'gray'

        # UI components
        self.views = []
        self.scenes = []
        self.pixmap_items = []
        self.slice_sliders = []
        self.slice_spins = []
        self.slice_labels = []
        self.coord_displays = []

        # Time slider for 4D data
        self.time_slider = None
        self.time_spin = None
        self.time_checkbox = None

        # Initialize UI
        self.init_ui()
        self.setup_connections()



    def init_ui(self):
        """Initialize the user interface"""
        # Central widget with splitter for responsive design

        # Main horizontal splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.addWidget(main_splitter)

        # Left control panel
        self.create_control_panel(main_splitter)

        # Right image display area
        self.create_image_display(main_splitter)

        # Set splitter proportions
        main_splitter.setSizes([300, 1100])
        main_splitter.setStretchFactor(0, 0)  # Control panel fixed width
        main_splitter.setStretchFactor(1, 1)  # Image area stretches



    def create_control_panel(self, parent):
        """Create the left control panel"""
        control_widget = QFrame()
        control_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        control_widget.setMaximumWidth(350)
        control_widget.setMinimumWidth(250)

        layout = QVBoxLayout(control_widget)
        layout.setSpacing(10)

        # File operations
        file_group = QFrame()
        file_layout = QVBoxLayout(file_group)


        self.file_info_label = QLabel("No file loaded")
        self.file_info_label.setWordWrap(True)
        self.file_info_label.setStyleSheet("color: #888888; font-size: 11px;")
        file_layout.addWidget(self.file_info_label)

        layout.addWidget(file_group)

        # Slice controls
        slice_group = QFrame()
        slice_layout = QVBoxLayout(slice_group)
        slice_layout.addWidget(QLabel("Slice Navigation:"))

        self.plane_names = ["Axial (Z)", "Coronal (Y)", "Sagittal (X)"]

        for i, plane_name in enumerate(self.plane_names):
            # Plane label
            label = QLabel(plane_name)
            label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            slice_layout.addWidget(label)
            self.slice_labels.append(label)

            # Slider and spinbox container
            controls_widget = QWidget()
            controls_layout = QHBoxLayout(controls_widget)
            controls_layout.setContentsMargins(0, 0, 0, 0)

            # Slider
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(100)
            slider.setValue(50)
            controls_layout.addWidget(slider, stretch=2)

            # Spinbox
            spinbox = QSpinBox()
            spinbox.setMinimum(0)
            spinbox.setMaximum(100)
            spinbox.setValue(50)
            spinbox.setMaximumWidth(60)
            controls_layout.addWidget(spinbox, stretch=1)

            # Coordinate display
            coord_label = QLabel("(-, -)")
            coord_label.setStyleSheet("color: #00ff00; font-weight: bold; font-size: 10px;")
            coord_label.setMinimumWidth(50)
            controls_layout.addWidget(coord_label)

            slice_layout.addWidget(controls_widget)

            self.slice_sliders.append(slider)
            self.slice_spins.append(spinbox)
            self.coord_displays.append(coord_label)

        layout.addWidget(slice_group)

        status_box = QFrame()
        status_layout = QVBoxLayout(status_box)
        self.coord_label = QLabel("Coordinates: (-, -, -)")
        self.value_label = QLabel("Value: -")
        self.slice_info_label = QLabel("Slice: -/-")
        status_layout.addWidget(self.coord_label)
        status_layout.addWidget(self.slice_info_label)
        status_layout.addWidget(self.value_label)

        layout.addWidget(status_box)

        # 4D Time controls
        time_group = QFrame()
        time_layout = QVBoxLayout(time_group)

        self.time_checkbox = QCheckBox("Enable 4D Time Navigation")
        self.time_checkbox.setChecked(False)
        time_layout.addWidget(self.time_checkbox)

        time_controls_widget = QWidget()
        time_controls_layout = QHBoxLayout(time_controls_widget)
        time_controls_layout.setContentsMargins(0, 0, 0, 0)

        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(0)
        self.time_slider.setValue(0)
        self.time_slider.setEnabled(False)
        time_controls_layout.addWidget(self.time_slider, stretch=3)

        self.time_spin = QSpinBox()
        self.time_spin.setMinimum(0)
        self.time_spin.setMaximum(0)
        self.time_spin.setValue(0)
        self.time_spin.setEnabled(False)
        self.time_spin.setMaximumWidth(80)
        time_controls_layout.addWidget(self.time_spin, stretch=1)

        time_layout.addWidget(QLabel("Time Point:"))
        time_layout.addWidget(time_controls_widget)

        layout.addWidget(time_group)

        # Display options
        display_group = QFrame()
        display_layout = QVBoxLayout(display_group)
        display_layout.addWidget(QLabel("Display Options:"))

        # Colormap selection
        colormap_layout = QHBoxLayout()
        colormap_layout.addWidget(QLabel("Colormap:"))
        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(['gray', 'viridis', 'plasma', 'inferno', 'magma', 'hot', 'cool', 'bone'])
        colormap_layout.addWidget(self.colormap_combo)
        display_layout.addLayout(colormap_layout)

        layout.addWidget(display_group)

        # Add stretch to push everything to top
        layout.addStretch()

        parent.addWidget(control_widget)

    def create_image_display(self, parent):
        """Create the main image display area with three anatomical views"""
        display_widget = QWidget()
        display_layout = QGridLayout(display_widget)
        display_layout.setSpacing(5)

        # Create three views in a 2x2 grid layout
        view_positions = [(0, 0), (0, 1), (1, 0)]
        view_titles = ["Axial", "Coronal", "Sagittal"]

        for i, (row, col) in enumerate(view_positions):
            # View container with title
            view_container = QFrame()
            view_container.setFrameStyle(QFrame.Shape.StyledPanel)
            container_layout = QVBoxLayout(view_container)
            container_layout.setContentsMargins(2, 2, 2, 2)

            # Title label
            title_label = QLabel(view_titles[i])
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("font-weight: bold; padding: 4px; ") #background-color: #404040; ")
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

        # Add info panel to bottom right !! TODO fix or remove
        time_widget = QFrame()
        info_widget = QFrame()
        info_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        info_layout = QVBoxLayout(info_widget)

        info_title = QLabel("Image Information")
        info_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_title.setStyleSheet("font-weight: bold; padding: 4px; ") #background-color: #404040;")
        info_layout.addWidget(info_title)

        self.info_text = QLabel("No image loaded")
        self.info_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.info_text.setStyleSheet("color: #cccccc; font-size: 11px; padding: 10px;")
        self.info_text.setWordWrap(True)
        info_layout.addWidget(self.info_text)

        display_layout.addWidget(info_widget, 1, 1)

        parent.addWidget(display_widget)

        # Setup crosshairs after views are created
        QTimer.singleShot(100, self.setup_crosshairs)

    def setup_crosshairs(self):
        """Setup crosshairs for all views"""
        for view in self.views:
            view.setup_crosshairs()

    def setup_connections(self):
        """Setup signal-slot connections"""

        # Slice controls
        for i, (slider, spinbox) in enumerate(zip(self.slice_sliders, self.slice_spins)):
            slider.valueChanged.connect(lambda value, idx=i: self.slice_changed(idx, value))
            spinbox.valueChanged.connect(lambda value, idx=i: self.slice_changed(idx, value))

        # Time controls
        self.time_checkbox.toggled.connect(self.toggle_time_controls)
        self.time_slider.valueChanged.connect(self.time_changed)
        self.time_spin.valueChanged.connect(self.time_changed)

        # Colormap
        self.colormap_combo.currentTextChanged.connect(self.colormap_changed)

        # View coordinate changes
        for view in self.views:
            view.coordinate_changed.connect(self.update_coordinates)

    def open_file(self,file_path):
        """Open a NIfTI file with progress dialog"""

        if file_path:
            # Show progress dialog
            self.progress_dialog = QProgressDialog("Loading NIfTI file...", "Cancel", 0, 100, self)
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setMinimumDuration(0)

            # Start loading thread
            self.load_thread = ImageLoadThread(file_path)
            self.load_thread.finished.connect(self.on_file_loaded)
            self.load_thread.error.connect(self.on_load_error)
            self.load_thread.progress.connect(self.progress_dialog.setValue)
            self.load_thread.start()

            self.file_path = file_path

    def on_file_loaded(self, img_data, dims, affine, is_4d):
        """Handle successful file loading"""
        self.progress_dialog.close()

        self.img_data = img_data
        self.dims = dims
        self.affine = affine
        self.is_4d = is_4d

        # Update file info
        filename = os.path.basename(self.file_path)
        if is_4d:
            info_text = f"File: {filename}\nDimensions: {dims[0]}×{dims[1]}×{dims[2]}×{dims[3]}\n4D Time Series"
            self.time_checkbox.setChecked(True)
            self.time_checkbox.setEnabled(True)
        else:
            info_text = f"File: {filename}\nDimensions: {dims[0]}×{dims[1]}×{dims[2]}\n3D Volume"
            self.time_checkbox.setChecked(False)
            self.time_checkbox.setEnabled(False)

        self.file_info_label.setText(info_text)
        self.info_text.setText(info_text)

        self.initialize_display()

    def on_load_error(self, error_message):
        """Handle file loading errors"""
        self.progress_dialog.close()
        QMessageBox.critical(self, "Error Loading File", f"Failed to load NIfTI file:\n{error_message}")

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
        self.time_slider.setEnabled(enabled and self.is_4d)
        self.time_spin.setEnabled(enabled and self.is_4d)

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

            self.coord_label.setText(f"Coordinates: ({img_coords[0]}, {img_coords[1]}, {img_coords[2]})")
            self.value_label.setText(f"Value: {value:.2f}")

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
        self.coord_label.setText(f"Coordinates: ({coords[0]}, {coords[1]}, {coords[2]})")

        try:
            if self.is_4d:
                value = self.img_data[coords[0], coords[1], coords[2], self.current_time]
            else:
                value = self.img_data[coords[0], coords[1], coords[2]]
            self.value_label.setText(f"Value: {value:.2f}")
        except (IndexError, ValueError):
            self.value_label.setText("Value: -")

    def update_cross_view_lines(self):
        """Update crosshair lines across all views to show current position"""
        if self.img_data is None:
            return

        coords = self.current_coordinates

        for i, view in enumerate(self.views):
            if i == 0:  # Axial view
                # Show crosshairs at X, Y position
                view.set_crosshair_position(coords[0], self.img_data.shape[1] - 1 - coords[1])
            elif i == 1:  # Coronal view
                # Show crosshairs at X, Z position
                view.set_crosshair_position(coords[0], self.img_data.shape[2] - 1 - coords[2])
            elif i == 2:  # Sagittal view
                # Show crosshairs at Y, Z position
                view.set_crosshair_position(coords[1], self.img_data.shape[2] - 1 - coords[2])

    def update_display(self, plane_idx):
        """Update a specific plane display with matplotlib-style rendering"""
        if self.img_data is None:
            return

        try:
            # Get current data (3D or 4D)
            if self.is_4d:
                current_data = self.img_data[..., self.current_time]
            else:
                current_data = self.img_data

            # Extract slice with correct orientation
            slice_idx = self.current_slices[plane_idx]

            if plane_idx == 0:  # Axial (XY plane)
                slice_data = current_data[:, :, slice_idx].T
                # Flip vertically for correct orientation
                slice_data = np.flipud(slice_data)
            elif plane_idx == 1:  # Coronal (XZ plane)
                slice_data = current_data[:, slice_idx, :].T
                # Flip vertically for correct orientation
                slice_data = np.flipud(slice_data)
            elif plane_idx == 2:  # Sagittal (YZ plane)
                slice_data = current_data[slice_idx, :, :].T
                # Flip vertically for correct orientation
                slice_data = np.flipud(slice_data)
            else:
                return

            # Normalize data using matplotlib-style approach
            slice_data = self.normalize_data_matplotlib_style(slice_data)

            # Apply colormap
            qimage = self.apply_colormap(slice_data, self.colormap)

            if qimage is not None:
                # Update display
                self.pixmap_items[plane_idx].setPixmap(QPixmap.fromImage(qimage))
                self.scenes[plane_idx].setSceneRect(0, 0, qimage.width(), qimage.height())

                # Fit view
                self.views[plane_idx].fitInView(self.scenes[plane_idx].sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

        except Exception as e:
            print(f"Error updating display {plane_idx}: {e}")

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

    def apply_colormap(self, data, colormap_name):
        """Apply colormap to normalized data and return QImage"""
        try:
            # Get matplotlib colormap
            cmap = cm.get_cmap(colormap_name)

            # Apply colormap
            colored_data = cmap(data)

            # Convert to 8-bit RGBA
            rgba_data = (colored_data * 255).astype(np.uint8)

            height, width = data.shape

            # Create QImage
            qimage = QImage(rgba_data.data, width, height, width * 4, QImage.Format.Format_RGBA8888)

            return qimage

        except Exception as e:
            print(f"Error applying colormap: {e}")
            return None

    def update_all_displays(self):
        """Update all plane displays"""
        for i in range(3):
            self.update_display(i)

        # Update slice info in status bar
        if self.img_data is not None:
            spatial_dims = self.dims[:3] if self.is_4d else self.dims
            slice_info = f"Slices: {self.current_slices[0] + 1}/{spatial_dims[2]} | {self.current_slices[1] + 1}/{spatial_dims[1]} | {self.current_slices[2] + 1}/{spatial_dims[0]}"
            if self.is_4d:
                slice_info += f" | Time: {self.current_time + 1}/{self.dims[3]}"
            self.slice_info_label.setText(slice_info)

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

    def closeEvent(self, event):
        """Clean up on application exit"""
        # Clean up any running threads
        if hasattr(self, 'load_thread') and self.load_thread.isRunning():
            self.load_thread.terminate()
            self.load_thread.wait()

        # Clear image data to free memory
        self.img_data = None
        gc.collect()

        event.accept()

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    frame = NiftiViewer()
    frame.show()
    sys.exit(app.exec())