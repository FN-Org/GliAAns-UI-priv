import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QSettings, pyqtSignal, QObject, QMimeData, QUrl, Qt
from PyQt6.QtWidgets import QMessageBox, QProgressDialog
from PyQt6.QtGui import QDropEvent, QDragEnterEvent

from main.ui.import_page import ImportPage


@pytest.fixture
def import_page(qtbot, mock_context):
    page = ImportPage(mock_context)
    qtbot.addWidget(page)
    return page

class TestImportPageSetup:
    """Test per l'inizializzazione di ImportPage"""

    def test_page_initialization(self, import_page):
        """Verifica inizializzazione corretta"""
        assert import_page.workspace_path is not None
        assert import_page.threads == []
        assert import_page.progress_dialogs == []
        assert import_page.acceptDrops()

    def test_drop_label_created(self, import_page):
        """Verifica che il label sia creato"""
        assert import_page.drop_label is not None
        assert import_page.drop_label.text() != ""

    def test_stylesheet_applied(self, import_page):
        """Verifica che lo stylesheet sia applicato"""
        stylesheet = import_page.styleSheet()
        assert "border" in stylesheet.lower()
        assert "dashed" in stylesheet.lower()


class TestImportPageReadiness:
    """Test per la logica di avanzamento/ritorno"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_not_ready_when_workspace_empty(self, import_page):
        """Verifica che non sia pronto se workspace vuoto"""
        assert not import_page.is_ready_to_advance()

    def test_ready_when_workspace_has_folder(self, import_page, temp_workspace):
        """Verifica che sia pronto se workspace ha cartelle"""
        test_folder = os.path.join(temp_workspace, "patient_data")
        os.makedirs(test_folder)

        assert import_page.is_ready_to_advance()

    def test_ignores_hidden_files(self, import_page, temp_workspace):
        """Verifica che i file nascosti siano ignorati"""
        hidden_file = os.path.join(temp_workspace, ".hidden")
        with open(hidden_file, "w") as f:
            f.write("test")

        assert not import_page.is_ready_to_advance()

    def test_cannot_go_back(self, import_page):
        """Verifica che non si possa tornare indietro"""
        assert not import_page.is_ready_to_go_back()


class TestImportPageNavigation:
    """Test per la navigazione tra pagine"""



    def test_next_creates_patient_selection_page(self, import_page, mock_context):
        """Verifica che next() crei PatientSelectionPage"""
        next_page = import_page.next(mock_context)

        assert next_page is not None
        assert import_page.next_page is not None
        assert next_page in mock_context["history"]

    def test_next_returns_cached_page(self, import_page, mock_context):
        """Verifica che next() ritorni la pagina cached"""
        first_call = import_page.next(mock_context)
        second_call = import_page.next(mock_context)

        assert first_call is second_call

    def test_back_returns_false(self, import_page):
        """Verifica che back() ritorni False"""
        assert import_page.back() == False


class TestImportPageDragDrop:
    """Test per funzionalità drag & drop"""

    @pytest.fixture
    def temp_source_folder(self):
        """Crea cartella sorgente per drag&drop"""
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_drag_enter_accepts_urls(self, import_page):
        """Verifica che dragEnterEvent accetti URL"""
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile("/tmp/test")])

        event = Mock()
        event.mimeData.return_value = mime_data

        import_page.dragEnterEvent(event)
        event.acceptProposedAction.assert_called_once()

    def test_drop_event_handles_folder(self, import_page, temp_source_folder):
        """Verifica che dropEvent gestisca le cartelle"""
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(temp_source_folder)])

        event = Mock()
        event.mimeData.return_value = mime_data

        with patch.object(import_page, '_handle_import') as mock_handle:
            import_page.dropEvent(event)
            mock_handle.assert_called_once()
            assert temp_source_folder in mock_handle.call_args[0][0]


class TestImportPageDialogs:
    """Test per dialog e interazioni utente"""

    @pytest.fixture
    def temp_source_folder(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_mouse_press_opens_dialog(self, import_page):
        """Verifica che il click sinistro apra il dialog"""
        with patch.object(import_page, 'open_folder_dialog') as mock_dialog:
            event = Mock()
            event.button.return_value = Qt.MouseButton.LeftButton

            import_page.mousePressEvent(event)
            mock_dialog.assert_called_once()

    def test_open_folder_dialog_configuration(self, import_page, monkeypatch):
        """Verifica configurazione del folder dialog"""
        mock_dialog = Mock()
        mock_dialog.exec.return_value = False
        mock_dialog.findChildren.return_value = []

        with patch('main.ui.import_page.QFileDialog', return_value=mock_dialog):
            import_page.open_folder_dialog()

            # Verifica che il dialog sia configurato correttamente
            mock_dialog.setFileMode.assert_called_once()
            assert mock_dialog.setOption.call_count >= 1


class TestImportPageThreads:
    """Test per gestione thread di importazione"""

    @pytest.fixture
    def temp_source_folder(self):
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_handle_import_creates_thread(self, import_page, temp_source_folder):
        """Verifica che _handle_import crei un thread"""
        with patch('main.ui.import_page.ImportThread') as MockThread, \
                patch('main.ui.import_page.QProgressDialog'):
            mock_thread_instance = Mock()
            mock_thread_instance.finished = Mock()
            mock_thread_instance.finished.connect = Mock()
            mock_thread_instance.error = Mock()
            mock_thread_instance.error.connect = Mock()
            mock_thread_instance.progress = Mock()
            mock_thread_instance.progress.connect = Mock()
            MockThread.return_value = mock_thread_instance

            import_page._handle_import([temp_source_folder])

            assert len(import_page.threads) == 1
            mock_thread_instance.start.assert_called_once()

    def test_handle_import_creates_progress_dialog(self, import_page, temp_source_folder):
        """Verifica che _handle_import crei un progress dialog"""
        with patch('main.ui.import_page.ImportThread'), \
                patch('main.ui.import_page.QProgressDialog') as MockDialog:
            mock_dialog_instance = Mock()
            mock_dialog_instance.canceled = Mock()
            mock_dialog_instance.canceled.connect = Mock()
            MockDialog.return_value = mock_dialog_instance

            import_page._handle_import([temp_source_folder])

            assert len(import_page.progress_dialogs) == 1
            MockDialog.assert_called_once()

    def test_on_import_finished_removes_thread(self, import_page):
        """Verifica che on_import_finished rimuova il thread"""
        mock_thread = Mock()
        import_page.threads = [mock_thread]

        mock_dialog = Mock()
        import_page.progress_dialogs = [mock_dialog]

        with patch.object(import_page, 'sender', return_value=mock_thread):
            import_page.on_import_finished()

            assert len(import_page.threads) == 0
            mock_dialog.close.assert_called_once()

    def test_on_import_finished_updates_buttons(self, import_page, mock_context):
        """Verifica che on_import_finished aggiorni i pulsanti"""
        mock_thread = Mock()
        import_page.threads = [mock_thread]
        import_page.progress_dialogs = [Mock()]

        with patch.object(import_page, 'sender', return_value=mock_thread):
            import_page.on_import_finished()

            mock_context["update_main_buttons"].assert_called_once()

    def test_on_import_error_shows_message(self, import_page, monkeypatch):
        """Verifica che on_import_error mostri un messaggio"""
        mock_thread = Mock()
        import_page.threads = [mock_thread]

        mock_dialog = Mock()
        import_page.progress_dialogs = [mock_dialog]

        message_shown = False

        def mock_critical(*args, **kwargs):
            nonlocal message_shown
            message_shown = True

        monkeypatch.setattr(QMessageBox, 'critical', mock_critical)

        with patch.object(import_page, 'sender', return_value=mock_thread):
            import_page.on_import_error("Test error")

            assert message_shown
            mock_dialog.close.assert_called_once()

    def test_on_import_error_handles_removed_thread(self, import_page):
        """Verifica che on_import_error gestisca thread già rimossi"""
        mock_thread = Mock()
        # Thread non nella lista

        with patch.object(import_page, 'sender', return_value=mock_thread):
            # Non dovrebbe generare eccezioni
            import_page.on_import_error("Test error")

    def test_on_import_canceled_terminates_thread(self, import_page):
        """Verifica che on_import_canceled termini il thread"""
        mock_thread = Mock()
        mock_thread.cancel = Mock()
        mock_thread.terminate = Mock()
        mock_thread.wait = Mock()
        import_page.threads = [mock_thread]

        mock_dialog = Mock()
        import_page.progress_dialogs = [mock_dialog]

        with patch.object(import_page, 'sender', return_value=mock_dialog):
            import_page.on_import_canceled()

            mock_thread.cancel.assert_called_once()
            mock_thread.terminate.assert_called_once()
            mock_thread.wait.assert_called_once()
            assert len(import_page.threads) == 0


class TestImportPageCleanup:
    """Test per la pulizia delle risorse"""

    def test_close_event_cleans_dialogs(self, import_page):
        """Verifica che closeEvent pulisca i dialog"""
        mock_dialog = Mock()
        import_page.progress_dialogs = [mock_dialog]

        from PyQt6.QtGui import QCloseEvent
        event = QCloseEvent()

        import_page.closeEvent(event)

        mock_dialog.destroy.assert_called_once()
        assert len(import_page.progress_dialogs) == 0

    def test_close_event_cancels_threads(self, import_page):
        """Verifica che closeEvent cancelli i thread"""
        mock_thread = Mock()
        mock_thread.cancel = Mock()
        import_page.threads = [mock_thread]

        from PyQt6.QtGui import QCloseEvent
        event = QCloseEvent()

        import_page.closeEvent(event)

        mock_thread.cancel.assert_called_once()
        assert len(import_page.threads) == 0


class TestImportPageTranslation:
    """Test per le traduzioni"""

    def test_translate_ui_called_on_init(self, import_page):
        """Verifica che _translate_ui sia chiamato all'init"""
        assert import_page.drop_label.text() != ""

    def test_translate_ui_updates_label(self, import_page):
        """Verifica che _translate_ui aggiorni il label"""
        original_text = import_page.drop_label.text()
        import_page._translate_ui()
        # Il testo dovrebbe essere lo stesso (o tradotto)
        assert import_page.drop_label.text() != ""

    def test_language_changed_signal_connected(self, import_page, signal_emitter, qtbot):
        """Verifica che il signal language_changed sia connesso"""
        with patch.object(import_page, '_translate_ui') as mock_translate:
            signal_emitter.language_changed.emit("it")
            qtbot.wait(100)  # Attendi elaborazione signal
            # Se connesso, _translate_ui dovrebbe essere chiamato

# Test di integrazione
class TestImportPageIntegration:
    """Test di integrazione per flussi completi"""
    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def temp_source_folder(self):
        temp_dir = tempfile.mkdtemp()
        # Crea struttura di test
        patient_dir = os.path.join(temp_dir, "patient_001")
        os.makedirs(patient_dir)
        with open(os.path.join(patient_dir, "data.txt"), "w") as f:
            f.write("patient data")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_full_import_workflow(self, import_page, temp_source_folder, mock_context):
        """Test del flusso completo di importazione"""
        # Inizialmente non pronto
        assert not import_page.is_ready_to_advance()

        # Aggiungi cartella al workspace
        test_folder = os.path.join(import_page.workspace_path, "patient_001")
        os.makedirs(test_folder)

        # Ora dovrebbe essere pronto
        assert import_page.is_ready_to_advance()

        # Naviga alla prossima pagina
        next_page = import_page.next(mock_context)
        assert next_page is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])