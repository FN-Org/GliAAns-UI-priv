import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch, call
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QSettings, pyqtSignal, QObject, Qt, QModelIndex
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QMenu
from PyQt6.QtGui import QFileSystemModel

# Import dal tuo progetto
from ui.ui_workspace_tree_view import WorkspaceTreeView

@pytest.fixture
def tree_view(qtbot, mock_context):
    view = WorkspaceTreeView(mock_context)
    qtbot.addWidget(view)
    return view

class TestWorkspaceTreeViewSetup:
    """Test per l'inizializzazione di WorkspaceTreeView"""

    def test_full_workflow_selection_and_export(self, tree_view, temp_workspace):
        """Test flusso completo: selezione e export"""
        # Seleziona un file
        tree_view.handle_workspace_click()
        assert isinstance(tree_view.selected_files, list)

        # Export dovrebbe richiedere dialog
        nifti_file = os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii")

        with patch('ui.ui_workspace_tree_view.QFileDialog') as MockDialog:
            MockDialog.getSaveFileName.return_value = ("", "")
            tree_view.export_files([nifti_file], is_dir=False)
            MockDialog.getSaveFileName.assert_called_once()

    def test_full_workflow_double_click_nifti(self, tree_view, temp_workspace):
        """Test flusso completo: doppio click su NIfTI"""
        nifti_file = os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii")
        index = tree_view.tree_model.index(nifti_file)

        tree_view.handle_double_click(index)

        # Dovrebbe aprire il viewer
        tree_view.context["open_nifti_viewer"].assert_called_once_with(nifti_file)


def test_initialization(tree_view, temp_workspace):
    """Verifica inizializzazione corretta"""
    assert tree_view.workspace_path == temp_workspace
    assert tree_view.selected_files == []
    assert tree_view.tree_model is not None
    assert isinstance(tree_view.tree_model, QFileSystemModel)


def test_model_root_path(tree_view, temp_workspace):
    """Verifica che il modello punti al workspace"""
    assert tree_view.tree_model.rootPath() == temp_workspace


def test_selection_mode(tree_view):
    """Verifica modalità di selezione estesa"""
    assert tree_view.selectionMode() == QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection


def test_context_menu_policy(tree_view):
    """Verifica policy per context menu"""
    assert tree_view.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_signals_connected(tree_view):
    """Verifica che i signal siano connessi"""
    # I signal dovrebbero essere connessi (difficile testare direttamente)
    assert hasattr(tree_view, 'new_thread')


class TestWorkspaceTreeViewSelection:
    """Test per la gestione delle selezioni"""

    def test_handle_workspace_click_updates_selection(self, tree_view, qtbot):
        """Verifica che il click aggiorni la selezione"""
        with qtbot.waitSignal(tree_view.context["selected_files_signal"], timeout=1000):
            tree_view.handle_workspace_click()

        # Verifica che selected_files sia aggiornato
        assert isinstance(tree_view.selected_files, list)

    def test_selected_files_emits_signal(self, tree_view, signal_emitter, qtbot):
        """Verifica che il signal venga emesso con i file selezionati"""
        with qtbot.waitSignal(signal_emitter.selected_files, timeout=1000) as blocker:
            tree_view.handle_workspace_click()

        assert isinstance(blocker.args[0], list)


class TestWorkspaceTreeViewDoubleClick:
    """Test per gestione doppio click"""

    def test_double_click_on_nifti_opens_viewer(self, tree_view, temp_workspace):
        """Verifica che doppio click su NIfTI apra il viewer"""
        nifti_file = os.path.join(temp_workspace, "brain.nii")
        index = tree_view.tree_model.index(nifti_file)

        tree_view.handle_double_click(index)

        tree_view.context["open_nifti_viewer"].assert_called_once_with(nifti_file)

    def test_double_click_on_nifti_gz_opens_viewer(self, tree_view, temp_workspace):
        """Verifica che .nii.gz apra il viewer"""
        nifti_file = os.path.join(temp_workspace, "scan.nii.gz")
        index = tree_view.tree_model.index(nifti_file)

        tree_view.handle_double_click(index)

        tree_view.context["open_nifti_viewer"].assert_called_once_with(nifti_file)

    def test_double_click_on_regular_file_opens_in_explorer(self, tree_view, temp_workspace):
        """Verifica che file normali si aprano con app di sistema"""
        regular_file = os.path.join(temp_workspace, "test.txt")
        index = tree_view.tree_model.index(regular_file)

        with patch.object(tree_view, '_open_in_explorer') as mock_open:
            tree_view.handle_double_click(index)
            mock_open.assert_called_once_with(regular_file)

    def test_double_click_on_folder_does_nothing(self, tree_view, temp_workspace):
        """Verifica che doppio click su cartella non faccia nulla"""
        folder = os.path.join(temp_workspace, "subfolder")
        os.makedirs(folder)
        index = tree_view.tree_model.index(folder)

        with patch.object(tree_view, '_open_in_explorer') as mock_open:
            tree_view.handle_double_click(index)
            mock_open.assert_not_called()

    def test_double_click_nifti_error_shows_message(self, tree_view, temp_workspace, monkeypatch):
        """Verifica gestione errore apertura NIfTI"""
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
    """Test per gestione colonne"""

    def test_adjust_tree_columns_wide(self, tree_view):
        """Verifica regolazione colonne con finestra larga"""
        tree_view.resize(500, 300)
        tree_view.adjust_tree_columns()

        # Con larghezza > 400, le colonne dovrebbero essere visibili
        for i in range(1, tree_view.tree_model.columnCount()):
            assert not tree_view.isColumnHidden(i)

    def test_adjust_tree_columns_narrow(self, tree_view):
        """Verifica regolazione colonne con finestra stretta"""
        tree_view.resize(300, 300)
        tree_view.adjust_tree_columns()

        # Con larghezza < 400, le colonne dovrebbero essere nascoste
        for i in range(1, tree_view.tree_model.columnCount()):
            assert tree_view.isColumnHidden(i)


class TestWorkspaceTreeViewContextMenu:
    """Test per context menu"""

    def test_workspace_actions_created(self, tree_view):
        """Verifica creazione azioni workspace"""
        menu = QMenu()
        actions = tree_view._add_workspace_actions(menu)

        assert len(actions) == 4
        assert all(isinstance(action, Mock) or hasattr(action, 'text') for action in actions.keys())

    def test_folder_actions_created(self, tree_view, temp_workspace):
        """Verifica creazione azioni cartella"""
        menu = QMenu()
        folder_path = os.path.join(temp_workspace, "folder1")
        actions = tree_view._add_folder_actions(menu, folder_path)

        assert len(actions) == 4  # open, add, remove, export

    def test_file_actions_created(self, tree_view, temp_workspace):
        """Verifica creazione azioni file"""
        menu = QMenu()
        file_path = os.path.join(temp_workspace, "test.txt")
        actions = tree_view._add_file_actions(menu, file_path, is_nifty=False)

        assert len(actions) >= 4  # open, add, remove, export

    def test_nifti_file_actions_include_viewer(self, tree_view, temp_workspace):
        """Verifica che file NIfTI abbiano azione viewer"""
        menu = QMenu()
        nifti_path = os.path.join(temp_workspace, "brain.nii")
        actions = tree_view._add_file_actions(menu, nifti_path, is_nifty=True)

        assert len(actions) >= 5  # include NIfTI viewer action

    def test_multi_file_actions_created(self, tree_view):
        """Verifica creazione azioni multi-file"""
        menu = QMenu()
        actions = tree_view._add_multi_file_actions(menu)

        assert len(actions) == 2  # export, remove


class TestWorkspaceTreeViewFileOperations:
    """Test per operazioni su file"""

    @pytest.fixture
    def temp_source_file(self):
        """File sorgente per test"""
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "source.txt")
        with open(test_file, "w") as f:
            f.write("source content")
        yield test_file
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_add_file_to_workspace_opens_dialog(self, tree_view):
        """Verifica che add_file_to_workspace apra dialog"""
        with patch('ui.ui_workspace_tree_view.QFileDialog') as MockDialog:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = False
            MockDialog.return_value = mock_dialog

            tree_view.add_file_to_workspace(None, False)

            MockDialog.assert_called_once()

    def test_remove_from_workspace_confirms(self, tree_view, temp_workspace, monkeypatch):
        """Verifica richiesta conferma prima di rimuovere"""
        test_file = os.path.join(temp_workspace, "test.txt")

        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.No)

        tree_view.remove_from_workspace([test_file])

        # File dovrebbe esistere ancora
        assert os.path.exists(test_file)

    def test_remove_from_workspace_emits_thread(self, tree_view, temp_workspace, monkeypatch, qtbot):
        """Verifica che remove emetta signal per thread"""
        test_file = os.path.join(temp_workspace, "test.txt")

        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        with qtbot.waitSignal(tree_view.new_thread, timeout=1000):
            tree_view.remove_from_workspace([test_file])

    def test_export_single_file_dialog(self, tree_view, temp_workspace):
        """Verifica export di singolo file"""
        test_file = os.path.join(temp_workspace, "test.txt")

        with patch('ui.ui_workspace_tree_view.QFileDialog') as MockDialog:
            MockDialog.getSaveFileName.return_value = ("", "")

            tree_view.export_files([test_file], is_dir=False)

            MockDialog.getSaveFileName.assert_called_once()

    def test_export_folder_dialog(self, tree_view, temp_workspace):
        """Verifica export di cartella"""
        folder = os.path.join(temp_workspace, "sub-01")

        with patch('ui.ui_workspace_tree_view.QFileDialog') as MockDialog:
            MockDialog.getExistingDirectory.return_value = ""

            tree_view.export_files([folder], is_dir=True)

            MockDialog.getExistingDirectory.assert_called_once()

    def test_export_multiple_files_dialog(self, tree_view, temp_workspace):
        """Verifica export di file multipli"""
        file1 = os.path.join(temp_workspace, "test.txt")
        file2 = os.path.join(temp_workspace, "test2.txt")
        with open(file2, "w") as f:
            f.write("test2")

        with patch('ui.ui_workspace_tree_view.QFileDialog') as MockDialog:
            MockDialog.getExistingDirectory.return_value = ""

            tree_view.export_files([file1, file2], is_dir=False)

            MockDialog.getExistingDirectory.assert_called_once()


class TestWorkspaceTreeViewNIfTIOperations:
    """Test specifici per file NIfTI"""

    def test_open_nifti_calls_viewer(self, tree_view, temp_workspace):
        """Verifica apertura NIfTI con viewer"""
        nifti_file = os.path.join(temp_workspace, "brain.nii")

        tree_view._open_nifti(nifti_file)

        tree_view.context["open_nifti_viewer"].assert_called_once_with(nifti_file)

    def test_open_nifti_error_shows_message(self, tree_view, temp_workspace, monkeypatch):
        """Verifica gestione errore apertura NIfTI"""
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
        """Verifica richiesta inclusione JSON"""
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
        """Verifica ritorno vuoto su cancellazione"""
        monkeypatch.setattr(QMessageBox, 'information',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Cancel)

        result = tree_view._including_json("brain", temp_workspace)

        assert result == ""

    def test_including_json_returns_empty_if_not_exists(self, tree_view, temp_workspace, monkeypatch):
        """Verifica ritorno vuoto se JSON non esiste"""
        monkeypatch.setattr(QMessageBox, 'information',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

        result = tree_view._including_json("nonexistent", temp_workspace)

        assert result == ""


class TestWorkspaceTreeViewExplorer:
    """Test per apertura in explorer"""

    def test_open_in_explorer_success(self, tree_view, temp_workspace):
        """Verifica apertura in explorer con successo"""
        test_file = os.path.join(temp_workspace, "test.txt")

        with patch('ui.ui_workspace_tree_view.QDesktopServices') as MockServices:
            MockServices.openUrl.return_value = True

            tree_view._open_in_explorer(test_file)

            MockServices.openUrl.assert_called_once()

    def test_open_in_explorer_no_app_shows_warning(self, tree_view, temp_workspace, monkeypatch):
        """Verifica warning se nessuna app predefinita"""
        test_file = os.path.join(temp_workspace, "test.txt")

        with patch('ui.ui_workspace_tree_view.QDesktopServices') as MockServices:
            MockServices.openUrl.return_value = False

            warning_shown = False

            def mock_warning(*args, **kwargs):
                nonlocal warning_shown
                warning_shown = True

            monkeypatch.setattr(QMessageBox, 'warning', mock_warning)

            tree_view._open_in_explorer(test_file)

            assert warning_shown

    def test_open_in_explorer_exception_shows_error(self, tree_view, temp_workspace, monkeypatch):
        """Verifica gestione eccezione"""
        test_file = os.path.join(temp_workspace, "test.txt")

        with patch('ui.ui_workspace_tree_view.QDesktopServices') as MockServices:
            MockServices.openUrl.side_effect = Exception("Error")

            error_shown = False

            def mock_critical(*args, **kwargs):
                nonlocal error_shown
                error_shown = True

            monkeypatch.setattr(QMessageBox, 'critical', mock_critical)

            tree_view._open_in_explorer(test_file)

            assert error_shown

class TestWorkspaceTreeViewRoleDialog:
    """Test per dialog di selezione ruolo"""

    def test_open_role_dialog_creates_dialog(self, tree_view, temp_workspace):
        """Verifica creazione dialog ruolo"""
        with patch('ui.ui_workspace_tree_view.FileRoleDialog') as MockDialog:
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
        """Verifica che su accept venga emesso thread"""
        with patch('ui.ui_workspace_tree_view.FileRoleDialog') as MockDialog:
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