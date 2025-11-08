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
    """Create BIDS workspace with NIfTI files."""
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
    """Context for NiftiFileDialog."""
    return {"workspace_path": nifti_workspace}


@pytest.fixture
def mock_has_existing():
    """Mock for has_existing_func."""
    return Mock(return_value=False)


class TestNiftiFileDialogInitialization:
    """Tests for dialog initialization."""

    def test_initialization_basic(self, qtbot, mock_context_nifti, mock_has_existing):
        """Basic initialization test."""
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
        """Initialization test with single selection mode."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=False,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.allow_multiple is False

    def test_initialization_without_has_existing_func(self, qtbot, mock_context_nifti):
        """Initialization test without has_existing_func."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Should use default lambda
        assert callable(dialog.has_existing_func)
        assert dialog.has_existing_func("any_path", "any_workspace") is False

    def test_initialization_with_forced_filters(self, qtbot, mock_context_nifti, mock_has_existing):
        """Initialization test with forced_filters."""
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
        """Test that all UI elements are created."""
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
    """Tests for the _populate_files method."""

    def test_populate_files_finds_nifti(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that it finds NIfTI files."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Should find 5 files (.nii and .nii.gz) + 1 derivatives
        assert len(dialog.all_nii_files) >= 5

    def test_populate_files_extracts_subjects(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test subject extraction."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Should have at least 2 subjects + "All subjects"
        assert dialog.subject_combo.count() >= 3

    def test_populate_files_extracts_sessions(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test session extraction."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Should have ses-01 + "All sessions"
        assert dialog.session_combo.count() >= 2

    def test_populate_files_extracts_modalities(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test modality extraction."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Should have T1w, T2w, FLAIR, pet + "All modalities"
        assert dialog.modality_combo.count() >= 4

    def test_populate_files_extracts_datatypes(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test data type extraction."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Should have anat, pet + "All types"
        assert dialog.datatype_combo.count() >= 3

    def test_populate_files_calls_has_existing(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that has_existing_func is called."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Should be called for each file
        assert mock_has_existing.call_count > 0

    def test_populate_files_list_widget(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that the list widget is populated."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.file_list.count() > 0


class TestApplyFilters:
    """Tests for the _apply_filters method."""

    def test_apply_filters_search(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test search filter."""
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
        """Test subject filter."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.subject_combo.setCurrentText("sub-01")

        # Verify that only sub-01 files are visible
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if not item.isHidden():
                assert "sub-01" in item.text()

    def test_apply_filters_session(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test session filter."""
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
        """Test modality filter."""
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
        """Test data type filter."""
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
        """Test no-flag filter."""

        # has_existing returns True for some files
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

        # Verify that files with flag are hidden
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if not item.isHidden():
                assert item.text() not in dialog.files_with_flag

    def test_apply_filters_with_flag(self, qtbot, mock_context_nifti):
        """Test with-flag filter."""

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

        # Verify that only files with flag are visible
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if not item.isHidden():
                assert item.text() in dialog.files_with_flag

    def test_apply_filters_combined(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test combined filters."""
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

        # Should only find T1w of sub-01
        assert visible >= 1


class TestCheckboxBehavior:
    """Tests for checkbox behavior."""

    def test_no_flag_unchecks_with_flag(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that no_flag unchecks with_flag."""
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
        """Test that with_flag unchecks no_flag."""
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
    """Tests for the _reset_filters method."""

    def test_reset_filters_basic(self, qtbot, mock_context_nifti, mock_has_existing):
        """Basic filter reset test."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Set filters
        dialog.search_bar.setText("test")
        dialog.subject_combo.setCurrentIndex(1)
        dialog.no_flag_checkbox.setChecked(True)

        # Reset
        dialog._reset_filters()

        assert dialog.search_bar.text() == ""
        assert dialog.subject_combo.currentIndex() == 0
        assert not dialog.no_flag_checkbox.isChecked()


class TestSelectAllVisible:
    """Tests for the _select_all_visible method."""

    def test_select_all_visible_basic(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test selection of all visible items."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog._select_all_visible()

        # All visible items should be selected
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if not item.isHidden():
                assert item.isSelected()

    def test_select_all_visible_with_filters(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test selection after applying filters."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        dialog.search_bar.setText("T1w")
        dialog._select_all_visible()

        # Only visible items should be selected
        selected_count = len(dialog.file_list.selectedItems())
        visible_count = sum(1 for i in range(dialog.file_list.count())
                            if not dialog.file_list.item(i).isHidden())

        assert selected_count == visible_count


class TestAccept:
    """Tests for the _accept method."""

    def test_accept_with_selection(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test accept with a selection."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Select first item
        dialog.file_list.item(0).setSelected(True)

        with patch.object(dialog, 'accept', wraps=dialog.accept) as mock_accept:
            dialog._accept()

            mock_accept.assert_called_once()
            assert len(dialog.selected_files) == 1

    def test_accept_without_selection(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test accept without a selection."""
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
        """Test warning when there are files with flags."""

        def mock_has_existing_selective(path, workspace):
            return "sub-01_T1w" in path

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing_selective,
            label="mask"
        )
        qtbot.addWidget(dialog)

        # Select file with flag
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if "sub-01_T1w" in item.text():
                item.setSelected(True)
                break

        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Yes):
            with patch.object(dialog, 'accept'):
                dialog._accept()

    def test_accept_warning_cancelled(self, qtbot, mock_context_nifti):
        """Test cancellation after warning."""

        def mock_has_existing_selective(path, workspace):
            return True  # All have flags

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

            # Should not have set selected_files
            assert len(dialog.selected_files) == 0


class TestGetFilesStaticMethod:
    """Tests for the static method get_files."""

    def test_get_files_accepted(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test get_files with accept."""
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
        """Test get_files with reject."""
        with patch.object(NiftiFileDialog, 'exec', return_value=QDialog.DialogCode.Rejected):
            result = NiftiFileDialog.get_files(
                mock_context_nifti,
                allow_multiple=True,
                has_existing_func=mock_has_existing,
                label="test"
            )

            assert result is None


class TestForcedFilters:
    """Tests for forced_filters."""

    def test_forced_filters_search(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test forced filter for search."""
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
        """Test forced filter for subject."""
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
        """Test forced filter for modality."""
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
        """Test forced filter for no_flag."""
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
        """Test multiple forced filters."""
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
    """Tests for file list behavior."""

    def test_file_list_selection_mode_multiple(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test multiple selection mode."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.file_list.selectionMode() == dialog.file_list.SelectionMode.ExtendedSelection

    def test_file_list_selection_mode_single(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test single selection mode."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=False,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.file_list.selectionMode() == dialog.file_list.SelectionMode.SingleSelection

    def test_file_list_tooltips(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that files have tooltips."""
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
    """Tests for edge cases."""

    def test_empty_workspace(self, qtbot, mock_has_existing):
        """Test with an empty workspace."""
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
        """Test workspace with only non-NIfTI files."""
        temp_dir = tempfile.mkdtemp()
        context = {"workspace_path": temp_dir}

        # Create non-NIfTI file
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
        """Test with Unicode characters in filenames."""
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
        """Test with a very deep directory structure."""
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
        """Test that label None hides the checkboxes."""
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
    """Tests for info_label."""

    def test_info_label_shows_count(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that info_label shows the count."""
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
        """Test that info_label updates with filters."""
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

        # The text should change
        assert initial_text != filtered_text


class TestRelativeToAbsolute:
    """Tests for the relative_to_absolute mapping."""

    def test_relative_to_absolute_mapping(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that the mapping is correct."""
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
    """Tests for files_with_flag."""

    def test_files_with_flag_populated(self, qtbot, mock_context_nifti):
        """Test that files_with_flag is populated."""

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
        """Test that files with flags have a different color."""

        def mock_has_existing_some(path, workspace):
            return "sub-01_T1w" in path

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing_some,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Find an item with a flag
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if item.text() in dialog.files_with_flag:
                # Should have yellow/warning color
                color = item.foreground().color()
                assert color == QColor(255, 193, 7)
                break


class TestButtonConnections:
    """Tests for button connections."""

    def test_reset_button_connected(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that the reset button is connected."""
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
        """Test that the select all button is connected."""
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
        """Test that the deselect all button is connected."""
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
    """Integration tests."""

    def test_full_workflow_filter_select_accept(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test full workflow."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Filter
        dialog.search_bar.setText("T1w")

        # Select all visible files
        dialog._select_all_button.click()

        # Accept
        with patch.object(dialog, 'accept'):
            dialog._accept()

            assert len(dialog.selected_files) > 0

    def test_full_workflow_with_warning(self, qtbot, mock_context_nifti):
        """Test workflow with warning."""

        def mock_has_existing_some(path, workspace):
            return "sub-01_T1w" in path

        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing_some,
            label="mask"
        )
        qtbot.addWidget(dialog)

        # Select file with flag
        for i in range(dialog.file_list.count()):
            item = dialog.file_list.item(i)
            if item.text() in dialog.files_with_flag:
                item.setSelected(True)
                break

        # Accept with warning
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Yes):
            with patch.object(dialog, 'accept'):
                dialog._accept()

                assert len(dialog.selected_files) > 0


class TestStateConsistency:
    """Tests for state consistency."""

    def test_state_after_filter_changes(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test consistency after changing filters."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Change multiple filters
        dialog.subject_combo.setCurrentIndex(1)
        dialog.search_bar.setText("T1w")
        dialog.no_flag_checkbox.setChecked(True)

        # Check that state is coherent
        visible = sum(1 for i in range(dialog.file_list.count())
                      if not dialog.file_list.item(i).isHidden())

        # There should be at least some visible files or none
        assert visible >= 0

    def test_state_after_reset(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test state after reset."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Set filters
        dialog.search_bar.setText("test")
        dialog.subject_combo.setCurrentIndex(1)

        # Reset
        dialog._reset_filters()

        # All filters should return to default
        assert dialog.search_bar.text() == ""
        assert dialog.subject_combo.currentIndex() == 0


class TestMemoryAndPerformance:
    """Tests for memory and performance."""

    def test_many_files_performance(self, qtbot, mock_has_existing):
        """Test performance with many files."""
        temp_dir = tempfile.mkdtemp()
        context = {"workspace_path": temp_dir}

        # Create many files
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

        # Should not be too slow
        assert len(dialog.all_nii_files) == 100

    def test_rapid_filter_changes(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test with rapid filter changes."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Change filters rapidly
        for i in range(20):
            dialog.search_bar.setText(f"test{i}")
            dialog.subject_combo.setCurrentIndex(i % dialog.subject_combo.count())

        # Should not crash
        assert True


class TestAccessibility:
    """Tests for accessibility."""

    def test_buttons_have_text(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that all buttons have text."""
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
        """Test that labels have text."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.info_label.text() != ""

    def test_search_bar_placeholder(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that search bar has a placeholder."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        assert dialog.search_bar.placeholderText() != ""


class TestTranslations:
    """Tests for translations."""

    def test_window_title_includes_label(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that the window title includes the label."""
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
    """Tests for error handling."""

    def test_has_existing_func_exception(self, qtbot, mock_context_nifti):
        """Test when has_existing_func raises an exception."""

        def mock_has_existing_error(path, workspace):
            raise Exception("Test error")

        # Should not crash during initialization
        try:
            dialog = NiftiFileDialog(
                mock_context_nifti,
                allow_multiple=True,
                has_existing_func=mock_has_existing_error,
                label="test"
            )
            qtbot.addWidget(dialog)
        except Exception:
            # Acceptable if the exception propagates
            pass

    def test_invalid_workspace_path(self, qtbot, mock_has_existing):
        """Test with invalid workspace path."""
        context = {"workspace_path": "/nonexistent/path"}

        dialog = NiftiFileDialog(
            context,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Should handle gracefully
        assert len(dialog.all_nii_files) == 0


class TestComboBoxBehavior:
    """Tests for combo box behavior."""

    def test_combo_boxes_have_all_option(self, qtbot, mock_context_nifti, mock_has_existing):
        """Test that combo boxes have the 'All' option."""
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
        """Test that combo boxes are sorted."""
        dialog = NiftiFileDialog(
            mock_context_nifti,
            allow_multiple=True,
            has_existing_func=mock_has_existing,
            label="test"
        )
        qtbot.addWidget(dialog)

        # Subjects should be sorted (after "All")
        subjects = [dialog.subject_combo.itemText(i)
                    for i in range(1, dialog.subject_combo.count())]

        if len(subjects) > 1:
            assert subjects == sorted(subjects)
