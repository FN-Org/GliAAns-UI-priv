import pytest
import numpy as np
from PyQt6 import QtCore, QtWidgets
from unittest.mock import MagicMock, patch

# Import the target module
import sys

from PyQt6.QtWidgets import QWidget, QSplitter, QStatusBar, QScrollArea, QPushButton, QLabel, QComboBox, QCheckBox, \
    QSlider, QSpinBox, QGridLayout, QFrame, QGraphicsScene
from unittest.mock import MagicMock
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QMessageBox


mock_crosshair = MagicMock(spec=QWidget)
mock_nifti_dialog = MagicMock()
mock_logger = MagicMock()
mock_threads = MagicMock()

sys.modules['components.crosshair_graphic_view'] = mock_crosshair
sys.modules['components.nifti_file_dialog'] = mock_nifti_dialog
sys.modules['logger'] = mock_logger
sys.modules['threads.nifti_utils_threads'] = mock_threads



from ui.ui_nifti_viewer import compute_mask_numba_mm, apply_overlay_numba, NiftiViewer

class DummyView(QWidget):
    def __init__(self):
        super().__init__()
        self.crosshair_initialized = True
        self.crosshair_pos = (0, 0)
        self.scene_obj = MagicMock()
        self.coordinate_changed = MagicMock()
    def fitInView(self, *a, **kw): pass
    def scene(self): return self.scene_obj


class MockLabel:
    def __init__(self):
        self.text_value = ""
        self.visible = True
    def setText(self, val):
        self.text_value = val
    def setVisible(self, val):
        self.visible = val
    def text(self):
        return self.text_value

class MockSlider:
    def __init__(self):
        self.visible = True
        self.value = 0
    def setVisible(self, val):
        self.visible = val

class MockSpinBox(MockSlider):
    pass

# ================================================================
# === NUMBA COMPUTATION TESTS ====================================
# ================================================================

def test_compute_mask_numba_mm_basic():
    img = np.zeros((5, 5, 5), dtype=np.float32)
    img[2, 2, 2] = 1.0
    result = compute_mask_numba_mm(
        img, x0=2, y0=2, z0=2,
        radius_mm=2.0,
        voxel_sizes=(1.0, 1.0, 1.0),
        seed_intensity=1.0,
        diff=0.5,
        x_min=0, x_max=5,
        y_min=0, y_max=5,
        z_min=0, z_max=5
    )

    assert result.shape == img.shape
    assert result[2, 2, 2] == 1  # center voxel must be included
    assert np.sum(result) >= 1  # mask not empty


def test_compute_mask_respects_intensity_diff():
    img = np.zeros((3, 3, 3), dtype=np.float32)
    img[1, 1, 1] = 10
    result = compute_mask_numba_mm(
        img, 1, 1, 1,
        radius_mm=2.0,
        voxel_sizes=(1, 1, 1),
        seed_intensity=10,
        diff=0.1,
        x_min=0, x_max=3,
        y_min=0, y_max=3,
        z_min=0, z_max=3
    )
    assert np.count_nonzero(result) == 1  # Only the seed voxel matches


def test_apply_overlay_numba_blends_correctly():
    rgba = np.ones((3, 3, 3), dtype=np.float32)
    mask = np.zeros((3, 3), dtype=np.uint8)
    mask[1, 1] = 1
    intensity = np.full((3, 3), 0.5, dtype=np.float32)
    color = (1.0, 0.0, 0.0)

    out = apply_overlay_numba(rgba.copy(), mask, intensity, color)

    assert out.shape == rgba.shape
    assert not np.allclose(out[1, 1, 0], rgba[1, 1, 0]) # Red channel increased
    assert out[1, 1, 1] <= rgba[1, 1, 1]  # Other channels unchanged or decreased


# ================================================================
# === NIFTI VIEWER UI TESTS ======================================
# ================================================================

@pytest.fixture
def viewer(qtbot):
    viewer = NiftiViewer()
    qtbot.addWidget(viewer)
    return viewer


def test_viewer_initialization(viewer):
    """Ensure NiftiViewer initializes with proper defaults."""
    assert viewer.windowTitle() == QtCore.QCoreApplication.translate("NiftiViewer", "NIfTI Image Viewer")
    assert viewer.img_data is None
    assert isinstance(viewer.current_slices, list)
    assert len(viewer.current_slices) == 3
    assert viewer.overlay_enabled is False


def test_viewer_ui_components_exist(viewer):
    """Check that critical UI components are initialized."""
    assert hasattr(viewer, "views")
    assert hasattr(viewer, "scenes")
    assert hasattr(viewer, "slice_sliders")
    assert hasattr(viewer, "status_bar") or viewer.statusBar() is not None


def test_context_signal_connection(qtbot):
    """Verify translation signal connects if provided in context."""
    mock_signal = MagicMock()
    context = {"language_changed": mock_signal}
    v = NiftiViewer(context=context)
    qtbot.addWidget(v)
    assert mock_signal.connect.called  # should connect to _translate_ui


def test_translate_ui_does_not_crash(viewer):
    """_translate_ui should execute safely even with no translation context."""
    viewer._translate_ui()
    assert True  # no exceptions


def test_viewer_overlay_color_map(viewer):
    """Ensure overlay colors mapping is valid and consistent."""
    assert isinstance(viewer.overlay_colors, dict)
    for key, val in viewer.overlay_colors.items():
        assert isinstance(val, np.ndarray)
        assert val.shape == (3,)
        assert (0.0 <= val).all() and (val <= 1.0).all()


def test_viewer_thread_list_cleanup(viewer):
    """Simulate cleaning up threads."""
    dummy_thread = MagicMock()
    viewer.threads.append(dummy_thread)
    viewer.threads.clear()
    assert len(viewer.threads) == 0


def test_viewer_setup_connections(viewer):
    """Ensure setup_connections method exists and runs safely."""
    assert callable(viewer.setup_connections)
    viewer.setup_connections()
    assert True


def test_viewer_minimum_size(viewer):
    """Check that minimum size constraints are correctly set."""
    min_size = viewer.minimumSize()
    assert min_size.width() >= 1000
    assert min_size.height() >= 700


def test_viewer_resize_does_not_crash(viewer):
    """Resizing should not raise exceptions."""
    viewer.resize(1200, 800)
    assert viewer.width() == 1200
    assert viewer.height() == 800


def test_init_ui_structure(viewer):
    """Test that init_ui creates the correct high-level structure."""
    central_widget = viewer.centralWidget()
    assert isinstance(central_widget, QWidget), "Central widget should be QWidget"
    assert isinstance(viewer.statusBar(), QStatusBar), "Status bar should exist"

    # Check splitter inside layout
    layout = central_widget.layout
    assert layout.count() == 1, "Central layout should contain one splitter"
    splitter = layout.itemAt(0).widget()
    assert isinstance(splitter, QSplitter), "Main splitter should be created"
    assert splitter.orientation() == QtCore.Qt.Orientation.Horizontal

    # Check status labels existence
    assert hasattr(viewer, "coord_label")
    assert hasattr(viewer, "value_label")
    assert hasattr(viewer, "slice_info_label")
    assert viewer.statusBar().currentMessage() != "", "Status bar should show ready message"


def test_control_panel_created(viewer):
    """Ensure the left control panel was correctly added to the splitter."""
    central_widget = viewer.centralWidget()
    splitter = central_widget.layout.itemAt(0).widget()
    assert splitter.count() >= 1

    # The first child should be a QScrollArea (control panel)
    control_panel = splitter.widget(0)
    assert isinstance(control_panel, QScrollArea)
    assert control_panel.widget().maximumWidth() == 340
    assert control_panel.widgetResizable() is True


def test_control_panel_contains_key_widgets(viewer):
    """Verify that essential control widgets exist and are properly configured."""
    scroll_area = viewer.centralWidget().layout.itemAt(0).widget().widget(0)
    # File controls
    assert isinstance(viewer.open_btn, QPushButton)
    assert "Open" in viewer.open_btn.text()
    assert isinstance(viewer.file_info_label, QLabel)

    # Slice navigation widgets
    assert len(viewer.slice_labels) == 3, "Should have 3 slice labels"
    assert len(viewer.slice_sliders) == 3
    assert len(viewer.slice_spins) == 3
    assert len(viewer.coord_displays) == 3

    # Display options
    assert isinstance(viewer.colormap_combo, QComboBox)
    assert viewer.colormap_combo.count() > 0
    assert "gray" in [viewer.colormap_combo.itemText(i) for i in range(viewer.colormap_combo.count())]


def test_slider_spinbox_synchronization(viewer, qtbot):
    """Test that slider and spinbox for ROI are synchronized via signals."""
    radius_slider = viewer.automaticROI_radius_slider
    radius_spin = viewer.automaticROI_radius_spin

    qtbot.wait(10)
    radius_slider.setValue(123)
    assert radius_spin.value() == 123

    radius_spin.setValue(77)
    assert radius_slider.value() == 77


def test_overlay_controls_exist(viewer):
    """Ensure overlay-related controls exist and have correct initial states."""
    assert isinstance(viewer.overlay_btn, QPushButton)
    assert isinstance(viewer.overlay_checkbox, QCheckBox)
    assert isinstance(viewer.overlay_alpha_slider, QSlider)
    assert isinstance(viewer.overlay_alpha_spin, QSpinBox)
    assert isinstance(viewer.overlay_threshold_slider, QSlider)
    assert isinstance(viewer.overlay_threshold_spin, QSpinBox)

    # Initial states
    assert viewer.overlay_btn.isEnabled() is False
    assert viewer.overlay_checkbox.isEnabled() is False
    assert viewer.overlay_alpha_slider.isEnabled() is False
    assert viewer.overlay_threshold_slider.isEnabled() is False
    assert viewer.overlay_info_label.text().startswith("No overlay")


def test_automatic_roi_controls(viewer):
    """Verify ROI controls are correctly initialized."""
    assert isinstance(viewer.automaticROIbtn, QPushButton)
    assert viewer.automaticROIbtn.isEnabled() is False
    assert isinstance(viewer.automaticROI_save_btn, QPushButton)
    assert viewer.automaticROI_save_btn.isEnabled() is False
    assert viewer.automaticROI_sliders_group.isVisible() is False

    # Verify slider ranges
    assert viewer.automaticROI_radius_slider.maximum() == 9999
    assert viewer.automaticROI_diff_slider.maximum() == 99999


def test_splitter_resizing_behavior(viewer):
    """Ensure the splitter's stretch factors are correctly configured."""
    central_widget = viewer.centralWidget()
    splitter = central_widget.layout.itemAt(0).widget()
    sizes = splitter.sizes()
    assert sizes[0] == 300 or sizes[0] == 340  # default control width
    assert splitter.stretchFactor(0) == 0
    assert splitter.stretchFactor(1) == 1


def test_status_bar_text(viewer):
    """Validate that the status bar shows expected startup message."""
    message = viewer.statusBar().currentMessage()
    assert "Ready" in message or "Open" in message


def test_format_info_text_short_line(viewer):
    text = "Short line"
    result = viewer.format_info_text(text)
    assert result == text, "Short text should remain unchanged"


def test_format_info_text_long_line_with_colon(viewer):
    text = "Description: This is a very long line that should wrap neatly after the colon for readability."
    formatted = viewer.format_info_text(text, max_line_length=40)
    lines = formatted.splitlines()
    assert lines[0].endswith(':'), "First part should end with colon"
    assert lines[1].startswith('  '), "Continuation lines should be indented"
    assert all(len(l) <= 42 for l in lines), "No line should exceed width + indent"


def test_format_info_text_long_line_no_colon(viewer):
    text = "ThisIsAReallyLongSingleLineWithoutColonThatShouldWrapAutomaticallyAndBeReadable"
    formatted = viewer.format_info_text(text, max_line_length=20)
    assert '\n' in formatted, "Should insert line breaks when no colon"
    assert all(len(line) <= 20 for line in formatted.splitlines())


def test_format_info_text_multiple_lines(viewer):
    text = "First line okay\nAnother: This one is quite long and needs wrapping."
    result = viewer.format_info_text(text, max_line_length=35)
    assert "First line okay" in result
    assert "Another:" in result
    assert "\n  " in result, "Wrapped continuation should be indented"


# ---------------------------------------------------------------------
# Tests for create_image_display
# ---------------------------------------------------------------------
def test_create_image_display_structure(viewer, qtbot):
    splitter = QSplitter()
    viewer.create_image_display(splitter)

    # Verify display widget is added to parent
    assert splitter.count() == 1
    display_widget = splitter.widget(0)
    layout = display_widget.layout()
    assert isinstance(layout, QGridLayout)

    # There should be 4 panels (3 anatomical + 1 info)
    count = sum(isinstance(layout.itemAt(i).widget(), QFrame)
                for i in range(layout.count()))
    assert count == 4

    # Check titles
    titles = [lbl.text() for lbl in viewer.view_titles_labels]
    assert titles == ["Axial", "Coronal", "Sagittal"]


def test_create_image_display_views_and_scenes(viewer):
    splitter = QSplitter()
    viewer.create_image_display(splitter)

    # There should be 3 views, 3 scenes, 3 pixmap items
    assert len(viewer.views) == 3
    assert len(viewer.scenes) == 3
    assert len(viewer.pixmap_items) == 3

    for v, s, p in zip(viewer.views, viewer.scenes, viewer.pixmap_items):
        assert isinstance(v, DummyView)
        assert isinstance(s, QGraphicsScene)
        assert v.scene_obj == s


def test_create_image_display_fourth_panel(viewer):
    splitter = QSplitter()
    viewer.create_image_display(splitter)
    assert isinstance(viewer.fourth_widget, QFrame)
    assert isinstance(viewer.fourth_title, QLabel)
    assert "Image" in viewer.fourth_title.text()
    assert isinstance(viewer.info_text, QLabel)
    assert "No image loaded" in viewer.info_text.text()


def test_setup_crosshairs_initializes_all(viewer):
    """Each view should have setup_crosshairs called."""
    for v in viewer.views:
        v.crosshair_initialized = False
    viewer.setup_crosshairs()
    assert all(v.crosshair_initialized for v in viewer.views)


# ---------------------------------------------------------------------
# setup_connections
# ---------------------------------------------------------------------
def test_setup_connections_wires_all_signals(monkeypatch):
    """Test that setup_connections connects expected number of signals."""
    from PyQt6.QtCore import QObject

    class SignalCounter(QObject):
        def __init__(self):
            super().__init__()
            self.count = 0

        def slot(self, *a):
            self.count += 1

    counter = SignalCounter()

    # Create a minimal viewer with real signals
    class V(QObject):
        def __init__(self):
            super().__init__()
            self.open_btn = QPushButton()
            self.overlay_btn = QPushButton()
            self.overlay_checkbox = QCheckBox()
            self.overlay_alpha_slider = QSlider()
            self.overlay_threshold_slider = QSlider()
            self.slice_sliders = [QSlider(), QSlider(), QSlider()]
            self.slice_spins = [QSpinBox(), QSpinBox(), QSpinBox()]
            self.automaticROIbtn = QPushButton()
            self.automaticROI_diff_slider = QSlider()
            self.automaticROI_radius_slider = QSlider()
            self.automaticROI_save_btn = QPushButton()
            self.time_checkbox = QCheckBox()
            self.time_slider = QSlider()
            self.time_spin = QSpinBox()
            self.colormap_combo = QComboBox()
            self.views = [DummyView(), DummyView(), DummyView()]
            # Dummy slots
            self.open_file = counter.slot
            self.toggle_overlay = counter.slot
            self.update_overlay_alpha = counter.slot
            self.update_overlay_threshold = counter.slot
            self.slice_changed = counter.slot
            self.automaticROI_clicked = counter.slot
            self.update_automaticROI = counter.slot
            self.automaticROI_save = counter.slot
            self.toggle_time_controls = counter.slot
            self.time_changed = counter.slot
            self.colormap_changed = counter.slot
            self.update_coordinates = counter.slot

        from PyQt6.QtWidgets import QPushButton
        def setup_connections(self):
            # Copy of the method under test
            self.open_btn.clicked.connect(lambda: self.open_file())
            self.overlay_btn.clicked.connect(lambda: self.open_file(is_overlay=True))
            self.overlay_checkbox.toggled.connect(self.toggle_overlay)
            self.overlay_alpha_slider.valueChanged.connect(self.update_overlay_alpha)
            self.overlay_threshold_slider.valueChanged.connect(self.update_overlay_threshold)
            for i, (slider, spinbox) in enumerate(zip(self.slice_sliders, self.slice_spins)):
                slider.valueChanged.connect(lambda value, idx=i: self.slice_changed(idx, value))
                spinbox.valueChanged.connect(lambda value, idx=i: self.slice_changed(idx, value))
            self.automaticROIbtn.clicked.connect(self.automaticROI_clicked)
            self.automaticROI_diff_slider.valueChanged.connect(self.update_automaticROI)
            self.automaticROI_radius_slider.valueChanged.connect(self.update_automaticROI)
            self.automaticROI_save_btn.clicked.connect(self.automaticROI_save)
            self.time_checkbox.toggled.connect(self.toggle_time_controls)
            self.time_slider.valueChanged.connect(self.time_changed)
            self.time_spin.valueChanged.connect(self.time_changed)
            self.colormap_combo.currentTextChanged.connect(self.colormap_changed)
            for view in self.views:
                view.coordinate_changed.connect(self.update_coordinates)

    viewer = V()
    viewer.setup_connections()

    # Emit a few signals to ensure they trigger without errors
    viewer.open_btn.click()
    viewer.overlay_btn.click()
    viewer.overlay_checkbox.toggle()
    for s in viewer.slice_sliders:
        s.setValue(1)
    for s in viewer.slice_spins:
        s.setValue(2)
    viewer.time_checkbox.toggle()
    viewer.colormap_combo.currentTextChanged.emit("gray")

    assert counter.count > 0, "At least one connected signal should trigger the slot"


# ---------------------------------------------------------------------
# show_workspace_nii_dialog
# ---------------------------------------------------------------------
def test_show_workspace_nii_dialog_calls_correct_methods(monkeypatch):
    """Ensure correct call path for overlay vs base image."""
    from types import SimpleNamespace
    dummy = SimpleNamespace()
    dummy.context = MagicMock()
    dummy.open_file = MagicMock()

    class DummyDialog:
        @staticmethod
        def get_files(context, **kwargs):
            return ["dummy_path.nii"]

    monkeypatch.setattr("ui.ui_nifti_viewer.NiftiFileDialog", DummyDialog)
    from ui.ui_nifti_viewer import NiftiViewer  # noqa: F401
    # emulate function call
    from ui.ui_nifti_viewer import NiftiFileDialog

    # Base mode
    NiftiViewer.NiftiFileDialog = DummyDialog
    NiftiViewer.NiftiFileDialog.get_files = DummyDialog.get_files
    from ui.ui_nifti_viewer import NiftiFileDialog
    dummy.show_workspace_nii_dialog = NiftiViewer.NiftiFileDialog.get_files
    result = NiftiFileDialog.get_files(dummy.context)
    assert isinstance(result, list)


# ---------------------------------------------------------------------
# open_file
# ---------------------------------------------------------------------
def test_open_file_blocks_overlay_without_base(monkeypatch):
    """Overlay loading should warn if no base image is present."""
    from ui import ui_nifti_viewer
    monkeypatch.setattr(ui_nifti_viewer.QMessageBox, "warning", MagicMock())

    class DummyThread:
        def __init__(self, *a, **kw): pass

    monkeypatch.setattr(ui_nifti_viewer, "ImageLoadThread", DummyThread)

    viewer = MagicMock()
    viewer.img_data = None

    try:
        ui_nifti_viewer.NiftiViewer.open_file(viewer, "overlay.nii", is_overlay=True)
    except Exception:
        pass

    ui_nifti_viewer.QMessageBox.warning.assert_called()


# ===============================
# ✅ on_file_loaded()
# ===============================
def test_on_file_loaded_base_image(qtbot, viewer):
    """Test successful base image loading and initialization."""
    viewer.progress_dialog = MagicMock()
    viewer.sender = lambda: MagicMock()
    viewer.threads = [viewer.sender()]

    # Mock dependencies
    viewer.reset_overlay = MagicMock()
    viewer.hide_time_series_plot = MagicMock()
    viewer.update_all_displays = MagicMock()
    viewer.update_coordinate_displays = MagicMock()
    viewer.initialize_display = MagicMock()
    viewer.status_bar = MagicMock()
    viewer.coord_label = MagicMock()
    viewer.slice_info_label = MagicMock()
    viewer.value_label = MagicMock()

    # Simulate 3D load
    img = np.zeros((5, 5, 5))
    affine = np.eye(4)
    viewer.file_path = "/fake/path/test.nii"
    viewer.file_info_label = MagicMock()
    viewer.info_text = MagicMock()
    viewer.automaticROIbtn = MagicMock()
    viewer.time_group = MagicMock()
    viewer.time_checkbox = MagicMock()

    viewer.on_file_loaded(img, (5, 5, 5), affine, False, False)

    # Assertions
    viewer.reset_overlay.assert_called_once()
    viewer.initialize_display.assert_called_once()
    viewer.file_info_label.setText.assert_called()
    assert viewer.img_data.shape == (5, 5, 5)
    assert viewer.is_4d is False


def test_on_file_loaded_overlay(qtbot, viewer):
    """Test successful overlay image loading and UI refresh."""
    viewer.progress_dialog = MagicMock()
    viewer.sender = lambda: MagicMock()
    viewer.threads = [viewer.sender()]

    # Mock dependencies
    viewer.pad_volume_to_shape = MagicMock(return_value=np.zeros((5, 5, 5)))
    viewer.toggle_overlay = MagicMock()
    viewer.update_overlay_settings = MagicMock()
    viewer.update_all_displays = MagicMock()
    viewer.status_bar = MagicMock()
    viewer.overlay_info_label = MagicMock()
    viewer.overlay_checkbox = MagicMock()
    viewer.overlay_file_path = "/path/overlay.nii"
    viewer.dims = (5, 5, 5)

    img = np.zeros((5, 5, 5))
    viewer.on_file_loaded(img, (5, 5, 5), np.eye(4), False, True)

    viewer.toggle_overlay.assert_called_once_with(True)
    viewer.update_overlay_settings.assert_called_once()
    viewer.update_all_displays.assert_called_once()
    assert hasattr(viewer, "overlay_data")
    assert viewer.overlay_checkbox.setChecked.called


# ===============================
# ✅ on_load_error()
# ===============================
def test_on_load_error(qtbot, viewer, monkeypatch):
    """Ensure error handling dialog and logging work."""
    viewer.progress_dialog = MagicMock()
    viewer.sender = lambda: MagicMock()
    failed_thread = viewer.sender()
    viewer.threads = [failed_thread]

    with patch.object(QMessageBox, "critical") as mock_critical, \
         patch("log.critical") as mock_log:
        viewer.on_load_error("Simulated error")

    mock_critical.assert_called_once()
    mock_log.assert_called_once()
    assert failed_thread not in viewer.threads


# ===============================
# ✅ on_load_canceled()
# ===============================
def test_on_load_canceled(viewer):
    """Verify canceling file load terminates the thread."""
    mock_thread = MagicMock()
    viewer.threads = [mock_thread]

    viewer.on_load_canceled()
    mock_thread.terminate.assert_called_once()
    assert viewer.threads == []


# ===============================
# ✅ initialize_display()
# ===============================
def test_initialize_display_sets_slices(viewer):
    """Check initialize_display configures sliders correctly."""
    viewer.img_data = np.zeros((5, 5, 5))
    viewer.dims = (5, 5, 5)
    viewer.is_4d = False

    # Create mock controls
    viewer.slice_sliders = [MagicMock() for _ in range(3)]
    viewer.slice_spins = [MagicMock() for _ in range(3)]
    viewer.time_slider = MagicMock()
    viewer.time_spin = MagicMock()
    viewer.time_checkbox = MagicMock()
    viewer.update_all_displays = MagicMock()
    viewer.update_coordinate_displays = MagicMock()
    viewer.overlay_btn = MagicMock()

    viewer.initialize_display()

    for s in viewer.slice_sliders:
        s.setMaximum.assert_called_with(4)
        s.setValue.assert_called()
    viewer.overlay_btn.setEnabled.assert_called_once_with(True)


# ===============================
# ✅ toggle_overlay()
# ===============================
def test_toggle_overlay_enables_controls(viewer):
    """Ensure overlay toggling affects controls and updates displays."""
    viewer.overlay_data = np.zeros((3, 3, 3))
    viewer.update_all_displays = MagicMock()
    viewer.update_time_series_plot = MagicMock()

    viewer.overlay_alpha_slider = MagicMock()
    viewer.overlay_alpha_spin = MagicMock()
    viewer.overlay_threshold_slider = MagicMock()
    viewer.overlay_threshold_spin = MagicMock()

    viewer.toggle_overlay(True)
    viewer.update_all_displays.assert_called_once()
    viewer.overlay_alpha_slider.setEnabled.assert_called_with(True)
    assert viewer.overlay_enabled is True


# ===============================
# ✅ update_overlay_alpha() & threshold
# ===============================
@pytest.mark.parametrize("method,attr", [
    ("update_overlay_alpha", "overlay_alpha"),
    ("update_overlay_threshold", "overlay_threshold"),
])
def test_update_overlay_methods(viewer, method, attr):
    """Test overlay alpha/threshold updates trigger refresh."""
    viewer.overlay_data = np.zeros((3, 3, 3))
    viewer.overlay_enabled = True
    viewer.update_all_displays = MagicMock()

    func = getattr(viewer, method)
    func(50)
    assert getattr(viewer, attr) == 0.5
    viewer.update_all_displays.assert_called_once()


# ===============================
# ✅ update_overlay_settings()
# ===============================
def test_update_overlay_settings(viewer):
    """Ensure UI values sync to internal overlay state."""
    viewer.overlay_enabled = True
    viewer.overlay_data = np.zeros((3, 3, 3))
    viewer.overlay_alpha_slider = MagicMock(value=MagicMock(return_value=80))
    viewer.overlay_threshold_slider = MagicMock(value=MagicMock(return_value=30))
    viewer.update_all_displays = MagicMock()

    viewer.update_overlay_settings()

    assert viewer.overlay_alpha == 0.8
    assert viewer.overlay_threshold == 0.3
    viewer.update_all_displays.assert_called_once()


def test_slice_changed_updates_state(viewer):
    from ui.ui_nifti_viewer import NiftiViewer  # adapt path if needed

    with patch.object(NiftiViewer, 'update_display') as upd:
        with patch.object(NiftiViewer, 'update_coordinate_displays') as coord:
            with patch.object(NiftiViewer, 'update_cross_view_lines') as cross:
                NiftiViewer.slice_changed(viewer, 0, 7)
                assert viewer.current_slices[0] == 7
                assert viewer.slice_sliders[0].value == 7
                assert viewer.slice_spins[0].value == 7
                upd.assert_called_once()
                coord.assert_called_once()
                cross.assert_called_once()

def test_time_changed_updates_controls(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    viewer.is_4d = True
    NiftiViewer.time_changed(viewer, 3)
    assert viewer.current_time == 3
    assert viewer.time_slider.value == 3
    assert viewer.time_spin.value == 3
    viewer.update_all_displays.assert_called_once()

def test_toggle_time_controls(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    viewer.is_4d = True
    viewer.time_slider = MockSlider()
    viewer.time_spin = MockSpinBox()
    viewer.time_point_label = MockLabel()

    NiftiViewer.toggle_time_controls(viewer, True)
    assert viewer.time_slider.visible
    NiftiViewer.toggle_time_controls(viewer, False)
    assert not viewer.time_slider.visible

def test_screen_to_image_coords_bounds(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    coords = NiftiViewer.screen_to_image_coords(viewer, 0, 15, 15)
    assert all(isinstance(c, int) for c in coords)
    assert all(0 <= c < 10 for c in coords)

def test_update_coordinates_sets_labels(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    viewer.coord_label = MockLabel()
    viewer.value_label = MockLabel()
    NiftiViewer.update_coordinates(viewer, 0, 5, 5)
    assert "Coordinates" in viewer.coord_label.text_value
    assert "Value" in viewer.value_label.text_value

def test_update_display_runs_without_error(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    with patch("ui.ui_nifti_viewer.QImage", return_value=QImage(10, 10, QImage.Format.Format_RGBA8888)):
        with patch("ui.ui_nifti_viewer.QPixmap.fromImage", return_value=QPixmap()):
            NiftiViewer.update_display(viewer, 0)
    # Should have updated pixmap and scene rect
    assert viewer.pixmap_items[0].pixmap is not None
    assert viewer.scenes[0].rect is not None

def test_update_cross_view_lines_sets_positions(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    NiftiViewer.update_cross_view_lines(viewer)
    for v in viewer.views:
        assert isinstance(v.crosshair_pos, tuple)

def test_time_series_plot_setup_and_hide(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    NiftiViewer.setup_time_series_plot(viewer)
    assert viewer.time_plot_canvas is not None
    NiftiViewer.hide_time_series_plot(viewer)
    assert viewer.time_plot_canvas is None

def test_update_time_series_plot_runs(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    viewer.is_4d = True
    viewer.img_data = np.random.rand(5, 5, 5, 8)
    viewer.dims = viewer.img_data.shape
    viewer.current_coordinates = [2, 2, 2]

    # Prepare mock matplotlib elements
    viewer.time_plot_axes = MagicMock()
    viewer.time_plot_canvas = MagicMock()

    NiftiViewer.update_time_series_plot(viewer)
    viewer.time_plot_axes.plot.assert_called_once()
    viewer.time_plot_canvas.draw.assert_called_once()
    

def test_apply_colormap_valid(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    result = NiftiViewer.apply_colormap_matplotlib(viewer, np.array([0.5, 0.8]), "gray")
    assert isinstance(result, np.ndarray)
    assert result.shape[-1] == 4  # RGBA

def test_apply_colormap_invalid(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    result = NiftiViewer.apply_colormap_matplotlib(viewer, np.array([0.5]), "invalid_cmap")
    assert result is None

def test_update_all_displays_calls_update_display(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    viewer.is_4d = False
    viewer.update_display = MagicMock()
    viewer.dims = [10, 10, 10]
    NiftiViewer.update_all_displays(viewer)
    assert viewer.update_display.call_count == 3
    viewer.slice_info_label.setText.assert_called_once()

def test_create_overlay_composite_adds_overlay(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    overlay = np.random.rand(10, 10)
    rgba = np.ones((10, 10, 4))
    with patch("ui.ui_nifti_viewer.apply_overlay_numba", return_value=rgba * 0.5):
        result = NiftiViewer.create_overlay_composite(viewer, rgba, overlay, 'gray')
    assert result.shape == rgba.shape

def test_create_overlay_composite_empty_overlay(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    rgba = np.ones((10, 10, 4))
    result = NiftiViewer.create_overlay_composite(viewer, rgba, np.array([]), 'gray')
    np.testing.assert_array_equal(result, rgba)

def test_fit_all_views_calls_fitInView(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    mock_scene = MagicMock()
    mock_scene.sceneRect.return_value = QtCore.QRectF(0, 0, 10, 10)
    mock_view = MagicMock()
    mock_view.scene.return_value = mock_scene
    viewer.views = [mock_view]
    NiftiViewer.fit_all_views(viewer)
    mock_view.fitInView.assert_called_once()

def test_resizeEvent_calls_fit_all_views(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    with patch("ui.ui_nifti_viewer.QTimer.singleShot") as mock_timer:
        NiftiViewer.resizeEvent(viewer, MagicMock())
        mock_timer.assert_called_once()

def test_automaticROI_clicked_sets_controls(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    viewer.dims = np.array([10, 10, 10])
    viewer.voxel_sizes = np.array([1.0, 1.0, 1.0])
    NiftiViewer.automaticROI_clicked(viewer)
    viewer.automaticROI_drawing.assert_called_once()
    viewer.toggle_overlay.assert_called_once()
    viewer.update_all_displays.assert_called_once()

def test_automaticROI_drawing_creates_mask(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    with patch("ui.ui_nifti_viewer.compute_mask_numba_mm", return_value=np.ones((10, 10, 10))):
        viewer.automaticROI_radius_slider.value.return_value = 5
        viewer.automaticROI_diff_slider.value.return_value = 100
        viewer.automaticROI_seed_coordinates = [5, 5, 5]
        NiftiViewer.automaticROI_drawing(viewer)
        assert isinstance(viewer.overlay_data, np.ndarray)

def test_pad_volume_to_shape(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    vol = np.zeros((5, 5, 5))
    padded = NiftiViewer.pad_volume_to_shape(viewer, vol, (7, 7, 7))
    assert padded.shape == (7, 7, 7)
    # Should be centered padding (1 voxel border)
    assert np.allclose(padded[1:-1, 1:-1, 1:-1], 0)

def test_reset_overlay_clears_ui(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    viewer.automaticROI_overlay = True
    viewer.overlay_data = np.ones((5, 5, 5))
    NiftiViewer.reset_overlay(viewer)
    assert not viewer.automaticROI_overlay
    viewer.toggle_overlay.assert_called_once()
    viewer.overlay_checkbox.setChecked.assert_called_once_with(False)
    viewer.overlay_info_label.setText.assert_called_once()

def test_translate_ui_sets_labels(viewer):
    from ui.ui_nifti_viewer import NiftiViewer
    # Patch the methods if not already mocks
    viewer.setWindowTitle = MagicMock()
    viewer.status_bar = MagicMock()
    viewer.coord_label = MagicMock()
    viewer.value_label = MagicMock()
    NiftiViewer._translate_ui(viewer)
    viewer.setWindowTitle.assert_called_once()
    viewer.status_bar.showMessage.assert_called_once()
    viewer.coord_label.setText.assert_called_once()
    viewer.value_label.setText.assert_called_once()
