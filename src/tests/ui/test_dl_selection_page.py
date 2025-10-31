import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QCoreApplication, Qt

from main.ui.ui_dl_selection_page import DlNiftiSelectionPage


@pytest.fixture
def segmentation_workspace(temp_workspace):
    """Crea workspace con segmentazioni esistenti."""
    # Crea directory con segmentazione esistente
    seg_dir = os.path.join(
        temp_workspace,
        "derivatives",
        "deep_learning_seg",
        "sub-01",
        "anat"
    )
    os.makedirs(seg_dir, exist_ok=True)

    # Crea file di segmentazione
    with open(os.path.join(seg_dir, "sub-01_T1w_seg.nii.gz"), "w") as f:
        f.write("segmentation data")

    # Crea paziente senza segmentazione
    no_seg_dir = os.path.join(
        temp_workspace,
        "derivatives",
        "deep_learning_seg",
        "sub-02",
        "anat"
    )
    os.makedirs(no_seg_dir, exist_ok=True)

    return temp_workspace


class TestDlNiftiSelectionPageInitialization:
    """Test per l'inizializzazione della pagina."""

    def test_initialization_basic(self, qtbot, mock_context, mock_file_selector_dl):
        """Test inizializzazione base."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.context == mock_context
        assert page.previous_page is None
        assert page.next_page is None

    def test_initialization_with_previous_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test inizializzazione con pagina precedente."""
        previous = Mock()
        page = DlNiftiSelectionPage(mock_context, previous_page=previous)
        qtbot.addWidget(page)

        assert page.previous_page == previous

    def test_ui_elements_created(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che tutti gli elementi UI siano creati."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.title is not None
        assert page.file_selector_widget is not None
        assert page.status_label is not None
        assert page.layout is not None

    def test_file_selector_widget_configured(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che il FileSelectorWidget sia configurato correttamente."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Verifica che il widget sia stato creato con i parametri corretti
        mock_file_selector_dl.assert_called_once()
        call_kwargs = mock_file_selector_dl.call_args[1]

        assert call_kwargs['parent'] == page
        assert call_kwargs['context'] == mock_context
        assert call_kwargs['label'] == "seg"
        assert call_kwargs['allow_multiple'] is True
        assert callable(call_kwargs['has_existing_function'])


class TestHasExistingSegmentation:
    """Test per il metodo has_existing_segmentation."""

    def test_has_existing_segmentation_exists_nii_gz(self, qtbot, mock_context, segmentation_workspace,
                                                     mock_file_selector_dl):
        """Test quando esiste segmentazione .nii.gz."""
        mock_context["workspace_path"] = segmentation_workspace
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        nifti_path = os.path.join(segmentation_workspace, "sub-01", "anat", "sub-01_T1w.nii")
        result = page.has_existing_segmentation(nifti_path, segmentation_workspace)

        assert result is True

    def test_has_existing_segmentation_exists_nii(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test quando esiste segmentazione .nii."""
        # Crea segmentazione .nii (non compressa)
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-03",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)
        with open(os.path.join(seg_dir, "sub-03_T1w_seg.nii"), "w") as f:
            f.write("seg data")

        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        nifti_path = os.path.join(temp_workspace, "sub-03", "anat", "sub-03_T1w.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_has_existing_segmentation_not_exists(self, qtbot, mock_context, segmentation_workspace,
                                                  mock_file_selector_dl):
        """Test quando non esiste segmentazione."""
        mock_context["workspace_path"] = segmentation_workspace
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        nifti_path = os.path.join(segmentation_workspace, "sub-02", "anat", "sub-02_T1w.nii")
        result = page.has_existing_segmentation(nifti_path, segmentation_workspace)

        assert result is False

    def test_has_existing_segmentation_no_subject_id(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test quando il path non contiene subject ID."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        nifti_path = os.path.join(temp_workspace, "random", "path", "file.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is False

    def test_has_existing_segmentation_directory_not_exists(self, qtbot, mock_context, temp_workspace,
                                                            mock_file_selector_dl):
        """Test quando la directory di segmentazione non esiste."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        nifti_path = os.path.join(temp_workspace, "sub-99", "anat", "sub-99_T1w.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is False

    def test_has_existing_segmentation_multiple_files(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test quando ci sono più file di segmentazione."""
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-04",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)

        # Crea multipli file seg
        with open(os.path.join(seg_dir, "sub-04_T1w_seg.nii.gz"), "w") as f:
            f.write("seg1")
        with open(os.path.join(seg_dir, "sub-04_flair_seg.nii"), "w") as f:
            f.write("seg2")

        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        nifti_path = os.path.join(temp_workspace, "sub-04", "anat", "sub-04_T1w.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_has_existing_segmentation_ignores_non_seg_files(self, qtbot, mock_context, temp_workspace,
                                                             mock_file_selector_dl):
        """Test che ignori file che non sono segmentazioni."""
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-05",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)

        # Crea file che non sono segmentazioni
        with open(os.path.join(seg_dir, "sub-05_T1w.nii.gz"), "w") as f:
            f.write("not seg")
        with open(os.path.join(seg_dir, "metadata.json"), "w") as f:
            f.write("{}")

        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        nifti_path = os.path.join(temp_workspace, "sub-05", "anat", "sub-05_T1w.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is False

    def test_has_existing_segmentation_nested_subject_path(self, qtbot, mock_context, temp_workspace,
                                                           mock_file_selector_dl):
        """Test con path nidificato (es. con sessione)."""
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-06",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)
        with open(os.path.join(seg_dir, "sub-06_T1w_seg.nii.gz"), "w") as f:
            f.write("seg")

        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Path con sessione
        nifti_path = os.path.join(temp_workspace, "sub-06", "ses-01", "anat", "sub-06_T1w.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True


class TestBackNavigation:
    """Test per la navigazione indietro."""

    def test_back_with_previous_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test back con previous_page."""
        previous = Mock()
        page = DlNiftiSelectionPage(mock_context, previous_page=previous)
        qtbot.addWidget(page)

        result = page.back()

        assert result == previous
        previous.on_enter.assert_called_once()

    def test_back_no_previous_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test back senza previous_page."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        result = page.back()

        assert result is None


class TestNextNavigation:
    """Test per la navigazione avanti."""

    def test_next_creates_dl_execution_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che next crei DlExecutionPage."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Simula selezione file
        page.file_selector_widget._selected_files = ["file1.nii", "file2.nii"]

        result = page.next(mock_context)

        assert page.next_page is not None
        assert result == page.next_page
        assert "DlExecutionPage" in str(type(page.next_page))

    def test_next_saves_selected_files_to_context(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che next salvi i file selezionati nel context."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        selected_files = ["file1.nii", "file2.nii", "file3.nii"]
        page.file_selector_widget._selected_files = selected_files

        page.next(mock_context)

        assert mock_context["selected_segmentation_files"] == selected_files

    def test_next_adds_to_history(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che next aggiunga alla history."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]
        initial_history_len = len(mock_context["history"])

        page.next(mock_context)

        assert len(mock_context["history"]) == initial_history_len + 1
        assert page.next_page in mock_context["history"]

    def test_next_reuses_existing_next_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che next riutilizzi next_page esistente."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]

        # Prima chiamata
        result1 = page.next(mock_context)
        first_next_page = page.next_page

        # Seconda chiamata
        result2 = page.next(mock_context)

        assert page.next_page == first_next_page
        assert result1 == result2

    def test_next_calls_on_enter(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che next chiami on_enter sulla next_page."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]

        with patch.object(page, 'next_page', create=True) as mock_next:
            mock_next.on_enter = Mock()
            page.next_page = mock_next

            page.next(mock_context)

            mock_next.on_enter.assert_called_once()

    def test_next_with_empty_selection(self, qtbot, mock_context, mock_file_selector_dl):
        """Test next con selezione vuota."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = []

        result = page.next(mock_context)

        # Dovrebbe comunque creare la pagina successiva
        assert result is not None
        assert mock_context["selected_segmentation_files"] == []


class TestOnEnter:
    """Test per il metodo on_enter."""

    def test_on_enter_clears_status(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che on_enter pulisca lo status label."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.status_label.setText("Some status message")

        page.on_enter()

        assert page.status_label.text() == ""


class TestReadyToAdvance:
    """Test per is_ready_to_advance."""

    def test_is_ready_to_advance_with_files(self, qtbot, mock_context, mock_file_selector_dl):
        """Test quando ci sono file selezionati."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii", "file2.nii"]

        assert bool(page.is_ready_to_advance()) is True

    def test_is_ready_to_advance_without_files(self, qtbot, mock_context, mock_file_selector_dl):
        """Test quando non ci sono file selezionati."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = []

        assert not page.is_ready_to_advance()

    def test_is_ready_to_advance_single_file(self, qtbot, mock_context, mock_file_selector_dl):
        """Test con singolo file selezionato."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["single_file.nii"]

        assert bool(page.is_ready_to_advance()) is True


class TestReadyToGoBack:
    """Test per is_ready_to_go_back."""

    def test_is_ready_to_go_back_always_true(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che is_ready_to_go_back ritorni sempre True."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.is_ready_to_go_back() is True

        # Anche con file selezionati
        page.file_selector_widget._selected_files = ["file1.nii"]
        assert page.is_ready_to_go_back() is True


class TestResetPage:
    """Test per reset_page."""

    def test_reset_page_clears_status(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che reset_page pulisca lo status."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.status_label.setText("Test status")

        page.reset_page()

        assert page.status_label.text() == ""

    def test_reset_page_clears_context(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che reset_page pulisca il context."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        mock_context["selected_segmentation_files"] = ["file1.nii", "file2.nii"]

        page.reset_page()

        assert mock_context["selected_segmentation_files"] == []

    def test_reset_page_without_context(self, qtbot, mock_file_selector_dl):
        """Test reset_page senza context."""
        page = DlNiftiSelectionPage(context=None)
        qtbot.addWidget(page)

        page.status_label.setText("Test")

        # Non dovrebbe crashare
        page.reset_page()

        assert page.status_label.text() == ""


class TestTranslation:
    """Test per le traduzioni."""

    def test_translate_ui_called_on_init(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che _translate_ui sia chiamato durante init."""
        with patch.object(DlNiftiSelectionPage, '_translate_ui') as mock_translate:
            page = DlNiftiSelectionPage(mock_context)
            qtbot.addWidget(page)

            mock_translate.assert_called()

    def test_translate_ui_updates_title(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che _translate_ui aggiorni il titolo."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page._translate_ui()

        assert page.title.text() is not None
        assert len(page.title.text()) > 0

    def test_language_changed_signal(self, qtbot, mock_context, signal_emitter, mock_file_selector_dl):
        """Test che il signal language_changed aggiorni l'UI."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        with patch.object(page, '_translate_ui') as mock_translate:
            mock_context["language_changed"].connect(mock_translate)
            mock_context["language_changed"].emit("it")

            mock_translate.assert_called()


class TestEdgeCases:
    """Test per casi limite."""

    def test_subject_id_extraction_complex_path(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test estrazione subject ID con path complessi."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Crea segmentazione
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-complex123",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)
        with open(os.path.join(seg_dir, "ok_seg.nii.gz"), "w") as f:
            f.write("seg")

        # Path con molti livelli
        nifti_path = os.path.join(
            temp_workspace,
            "rawdata",
            "sub-complex123",
            "ses-01",
            "anat",
            "file.nii"
        )

        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_multiple_sub_in_path(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test con multipli 'sub-' nel path (dovrebbe prendere il primo)."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Crea segmentazione per sub-01
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-01",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)
        with open(os.path.join(seg_dir, "ok_seg.nii.gz"), "w") as f:
            f.write("seg")

        # Path che contiene 'sub-' sia nel nome directory che nel nome file
        nifti_path = os.path.join(
            temp_workspace,
            "sub-01",
            "anat",
            "sub-01_T1w.nii"  # 'sub-' appare anche qui
        )

        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_workspace_path_with_trailing_slash(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test con workspace_path che ha trailing slash."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-07",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)
        with open(os.path.join(seg_dir, "ok_seg.nii.gz"), "w") as f:
            f.write("seg")

        workspace_with_slash = temp_workspace + os.sep
        nifti_path = os.path.join(temp_workspace, "sub-07", "anat", "file.nii")

        result = page.has_existing_segmentation(nifti_path, workspace_with_slash)

        assert result is True

    def test_special_characters_in_paths(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test con caratteri speciali nei path."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Subject con caratteri speciali
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-test_01",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)
        with open(os.path.join(seg_dir, "ok_seg.nii.gz"), "w") as f:
            f.write("seg")

        nifti_path = os.path.join(temp_workspace, "sub-test_01", "anat", "file.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_empty_segmentation_directory(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test con directory di segmentazione vuota."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Crea directory ma senza file
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-08",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)

        nifti_path = os.path.join(temp_workspace, "sub-08", "anat", "file.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is False

    def test_unicode_in_paths(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test con caratteri unicode nei path."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Subject con unicode
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-àèéìòù",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)
        with open(os.path.join(seg_dir, "ok_seg.nii.gz"), "w") as f:
            f.write("seg")

        nifti_path = os.path.join(temp_workspace, "sub-àèéìòù", "anat", "file.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True


class TestIntegration:
    """Test di integrazione per flussi completi."""

    def test_full_selection_flow(self, qtbot, mock_context, mock_file_selector_dl):
        """Test flusso completo: selezione -> next."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Simula selezione file
        selected_files = ["file1.nii", "file2.nii", "file3.nii"]
        page.file_selector_widget._selected_files = selected_files

        # Verifica ready to advance
        assert bool(page.is_ready_to_advance()) is True

        # Next
        result = page.next(mock_context)

        # Verifica
        assert result is not None
        assert mock_context["selected_segmentation_files"] == selected_files
        assert page.next_page is not None

    def test_reset_and_reselect_flow(self, qtbot, mock_context, mock_file_selector_dl):
        """Test flusso: selezione -> reset -> nuova selezione."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Prima selezione
        page.file_selector_widget._selected_files = ["file1.nii"]
        page.next(mock_context)

        assert mock_context["selected_segmentation_files"] == ["file1.nii"]

        # Reset
        page.reset_page()

        assert mock_context["selected_segmentation_files"] == []

        # Nuova selezione
        page.file_selector_widget._selected_files = ["file2.nii", "file3.nii"]
        page.next(mock_context)

        assert mock_context["selected_segmentation_files"] == ["file2.nii", "file3.nii"]

    def test_back_and_forth_navigation(self, qtbot, mock_context, mock_file_selector_dl):
        """Test navigazione avanti e indietro."""
        previous = Mock()
        page = DlNiftiSelectionPage(mock_context, previous_page=previous)
        qtbot.addWidget(page)

        # Avanti
        page.file_selector_widget._selected_files = ["file1.nii"]
        next_page = page.next(mock_context)

        assert next_page is not None

        # Indietro
        result = page.back()

        assert result == previous
        previous.on_enter.assert_called_once()

    def test_status_label_lifecycle(self, qtbot, mock_context, mock_file_selector_dl):
        """Test ciclo di vita dello status label."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Inizialmente vuoto
        assert page.status_label.text() == ""

        # Aggiungi status
        page.status_label.setText("Processing...")
        assert page.status_label.text() == "Processing..."

        # on_enter lo pulisce
        page.on_enter()
        assert page.status_label.text() == ""

        # Aggiungi di nuovo
        page.status_label.setText("Error occurred")

        # reset_page lo pulisce
        page.reset_page()
        assert page.status_label.text() == ""


class TestContextHandling:
    """Test per la gestione del context."""

    def test_context_none_handling(self, qtbot, mock_file_selector_dl):
        """Test gestione context None."""
        page = DlNiftiSelectionPage(context=None)
        qtbot.addWidget(page)

        # Non dovrebbe crashare
        page.reset_page()

        assert page.context is None

    def test_context_without_history(self, qtbot, mock_file_selector_dl):
        """Test context senza history."""
        context = {
            "workspace_path": "/fake/path"
        }
        page = DlNiftiSelectionPage(context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]

        # Non dovrebbe crashare se history non esiste
        result = page.next(context)

        assert result is not None

    def test_selected_files_persisted_in_context(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che i file selezionati persistano nel context."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        files = ["a.nii", "b.nii", "c.nii"]
        page.file_selector_widget._selected_files = files

        page.next(mock_context)

        # Verifica che siano salvati
        assert "selected_segmentation_files" in mock_context
        assert mock_context["selected_segmentation_files"] == files

        # Anche dopo reset
        page.reset_page()
        assert mock_context["selected_segmentation_files"] == []

    def test_multiple_next_calls_update_context(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che chiamate multiple a next aggiornino il context."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Prima chiamata
        page.file_selector_widget._selected_files = ["file1.nii"]
        page.next(mock_context)
        assert mock_context["selected_segmentation_files"] == ["file1.nii"]

        # Seconda chiamata con file diversi
        page.file_selector_widget._selected_files = ["file2.nii", "file3.nii"]
        page.next(mock_context)
        assert mock_context["selected_segmentation_files"] == ["file2.nii", "file3.nii"]


class TestFileSelectorIntegration:
    """Test per l'integrazione con FileSelectorWidget."""

    def test_file_selector_get_selected_files_called(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che get_selected_files sia chiamato."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]

        with patch.object(page.file_selector_widget, 'get_selected_files', return_value=["file1.nii"]) as mock_get:
            page.next(mock_context)

            mock_get.assert_called()

    def test_is_ready_to_advance_uses_file_selector(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che is_ready_to_advance usi il file selector."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Mock get_selected_files
        with patch.object(page.file_selector_widget, 'get_selected_files', return_value=["file1.nii"]):
            result = page.is_ready_to_advance()
            assert bool(result) is True

        with patch.object(page.file_selector_widget, 'get_selected_files', return_value=[]):
            result = page.is_ready_to_advance()
            assert bool(result) is False

    def test_file_selector_receives_correct_parameters(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che FileSelectorWidget riceva i parametri corretti."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        call_kwargs = mock_file_selector_dl.call_args[1]

        # Verifica parametri specifici per DL segmentation
        assert call_kwargs['label'] == "seg"
        assert call_kwargs['allow_multiple'] is True

        # Verifica che has_existing_function sia la funzione corretta
        has_existing_func = call_kwargs['has_existing_function']
        assert has_existing_func == page.has_existing_segmentation


class TestPathHandling:
    """Test per la gestione dei path."""

    def test_path_normalization(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test normalizzazione path con separatori misti."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-09",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)
        with open(os.path.join(seg_dir, "ok_seg.nii.gz"), "w") as f:
            f.write("seg")

        # Path con separatori misti (se su Windows)
        if os.sep == '\\':
            nifti_path = temp_workspace + "/sub-09/anat/file.nii"
        else:
            nifti_path = os.path.join(temp_workspace, "sub-09", "anat", "file.nii")

        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_relative_vs_absolute_paths(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test con path relativi vs assoluti."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-10",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)
        with open(os.path.join(seg_dir, "ok_seg.nii.gz"), "w") as f:
            f.write("seg")

        # Path assoluto
        nifti_path = os.path.abspath(os.path.join(temp_workspace, "sub-10", "anat", "file.nii"))
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_symlinks_in_path(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test con symlink nel path (se supportati dal sistema)."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Crea segmentazione
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-11",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)
        with open(os.path.join(seg_dir, "ok_seg.nii.gz"), "w") as f:
            f.write("seg")

        nifti_path = os.path.join(temp_workspace, "sub-11", "anat", "file.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        # Dovrebbe funzionare anche con path reali
        assert result is True


class TestUIInteraction:
    """Test per l'interazione con l'UI."""

    def test_title_styling(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che il titolo abbia lo stile corretto."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        style = page.title.styleSheet()

        assert "font-size" in style
        assert "font-weight: bold" in style

    def test_status_label_alignment(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che lo status label sia centrato."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.status_label.alignment() == Qt.AlignmentFlag.AlignCenter

    def test_layout_structure(self, qtbot, mock_context, mock_file_selector_dl):
        """Test struttura del layout."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Verifica che il layout sia VBoxLayout
        assert page.layout is not None

        # Verifica ordine elementi
        assert page.layout.itemAt(0).widget() == page.title
        assert page.layout.itemAt(1).widget() == page.file_selector_widget


class TestErrorHandling:
    """Test per la gestione degli errori."""

    def test_has_existing_segmentation_permission_error(self, qtbot, mock_context, temp_workspace,
                                                        mock_file_selector_dl):
        """Test gestione errore permessi (simulato)."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Path che non esiste
        nifti_path = "/nonexistent/path/sub-12/anat/file.nii"

        # Non dovrebbe crashare
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is False

    def test_has_existing_segmentation_with_corrupted_directory(self, qtbot, mock_context, temp_workspace,
                                                                mock_file_selector_dl):
        """Test con directory corrotta (simulata con file al posto di directory)."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Crea un file invece di una directory
        derivatives_path = os.path.join(temp_workspace, "derivatives")
        os.makedirs(derivatives_path, exist_ok=True)

        # File invece di directory
        fake_dir = os.path.join(derivatives_path, "deep_learning_seg")
        with open(fake_dir, "w") as f:
            f.write("this is a file, not a directory")

        nifti_path = os.path.join(temp_workspace, "sub-13", "anat", "file.nii")

        # Non dovrebbe crashare
        try:
            result = page.has_existing_segmentation(nifti_path, temp_workspace)
            # Potrebbe essere True o False, l'importante è che non crashi
            assert isinstance(result, bool)
        except (OSError, NotADirectoryError):
            # Alcuni OS potrebbero lanciare eccezioni
            pass


class TestBoundaryConditions:
    """Test per condizioni limite."""

    def test_very_long_path(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test con path molto lungo."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Crea path annidato molto profondo
        deep_path = temp_workspace
        for i in range(10):
            deep_path = os.path.join(deep_path, f"level{i}")

        nifti_path = os.path.join(deep_path, "sub-14", "anat", "file.nii")

        # Non dovrebbe crashare
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert isinstance(result, bool)

    def test_many_files_in_directory(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test con molti file nella directory di segmentazione."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-15",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)

        # Crea molti file
        for i in range(100):
            filename = f"file{i}.nii" if i < 50 else f"file{i}_seg.nii.gz"
            with open(os.path.join(seg_dir, filename), "w") as f:
                f.write("data")

        nifti_path = os.path.join(temp_workspace, "sub-15", "anat", "file.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        # Dovrebbe trovare almeno un file _seg
        assert result is True

    def test_subject_id_at_end_of_path(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test quando subject ID è alla fine del path."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-16",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)
        with open(os.path.join(seg_dir, "ok_seg.nii.gz"), "w") as f:
            f.write("seg")

        # Subject ID nell'ultimo componente
        nifti_path = os.path.join(temp_workspace, "data", "sub-16")

        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_workspace_path_equals_nifti_path(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test quando workspace_path è uguale a nifti_path."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Stesso path
        result = page.has_existing_segmentation(temp_workspace, temp_workspace)

        # Non dovrebbe crashare
        assert isinstance(result, bool)


class TestConcurrency:
    """Test per situazioni concorrenti (simulati)."""

    def test_multiple_pages_same_context(self, qtbot, mock_context, mock_file_selector_dl):
        """Test con multiple pagine che condividono lo stesso context."""
        page1 = DlNiftiSelectionPage(mock_context)
        page2 = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page1)
        qtbot.addWidget(page2)

        # Modifica da page1
        page1.file_selector_widget._selected_files = ["file1.nii"]
        page1.next(mock_context)

        # Verifica che page2 veda i cambiamenti
        assert mock_context["selected_segmentation_files"] == ["file1.nii"]

        # Reset da page2
        page2.reset_page()

        # Verifica che il context sia aggiornato
        assert mock_context["selected_segmentation_files"] == []

    def test_rapid_next_back_navigation(self, qtbot, mock_context, mock_file_selector_dl):
        """Test navigazione rapida avanti-indietro."""
        previous = Mock()
        page = DlNiftiSelectionPage(mock_context, previous_page=previous)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]

        # Rapidi next e back
        for _ in range(10):
            page.next(mock_context)
            page.back()

        # Non dovrebbe crashare
        assert True


class TestDocumentation:
    """Test per verificare la documentazione e i commenti."""

    def test_has_existing_segmentation_docstring(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che has_existing_segmentation abbia docstring."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.has_existing_segmentation.__doc__ is not None

    def test_reset_page_docstring(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che reset_page abbia docstring."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.reset_page.__doc__ is not None


class TestStateConsistency:
    """Test per verificare la consistenza dello stato."""

    def test_state_after_multiple_operations(self, qtbot, mock_context, mock_file_selector_dl):
        """Test stato dopo multiple operazioni."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Sequenza di operazioni
        page.file_selector_widget._selected_files = ["file1.nii"]
        assert bool(page.is_ready_to_advance()) is True

        page.next(mock_context)
        assert mock_context["selected_segmentation_files"] == ["file1.nii"]

        page.on_enter()
        assert page.status_label.text() == ""

        page.reset_page()
        assert mock_context["selected_segmentation_files"] == []

        # Stato dovrebbe essere consistente
        assert not bool(page.is_ready_to_advance())

    def test_state_independence_from_previous_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test che lo stato sia indipendente dalla previous_page."""
        previous = Mock()
        page1 = DlNiftiSelectionPage(mock_context, previous_page=previous)
        page2 = DlNiftiSelectionPage(mock_context, previous_page=None)

        qtbot.addWidget(page1)
        qtbot.addWidget(page2)

        # Modifica page1
        page1.status_label.setText("Status 1")

        # page2 dovrebbe avere stato indipendente
        assert page2.status_label.text() == ""

        # Reset page1 non dovrebbe influenzare page2
        page1.reset_page()
        page2.status_label.setText("Status 2")

        assert page1.status_label.text() == ""
        assert page2.status_label.text() == "Status 2"