import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, call
from PyQt6.QtCore import QSettings, pyqtSignal, QObject
from PyQt6.QtWidgets import QMessageBox

from test.conftest import SignalEmitter
# Import dal tuo progetto
from ui.ui_skull_stripping_page import SkullStrippingPage

@pytest.fixture
def skull_page(qtbot, mock_context, mock_file_selector):
    with patch('subprocess.run', return_value=Mock(returncode=0)):
        previous_page = Mock()
        page = SkullStrippingPage(mock_context, previous_page)
        qtbot.addWidget(page)
        page.show()
        return page

class TestSkullStrippingPageSetup:
    """Test per l'inizializzazione di SkullStrippingPage"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def signal_emitter(self):
        return SignalEmitter()

    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "update_main_buttons": Mock(),
        }
        return context

    def test_page_initialization(self, skull_page):
        """Verifica inizializzazione corretta"""
        assert skull_page.context is not None
        assert skull_page.previous_page is not None
        assert skull_page.worker is None
        assert skull_page.canceled == False

    def test_title_created(self, skull_page):
        """Verifica creazione titolo"""
        assert skull_page.title is not None
        assert skull_page.title.text() != ""

    def test_file_selector_created(self, skull_page):
        """Verifica creazione file selector"""
        assert skull_page.file_selector_widget is not None

    def test_run_button_created(self, skull_page):
        """Verifica creazione pulsante run"""
        assert skull_page.run_button is not None
        assert not skull_page.run_button.isEnabled()  # Disabilitato inizialmente

    def test_cancel_button_created(self, skull_page):
        """Verifica creazione pulsante cancel"""
        assert skull_page.cancel_button is not None
        assert not skull_page.cancel_button.isVisible()  # Nascosto inizialmente

    def test_progress_bar_created(self, skull_page):
        """Verifica creazione progress bar"""
        assert skull_page.progress_bar is not None
        assert not skull_page.progress_bar.isVisible()  # Nascosta inizialmente

    @patch('subprocess.run', return_value=Mock(returncode=0))
    def test_bet_detected_when_available(self, mock_run, qtbot, mock_context, mock_file_selector):
        """Verifica rilevamento BET quando disponibile"""
        page = SkullStrippingPage(mock_context, Mock())
        qtbot.addWidget(page)

        assert page.has_bet == True

    @patch('subprocess.run', side_effect=FileNotFoundError())
    def test_bet_not_detected_when_unavailable(self, mock_run, qtbot, mock_context, mock_file_selector):
        """Verifica che BET non sia rilevato quando non disponibile"""
        page = SkullStrippingPage(mock_context, Mock())
        qtbot.addWidget(page)

        assert page.has_bet == False


class TestSkullStrippingPageBETParameters:
    """Test per parametri BET"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def signal_emitter(self):
        return SignalEmitter()

    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "update_main_buttons": Mock(),
        }
        return context

    @pytest.fixture
    def skull_page_with_bet(self, qtbot, mock_context, mock_file_selector):
        with patch('subprocess.run', return_value=Mock(returncode=0)):
            page = SkullStrippingPage(mock_context, Mock())
            qtbot.addWidget(page)
            return page

    def test_f_parameter_default(self, skull_page_with_bet):
        """Verifica valore default parametro f"""
        assert skull_page_with_bet.f_spinbox.value() == 0.50

    def test_f_parameter_range(self, skull_page_with_bet):
        """Verifica range parametro f"""
        assert skull_page_with_bet.f_spinbox.minimum() == 0.0
        assert skull_page_with_bet.f_spinbox.maximum() == 1.0

    def test_g_parameter_default(self, skull_page_with_bet):
        """Verifica valore default parametro g"""
        assert skull_page_with_bet.g_spinbox.value() == 0.0

    def test_coordinate_parameters_default(self, skull_page_with_bet):
        """Verifica valori default coordinate"""
        assert skull_page_with_bet.c_x_spinbox.value() == 0
        assert skull_page_with_bet.c_y_spinbox.value() == 0
        assert skull_page_with_bet.c_z_spinbox.value() == 0

    def test_brain_extracted_checkbox_default(self, skull_page_with_bet):
        """Verifica che brain extracted sia checked di default"""
        assert skull_page_with_bet.opt_brain_extracted.isChecked()

    def test_other_checkboxes_default(self, skull_page_with_bet):
        """Verifica che altri checkbox siano unchecked di default"""
        assert not skull_page_with_bet.opt_m.isChecked()
        assert not skull_page_with_bet.opt_t.isChecked()
        assert not skull_page_with_bet.opt_s.isChecked()
        assert not skull_page_with_bet.opt_o.isChecked()


class TestSkullStrippingPageAdvancedOptions:
    """Test per opzioni avanzate"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def signal_emitter(self):
        return SignalEmitter()

    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "update_main_buttons": Mock(),
        }
        return context

    

    def test_advanced_options_hidden_initially(self, skull_page):
        """Verifica che opzioni avanzate siano nascoste inizialmente"""
        assert not skull_page.advanced_box.isVisible()

    def test_toggle_advanced_shows_options(self, skull_page):
        """Verifica che toggle mostri opzioni avanzate"""
        skull_page.advanced_btn.setChecked(True)
        skull_page.toggle_advanced()  # chiama direttamente la funzione
        assert skull_page.advanced_box.isVisible()

    def test_toggle_advanced_hides_options(self, skull_page, qtbot):
        """Verifica che toggle nasconda opzioni avanzate"""
        # Prima mostra
        skull_page.advanced_btn.setChecked(True)
        skull_page.toggle_advanced()
        assert skull_page.advanced_box.isVisible()

        # Poi nascondi
        skull_page.advanced_btn.setChecked(False)
        skull_page.toggle_advanced()
        assert not skull_page.advanced_box.isVisible()

    def test_toggle_updates_button_text(self, skull_page):
        """Verifica che toggle aggiorni il testo del pulsante"""
        initial_text = skull_page.advanced_btn.text()

        skull_page.advanced_btn.setChecked(True)
        skull_page.toggle_advanced()

        assert skull_page.advanced_btn.text() != initial_text


class TestSkullStrippingPageProcessing:
    """Test per processing"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def signal_emitter(self):
        return SignalEmitter()

    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "update_main_buttons": Mock(),
        }
        return context

    

    def test_run_without_files_shows_warning(self, skull_page, monkeypatch):
        """Verifica warning quando non ci sono file"""
        skull_page.file_selector_widget.get_selected_files = Mock(return_value=[])

        warning_shown = False

        def mock_warning(*args, **kwargs):
            nonlocal warning_shown
            warning_shown = True

        monkeypatch.setattr(QMessageBox, 'warning', mock_warning)

        skull_page.run_bet()
        assert warning_shown

    @patch('ui.ui_skull_stripping_page.SkullStripThread')
    def test_run_creates_worker_thread(self, MockThread, skull_page):
        """Verifica creazione worker thread"""
        skull_page.file_selector_widget.get_selected_files = Mock(
            return_value=['/path/to/file.nii']
        )

        mock_worker = Mock()
        MockThread.return_value = mock_worker

        skull_page.run_bet()

        MockThread.assert_called_once()
        mock_worker.start.assert_called_once()

    @patch('ui.ui_skull_stripping_page.SkullStripThread')
    def test_run_shows_progress_bar(self, MockThread, skull_page, qtbot):
        """Verifica che run mostri progress bar"""
        skull_page.file_selector_widget.get_selected_files = Mock(
            return_value=['/path/to/file.nii']
        )

        mock_worker = Mock()
        MockThread.return_value = mock_worker

        with qtbot.waitSignal(skull_page.processing, timeout=1000):
            skull_page.run_bet()

        assert skull_page.progress_bar.isVisible()

    def test_set_processing_mode_true(self, skull_page):
        """Verifica set_processing_mode(True)"""
        skull_page.set_processing_mode(True)

        assert not skull_page.run_button.isVisible()
        assert skull_page.cancel_button.isVisible()

    def test_set_processing_mode_false(self, skull_page):
        """Verifica set_processing_mode(False)"""
        skull_page.set_processing_mode(False)

        assert skull_page.run_button.isVisible()
        assert not skull_page.cancel_button.isVisible()

    def test_cancel_processing(self, skull_page):
        """Verifica cancellazione processing"""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        skull_page.worker = mock_worker

        skull_page.cancel_processing()

        assert skull_page.canceled == True
        mock_worker.cancel.assert_called_once()


class TestSkullStrippingPageProgressCallbacks:
    """Test per callback di progresso"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def signal_emitter(self):
        return SignalEmitter()

    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "update_main_buttons": Mock(),
        }
        return context

    

    def test_on_progress_updated(self, skull_page):
        """Verifica aggiornamento messaggio progresso"""
        test_message = "Processing file 1 of 3"
        skull_page.on_progress_updated(test_message)

        assert skull_page.status_label.text() == test_message

    def test_on_progress_value_updated(self, skull_page):
        """Verifica aggiornamento valore progress bar"""
        skull_page.on_progress_value_updated(50)

        assert skull_page.progress_bar.value() == 50

    def test_on_all_completed_success(self, skull_page):
        """Verifica callback completamento con successo"""
        skull_page.on_all_completed(3, [])

        assert not skull_page.progress_bar.isVisible()
        assert "3" in skull_page.status_label.text()

    def test_on_all_completed_with_failures(self, skull_page):
        """Verifica callback completamento con fallimenti"""
        failed_files = ['/path/file1.nii', '/path/file2.nii']
        skull_page.on_all_completed(1, failed_files)

        assert not skull_page.progress_bar.isVisible()
        status_text = skull_page.status_label.text()
        assert "1" in status_text  # Successi

    def test_on_all_completed_all_failed(self, skull_page):
        """Verifica callback quando tutti falliscono"""
        failed_files = ['/path/file1.nii', '/path/file2.nii']
        skull_page.on_all_completed(0, failed_files)

        assert not skull_page.progress_bar.isVisible()
        assert "failed" in skull_page.status_label.text().lower()

    def test_on_worker_finished(self, skull_page, qtbot):
        """Verifica callback fine worker"""
        mock_worker = Mock()
        skull_page.worker = mock_worker

        with qtbot.waitSignal(skull_page.processing, timeout=1000):
            skull_page.on_worker_finished()

        skull_page.context["update_main_buttons"].assert_called()


class TestSkullStrippingPageExistingCheck:
    """Test per controllo skull strip esistente"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        # Crea struttura con skull strip esistente
        subject_dir = os.path.join(temp_dir, "derivatives", "skullstrips", "sub-001", "anat")
        os.makedirs(subject_dir)
        with open(os.path.join(subject_dir, "brain.nii.gz"), "w") as f:
            f.write("test")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def signal_emitter(self):
        return SignalEmitter()

    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "update_main_buttons": Mock(),
        }
        return context

    

    def test_has_existing_skull_strip_true(self, skull_page, temp_workspace):
        """Verifica rilevamento skull strip esistente"""
        nifti_path = os.path.join(temp_workspace, "sub-001", "anat", "T1w.nii")

        result = skull_page.has_existing_skull_strip(nifti_path, temp_workspace)

        assert result == True

    def test_has_existing_skull_strip_false(self, skull_page, temp_workspace):
        """Verifica quando skull strip non esiste"""
        nifti_path = os.path.join(temp_workspace, "sub-002", "anat", "T1w.nii")

        result = skull_page.has_existing_skull_strip(nifti_path, temp_workspace)

        assert result == False

    def test_has_existing_skull_strip_no_subject_id(self, skull_page, temp_workspace):
        """Verifica comportamento senza subject ID"""
        nifti_path = os.path.join(temp_workspace, "invalid", "T1w.nii")

        result = skull_page.has_existing_skull_strip(nifti_path, temp_workspace)

        assert result == False


class TestSkullStrippingPageNavigation:
    """Test per navigazione"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def signal_emitter(self):
        return SignalEmitter()

    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "update_main_buttons": Mock(),
        }
        return context

    def test_back_returns_previous_page(self, skull_page):
        """Verifica ritorno a pagina precedente"""
        result = skull_page.back()
        assert result == skull_page.previous_page
        skull_page.previous_page.on_enter.assert_called_once()

    def test_back_blocked_during_processing(self, skull_page, monkeypatch):
        """Verifica che back sia bloccato durante processing"""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        skull_page.worker = mock_worker

        warning_shown = False

        def mock_warning(*args, **kwargs):
            nonlocal warning_shown
            warning_shown = True

        monkeypatch.setattr(QMessageBox, 'warning', mock_warning)

        result = skull_page.back()

        assert result is None
        assert warning_shown

    def test_is_ready_to_advance_false(self, skull_page):
        """Verifica che non si possa avanzare"""
        assert not skull_page.is_ready_to_advance()

    def test_is_ready_to_go_back_true_when_idle(self, skull_page):
        """Verifica che si possa tornare indietro quando idle"""
        assert skull_page.is_ready_to_go_back()

    def test_is_ready_to_go_back_false_during_processing(self, skull_page):
        """Verifica che non si possa tornare durante processing"""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        skull_page.worker = mock_worker

        assert not skull_page.is_ready_to_go_back()


class TestSkullStrippingPageReset:
    """Test per reset pagina"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def signal_emitter(self):
        return SignalEmitter()

    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "update_main_buttons": Mock(),
        }
        return context

    

    def test_reset_clears_files(self, skull_page):
        """Verifica che reset pulisca i file"""
        skull_page.reset_page()
        skull_page.file_selector_widget.clear_selected_files.assert_called_once()

    def test_reset_parameters(self, skull_page):
        """Verifica che reset ripristini i parametri"""
        # Modifica parametri
        skull_page.f_spinbox.setValue(0.7)
        skull_page.g_spinbox.setValue(0.5)

        # Reset
        skull_page.reset_page()

        # Verifica valori default
        assert skull_page.f_spinbox.value() == 0.50
        assert skull_page.g_spinbox.value() == 0.0

    def test_reset_checkboxes(self, skull_page):
        """Verifica che reset ripristini checkbox"""
        # Modifica checkbox
        skull_page.opt_m.setChecked(True)
        skull_page.opt_t.setChecked(True)

        # Reset
        skull_page.reset_page()

        # Verifica valori default
        assert skull_page.opt_brain_extracted.isChecked()
        assert not skull_page.opt_m.isChecked()
        assert not skull_page.opt_t.isChecked()

    def test_reset_hides_progress_bar(self, skull_page):
        """Verifica che reset nasconda progress bar"""
        skull_page.progress_bar.setVisible(True)

        skull_page.reset_page()

        assert not skull_page.progress_bar.isVisible()

    def test_reset_cancels_running_worker(self, skull_page):
        """Verifica che reset cancelli worker in esecuzione"""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        skull_page.worker = mock_worker

        skull_page.reset_page()

        mock_worker.cancel.assert_called_once()
        mock_worker.wait.assert_called_once()


class TestSkullStrippingPageTranslation:
    """Test per traduzioni"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def signal_emitter(self):
        return SignalEmitter()

    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "update_main_buttons": Mock(),
        }
        return context

    

    def test_translate_ui_updates_title(self, skull_page):
        """Verifica aggiornamento titolo"""
        skull_page._translate_ui()
        assert skull_page.title.text() != ""

    def test_translate_ui_updates_buttons(self, skull_page):
        """Verifica aggiornamento pulsanti"""
        skull_page._translate_ui()
        assert skull_page.run_button.text() != ""
        assert skull_page.cancel_button.text() != ""


# Test di integrazione
class TestSkullStrippingPageIntegration:
    """Test di integrazione"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def signal_emitter(self):
        return SignalEmitter()

    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "update_main_buttons": Mock(),
        }
        return context

    

    @patch('ui.ui_skull_stripping_page.SkullStripThread')
    def test_full_processing_workflow(self, MockThread, skull_page, qtbot):
        """Test flusso completo di processing"""
        # Setup
        skull_page.file_selector_widget.get_selected_files = Mock(
            return_value=['/path/file.nii']
        )

        mock_worker = Mock()
        MockThread.return_value = mock_worker

        # Start processing
        with qtbot.waitSignal(skull_page.processing, timeout=1000):
            skull_page.run_bet()

        # Verifica stato processing
        assert skull_page.progress_bar.isVisible()
        assert skull_page.cancel_button.isVisible()
        assert not skull_page.run_button.isVisible()

        # Simula completamento
        with qtbot.waitSignal(skull_page.processing, timeout=1000):
            skull_page.on_worker_finished()

        # Verifica stato finale
        assert not skull_page.cancel_button.isVisible()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])