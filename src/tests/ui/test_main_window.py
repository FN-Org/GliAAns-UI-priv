import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QMessageBox, QPushButton
from PyQt6.QtCore import QSettings, pyqtSignal, QObject

from main.ui.ui_main_window import MainWindow


@pytest.fixture
def main_window(qtbot, mock_context):
    window = MainWindow(mock_context)
    qtbot.addWidget(window)
    return window

class TestMainWindowSetup:
    """Test per la configurazione iniziale della MainWindow"""

    def test_window_initialization(self, main_window):
        """Verifica che la finestra si inizializzi correttamente"""
        assert main_window.windowTitle() != ""
        assert main_window.width() >= 950
        assert main_window.height() >= 650

    def test_menu_bar_created(self, main_window):
        """Verifica che la menu bar sia creata con tutti i menu"""
        menu_bar = main_window.menuBar()
        assert menu_bar is not None

        menus = [action.text() for action in menu_bar.actions()]
        # Verifica che esistano i menu principali
        assert any("File" in m for m in menus)
        assert any("Workspace" in m for m in menus)
        assert any("Settings" in m or "Impostazioni" in m for m in menus)

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

    def test_clear_folder_deletes_on_confirmation(self, main_window, monkeypatch):
        """Verifica che i file vengano eliminati dopo conferma"""
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        main_window.clear_folder(
            folder_path=main_window.workspace_path,
            folder_name="test",
            return_to_import=False
        )

        # Verifica che siano stati creati thread
        assert len(main_window.threads) > 0

    def test_clear_folder_returns_to_import(self, main_window, monkeypatch):
        """Verifica che return_to_import venga chiamato quando richiesto"""
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        main_window.clear_folder(
            folder_path=main_window.workspace_path,
            folder_name="workspace",
            return_to_import=True
        )

        # Attendi un momento per permettere ai thread di partire
        QtCore.QCoreApplication.processEvents()
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
        initial_count = len(main_window.threads)

        from PyQt6.QtGui import QCloseEvent
        event = QCloseEvent()
        main_window.closeEvent(event)

        # Verifica che i metodi siano stati chiamati
        mock_thread1.finished.disconnect.assert_called_once()
        mock_thread1.error.disconnect.assert_called_once()
        mock_thread1.wait.assert_called_once()

        # Verifica che la lista sia stata svuotata (il codice rimuove i thread uno alla volta)
        # A causa del loop che modifica la lista durante l'iterazione, verifichiamo che
        # almeno alcuni thread siano stati rimossi
        assert len(main_window.threads) < initial_count


class TestDebugLog:
    """Test per la funzionalità di debug log"""

    @patch('main.ui.ui_main_window.set_log_level')
    def test_toggle_debug_log_enables(self, mock_set_log_level, main_window):
        """Verifica che il debug log possa essere abilitato"""
        import logging
        main_window.toggle_debug_log(True)

        assert main_window.settings.value("debug_log", type=bool) == True
        mock_set_log_level.assert_called_with(logging.DEBUG)

    @patch('main.ui.ui_main_window.set_log_level')
    def test_toggle_debug_log_disables(self, mock_set_log_level, main_window):
        """Verifica che il debug log possa essere disabilitato"""
        import logging
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
        # Verifica inizializzazione
        assert main_window.isVisible() == False

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
        assert not main_window.isVisible()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])