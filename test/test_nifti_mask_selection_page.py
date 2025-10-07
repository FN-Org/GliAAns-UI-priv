import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import QSettings, pyqtSignal, QObject

# Import dal tuo progetto
from ui.ui_mask_selection_page import NiftiMaskSelectionPage

@pytest.fixture
def mask_page(qtbot, mock_context, mock_file_selector_mask):
    previous_page = Mock()
    page = NiftiMaskSelectionPage(mock_context, previous_page)
    qtbot.addWidget(page)
    return page

class TestNiftiMaskSelectionPageSetup:
    """Test per l'inizializzazione di NiftiMaskSelectionPage"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "open_nifti_viewer": Mock(),
        }
        return context

    def test_page_initialization(self, mask_page):
        """Verifica inizializzazione corretta"""
        assert mask_page.context is not None
        assert mask_page.previous_page is not None
        assert mask_page.selected_file is None

    def test_title_created(self, mask_page):
        """Verifica creazione titolo"""
        assert mask_page.title is not None
        assert mask_page.title.text() != ""

    def test_file_selector_created(self, mask_page):
        """Verifica creazione file selector"""
        assert mask_page.file_selector_widget is not None

    def test_viewer_button_created(self, mask_page):
        """Verifica creazione pulsante viewer"""
        assert mask_page.viewer_button is not None
        assert not mask_page.viewer_button.isEnabled()  # Disabilitato inizialmente


class TestNiftiMaskSelectionPageExistingMask:
    """Test per controllo maschere esistenti"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        # Crea struttura con maschera manuale
        manual_dir = os.path.join(temp_dir, "derivatives", "manual_masks", "sub-001", "anat")
        os.makedirs(manual_dir)
        with open(os.path.join(manual_dir, "mask.nii.gz"), "w") as f:
            f.write("test")

        # Crea struttura con maschera deep learning
        dl_dir = os.path.join(temp_dir, "derivatives", "deep_learning_masks", "sub-002", "anat")
        os.makedirs(dl_dir)
        with open(os.path.join(dl_dir, "mask.nii.gz"), "w") as f:
            f.write("test")

        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)



    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "open_nifti_viewer": Mock(),
        }
        return context

    

    def test_has_existing_manual_mask(self, mask_page, temp_workspace):
        """Verifica rilevamento maschera manuale esistente"""
        nifti_path = os.path.join(temp_workspace, "sub-001", "anat", "T1w.nii")

        result = mask_page.has_existing_mask(nifti_path, temp_workspace)

        assert result == True

    def test_has_existing_dl_mask(self, mask_page, temp_workspace):
        """Verifica rilevamento maschera deep learning esistente"""
        nifti_path = os.path.join(temp_workspace, "sub-002", "anat", "T1w.nii")

        result = mask_page.has_existing_mask(nifti_path, temp_workspace)

        assert result == True

    def test_has_no_existing_mask(self, mask_page, temp_workspace):
        """Verifica quando maschera non esiste"""
        nifti_path = os.path.join(temp_workspace, "sub-003", "anat", "T1w.nii")

        result = mask_page.has_existing_mask(nifti_path, temp_workspace)

        assert result == False

    def test_has_existing_mask_no_subject_id(self, mask_page, temp_workspace):
        """Verifica comportamento senza subject ID"""
        nifti_path = os.path.join(temp_workspace, "invalid", "T1w.nii")

        result = mask_page.has_existing_mask(nifti_path, temp_workspace)

        assert result == False

    def test_has_existing_mask_empty_directory(self, mask_page, temp_workspace):
        """Verifica comportamento con directory vuota"""
        # Crea directory ma senza file
        empty_dir = os.path.join(temp_workspace, "derivatives", "manual_masks", "sub-004", "anat")
        os.makedirs(empty_dir)

        nifti_path = os.path.join(temp_workspace, "sub-004", "anat", "T1w.nii")

        result = mask_page.has_existing_mask(nifti_path, temp_workspace)

        assert result == False


class TestNiftiMaskSelectionPageViewer:
    """Test per apertura NIfTI viewer"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)



    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "open_nifti_viewer": Mock(),
        }
        return context

    

    def test_open_nifti_viewer_calls_context(self, mask_page):
        """Verifica che open_nifti_viewer chiami il context"""
        test_file = "/path/to/scan.nii"
        mask_page.file_selector_widget.get_selected_files = Mock(
            return_value=[test_file]
        )

        mask_page.open_nifti_viewer()

        mask_page.context["open_nifti_viewer"].assert_called_once_with(test_file)

    def test_open_nifti_viewer_uses_last_file(self, mask_page):
        """Verifica che usi l'ultimo file selezionato"""
        files = ["/path/file1.nii", "/path/file2.nii"]
        mask_page.file_selector_widget.get_selected_files = Mock(
            return_value=files
        )

        mask_page.open_nifti_viewer()

        # Dovrebbe usare l'ultimo file
        mask_page.context["open_nifti_viewer"].assert_called_once_with(files[-1])

    def test_open_nifti_viewer_handles_error(self, mask_page):
        """Verifica gestione errore"""
        mask_page.file_selector_widget.get_selected_files = Mock(
            side_effect=Exception("Test error")
        )

        # Non dovrebbe sollevare eccezione
        mask_page.open_nifti_viewer()


class TestNiftiMaskSelectionPageReadiness:
    """Test per logica di avanzamento"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)



    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "open_nifti_viewer": Mock(),
        }
        return context

    

    def test_not_ready_to_advance(self, mask_page):
        """Verifica che non si possa avanzare"""
        assert not mask_page.is_ready_to_advance()

    def test_ready_to_go_back(self, mask_page):
        """Verifica che si possa tornare indietro"""
        assert mask_page.is_ready_to_go_back()


class TestNiftiMaskSelectionPageNavigation:
    """Test per navigazione"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)



    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "open_nifti_viewer": Mock(),
        }
        return context

    def test_back_returns_previous_page(self, mask_page):
        """Verifica ritorno a pagina precedente"""
        result = mask_page.back()

        assert result == mask_page.previous_page
        mask_page.previous_page.on_enter.assert_called_once()

    def test_back_returns_none_without_previous(self, mask_page):
        """Verifica ritorno None senza pagina precedente"""
        mask_page.previous_page = None

        result = mask_page.back()

        assert result is None


class TestNiftiMaskSelectionPageReset:
    """Test per reset pagina"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)



    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "open_nifti_viewer": Mock(),
        }
        return context

    

    def test_reset_clears_selected_file(self, mask_page):
        """Verifica che reset pulisca il file selezionato"""
        mask_page.selected_file = "/path/to/file.nii"

        mask_page.reset_page()

        assert mask_page.selected_file is None

    def test_reset_calls_clear_selected_files(self, mask_page):
        """Verifica che reset chiami clear_selected_files"""
        mask_page.reset_page()

        mask_page.file_selector_widget.clear_selected_files.assert_called_once()

    def test_reset_disables_viewer_button(self, mask_page):
        """Verifica che reset disabiliti il pulsante viewer"""
        mask_page.viewer_button.setEnabled(True)

        mask_page.reset_page()

        assert not mask_page.viewer_button.isEnabled()


class TestNiftiMaskSelectionPageTranslation:
    """Test per traduzioni"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)



    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "open_nifti_viewer": Mock(),
        }
        return context

    

    def test_translate_ui_updates_title(self, mask_page):
        """Verifica aggiornamento titolo"""
        mask_page._translate_ui()
        assert mask_page.title.text() != ""

    def test_translate_ui_updates_button(self, mask_page):
        """Verifica aggiornamento pulsante"""
        mask_page._translate_ui()
        assert mask_page.viewer_button.text() != ""


class TestNiftiMaskSelectionPageOnEnter:
    """Test per on_enter"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)



    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "open_nifti_viewer": Mock(),
        }
        return context

    

    def test_on_enter_does_nothing(self, mask_page):
        """Verifica che on_enter non causi errori"""
        # Dovrebbe eseguire senza errori
        mask_page.on_enter()


# Test di integrazione
class TestNiftiMaskSelectionPageIntegration:
    """Test di integrazione"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        # Crea struttura completa
        manual_dir = os.path.join(temp_dir, "derivatives", "manual_masks", "sub-001", "anat")
        os.makedirs(manual_dir)
        with open(os.path.join(manual_dir, "mask.nii.gz"), "w") as f:
            f.write("test")

        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)



    @pytest.fixture
    def mock_context(self, temp_workspace, signal_emitter):
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed,
            "open_nifti_viewer": Mock(),
        }
        return context

    

    def test_full_workflow(self, mask_page, temp_workspace):
        """Test flusso completo"""
        # Verifica stato iniziale
        assert mask_page.selected_file is None
        assert not mask_page.viewer_button.isEnabled()

        # Simula selezione file
        test_file = os.path.join(temp_workspace, "sub-001", "anat", "T1w.nii")
        mask_page.file_selector_widget.get_selected_files = Mock(
            return_value=[test_file]
        )

        # Apri viewer
        mask_page.open_nifti_viewer()
        mask_page.context["open_nifti_viewer"].assert_called_once_with(test_file)

        # Reset
        mask_page.reset_page()
        assert mask_page.selected_file is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])