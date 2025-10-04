import pytest
import sys
import os
from PyQt6.QtCore import QSettings

# Aggiungi il percorso del progetto al PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


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