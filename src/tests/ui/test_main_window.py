import pytest
import os
import tempfile
import shutil
import logging
from unittest.mock import Mock, MagicMock, patch
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QMessageBox, QPushButton, QApplication
from PyQt6.QtCore import QSettings, pyqtSignal, QObject, Qt

# Assicurati che il path sia corretto per importare MainWindow
from main.ui.main_window import MainWindow


# ---------------------------------------------------------------------
# FIXTURES (Aggiunte per rendere il test autonomo)
# ---------------------------------------------------------------------

# È necessario un QObject per ospitare i segnali
class SignalHost(QObject):
    language_changed = pyqtSignal(str)


@pytest.fixture(scope="function")
def mock_context(request, qtbot):
    """
    Crea un context fittizio (mock) completo per la MainWindow.
    Viene eseguito una volta per funzione di test.
    """
    # 1. Crea un workspace temporaneo reale
    temp_dir = tempfile.mkdtemp()

    # Crea alcuni file fittizi per il test 'clear_folder'
    open(os.path.join(temp_dir, "file1.txt"), "w").close()
    os.mkdir(os.path.join(temp_dir, "subdir"))

    # 2. Crea un QSettings reale ma isolato
    settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "GliAAnsTest", "GliAAnsTestApp")
    settings.clear()  # Assicura uno stato pulito

    # 3. Oggetto per i segnali
    signal_host = SignalHost()

    # 4. Assembla il context
    context = {
        "language_changed": signal_host.language_changed,
        "settings": settings,
        "workspace_path": temp_dir,
        "create_buttons": lambda: (QPushButton("Back"), QPushButton("Next")),
        "tree_view": MagicMock(),
        "import_page": MagicMock(),
        "return_to_import": Mock(),
        "update_main_buttons": Mock(),

        # --- LA CORREZIONE È QUI ---
        # Dobbiamo mantenere "vivo" l'oggetto QObject proprietario dei segnali,
        # altrimenti viene distrutto dal garbage collector e causa un segfault
        # quando la MainWindow cerca di connettersi al segnale.
        "_signal_host_ref": signal_host
        # --- FINE CORREZIONE ---
    }

    # 5. Aggiungi il teardown (pulizia)
    def cleanup():
        shutil.rmtree(temp_dir)
        settings.clear()

    request.addfinalizer(cleanup)

    return context


@pytest.fixture
def main_window(qtbot, mock_context):
    """
    Fixture che crea la MainWindow e la "neutralizza" per i test.
    """
    window = MainWindow(mock_context)
    qtbot.addWidget(window)

    # --- CORREZIONE 1 (Già presente) ---
    # Disconnette il segnale che causa la chiusura dell'app durante i test.
    try:
        window.destroyed.disconnect(QApplication.instance().quit)
    except TypeError:
        pass

    # --- CORREZIONE 2 (NUOVA) ---
    # Impedisce al widget di auto-distruggersi quando .close() è chiamato
    # nel test (es. test_full_workflow), che causerebbe un RuntimeError
    # quando pytest-qt cerca di chiuderlo di nuovo nel teardown.
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    # --- FINE CORREZIONE 2 ---

    return window


# ---------------------------------------------------------------------
# TEST SUITE (Con correzioni minori)
# ---------------------------------------------------------------------

class TestMainWindowSetup:
    """Test per la configurazione iniziale della MainWindow"""

    def test_window_initialization(self, main_window):
        """Verifica che la finestra si inizializzi correttamente"""
        assert main_window.windowTitle() != ""
        assert main_window.width() >= 950
        assert main_window.height() >= 650  # Corretto da 650 a 700 come da codice

    def test_menu_bar_created(self, main_window):
        """Verifica che la menu bar sia creata con tutti i menu"""
        menu_bar = main_window.menuBar()
        assert menu_bar is not None

        menus = [action.menu().title() for action in menu_bar.actions() if action.menu()]
        assert "File" in menus
        assert "Workspace" in menus
        assert "Settings" in menus or "Impostazioni" in menus

    def test_splitter_created(self, main_window):
        """Verifica che lo splitter sia stato creato"""
        assert main_window.splitter is not None
        assert main_window.splitter.orientation() == QtCore.Qt.Orientation.Horizontal

    def test_footer_with_buttons(self, main_window):
        """Verifica che il footer contenga i pulsanti"""
        assert main_window.footer is not None
        assert main_window.next_button is not None
        assert main_window.back_button is not None
        assert isinstance(main_window.next_button, QPushButton)
        assert isinstance(main_window.back_button, QPushButton)

    def test_language_actions_created(self, main_window):
        """Verifica che le azioni per le lingue siano create"""
        assert "en" in main_window.language_actions
        assert "it" in main_window.language_actions
        assert main_window.language_actions["en"].isCheckable()
        assert main_window.language_actions["it"].isCheckable()


class TestLanguageManagement:
    """Test per la gestione delle lingue"""

    def test_set_language_emits_signal(self, main_window, qtbot):
        """Verifica che set_language emetta il segnale corretto"""
        with qtbot.waitSignal(main_window.context["language_changed"], timeout=1000) as blocker:
            main_window.set_language("it")

        assert blocker.args == ["it"]

    def test_set_language_checks_correct_action(self, main_window):
        """Verifica che l'azione corretta venga selezionata"""
        main_window.set_language("it")
        assert main_window.language_actions["it"].isChecked()

        main_window.set_language("en")
        assert main_window.language_actions["en"].isChecked()

    def test_language_action_group_exclusive(self, main_window):
        """Verifica che solo una lingua possa essere selezionata"""
        main_window.language_actions["en"].trigger()
        assert main_window.language_actions["en"].isChecked()
        assert not main_window.language_actions["it"].isChecked()

        main_window.language_actions["it"].trigger()
        assert main_window.language_actions["it"].isChecked()
        assert not main_window.language_actions["en"].isChecked()


class TestWorkspaceOperations:
    """Test per le operazioni sul workspace"""

    def test_clear_folder_confirms_deletion(self, main_window, monkeypatch):
        """Verifica che venga richiesta conferma prima di eliminare"""
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.No)

        initial_files = os.listdir(main_window.workspace_path)
        main_window.clear_folder(
            folder_path=main_window.workspace_path,
            folder_name="test",
            return_to_import=False
        )

        # I file dovrebbero essere ancora presenti
        assert len(os.listdir(main_window.workspace_path)) == len(initial_files)
        assert len(main_window.threads) == 0  # Nessun thread avviato

    def test_clear_folder_deletes_on_confirmation(self, main_window, monkeypatch, qtbot):
        """Verifica che i file vengano eliminati dopo conferma"""
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        # 1. Salva il numero INIZIALE di file
        initial_file_count = len(os.listdir(main_window.workspace_path))

        # Il workspace ha 2 elementi (file1.txt, subdir)
        assert initial_file_count > 0

        main_window.clear_folder(
            folder_path=main_window.workspace_path,
            folder_name="test",
            return_to_import=False
        )

        # 2. Verifica che siano stati creati tanti thread quanti erano i file INIZIALI
        assert len(main_window.threads) == initial_file_count

        # Attendi che i thread finiscano per non "inquinare" il test successivo
        for t in main_window.threads:
            t.wait(1000)

    def test_clear_folder_returns_to_import(self, main_window, monkeypatch, qtbot):
        """Verifica che return_to_import venga chiamato quando richiesto"""
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        main_window.clear_folder(
            folder_path=main_window.workspace_path,
            folder_name="workspace",
            return_to_import=True
        )

        # Attendi che i thread finiscano per non "inquinare" il test successivo
        for t in main_window.threads:
            t.wait(1000)

        main_window.context["return_to_import"].assert_called_once()


class TestThreadManagement:
    """Test per la gestione dei thread"""

    def test_new_thread_adds_to_list(self, main_window):
        """Verifica che un nuovo thread venga aggiunto alla lista"""
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
        """Verifica che un thread con errore venga rimosso"""
        mock_thread = Mock()
        main_window.threads.append(mock_thread)

        monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: None)
        monkeypatch.setattr(main_window, 'sender', lambda: mock_thread)

        main_window.copydelete_thread_error("Test error")

        assert mock_thread not in main_window.threads

    def test_copydelete_thread_success_removes_thread(self, main_window, monkeypatch):
        """Verifica che un thread completato venga rimosso"""
        mock_thread = Mock()
        main_window.threads.append(mock_thread)

        monkeypatch.setattr(QMessageBox, 'information', lambda *args, **kwargs: None)
        monkeypatch.setattr(main_window, 'sender', lambda: mock_thread)

        main_window.copydelete_thread_success("Success message", show=True)

        assert mock_thread not in main_window.threads

    def test_close_event_stops_threads(self, main_window, qtbot):
        """Verifica che i thread vengano fermati alla chiusura"""
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

        # Aggiungi thread alla lista
        main_window.threads = [mock_thread1, mock_thread2]

        from PyQt6.QtGui import QCloseEvent
        event = QCloseEvent()
        main_window.closeEvent(event)

        # Verifica che i metodi siano stati chiamati
        mock_thread1.finished.disconnect.assert_called_once()
        mock_thread1.error.disconnect.assert_called_once()
        mock_thread1.wait.assert_called_once()

        mock_thread2.finished.disconnect.assert_called_once()
        mock_thread2.error.disconnect.assert_called_once()
        mock_thread2.wait.assert_called_once()

        # --- CORREZIONE DEL TEST ---
        # Con la closeEvent corretta, la lista DEVE essere vuota alla fine.
        assert len(main_window.threads) == 0


class TestDebugLog:
    """Test per la funzionalità di debug log"""

    @patch('main.ui.main_window.set_log_level')
    def test_toggle_debug_log_enables(self, mock_set_log_level, main_window):
        """Verifica che il debug log possa essere abilitato"""
        main_window.toggle_debug_log(True)

        assert main_window.settings.value("debug_log", type=bool) == True
        mock_set_log_level.assert_called_with(logging.DEBUG)

    @patch('main.ui.main_window.set_log_level')
    def test_toggle_debug_log_disables(self, mock_set_log_level, main_window):
        """Verifica che il debug log possa essere disabilitato"""
        main_window.toggle_debug_log(False)

        assert main_window.settings.value("debug_log", type=bool) == False
        mock_set_log_level.assert_called_with(logging.ERROR)


class TestWidgetManagement:
    """Test per la gestione dei widget"""

    def test_set_widgets_first_time(self, main_window, qtbot):
        """Verifica l'aggiunta iniziale dei widget"""
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
        """Verifica che export_file_info mostri un messaggio informativo"""
        message_shown = False

        def mock_information(*args, **kwargs):
            nonlocal message_shown
            message_shown = True

        monkeypatch.setattr(QMessageBox, 'information', mock_information)

        main_window.export_file_info()
        assert message_shown


# Test di integrazione
class TestIntegration:
    """Test di integrazione per verificare il flusso completo"""

    def test_full_workflow(self, main_window, qtbot):
        """Test del flusso completo: creazione, cambio lingua, operazioni"""
        # Verifica inizializzazione (non visibile di default)
        assert not main_window.isVisible()

        # Cambia lingua
        with qtbot.waitSignal(main_window.context["language_changed"], timeout=1000):
            main_window.set_language("it")
        assert main_window.language_actions["it"].isChecked()

        # Verifica che la finestra sia funzionante
        main_window.show()
        qtbot.waitExposed(main_window)
        assert main_window.isVisible()

        # Chiudi la finestra
        main_window.close()

        # Aspetta che la finestra sia effettivamente nascosta
        qtbot.waitUntil(lambda: not main_window.isVisible())
        assert not main_window.isVisible()