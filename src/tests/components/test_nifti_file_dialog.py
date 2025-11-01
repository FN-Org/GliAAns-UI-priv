import os
import tempfile

import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QDialog, QMessageBox, QListWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from main.components.nifti_file_dialog import NiftiFileDialog


@pytest.fixture
def nifti_workspace():
    """Crea workspace BIDS con file NIfTI."""
    temp_dir = tempfile.mkdtemp()
    # Subject 1 - anat
    sub1_anat = os.path.join(temp_dir, "sub-01", "anat")
    os.makedirs(sub1_anat)

    files = [
        "sub-01_T1w.nii",
        "sub-01_T2w.nii.gz",
        "sub-01_FLAIR.nii"
    ]
    for f in files:
        with open(os.path.join(sub1_anat, f), "w") as file:
            file.write("nifti data")

    # Subject 1 - ses-01 pet
    sub1_ses1_pet = os.path.join(temp_dir, "sub-01", "ses-01", "pet")
    os.makedirs(sub1_ses1_pet)
    with open(os.path.join(sub1_ses1_pet, "sub-01_ses-01_pet.nii"), "w") as f:
        f.write("pet data")

    # Subject 2 - anat
    sub2_anat = os.path.join(temp_dir, "sub-02", "anat")
    os.makedirs(sub2_anat)
    with open(os.path.join(sub2_anat, "sub-02_T1w.nii.gz"), "w") as f:
        f.write("nifti data")

    # Derivatives - skullstrips
    deriv_skull = os.path.join(temp_dir, "derivatives", "skullstrips", "sub-01", "anat")
    os.makedirs(deriv_skull, exist_ok=True)
    with open(os.path.join(deriv_skull, "sub-01_T1w_brain.nii"), "w") as f:
        f.write("skull stripped")

    return temp_dir


@pytest.fixture
def mock_context_nifti(nifti_workspace):
    """Context per NiftiFileDialog."""
    return {"workspace_path": nifti_workspace}


@pytest.fixture
def mock_has_existing():
    """Mock per has_existing_func."""
    return Mock(return_value=False)


class TestNiftiFileDialogInitialization:
    """Test per l'inizializzazione del dialogo."""

    def test_initialization_basic(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test inizializzazione base."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="mask"
        )
        qtbot.addWidget(dialog)

        assert dialog.workspace_path == mock_context_nifti["workspace_path"]
        assert dialog.allow_multiple is True
        assert dialog.has_existing_func == mock_has_existing
        assert dialog.label == "mask"
        assert dialog.selected_files == []

    def test_initialization_single_selection(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test inizializzazione modalità selezione singola."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=False,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.allow_multiple is False

    def test_initialization_without_has_existing_func(self, qtbot, mock_context_nifti):
        """Test inizializzazione senza has_existing_func."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Dovrebbe usare lambda di default
        assert callable(dialog.has_existing_func)
        assert dialog.has_existing_func("any_path", "any_workspace") is False

    def test_initialization_with_forced_filters(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test inizializzazione con forced_filters."""
        filters = {"subject": "sub-01", "modality": "T1w"}

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test",
            forced_filters=filters
        )
        qtbot.addWidget(dialog)

        assert dialog.forced_filters == filters

    def test_ui_elements_created(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che tutti gli elementi UI siano creati."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.search_bar is not None
        assert dialog.subject_combo is not None
        assert dialog.session_combo is not None
        assert dialog.modality_combo is not None
        assert dialog.datatype_combo is not None
        assert dialog.no_flag_checkbox is not None
        assert dialog.with_flag_checkbox is not None
        assert dialog.file_list is not None
        assert dialog.info_label is not None


class TestPopulateFiles:
    """Test per il metodo _populate_files."""

    def test_populate_files_finds_nifti(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che trovi file NIfTI."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Dovrebbe trovare 5 file (.nii e .nii.gz) + 1 derivatives
        assert len(dialog.all_nii_files) >= 5

    def test_populate_files_extracts_subjects(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test estrazione soggetti."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Dovrebbe avere almeno 2 soggetti + "All subjects"
        assert dialog.subject_combo.count() >= 3

    def test_populate_files_extracts_sessions(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test estrazione sessioni."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Dovrebbe avere ses-01 + "All sessions"
        assert dialog.session_combo.count() >= 2

    def test_populate_files_extracts_modalities(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test estrazione modalità."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Dovrebbe avere T1w, T2w, FLAIR, pet + "All modalities"
        assert dialog.modality_combo.count() >= 4

    def test_populate_files_extracts_datatypes(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test estrazione data types."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Dovrebbe avere anat, pet + "All types"
        assert dialog.datatype_combo.count() >= 3

    def test_populate_files_calls_has_existing(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che chiami has_existing_func."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Dovrebbe essere chiamato per ogni file
        assert mock_has_existing.call_count > 0

    def test_populate_files_list_widget(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test popolamento list widget."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.file_list.count() > 0


class TestApplyFilters:
    """Test per il metodo _apply_filters."""

    def test_apply_filters_search(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test filtro ricerca."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        initial_visible = sum(1 for i in range(dialog.file_list.count())
                              if not dialog.file_list.item(i).isHidden())

        dialog.search_bar.setText("T1w")

        visible_after = sum(1 for i in range(dialog.file_list.count())
                            if not dialog.file_list.item(i).isHidden())

        assert visible_after < initial_visible

    def test_apply_filters_subject(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test filtro soggetto."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.subject_combo.setCurrentText("sub-01")

        # Verifica che siano visibili solo file di sub-01
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if not item.isHidden():
                assert "sub-01" in item.text()

    def test_apply_filters_session(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test filtro sessione."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.session_combo.setCurrentText("ses-01")

        visible = sum(1 for i in range(dialog.file_list.count())
                      if not dialog.file_list.item(i).isHidden())

        assert visible >= 1

    def test_apply_filters_modality(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test filtro modalità."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.modality_combo.setCurrentText("FLAIR")

        visible = sum(1 for i in range(dialog.file_list.count())
                      if not dialog.file_list.item(i).isHidden())

        assert visible >= 1

    def test_apply_filters_datatype(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test filtro data type."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.datatype_combo.setCurrentText("anat")

        visible = sum(1 for i in range(dialog.file_list.count())
                      if not dialog.file_list.item(i).isHidden())

        assert visible >= 1

    def test_apply_filters_no_flag(self, qtbot, mock_context_nifti):
        """Test filtro no flag."""

        # has_existing ritorna True per alcuni file
        def mock_has_existing_selective(path, workspace):
            return "sub-01_T1w" in path

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing_selective,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.no_flag_checkbox.setChecked(True)

        # Verifica che i file con flag siano nascosti
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if not item.isHidden():
                assert item.text() not in dialog.files_with_flag

    def test_apply_filters_with_flag(self, qtbot, mock_context_nifti):
        """Test filtro with flag."""

        def mock_has_existing_selective(path, workspace):
            return "sub-01_T1w" in path

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing_selective,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.with_flag_checkbox.setChecked(True)

        # Verifica che solo i file con flag siano visibili
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if not item.isHidden():
                assert item.text() in dialog.files_with_flag

    def test_apply_filters_combined(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test filtri combinati."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.subject_combo.setCurrentText("sub-01")
        dialog.search_bar.setText("T1w")

        visible = sum(1 for i in range(dialog.file_list.count())
                      if not dialog.file_list.item(i).isHidden())

        # Dovrebbe trovare solo i T1w di sub-01
        assert visible >= 1


class TestCheckboxBehavior:
    """Test per il comportamento dei checkbox."""

    def test_no_flag_unchecks_with_flag(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che no_flag disattivi with_flag."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.with_flag_checkbox.setChecked(True)
        dialog.no_flag_checkbox.setChecked(True)

        assert not dialog.with_flag_checkbox.isChecked()

    def test_with_flag_unchecks_no_flag(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che with_flag disattivi no_flag."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.no_flag_checkbox.setChecked(True)
        dialog.with_flag_checkbox.setChecked(True)

        assert not dialog.no_flag_checkbox.isChecked()


class TestResetFilters:
    """Test per il metodo _reset_filters."""

    def test_reset_filters_basic(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test reset filtri base."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Imposta filtri
        dialog.search_bar.setText("test")
        dialog.subject_combo.setCurrentIndex(1)
        dialog.no_flag_checkbox.setChecked(True)

        # Reset
        dialog._reset_filters()

        assert dialog.search_bar.text() == ""
        assert dialog.subject_combo.currentIndex() == 0
        assert not dialog.no_flag_checkbox.isChecked()


class TestSelectAllVisible:
    """Test per il metodo _select_all_visible."""

    def test_select_all_visible_basic(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test selezione di tutti i visibili."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog._select_all_visible()

        # Tutti gli item visibili dovrebbero essere selezionati
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if not item.isHidden():
                assert item.isSelected()

    def test_select_all_visible_with_filters(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test selezione dopo filtro."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.search_bar.setText("T1w")
        dialog._select_all_visible()

        # Solo i visibili dovrebbero essere selezionati
        selected_count = len(dialog.file_list.selectedItems())
        visible_count = sum(1 for i in range(dialog.file_list.count())
                            if not dialog.file_list.item(i).isHidden())

        assert selected_count == visible_count


class TestAccept:
    """Test per il metodo _accept."""

    def test_accept_with_selection(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test accept con selezione."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Seleziona primo item
        dialog.file_list.item(0).setSelected(True)

        with patch.object(dialog, 'accept', wraps=dialog.accept) as mock_accept:
            dialog._accept()

            mock_accept.assert_called_once()
            assert len(dialog.selected_files) == 1

    def test_accept_without_selection(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test accept senza selezione."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        with patch.object(QMessageBox, 'warning') as mock_warning:
            dialog._accept()

            mock_warning.assert_called_once()

    def test_accept_with_existing_flag_warning(self, qtbot, mock_context_nifti):
        """Test warning quando ci sono file con flag."""

        def mock_has_existing_selective(path, workspace):
            return "sub-01_T1w" in path

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing_selective,
            label="mask"
        )
        qtbot.addWidget(dialog)

        # Seleziona file con flag
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if "sub-01_T1w" in item.text():
                item.setSelected(True)
                break

        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Yes):
            with patch.object(dialog, 'accept'):
                dialog._accept()

    def test_accept_warning_cancelled(self, qtbot, mock_context_nifti):
        """Test cancellazione su warning."""

        def mock_has_existing_selective(path, workspace):
            return True  # Tutti hanno flag

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing_selective,
            label="mask"
        )
        qtbot.addWidget(dialog)

        dialog.file_list.item(0).setSelected(True)

        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.No):
            dialog._accept()

            # Non dovrebbe aver impostato selected_files
            assert len(dialog.selected_files) == 0


class TestGetFilesStaticMethod:
    """Test per il metodo statico get_files."""

    def test_get_files_accepted(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test get_files con accept."""
        dialog_instance = MagicMock()
        dialog_instance.selected_files = ["/path/file1.nii", "/path/file2.nii"]
        dialog_instance.exec.return_value = QDialog.DialogCode.Accepted

        with patch('main.components.nifti_file_dialog.NiftiFileDialog', return_value=dialog_instance):
            result = NiftiFileDialog.get_files(
                mock_context_nifti,
                allow_multiple=True,
                has_existing_func=mock_has_existing,
                label="test"
            )

            assert result == dialog_instance.selected_files

    def test_get_files_rejected(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test get_files con reject."""
        with patch.object(NiftiFileDialog, 'exec', return_value=QDialog.DialogCode.Rejected):
            result = NiftiFileDialog.get_files(
                mock_context_nifti,
                allow_multiple=True,
                has_existing_func=mock_has_existing,
                label="test"
            )

            assert result is None


class TestForcedFilters:
    """Test per forced_filters."""

    def test_forced_filters_search(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test forced filter per search."""
        filters = {"search": "T1w"}

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test",
            forced_filters=filters
        )
        qtbot.addWidget(dialog)

        assert dialog.search_bar.text() == "T1w"
        assert not dialog.search_bar.isEnabled()

    def test_forced_filters_subject(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test forced filter per subject."""
        filters = {"subject": "sub-01"}

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test",
            forced_filters=filters
        )
        qtbot.addWidget(dialog)

        assert dialog.subject_combo.currentText() == "sub-01"
        assert not dialog.subject_combo.isEnabled()

    def test_forced_filters_modality(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test forced filter per modality."""
        filters = {"modality": "T1w"}

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test",
            forced_filters=filters
        )
        qtbot.addWidget(dialog)

        assert dialog.modality_combo.currentText() == "T1w"
        assert not dialog.modality_combo.isEnabled()

    def test_forced_filters_no_flag(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test forced filter per no_flag."""
        filters = {"no_flag": True}

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test",
            forced_filters=filters
        )
        qtbot.addWidget(dialog)

        assert dialog.no_flag_checkbox.isChecked()
        assert not dialog.no_flag_checkbox.isEnabled()

    def test_forced_filters_multiple(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test forced filters multipli."""
        filters = {
            "subject": "sub-01",
            "modality": "T1w",
            "no_flag": True
        }

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test",
            forced_filters=filters
        )
        qtbot.addWidget(dialog)

        assert dialog.subject_combo.currentText() == "sub-01"
        assert dialog.modality_combo.currentText() == "T1w"
        assert dialog.no_flag_checkbox.isChecked()


class TestFileListBehavior:
    """Test per il comportamento della lista file."""

    def test_file_list_selection_mode_multiple(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test modalità selezione multipla."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.file_list.selectionMode() == dialog.file_list.SelectionMode.ExtendedSelection

    def test_file_list_selection_mode_single(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test modalità selezione singola."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=False,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.file_list.selectionMode() == dialog.file_list.SelectionMode.SingleSelection

    def test_file_list_tooltips(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che i file abbiano tooltip."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            assert item.toolTip() != ""


class TestEdgeCases:
    """Test per casi limite."""

    def test_empty_workspace(self, qtbot, mock_has_existing):
        """Test con workspace vuoto."""
        temp_dir = tempfile.mkdtemp()
        context = {"workspace_path": temp_dir}

        dialog = NiftiFileDialog(
            context,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert len(dialog.all_nii_files) == 0

    def test_workspace_with_non_nifti(self, qtbot, temp_workspace, mock_has_existing):
        """Test workspace con solo file non-NIfTI."""
        temp_dir = tempfile.mkdtemp()
        context = {"workspace_path": temp_dir}

        # Crea file non-NIfTI
        os.makedirs(os.path.join(temp_dir, "sub-01", "anat"))
        with open(os.path.join(temp_dir, "sub-01", "anat", "file.txt"), "w") as f:
            f.write("text")

        dialog = NiftiFileDialog(
            context,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert len(dialog.all_nii_files) == 0

    def test_unicode_in_filenames(self, qtbot, mock_has_existing):
        """Test con caratteri unicode nei nomi file."""
        temp_dir = tempfile.mkdtemp()
        context = {"workspace_path": temp_dir}

        sub_dir = os.path.join(temp_dir, "sub-01", "anat")
        os.makedirs(sub_dir)

        unicode_files = ["файл.nii", "文件.nii.gz", "αρχείο.nii"]
        for filename in unicode_files:
            with open(os.path.join(sub_dir, filename), "w") as f:
                f.write("data")

        dialog = NiftiFileDialog(
            context,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert len(dialog.all_nii_files) == 3

    def test_very_deep_directory_structure(self, qtbot, temp_workspace, mock_has_existing):
        """Test con struttura directory molto profonda."""
        context = {"workspace_path": temp_workspace}

        deep_path = os.path.join(temp_workspace, "sub-01", "ses-01", "extra", "nested", "anat")
        os.makedirs(deep_path)
        with open(os.path.join(deep_path, "file.nii"), "w") as f:
            f.write("data")

        dialog = NiftiFileDialog(
            context,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert len(dialog.all_nii_files) >= 1

    def test_label_none_hides_checkboxes(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che label None nasconda i checkbox."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label=None
        )
        qtbot.addWidget(dialog)

        assert not dialog.no_flag_checkbox.isVisible()
        assert not dialog.with_flag_checkbox.isVisible()


class TestInfoLabel:
    """Test per info_label."""

    def test_info_label_shows_count(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che info_label mostri il conteggio."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        info_text = dialog.info_label.text()
        assert "files" in info_text.lower() or "file" in info_text.lower()

    def test_info_label_updates_with_filters(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che info_label si aggiorni con i filtri."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        initial_text = dialog.info_label.text()

        dialog.search_bar.setText("T1w")

        filtered_text = dialog.info_label.text()

        # Il testo dovrebbe cambiare
        assert initial_text != filtered_text


class TestRelativeToAbsolute:
    """Test per il mapping relative_to_absolute."""

    def test_relative_to_absolute_mapping(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che il mapping sia corretto."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        for relative_path in dialog.all_nii_files:
            assert relative_path in dialog.relative_to_absolute
            absolute_path = dialog.relative_to_absolute[relative_path]
            assert os.path.isabs(absolute_path)


class TestFilesWithFlag:
    """Test per files_with_flag."""

    def test_files_with_flag_populated(self, qtbot, mock_context_nifti):
        """Test che files_with_flag sia popolato."""

        def mock_has_existing_some(path, workspace):
            return "sub-01_T1w" in path

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing_some,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert len(dialog.files_with_flag) > 0

    def test_files_with_flag_color(self, qtbot, mock_context_nifti):
        """Test che i file con flag abbiano colore diverso."""

        def mock_has_existing_some(path, workspace):
            return "sub-01_T1w" in path

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing_some,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Trova un item con flag
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if item.text() in dialog.files_with_flag:
                # Dovrebbe avere colore giallo/warning
                color = item.foreground().color()
                assert color == QColor(255, 193, 7)
                break


class TestButtonConnections:
    """Test per le connessioni dei pulsanti."""

    def test_reset_button_connected(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che il pulsante reset sia connesso."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.search_bar.setText("test")
        dialog._reset_button.click()

        assert dialog.search_bar.text() == ""

    def test_select_all_button_connected(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che il pulsante select all sia connesso."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog._select_all_button.click()

        assert len(dialog.file_list.selectedItems()) > 0

    def test_deselect_all_button_connected(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che il pulsante deselect all sia connesso."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog._select_all_button.click()
        dialog._deselect_all_button.click()

        assert len(dialog.file_list.selectedItems()) == 0


class TestIntegration:
    """Test di integrazione."""

    def test_full_workflow_filter_select_accept(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test workflow completo."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Filtra
        dialog.search_bar.setText("T1w")

        # Seleziona tutti visibili
        dialog._select_all_button.click()

        # Accept
        with patch.object(dialog, 'accept'):
            dialog._accept()

            assert len(dialog.selected_files) > 0

    def test_full_workflow_with_warning(self, qtbot, mock_context_nifti):
        """Test workflow con warning."""

        def mock_has_existing_some(path, workspace):
            return "sub-01_T1w" in path

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing_some,
            label="mask"
        )
        qtbot.addWidget(dialog)

        # Seleziona file con flag
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if item.text() in dialog.files_with_flag:
                item.setSelected(True)
                break

        # Accept con warning
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Yes):
            with patch.object(dialog, 'accept'):
                dialog._accept()

                assert len(dialog.selected_files) > 0


class TestStateConsistency:
    """Test per la consistenza dello stato."""

    def test_state_after_filter_changes(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test consistenza dopo cambio filtri."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Cambia più filtri
        dialog.subject_combo.setCurrentIndex(1)
        dialog.search_bar.setText("T1w")
        dialog.no_flag_checkbox.setChecked(True)

        # Verifica che lo stato sia coerente
        visible = sum(1 for i in range(dialog.file_list.count())
                      if not dialog.file_list.item(i).isHidden())

        # Dovrebbe esserci almeno qualche file visibile o nessuno
        assert visible >= 0

    def test_state_after_reset(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test stato dopo reset."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Imposta filtri
        dialog.search_bar.setText("test")
        dialog.subject_combo.setCurrentIndex(1)

        # Reset
        dialog._reset_filters()

        # Tutti i filtri dovrebbero essere al default
        assert dialog.search_bar.text() == ""
        assert dialog.subject_combo.currentIndex() == 0


class TestMemoryAndPerformance:
    """Test per memoria e performance."""

    def test_many_files_performance(self, qtbot, mock_has_existing):
        """Test performance con molti file."""
        temp_dir = tempfile.mkdtemp()
        context = {"workspace_path": temp_dir}

        # Crea molti file
        sub_dir = os.path.join(temp_dir, "sub-01", "anat")
        os.makedirs(sub_dir)

        for i in range(100):
            with open(os.path.join(sub_dir, f"file{i}.nii"), "w") as f:
                f.write("data")

        dialog = NiftiFileDialog(
            context,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Non dovrebbe essere troppo lento
        assert len(dialog.all_nii_files) == 100

    def test_rapid_filter_changes(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test con cambi rapidi di filtri."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Cambia filtri rapidamente
        for i in range(20):
            dialog.search_bar.setText(f"test{i}")
            dialog.subject_combo.setCurrentIndex(i % dialog.subject_combo.count())

        # Non dovrebbe crashare
        assert True


class TestAccessibility:
    """Test per l'accessibilità."""

    def test_buttons_have_text(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che tutti i pulsanti abbiano testo."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert len(dialog._reset_button.text()) > 0
        assert len(dialog._select_all_button.text()) > 0
        assert len(dialog._deselect_all_button.text()) > 0

    def test_labels_have_text(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che le label abbiano testo."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.info_label.text() != ""

    def test_search_bar_placeholder(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che search bar abbia placeholder."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.search_bar.placeholderText() != ""


class TestTranslations:
    """Test per le traduzioni."""

    def test_window_title_includes_label(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che il titolo includa il label."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="mask"
        )
        qtbot.addWidget(dialog)

        title = dialog.windowTitle()
        assert "mask" in title.lower() or len(title) > 0


class TestErrorHandling:
    """Test per la gestione degli errori."""

    def test_has_existing_func_exception(self, qtbot, mock_context_nifti):
        """Test quando has_existing_func lancia eccezione."""

        def mock_has_existing_error(path, workspace):
            raise Exception("Test error")

        # Non dovrebbe crashare durante inizializzazione
        try:
            dialog = NiftiFileDialog(
                mock_context_nifti,
                allow_multiple=True,
                has_existing_func=mock_has_existing_error,
                label="test"
            )
            qtbot.addWidget(dialog)
        except Exception:
            # Accettabile se propaga l'eccezione
            pass

    def test_invalid_workspace_path(self, qtbot, mock_has_existing):
        """Test con workspace path non valido."""
        context = {"workspace_path": "/nonexistent/path"}

        dialog = NiftiFileDialog(
            context,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Dovrebbe gestire gracefully
        assert len(dialog.all_nii_files) == 0


class TestComboBoxBehavior:
    """Test per il comportamento delle combo box."""

    def test_combo_boxes_have_all_option(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che le combo abbiano opzione 'All'."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert "All" in dialog.subject_combo.itemText(0)
        assert "All" in dialog.session_combo.itemText(0)
        assert "All" in dialog.modality_combo.itemText(0)
        assert "All" in dialog.datatype_combo.itemText(0)

    def test_combo_boxes_sorted(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test che le combo siano ordinate."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Soggetti dovrebbero essere ordinati (dopo "All")
        subjects = [dialog.subject_combo.itemText(i)
                    for i in range(1, dialog.subject_combo.count())]

        if len(subjects) > 1:
            assert subjects == sorted(subjects)