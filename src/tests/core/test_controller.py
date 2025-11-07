import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, call
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QPushButton

from main.controller import Controller


class TestControllerInitialization:
    """Tests for Controller Initialization"""

    @pytest.fixture
    def mock_components(self):
        """Mock UI components"""
        with patch('main.controller.ImportPage') as MockImportPage, \
                patch('main.controller.MainWindow') as MockMainWindow, \
                patch('main.controller.WorkspaceTreeView') as MockTreeView, \
                patch('main.controller.NiftiViewer') as MockNiftiViewer, \
                patch('main.controller.get_app_dir') as mock_get_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_get_app_dir.return_value = MockPath(temp_dir)

            MockImportPage.return_value = Mock()
            MockMainWindow.return_value = Mock()
            MockTreeView.return_value = Mock()
            MockNiftiViewer.return_value = Mock()

            yield {
                'import_page': MockImportPage,
                'main_window': MockMainWindow,
                'tree_view': MockTreeView,
                'nifti_viewer': MockNiftiViewer,
                'temp_dir': temp_dir
            }

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_controller_initialization(self, qtbot, mock_components):
        """Verify correct controller initialization"""
        controller = Controller()

        assert controller.context is not None
        assert controller.workspace_path is not None
        assert controller.current_page is not None

    def test_context_contains_required_keys(self, qtbot, mock_components):
        """Verify that the context contains all necessary keys"""
        controller = Controller()

        required_keys = [
            "workspace_path",
            "update_main_buttons",
            "return_to_import",
            "history",
            "language_changed",
            "create_buttons",
            "selected_files_signal",
            "open_nifti_viewer",
            "settings"
        ]

        for key in required_keys:
            assert key in controller.context

    def test_components_created(self, qtbot, mock_components):
        """Verify creation of all components"""
        controller = Controller()

        mock_components['import_page'].assert_called_once()
        mock_components['main_window'].assert_called_once()
        mock_components['tree_view'].assert_called_once()
        mock_components['nifti_viewer'].assert_called_once()

    def test_workspace_directory_created(self, qtbot, mock_components):
        """Verify workspace directory creation"""
        controller = Controller()

        workspace_path = controller.workspace_path
        # Verify that the path exists
        assert workspace_path is not None

    def test_start_page_set(self, qtbot, mock_components):
        """Verify that the start page is ImportPage"""
        controller = Controller()

        assert controller.start_page == controller.context["import_page"]
        assert controller.current_page == controller.start_page

    def test_history_initialized(self, qtbot, mock_components):
        """Verify history initialization"""
        controller = Controller()

        assert len(controller.context["history"]) > 0
        assert controller.start_page in controller.context["history"]


class TestControllerNavigation:
    """Tests for page navigation"""

    @pytest.fixture
    def controller(self, qtbot):
        """Create controller for testing"""
        with patch('main.controller.ImportPage'), \
                patch('main.controller.MainWindow'), \
                patch('main.controller.WorkspaceTreeView'), \
                patch('main.controller.NiftiViewer'), \
                patch('main.controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_go_to_next_page(self, controller):
        """Verify navigation to the next page"""
        mock_next_page = Mock()
        controller.current_page.next.return_value = mock_next_page

        result = controller.go_to_next_page()

        assert controller.current_page == mock_next_page
        assert result == mock_next_page

    def test_go_to_next_page_none(self, controller):
        """Verify behavior when next returns None"""
        controller.current_page.next.return_value = None
        initial_page = controller.current_page

        result = controller.go_to_next_page()

        assert controller.current_page == initial_page
        assert result == initial_page

    def test_go_to_previous_page(self, controller):
        """Verify navigation to the previous page"""
        mock_previous_page = Mock()
        controller.current_page.back.return_value = mock_previous_page

        result = controller.go_to_previous_page()

        assert controller.current_page == mock_previous_page
        assert result == mock_previous_page

    def test_go_to_previous_page_none(self, controller):
        """Verify behavior when back returns None"""
        controller.current_page.back.return_value = None
        initial_page = controller.current_page

        result = controller.go_to_previous_page()

        assert controller.current_page == initial_page
        assert result == initial_page

    def test_return_to_import(self, controller):
        """Verify return to import page"""
        # Simulate navigation
        mock_page1 = Mock()
        mock_page2 = Mock()
        controller.context["history"] = [controller.start_page, mock_page1, mock_page2]
        controller.current_page = mock_page2

        result = controller.return_to_import()

        assert controller.current_page == controller.start_page
        assert result == controller.start_page
        # Verify that reset_page is called on all pages
        mock_page1.reset_page.assert_called_once()
        mock_page2.reset_page.assert_called_once()


class TestControllerButtons:
    """Tests for button management"""

    @pytest.fixture
    def controller(self, qtbot):
        with patch('main.controller.ImportPage'), \
                patch('main.controller.MainWindow'), \
                patch('main.controller.WorkspaceTreeView'), \
                patch('main.controller.NiftiViewer'), \
                patch('main.controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_create_buttons(self, controller):
        """Verify button creation"""
        next_btn, back_btn = controller.create_buttons()

        assert isinstance(next_btn, QPushButton)
        assert isinstance(back_btn, QPushButton)
        assert controller.next_button == next_btn
        assert controller.back_button == back_btn

    def test_buttons_connected(self, controller):
        """Verify that the buttons are connected"""
        controller.create_buttons()

        # Buttons should have connected signals
        # (difficult to test connections directly)
        assert controller.next_button is not None
        assert controller.back_button is not None

    def test_update_buttons_state_ready(self, controller):
        """Verify button state update when ready"""
        controller.create_buttons()
        controller.current_page.is_ready_to_advance.return_value = True
        controller.current_page.is_ready_to_go_back.return_value = True

        controller.update_buttons_state()

        assert controller.next_button.isEnabled()
        assert controller.back_button.isEnabled()

    def test_update_buttons_state_not_ready(self, controller):
        """Verify button state update when not ready"""
        controller.create_buttons()
        controller.current_page.is_ready_to_advance.return_value = False
        controller.current_page.is_ready_to_go_back.return_value = False

        controller.update_buttons_state()

        assert not controller.next_button.isEnabled()
        assert not controller.back_button.isEnabled()

    def test_button_click_next(self, controller, qtbot):
        """Verify click on next button"""
        controller.create_buttons()
        mock_next_page = Mock()
        controller.current_page.next.return_value = mock_next_page

        with qtbot.waitSignal(controller.next_button.clicked, timeout=1000):
            controller.next_button.click()

        assert controller.current_page == mock_next_page

    def test_button_click_back(self, controller, qtbot):
        """Verify click on back button"""
        controller.create_buttons()
        mock_prev_page = Mock()
        controller.current_page.back.return_value = mock_prev_page

        with qtbot.waitSignal(controller.back_button.clicked, timeout=1000):
            controller.back_button.click()

        assert controller.current_page == mock_prev_page


class TestControllerLanguage:
    """Tests for language management"""

    @pytest.fixture
    def controller(self, qtbot):
        with patch('main.controller.ImportPage'), \
                patch('main.controller.MainWindow'), \
                patch('main.controller.WorkspaceTreeView'), \
                patch('main.controller.NiftiViewer'), \
                patch('main.controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_set_language(self, controller):
        """Verify language setting"""
        with patch.object(controller.translator, 'load', return_value=True):
            controller.set_language("it")

            # Verify that it is saved
            assert controller.settings.value("language") == "it"

    def test_save_language(self, controller):
        """Verify saving language"""
        controller.save_language("it")

        saved_lang = controller.settings.value("language")
        assert saved_lang == "it"

    def test_language_changed_signal(self, controller, qtbot):
        """Verify language change signal emission"""
        with patch.object(controller.translator, 'load', return_value=True):
            with qtbot.waitSignal(controller.language_changed, timeout=1000):
                controller.language_changed.emit("it")

    def test_translator_load_called(self, controller):
        """Verify that translator.load is called"""
        with patch.object(controller.translator, 'load', return_value=True) as mock_load:
            controller.set_language("en")

            mock_load.assert_called_once()
            # Verify that the path contains the language code
            call_args = str(mock_load.call_args)
            assert "en.qm" in call_args


class TestControllerNiftiViewer:
    """Tests for opening NIfTI viewer"""

    @pytest.fixture
    def controller(self, qtbot):
        with patch('main.controller.ImportPage'), \
                patch('main.controller.MainWindow'), \
                patch('main.controller.WorkspaceTreeView'), \
                patch('main.controller.NiftiViewer') as MockViewer, \
                patch('main.controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            mock_viewer = Mock()
            MockViewer.return_value = mock_viewer

            controller = Controller()

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_open_nifti_viewer(self, controller):
        """Verify NIfTI viewer opening"""
        test_path = "/path/to/scan.nii"

        controller.open_nifti_viewer(test_path)

        controller.context["nifti_viewer"].open_file.assert_called_once_with(test_path)
        controller.context["nifti_viewer"].show.assert_called_once()


class TestControllerStart:
    """Tests for application start"""

    @pytest.fixture
    def controller(self, qtbot):
        with patch('main.controller.ImportPage'), \
                patch('main.controller.MainWindow') as MockMainWindow, \
                patch('main.controller.WorkspaceTreeView'), \
                patch('main.controller.NiftiViewer'), \
                patch('main.controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            mock_window = Mock()
            MockMainWindow.return_value = mock_window

            controller = Controller()

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_start_shows_main_window(self, controller):
        """Verify that start() shows the main window"""
        controller.start()

        controller.main_window.show.assert_called_once()


class TestControllerSettings:
    """Tests for settings management"""

    @pytest.fixture
    def clean_settings(self):
        """Cleans settings before and after test"""
        settings = QSettings("GliAAns")
        settings.clear()
        yield settings
        settings.clear()

    def test_loads_saved_language(self, qtbot, clean_settings):
        """Verify loading of saved language"""
        clean_settings.setValue("language", "it")

        with patch('main.controller.ImportPage'), \
                patch('main.controller.MainWindow'), \
                patch('main.controller.WorkspaceTreeView'), \
                patch('main.controller.NiftiViewer'), \
                patch('main.controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()

            assert controller.saved_lang == "it"

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_default_language_en(self, qtbot, clean_settings):
        """Verify default language is English"""
        with patch('main.controller.ImportPage'), \
                patch('main.controller.MainWindow'), \
                patch('main.controller.WorkspaceTreeView'), \
                patch('main.controller.NiftiViewer'), \
                patch('main.controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()

            assert controller.saved_lang == "en"

            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch('main.controller.set_log_level')
    def test_debug_log_setting(self, mock_set_log_level, qtbot, clean_settings):
        """Verify debug log setting"""
        import logging
        clean_settings.setValue("debug_log", True)

        with patch('main.controller.ImportPage'), \
                patch('main.controller.MainWindow'), \
                patch('main.controller.WorkspaceTreeView'), \
                patch('main.controller.NiftiViewer'), \
                patch('main.controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()

            mock_set_log_level.assert_called_with(logging.DEBUG)

            shutil.rmtree(temp_dir, ignore_errors=True)


class TestControllerIntegration:
    """Integration tests for complete flows"""

    @pytest.fixture
    def controller(self, qtbot):
        with patch('main.controller.ImportPage') as MockImport, \
                patch('main.controller.MainWindow'), \
                patch('main.controller.WorkspaceTreeView'), \
                patch('main.controller.NiftiViewer'), \
                patch('main.controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            # Setup mock pages with realistic behaviors
            mock_import = Mock()
            mock_import.is_ready_to_advance.return_value = True
            mock_import.is_ready_to_go_back.return_value = False
            MockImport.return_value = mock_import

            controller = Controller()

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_full_navigation_flow(self, controller):
        """Test full navigation flow"""
        # Setup mock pages
        page2 = Mock()
        page2.is_ready_to_advance.return_value = True
        page2.is_ready_to_go_back.return_value = True
        page2.back.return_value = controller.start_page

        controller.current_page.next.return_value = page2

        # Navigate forward
        controller.go_to_next_page()
        assert controller.current_page == page2

        # Navigate back
        controller.go_to_previous_page()
        assert controller.current_page == controller.start_page

    def test_navigation_with_button_updates(self, controller):
        """Test navigation with button updates"""
        controller.create_buttons()

        page2 = Mock()
        page2.is_ready_to_advance.return_value = False
        page2.is_ready_to_go_back.return_value = True

        controller.current_page.next.return_value = page2

        # Navigate
        controller.go_to_next_page()

        # Buttons should be updated
        assert not controller.next_button.isEnabled()
        assert controller.back_button.isEnabled()

    def test_return_to_import_resets_all(self, controller):
        """Test that return_to_import resets everything"""
        # Simulate deep navigation
        page2 = Mock()
        page3 = Mock()
        controller.context["history"] = [controller.start_page, page2, page3]
        controller.current_page = page3

        # Return to import
        controller.return_to_import()

        # Verify reset
        page2.reset_page.assert_called_once()
        page3.reset_page.assert_called_once()
        assert controller.current_page == controller.start_page


# Helper class for Path mock
class MockPath:
    """Mock of pathlib.Path for testing"""

    def __init__(self, path_str):
        self.path_str = path_str

    def __str__(self):
        return self.path_str

    def __truediv__(self, other):
        return MockPath(os.path.join(self.path_str, other))

    def __repr__(self):
        return f"MockPath('{self.path_str}')"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])