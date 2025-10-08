import shutil
import tempfile
from unittest.mock import Mock, patch

import pytest
import sys
import os
from PyQt6.QtCore import QSettings, QObject, pyqtSignal
from PyQt6.QtWidgets import QPushButton, QWidget

from ui.ui_mask_selection_page import MaskNiftiSelectionPage
from ui.ui_workspace_tree_view import WorkspaceTreeView

# Aggiungi il percorso del progetto al PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class SignalEmitter(QObject):
    """Classe helper per signal mockati"""
    selected_files = pyqtSignal(list)
    language_changed = pyqtSignal(str)

@pytest.fixture
def signal_emitter():
    return SignalEmitter()

@pytest.fixture
def temp_workspace():
    """Crea una directory temporanea per il workspace"""
    temp_dir = tempfile.mkdtemp()
    os.makedirs(os.path.join(temp_dir, "pipeline"), exist_ok=True)
    with open(os.path.join(temp_dir, "pipeline", "output.txt"), "w") as f:
        f.write("output content")
    os.makedirs(os.path.join(temp_dir, "sub-01", "pet"))
    with open(os.path.join(temp_dir, "sub-01", "pet", "pet.nii"), "w") as f:
        f.write("PET")
    os.makedirs(os.path.join(temp_dir, "sub-01", "anat"))
    with open(os.path.join(temp_dir, "sub-01", "anat", "T1w.nii"), "w") as f:
        f.write("T1w")
    os.makedirs(os.path.join(temp_dir, "sub-02"))

    manual_dir = os.path.join(temp_dir, "derivatives", "manual_masks", "sub-01", "anat")
    os.makedirs(manual_dir)
    with open(os.path.join(manual_dir, "mask.nii.gz"), "w") as f:
        f.write("test_mask")

    with open(os.path.join(temp_dir, "test.txt"), "w") as f:
        f.write("test content")
    with open(os.path.join(temp_dir, "brain.nii"), "w") as f:
        f.write("nifti data")
    with open(os.path.join(temp_dir, "brain.json"), "w") as f:
        f.write("{}")
    # File NIfTI.gz con JSON
    with open(os.path.join(temp_dir, "scan.nii.gz"), "w") as f:
        f.write("compressed")
    with open(os.path.join(temp_dir, "scan.json"), "w") as f:
        f.write("{}")

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def mock_context(temp_workspace, signal_emitter):
    """Crea un context mock con tutti i componenti necessari"""
    def create_buttons():
        # Ritorna QPushButton reali invece di Mock
        return QPushButton("Next"), QPushButton("Back")

    context = {
        "language_changed": signal_emitter.language_changed,
        "selected_files_signal": signal_emitter.selected_files,
        "settings": QSettings("TestOrg", "TestApp"),
        "workspace_path": temp_workspace,
        "create_buttons": create_buttons,
        "import_page": Mock(spec=['open_folder_dialog']),
        "update_main_buttons": Mock(),
        "return_to_import": Mock(),
        "main_window": Mock(),
        "history": [],
        "open_nifti_viewer": Mock(),
        "tree_view": Mock()
    }
    return context

@pytest.fixture(autouse=True)
def clean_settings():
    """Pulisce le impostazioni prima e dopo ogni test"""
    settings = QSettings("TestOrg", "TestApp")
    settings.clear()
    yield
    settings.clear()

@pytest.fixture
def mock_logger():
    """Mock per il logger"""
    from unittest.mock import Mock
    logger = Mock()
    logger.info = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    logger.warning = Mock()
    return logger

class DummySignal:
    def connect(self, slot):
        pass

class DummyFileSelectorWidget(QWidget):
    """Mock del FileSelectorWidget usato nei test."""
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.has_file = DummySignal()
        self._selected_files = []
        # Mock per verifiche nei test
        self.clear_selected_files = Mock()

    def get_selected_files(self):
        return self._selected_files

    def reset(self):
        self._selected_files.clear()

    def setEnabled(self, value: bool):
        pass

@pytest.fixture
def mock_file_selector():
    """Patcha FileSelectorWidget con un mock compatibile."""
    with patch(
        "ui.ui_skull_stripping_page.FileSelectorWidget",
        return_value=DummyFileSelectorWidget()
    ) as mock:
        yield mock

@pytest.fixture
def mock_file_selector_mask():
    """Patcha FileSelectorWidget nel modulo ui_mask_selection_page con un widget valido."""
    with patch(
        "ui.ui_mask_selection_page.FileSelectorWidget",
        return_value=DummyFileSelectorWidget()
    ) as mock:
        yield mock

# Configurazione pytest
def pytest_configure(config):
    """Configurazione globale di pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )