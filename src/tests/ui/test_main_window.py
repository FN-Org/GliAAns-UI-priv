import pytest
import os
import tempfile
import shutil
import logging
from unittest.mock import Mock, MagicMock, patch
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QMessageBox, QPushButton, QApplication
from PyQt6.QtCore import QSettings, pyqtSignal, QObject, Qt

# Ensure the path is correct to import MainWindow
from main.ui.main_window import MainWindow


# A QObject is necessary to host signals
class SignalHost(QObject):
    language_changed = pyqtSignal(str)


@pytest.fixture(scope="function")
def mock_context(request, qtbot):
    """
    Creates a complete mock context for the MainWindow.
    Runs once per test function.
    """
    # 1. Create a real temporary workspace
    temp_dir = tempfile.mkdtemp()

    # Create some dummy files for the 'clear_folder' test
    open(os.path.join(temp_dir, "file1.txt"), "w").close()
    os.mkdir(os.path.join(temp_dir, "subdir"))

    # 2. Create a real but isolated QSettings
    settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "GliAAnsTest", "GliAAnsTestApp")
    settings.clear()  # Ensures a clean state

    # 3. Signal object
    signal_host = SignalHost()

    # 4. Assemble the context
    context = {
        "language_changed": signal_host.language_changed,
        "settings": settings,
        "workspace_path": temp_dir,
        "create_buttons": lambda: (QPushButton("Back"), QPushButton("Next")),
        "tree_view": MagicMock(),
        "import_page": MagicMock(),
        "return_to_import": Mock(),
        "update_main_buttons": Mock(),

        "_signal_host_ref": signal_host
    }

    # 5. Add teardown (cleanup)
    def cleanup():
        shutil.rmtree(temp_dir)
        settings.clear()

    request.addfinalizer(cleanup)

    return context


@pytest.fixture
def main_window(qtbot, mock_context):
    """
    Fixture that creates the MainWindow and "neutralizes" it for testing.
    """
    window = MainWindow(mock_context)
    qtbot.addWidget(window)

    try:
        window.destroyed.disconnect(QApplication.instance().quit)
    except TypeError:
        pass

    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

    return window

class TestMainWindowSetup:
    """Tests for MainWindow initial configuration"""

    def test_window_initialization(self, main_window):
        """Verify that the window initializes correctly"""
        assert main_window.windowTitle() != ""
        assert main_window.width() >= 950
        assert main_window.height() >= 650  # Corrected from 650 to 700 as per code

    def test_menu_bar_created(self, main_window):
        """Verify that the menu bar is created with all menus"""
        menu_bar = main_window.menuBar()
        assert menu_bar is not None

        menus = [action.menu().title() for action in menu_bar.actions() if action.menu()]
        assert "File" in menus
        assert "Workspace" in menus
        assert "Settings" in menus or "Impostazioni" in menus

    def test_splitter_created(self, main_window):
        """Verify that the splitter has been created"""
        assert main_window.splitter is not None
        assert main_window.splitter.orientation() == QtCore.Qt.Orientation.Horizontal

    def test_footer_with_buttons(self, main_window):
        """Verify that the footer contains the buttons"""
        assert main_window.footer is not None
        assert main_window.next_button is not None
        assert main_window.back_button is not None
        assert isinstance(main_window.next_button, QPushButton)
        assert isinstance(main_window.back_button, QPushButton)

    def test_language_actions_created(self, main_window):
        """Verify that language actions are created"""
        assert "en" in main_window.language_actions
        assert "it" in main_window.language_actions
        assert main_window.language_actions["en"].isCheckable()
        assert main_window.language_actions["it"].isCheckable()


class TestLanguageManagement:
    """Tests for language management"""

    def test_set_language_emits_signal(self, main_window, qtbot):
        """Verify that set_language emits the correct signal"""
        with qtbot.waitSignal(main_window.context["language_changed"], timeout=1000) as blocker:
            main_window.set_language("it")

        assert blocker.args == ["it"]

    def test_set_language_checks_correct_action(self, main_window):
        """Verify that the correct action is checked"""
        main_window.set_language("it")
        assert main_window.language_actions["it"].isChecked()

        main_window.set_language("en")
        assert main_window.language_actions["en"].isChecked()

    def test_language_action_group_exclusive(self, main_window):
        """Verify that only one language can be selected"""
        main_window.language_actions["en"].trigger()
        assert main_window.language_actions["en"].isChecked()
        assert not main_window.language_actions["it"].isChecked()

        main_window.language_actions["it"].trigger()
        assert main_window.language_actions["it"].isChecked()
        assert not main_window.language_actions["en"].isChecked()


class TestWorkspaceOperations:
    """Tests for workspace operations"""

    def test_clear_folder_confirms_deletion(self, main_window, monkeypatch):
        """Verify that confirmation is requested before deleting"""
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.No)

        initial_files = os.listdir(main_window.workspace_path)
        main_window.clear_folder(
            folder_path=main_window.workspace_path,
            folder_name="test",
            return_to_import=False
        )

        # Files should still be present
        assert len(os.listdir(main_window.workspace_path)) == len(initial_files)
        assert len(main_window.threads) == 0  # No threads started

    def test_clear_folder_deletes_on_confirmation(self, main_window, monkeypatch, qtbot):
        """Verify that files are deleted after confirmation"""
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        # 1. Save the INITIAL number of files
        initial_file_count = len(os.listdir(main_window.workspace_path))

        # The workspace has 2 items (file1.txt, subdir)
        assert initial_file_count > 0

        main_window.clear_folder(
            folder_path=main_window.workspace_path,
            folder_name="test",
            return_to_import=False
        )

        # 2. Verify that as many threads were created as there were INITIAL files
        assert len(main_window.threads) == initial_file_count

        # Wait for threads to finish so as not to "pollute" the next test
        for t in main_window.threads:
            t.wait(1000)

    def test_clear_folder_returns_to_import(self, main_window, monkeypatch, qtbot):
        """Verify that return_to_import is called when requested"""
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        main_window.clear_folder(
            folder_path=main_window.workspace_path,
            folder_name="workspace",
            return_to_import=True
        )

        # Wait for threads to finish so as not to "pollute" the next test
        for t in main_window.threads:
            t.wait(1000)

        main_window.context["return_to_import"].assert_called_once()


class TestThreadManagement:
    """Tests for thread management"""

    def test_new_thread_adds_to_list(self, main_window):
        """Verify that a new thread is added to the list"""
        mock_thread = Mock(spec=['error', 'finished', 'start', 'wait'])
        mock_thread.error = Mock()
        mock_thread.error.connect = Mock()
        mock_thread.error.disconnect = Mock()
        mock_thread.finished = Mock()
        mock_thread.finished.connect = Mock()
        mock_thread.finished.disconnect = Mock()

        initial_count = len(main_window.threads)
        main_window.new_thread(mock_thread)

        assert len(main_window.threads) == initial_count + 1
        mock_thread.start.assert_called_once()

    def test_copydelete_thread_error_removes_thread(self, main_window, monkeypatch):
        """Verify that a thread with error is removed"""
        mock_thread = Mock()
        main_window.threads.append(mock_thread)

        monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: None)
        monkeypatch.setattr(main_window, 'sender', lambda: mock_thread)

        main_window.copydelete_thread_error("Test error")

        assert mock_thread not in main_window.threads

    def test_copydelete_thread_success_removes_thread(self, main_window, monkeypatch):
        """Verify that a completed thread is removed"""
        mock_thread = Mock()
        main_window.threads.append(mock_thread)

        monkeypatch.setattr(QMessageBox, 'information', lambda *args, **kwargs: None)
        monkeypatch.setattr(main_window, 'sender', lambda: mock_thread)

        main_window.copydelete_thread_success("Success message", show=True)

        assert mock_thread not in main_window.threads

    def test_close_event_stops_threads(self, main_window, qtbot):
        """Verify that threads are stopped on close"""
        mock_thread1 = Mock(spec=['finished', 'error', 'wait'])
        mock_thread1.finished = Mock()
        mock_thread1.finished.disconnect = Mock()
        mock_thread1.error = Mock()
        mock_thread1.error.disconnect = Mock()
        mock_thread1.wait = Mock()

        mock_thread2 = Mock(spec=['finished', 'error', 'wait'])
        mock_thread2.finished = Mock()
        mock_thread2.finished.disconnect = Mock()
        mock_thread2.error = Mock()
        mock_thread2.error.disconnect = Mock()
        mock_thread2.wait = Mock()

        # Add threads to list
        main_window.threads = [mock_thread1, mock_thread2]

        from PyQt6.QtGui import QCloseEvent
        event = QCloseEvent()
        main_window.closeEvent(event)

        # Verify that methods were called
        mock_thread1.finished.disconnect.assert_called_once()
        mock_thread1.error.disconnect.assert_called_once()
        mock_thread1.wait.assert_called_once()

        mock_thread2.finished.disconnect.assert_called_once()
        mock_thread2.error.disconnect.assert_called_once()
        mock_thread2.wait.assert_called_once()

        assert len(main_window.threads) == 0


class TestDebugLog:
    """Tests for debug log functionality"""

    @patch('main.ui.main_window.set_log_level')
    def test_toggle_debug_log_enables(self, mock_set_log_level, main_window):
        """Verify that debug log can be enabled"""
        main_window.toggle_debug_log(True)

        assert main_window.settings.value("debug_log", type=bool) == True
        mock_set_log_level.assert_called_with(logging.DEBUG)

    @patch('main.ui.main_window.set_log_level')
    def test_toggle_debug_log_disables(self, mock_set_log_level, main_window):
        """Verify that debug log can be disabled"""
        main_window.toggle_debug_log(False)

        assert main_window.settings.value("debug_log", type=bool) == False
        mock_set_log_level.assert_called_with(logging.ERROR)


class TestWidgetManagement:
    """Tests for widget management"""

    def test_set_widgets_first_time(self, main_window, qtbot):
        """Verify initial widget addition"""
        from PyQt6.QtWidgets import QWidget

        left_widget = QWidget()
        left_widget.adjust_tree_columns = Mock()
        left_widget.new_thread = Mock()
        left_widget.new_thread.connect = Mock()

        right_widget = QWidget()

        qtbot.addWidget(left_widget)
        qtbot.addWidget(right_widget)

        main_window.set_widgets(left_widget, right_widget)

        assert main_window.splitter.count() == 2
        assert main_window.left_panel == left_widget
        assert main_window.right_panel == right_widget
        left_widget.new_thread.connect.assert_called_once_with(main_window.new_thread)

    def test_export_file_info_shows_message(self, main_window, monkeypatch):
        """Verify that export_file_info shows an informational message"""
        message_shown = False

        def mock_information(*args, **kwargs):
            nonlocal message_shown
            message_shown = True

        monkeypatch.setattr(QMessageBox, 'information', mock_information)

        main_window.export_file_info()
        assert message_shown


# Integration tests
class TestIntegration:
    """Integration tests to verify the full flow"""

    def test_full_workflow(self, main_window, qtbot):
        """Test full workflow: creation, language change, operations"""
        # Verify initialization (not visible by default)
        assert not main_window.isVisible()

        # Change language
        with qtbot.waitSignal(main_window.context["language_changed"], timeout=1000):
            main_window.set_language("it")
        assert main_window.language_actions["it"].isChecked()

        # Verify that the window is functional
        main_window.show()
        qtbot.waitExposed(main_window)
        assert main_window.isVisible()

        # Close the window
        main_window.close()

        # Wait for the window to be actually hidden
        qtbot.waitUntil(lambda: not main_window.isVisible())
        assert not main_window.isVisible()