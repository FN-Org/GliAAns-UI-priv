import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch, call
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QSettings, pyqtSignal, QObject, Qt, QModelIndex
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QMenu
from PyQt6.QtGui import QFileSystemModel

from main.ui.workspace_tree_view import WorkspaceTreeView


@pytest.fixture
def tree_view(qtbot, mock_context):
    view = WorkspaceTreeView(mock_context)
    qtbot.addWidget(view)
    return view


class TestWorkspaceTreeViewSetup:
    """Tests for WorkspaceTreeView initialization and full workflows."""

    def test_full_workflow_selection_and_export(self, tree_view, temp_workspace):
        """Full workflow: file selection and export."""
        tree_view.handle_workspace_click()
        assert isinstance(tree_view.selected_files, list)

        nifti_file = os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii")

        with patch('main.ui.workspace_tree_view.QFileDialog') as MockDialog:
            MockDialog.getSaveFileName.return_value = ("", "")
            tree_view.export_files([nifti_file], is_dir=False)
            MockDialog.getSaveFileName.assert_called_once()

    def test_full_workflow_double_click_nifti(self, tree_view, temp_workspace):
        """Full workflow: double-click on NIfTI file should open viewer."""
        nifti_file = os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii")
        index = tree_view.tree_model.index(nifti_file)

        tree_view.handle_double_click(index)
        tree_view.context["open_nifti_viewer"].assert_called_once_with(nifti_file)


def test_initialization(tree_view, temp_workspace):
    """Verify proper initialization of the tree view."""
    assert tree_view.workspace_path == temp_workspace
    assert tree_view.selected_files == []
    assert isinstance(tree_view.tree_model, QFileSystemModel)


def test_model_root_path(tree_view, temp_workspace):
    """Ensure the model points to the workspace path."""
    assert tree_view.tree_model.rootPath() == temp_workspace


def test_selection_mode(tree_view):
    """Check that extended selection mode is enabled."""
    assert tree_view.selectionMode() == QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection


def test_context_menu_policy(tree_view):
    """Check that the context menu policy is set correctly."""
    assert tree_view.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_signals_connected(tree_view):
    """Verify that required signals are connected."""
    assert hasattr(tree_view, 'new_thread')


class TestWorkspaceTreeViewSelection:
    """Tests for selection handling."""

    def test_handle_workspace_click_updates_selection(self, tree_view, qtbot):
        """Clicking in the workspace should update selected files."""
        with qtbot.waitSignal(tree_view.context["selected_files_signal"], timeout=1000):
            tree_view.handle_workspace_click()
        assert isinstance(tree_view.selected_files, list)

    def test_selected_files_emits_signal(self, tree_view, signal_emitter, qtbot):
        """Ensure that selection emits the correct signal."""
        with qtbot.waitSignal(signal_emitter.selected_files, timeout=1000) as blocker:
            tree_view.handle_workspace_click()
        assert isinstance(blocker.args[0], list)


class TestWorkspaceTreeViewDoubleClick:
    """Tests for handling double-click actions."""

    def test_double_click_on_nifti_opens_viewer(self, tree_view, temp_workspace):
        """Double-clicking a .nii file should open the viewer."""
        nifti_file = os.path.join(temp_workspace, "brain.nii")
        index = tree_view.tree_model.index(nifti_file)
        tree_view.handle_double_click(index)
        tree_view.context["open_nifti_viewer"].assert_called_once_with(nifti_file)

    def test_double_click_on_nifti_gz_opens_viewer(self, tree_view, temp_workspace):
        """Double-clicking a .nii.gz file should open the viewer."""
        nifti_file = os.path.join(temp_workspace, "scan.nii.gz")
        index = tree_view.tree_model.index(nifti_file)
        tree_view.handle_double_click(index)
        tree_view.context["open_nifti_viewer"].assert_called_once_with(nifti_file)

    def test_double_click_on_regular_file_opens_in_explorer(self, tree_view, temp_workspace):
        """Double-clicking a regular file should open it with the default app."""
        regular_file = os.path.join(temp_workspace, "test.txt")
        index = tree_view.tree_model.index(regular_file)
        with patch.object(tree_view, '_open_in_explorer') as mock_open:
            tree_view.handle_double_click(index)
            mock_open.assert_called_once_with(regular_file)

    def test_double_click_on_folder_does_nothing(self, tree_view, temp_workspace):
        """Double-clicking a folder should not trigger any action."""
        folder = os.path.join(temp_workspace, "subfolder")
        os.makedirs(folder)
        index = tree_view.tree_model.index(folder)
        with patch.object(tree_view, '_open_in_explorer') as mock_open:
            tree_view.handle_double_click(index)
            mock_open.assert_not_called()

    def test_double_click_nifti_error_shows_message(self, tree_view, temp_workspace, monkeypatch):
        """If opening NIfTI fails, an error message should be shown."""
        tree_view.context["open_nifti_viewer"].side_effect = Exception("Viewer error")
        nifti_file = os.path.join(temp_workspace, "brain.nii")
        index = tree_view.tree_model.index(nifti_file)
        message_shown = False

        def mock_critical(*args, **kwargs):
            nonlocal message_shown
            message_shown = True

        monkeypatch.setattr(QMessageBox, 'critical', mock_critical)
        tree_view.handle_double_click(index)
        assert message_shown


class TestWorkspaceTreeViewColumns:
    """Tests for column visibility adjustments."""

    def test_adjust_tree_columns_wide(self, tree_view):
        """Columns should be visible when the window is wide."""
        tree_view.resize(500, 300)
        tree_view.adjust_tree_columns()
        for i in range(1, tree_view.tree_model.columnCount()):
            assert not tree_view.isColumnHidden(i)

    def test_adjust_tree_columns_narrow(self, tree_view):
        """Columns should be hidden when the window is narrow."""
        tree_view.resize(300, 300)
        tree_view.adjust_tree_columns()
        for i in range(1, tree_view.tree_model.columnCount()):
            assert tree_view.isColumnHidden(i)


class TestWorkspaceTreeViewContextMenu:
    """Tests for context menu creation."""

    def test_workspace_actions_created(self, tree_view):
        """Workspace-level context actions should be created."""
        menu = QMenu()
        actions = tree_view._add_workspace_actions(menu)
        assert len(actions) == 4
        assert all(isinstance(action, Mock) or hasattr(action, 'text') for action in actions.keys())

    def test_folder_actions_created(self, tree_view, temp_workspace):
        """Folder-level context actions should be created."""
        menu = QMenu()
        folder_path = os.path.join(temp_workspace, "folder1")
        actions = tree_view._add_folder_actions(menu, folder_path)
        assert len(actions) == 4

    def test_file_actions_created(self, tree_view, temp_workspace):
        """File-level context actions should be created."""
        menu = QMenu()
        file_path = os.path.join(temp_workspace, "test.txt")
        actions = tree_view._add_file_actions(menu, file_path, is_nifty=False)
        assert len(actions) >= 4

    def test_nifti_file_actions_include_viewer(self, tree_view, temp_workspace):
        """NIfTI files should include the viewer action."""
        menu = QMenu()
        nifti_path = os.path.join(temp_workspace, "brain.nii")
        actions = tree_view._add_file_actions(menu, nifti_path, is_nifty=True)
        assert len(actions) >= 5

    def test_multi_file_actions_created(self, tree_view):
        """Multi-file context actions should be created."""
        menu = QMenu()
        actions = tree_view._add_multi_file_actions(menu)
        assert len(actions) == 2


class TestWorkspaceTreeViewFileOperations:
    """Tests for file-related operations."""

    @pytest.fixture
    def temp_source_file(self):
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "source.txt")
        with open(test_file, "w") as f:
            f.write("source content")
        yield test_file
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_add_file_to_workspace_opens_dialog(self, tree_view):
        """Adding a file to the workspace should open a dialog."""
        with patch('main.ui.workspace_tree_view.QFileDialog') as MockDialog:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = False
            MockDialog.return_value = mock_dialog
            tree_view.add_file_to_workspace(None, False)
            MockDialog.assert_called_once()

    def test_remove_from_workspace_confirms(self, tree_view, temp_workspace, monkeypatch):
        """Removing a file should ask for confirmation."""
        test_file = os.path.join(temp_workspace, "test.txt")
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.No)
        tree_view.remove_from_workspace([test_file])
        assert os.path.exists(test_file)

    def test_remove_from_workspace_emits_thread(self, tree_view, temp_workspace, monkeypatch, qtbot):
        """Confirmed removal should emit a thread signal."""
        test_file = os.path.join(temp_workspace, "test.txt")
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        with qtbot.waitSignal(tree_view.new_thread, timeout=1000):
            tree_view.remove_from_workspace([test_file])

    def test_export_single_file_dialog(self, tree_view, temp_workspace):
        """Exporting a single file should open a save dialog."""
        test_file = os.path.join(temp_workspace, "test.txt")
        with patch('main.ui.workspace_tree_view.QFileDialog') as MockDialog:
            MockDialog.getSaveFileName.return_value = ("", "")
            tree_view.export_files([test_file], is_dir=False)
            MockDialog.getSaveFileName.assert_called_once()

    def test_export_folder_dialog(self, tree_view, temp_workspace):
        """Exporting a folder should open a directory dialog."""
        folder = os.path.join(temp_workspace, "sub-01")
        with patch('main.ui.workspace_tree_view.QFileDialog') as MockDialog:
            MockDialog.getExistingDirectory.return_value = ""
            tree_view.export_files([folder], is_dir=True)
            MockDialog.getExistingDirectory.assert_called_once()

    def test_export_multiple_files_dialog(self, tree_view, temp_workspace):
        """Exporting multiple files should open a directory dialog."""
        file1 = os.path.join(temp_workspace, "test.txt")
        file2 = os.path.join(temp_workspace, "test2.txt")
        with open(file2, "w") as f:
            f.write("test2")
        with patch('main.ui.workspace_tree_view.QFileDialog') as MockDialog:
            MockDialog.getExistingDirectory.return_value = ""
            tree_view.export_files([file1, file2], is_dir=False)
            MockDialog.getExistingDirectory.assert_called_once()


class TestWorkspaceTreeViewNIfTIOperations:
    """Tests specific to NIfTI file handling."""

    def test_open_nifti_calls_viewer(self, tree_view, temp_workspace):
        """Opening a NIfTI file should call the viewer."""
        nifti_file = os.path.join(temp_workspace, "brain.nii")
        tree_view._open_nifti(nifti_file)
        tree_view.context["open_nifti_viewer"].assert_called_once_with(nifti_file)

    def test_open_nifti_error_shows_message(self, tree_view, temp_workspace, monkeypatch):
        """An error while opening NIfTI should show a critical message."""
        tree_view.context["open_nifti_viewer"].side_effect = Exception("Error")
        nifti_file = os.path.join(temp_workspace, "brain.nii")
        message_shown = False

        def mock_critical(*args, **kwargs):
            nonlocal message_shown
            message_shown = True

        monkeypatch.setattr(QMessageBox, 'critical', mock_critical)
        tree_view._open_nifti(nifti_file)
        assert message_shown

    def test_including_json_asks_user(self, tree_view, temp_workspace, monkeypatch):
        """User should be prompted about including a related JSON file."""
        asked = False

        def mock_information(*args, **kwargs):
            nonlocal asked
            asked = True
            return QMessageBox.StandardButton.Ok

        monkeypatch.setattr(QMessageBox, 'information', mock_information)
        result = tree_view._including_json("brain", temp_workspace)
        assert asked
        assert result.endswith("brain.json")

    def test_including_json_returns_empty_on_cancel(self, tree_view, temp_workspace, monkeypatch):
        """If user cancels, the function should return an empty string."""
        monkeypatch.setattr(QMessageBox, 'information',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Cancel)
        result = tree_view._including_json("brain", temp_workspace)
        assert result == ""

    def test_including_json_returns_empty_if_not_exists(self, tree_view, temp_workspace, monkeypatch):
        """If JSON does not exist, return an empty string."""
        monkeypatch.setattr(QMessageBox, 'information',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
        result = tree_view._including_json("nonexistent", temp_workspace)
        assert result == ""


class TestWorkspaceTreeViewExplorer:
    """Tests for file opening in system explorer."""

    def test_open_in_explorer_success(self, tree_view, temp_workspace):
        """Opening a file should succeed if an app is available."""
        test_file = os.path.join(temp_workspace, "test.txt")
        with patch('main.ui.workspace_tree_view.QDesktopServices') as MockServices:
            MockServices.openUrl.return_value = True
            tree_view._open_in_explorer(test_file)
            MockServices.openUrl.assert_called_once()

    def test_open_in_explorer_no_app_shows_warning(self, tree_view, temp_workspace, monkeypatch):
        """If no default app exists, a warning should be shown."""
        test_file = os.path.join(temp_workspace, "test.txt")
        with patch('main.ui.workspace_tree_view.QDesktopServices') as MockServices:
            MockServices.openUrl.return_value = False
            warning_shown = False

            def mock_warning(*args, **kwargs):
                nonlocal warning_shown
                warning_shown = True

            monkeypatch.setattr(QMessageBox, 'warning', mock_warning)
            tree_view._open_in_explorer(test_file)
            assert warning_shown

    def test_open_in_explorer_exception_shows_error(self, tree_view, temp_workspace, monkeypatch):
        """If an exception occurs, a critical message should be shown."""
        test_file = os.path.join(temp_workspace, "test.txt")
        with patch('main.ui.workspace_tree_view.QDesktopServices') as MockServices:
            MockServices.openUrl.side_effect = Exception("Error")
            error_shown = False

            def mock_critical(*args, **kwargs):
                nonlocal error_shown
                error_shown = True

            monkeypatch.setattr(QMessageBox, 'critical', mock_critical)
            tree_view._open_in_explorer(test_file)
            assert error_shown


class TestWorkspaceTreeViewRoleDialog:
    """Tests for role selection dialog behavior."""

    def test_open_role_dialog_creates_dialog(self, tree_view, temp_workspace):
        """Opening the role dialog should instantiate the dialog."""
        with patch('main.ui.workspace_tree_view.FileRoleDialog') as MockDialog:
            mock_dialog_instance = Mock()
            mock_dialog_instance.exec.return_value = False
            MockDialog.return_value = mock_dialog_instance
            tree_view.open_role_dialog(
                files=["test.nii"],
                folder_path=temp_workspace,
                subj="sub-01"
            )
            MockDialog.assert_called_once()

    def test_open_role_dialog_on_accept_emits_thread(self, tree_view, temp_workspace, qtbot):
        """Accepting the role dialog should emit a thread signal."""
        with patch('main.ui.workspace_tree_view.FileRoleDialog') as MockDialog:
            mock_dialog_instance = Mock()
            mock_dialog_instance.exec.return_value = True
            mock_dialog_instance.get_relative_path.return_value = "anat"
            MockDialog.return_value = mock_dialog_instance

            with qtbot.waitSignal(tree_view.new_thread, timeout=1000):
                tree_view.open_role_dialog(
                    files=["test.nii"],
                    folder_path=temp_workspace,
                    subj="sub-01"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
