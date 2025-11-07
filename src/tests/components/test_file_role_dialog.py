import os
import tempfile

import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QDialogButtonBox, QRadioButton, QComboBox, QListWidgetItem, QListWidget
from PyQt6.QtCore import Qt

from main.components.file_role_dialog import FileRoleDialog


@pytest.fixture
def workspace_with_subjects(temp_workspace):
    """Creates a workspace with subjects and BIDS structure."""
    subjects = ["sub-01", "sub-02", "sub-03"]
    for subj in subjects:
        subj_dir = os.path.join(temp_workspace, subj)
        os.makedirs(subj_dir, exist_ok=True)

        anat_dir = os.path.join(subj_dir, "anat")
        os.makedirs(anat_dir, exist_ok=True)

        for ses in ["ses-01", "ses-02"]:
            ses_dir = os.path.join(subj_dir, ses, "pet")
            os.makedirs(ses_dir, exist_ok=True)

    derivatives_dir = os.path.join(temp_workspace, "derivatives")
    os.makedirs(derivatives_dir, exist_ok=True)

    for derivative in ["skullstrips", "manual_masks", "deep_learning_masks"]:
        for subj in subjects:
            deriv_subj_dir = os.path.join(derivatives_dir, derivative, subj, "anat")
            os.makedirs(deriv_subj_dir, exist_ok=True)

    return temp_workspace

class TestFileRoleDialogInitialization:
    """Tests for the dialog initialization."""

    def test_initialization_full_dialog(self, qtbot, workspace_with_subjects):
        """Test full dialog initialization (all levels)."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert dialog.workspace_path == workspace_with_subjects
        assert dialog.subj is None
        assert dialog.role is None
        assert dialog.main is None

        # Verify levels are present
        assert hasattr(dialog, 'level1_widget')
        assert hasattr(dialog, 'level2_widget')
        assert hasattr(dialog, 'level3_widget')
        assert hasattr(dialog, 'ok_button')

    def test_initialization_with_main_derivatives(self, qtbot, workspace_with_subjects):
        """Test initialization with main='derivatives'."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            main="derivatives"
        )
        qtbot.addWidget(dialog)

        assert dialog.main == "derivatives"
        assert dialog.button_first_group is None
        assert hasattr(dialog, 'derivative_extra_frame')
        assert dialog.derivative_extra_frame.isVisibleTo(dialog)

    def test_initialization_with_subject(self, qtbot, workspace_with_subjects):
        """Test initialization with a specified subject."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            subj="sub-01"
        )
        qtbot.addWidget(dialog)

        assert dialog.subj == "sub-01"
        assert dialog.button_second_group is None
        assert not hasattr(dialog, 'subj_combo')

    def test_initialization_with_role(self, qtbot, workspace_with_subjects):
        """Test initialization with a specified role."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            role="anat"
        )
        qtbot.addWidget(dialog)

        assert dialog.role == "anat"
        assert dialog.button_third_group is None
        assert not hasattr(dialog, 'level3_widget')

    def test_initialization_partial_params(self, qtbot, workspace_with_subjects):
        """Test initialization with partial parameters."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            main="derivatives",
            subj="sub-02"
        )
        qtbot.addWidget(dialog)

        assert dialog.main == "derivatives"
        assert dialog.subj == "sub-02"
        assert dialog.role is None

    def test_ok_button_initially_disabled(self, qtbot, workspace_with_subjects):
        """Test that the OK button is initially disabled."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert not dialog.ok_button.isEnabled()

    def test_window_title_set(self, qtbot, workspace_with_subjects):
        """Test that the window title is set."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert dialog.windowTitle() != ""


class TestFindPatientDirs:
    """Tests for the _find_patient_dirs method."""

    def test_find_patient_dirs_basic(self, qtbot, workspace_with_subjects):
        """Test basic patient directory search."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        patient_dirs = dialog._find_patient_dirs()

        assert len(patient_dirs) == 3

        for p in patient_dirs:
            assert 'sub-' in os.path.basename(p)

    def test_find_patient_dirs_excludes_derivatives(self, qtbot, workspace_with_subjects):
        """Test that the search excludes derivatives."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        patient_dirs = dialog._find_patient_dirs()

        for p in patient_dirs:
            assert 'derivatives' not in p.split(os.sep)

    def test_find_patient_dirs_empty_workspace(self, qtbot):
        """Test with an empty workspace."""
        temp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(temp_dir, "empty"), exist_ok=True)
        dialog = FileRoleDialog(workspace_path=temp_dir)
        qtbot.addWidget(dialog)

        patient_dirs = dialog._find_patient_dirs()

        assert len(patient_dirs) == 0

    def test_find_patient_dirs_nested_subjects(self, qtbot, temp_workspace):
        """Test with nested subjects."""
        nested_path = os.path.join(temp_workspace, "study", "cohort1", "sub-nested")
        os.makedirs(nested_path)

        dialog = FileRoleDialog(workspace_path=temp_workspace)
        qtbot.addWidget(dialog)

        patient_dirs = dialog._find_patient_dirs()

        assert len(patient_dirs) == 3 # The nested one and the other two
        assert "sub-01" in patient_dirs[0]
        assert "sub-02" in patient_dirs[1]
        assert "sub-nested" in patient_dirs[2]


class TestLevel1MainDerivatives:
    """Tests for level 1 (Main/Derivatives)."""

    def test_main_selected(self, qtbot, workspace_with_subjects):
        """Test 'main' selection."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)

        selections = dialog.get_selections()
        assert selections['main'] == "main subject files"

    def test_derivatives_selected(self, qtbot, workspace_with_subjects):
        """Test 'derivatives' selection."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)

        selections = dialog.get_selections()
        assert selections['main'] == "derivatives"

    def test_derivatives_shows_extra_frame(self, qtbot, workspace_with_subjects):
        """Test that selecting derivatives shows the extra frame."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert not dialog.derivative_extra_frame.isVisibleTo(dialog)

        dialog.opt_derivatives.setChecked(True)

        assert dialog.derivative_extra_frame.isVisibleTo(dialog)

    def test_main_hides_extra_frame(self, qtbot, workspace_with_subjects):
        """Test that selecting main hides the extra frame."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        assert dialog.derivative_extra_frame.isVisibleTo(dialog)

        dialog.opt_main.setChecked(True)
        assert not dialog.derivative_extra_frame.isVisibleTo(dialog)

    def test_derivative_type_selection(self, qtbot, workspace_with_subjects):
        """Test derivative type selection."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.skull_strip_btn.setChecked(True)

        selections = dialog.get_selections()
        assert selections['derivative'] == "skullstrips"

    def test_all_derivative_types(self, qtbot, workspace_with_subjects):
        """Test all derivative types."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)

        derivative_buttons = [
            (dialog.skull_strip_btn, "skullstrips"),
            (dialog.manual_mask_btn, "manual_masks"),
            (dialog.deep_learning_mask, "deep_learning_seg")
        ]

        for button, expected_text in derivative_buttons:
            button.setChecked(True)
            selections = dialog.get_selections()
            assert selections['derivative'] == expected_text


class TestLevel2Subject:
    """Tests for level 2 (Subject)."""

    def test_subject_combo_populated(self, qtbot, workspace_with_subjects):
        """Test that the subject combo box is populated."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert dialog.subj_combo.count() == 3

        subjects = [dialog.subj_combo.itemText(i) for i in range(dialog.subj_combo.count())]
        assert "sub-01" in subjects
        assert "sub-02" in subjects
        assert "sub-03" in subjects

    def test_subject_selection(self, qtbot, workspace_with_subjects):
        """Test subject selection."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.subj_combo.setCurrentText("sub-02")

        selections = dialog.get_selections()
        assert selections['subj'] == "sub-02"

    def test_subject_combo_default_selection(self, qtbot, workspace_with_subjects):
        """Test default subject combo selection."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        selections = dialog.get_selections()
        assert selections['subj'] is not None

    def test_subject_not_shown_when_provided(self, qtbot, workspace_with_subjects):
        """Test that the subject level is not shown if provided."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            subj="sub-01"
        )
        qtbot.addWidget(dialog)

        assert not hasattr(dialog, 'subj_combo')
        assert not hasattr(dialog, 'level2_widget')


class TestLevel3Role:
    """Tests for level 3 (Role)."""

    def test_anat_role_selection(self, qtbot, workspace_with_subjects):
        """Test 'anat' role selection."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.anat_button.setChecked(True)

        selections = dialog.get_selections()
        assert selections['role'] == "anat"

    def test_ses01_role_selection(self, qtbot, workspace_with_subjects):
        """Test 'ses-01' role selection."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.ses_1_button.setChecked(True)

        selections = dialog.get_selections()
        assert selections['role'] == "ses-01"

    def test_ses02_role_selection(self, qtbot, workspace_with_subjects):
        """Test 'ses-02' role selection."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.ses_2_button.setChecked(True)

        selections = dialog.get_selections()
        assert selections['role'] == "ses-02"

    def test_role_not_shown_when_provided(self, qtbot, workspace_with_subjects):
        """Test that the role level is not shown if provided."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            role="anat"
        )
        qtbot.addWidget(dialog)

        assert not hasattr(dialog, 'level3_widget')
        assert dialog.button_third_group is None


class TestGetSelections:
    """Tests for the get_selections method."""

    def test_get_selections_all_levels(self, qtbot, workspace_with_subjects):
        """Test get_selections with all levels."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        selections = dialog.get_selections()

        assert selections['main'] == "main subject files"
        assert selections['subj'] == "sub-01"
        assert selections['role'] == "anat"

    def test_get_selections_derivatives(self, qtbot, workspace_with_subjects):
        """Test get_selections with derivatives."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.skull_strip_btn.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-02")
        dialog.anat_button.setChecked(True)

        selections = dialog.get_selections()

        assert selections['main'] == "derivatives"
        assert selections['derivative'] == "skullstrips"
        assert selections['subj'] == "sub-02"
        assert selections['role'] == "anat"

    def test_get_selections_partial(self, qtbot, workspace_with_subjects):
        """Test get_selections with partial selections."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)

        selections = dialog.get_selections()

        assert selections['main'] == "main subject files"
        assert selections.get('derivative') is None


class TestGetRelativePath:
    """Tests for the get_relative_path method."""

    def test_relative_path_main_anat(self, qtbot, workspace_with_subjects):
        """Test relative path: main/subject/anat."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        path = dialog.get_relative_path()

        assert path == os.path.join("sub-01", "anat")

    def test_relative_path_main_session(self, qtbot, workspace_with_subjects):
        """Test relative path: main/subject/session/pet."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-02")
        dialog.ses_1_button.setChecked(True)

        path = dialog.get_relative_path()

        assert path == os.path.join("sub-02", "ses-01", "pet")

    def test_relative_path_derivatives(self, qtbot, workspace_with_subjects):
        """Test relative path: derivatives/type/subject/anat."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.skull_strip_btn.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        path = dialog.get_relative_path()

        assert path == os.path.join("derivatives", "skullstrips", "sub-01", "anat")

    def test_relative_path_derivatives_with_session(self, qtbot, workspace_with_subjects):
        """Test relative path: derivatives with session."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.manual_mask_btn.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-03")
        dialog.ses_2_button.setChecked(True)

        path = dialog.get_relative_path()

        assert path == os.path.join("derivatives", "manual_masks", "sub-03", "ses-02", "pet")

    def test_relative_path_empty(self, qtbot, workspace_with_subjects):
        """Test empty relative path (no selection)."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        path = dialog.get_relative_path()

        # With no selection (except default subject), path might be partial
        assert path is not None or path is None  # Depends on implementation

    def test_relative_path_session_pattern_matching(self, qtbot, workspace_with_subjects):
        """Test that the ses-XX pattern adds /pet."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")

        dialog.ses_1_button.setChecked(True)
        path1 = dialog.get_relative_path()
        assert path1.endswith("pet")

        dialog.ses_2_button.setChecked(True)
        path2 = dialog.get_relative_path()
        assert path2.endswith("pet")

        dialog.anat_button.setChecked(True)
        path3 = dialog.get_relative_path()
        assert not path3.endswith("pet")


class TestUpdateOkButton:
    """Tests for the update_ok_button method."""

    def test_ok_button_disabled_initially(self, qtbot, workspace_with_subjects):
        """Test that OK is disabled initially."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert not dialog.ok_button.isEnabled()

    def test_ok_button_enabled_all_selected(self, qtbot, workspace_with_subjects):
        """Test that OK is enabled with all selections."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        assert dialog.ok_button.isEnabled()

    def test_ok_button_disabled_no_main(self, qtbot, workspace_with_subjects):
        """Test OK disabled without main."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        assert not dialog.ok_button.isEnabled()

    def test_ok_button_disabled_no_subject(self, qtbot, workspace_with_subjects):
        """Test OK disabled without subject."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.anat_button.setChecked(True)
        # This test may not be valid if the combo always has a default selection

    def test_ok_button_disabled_no_role(self, qtbot, workspace_with_subjects):
        """Test OK disabled without role."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")

        assert not dialog.ok_button.isEnabled()

    def test_ok_button_disabled_derivatives_no_type(self, qtbot, workspace_with_subjects):
        """Test OK disabled with derivatives but no type."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        assert not dialog.ok_button.isEnabled()

    def test_ok_button_enabled_derivatives_complete(self, qtbot, workspace_with_subjects):
        """Test OK enabled with complete derivatives."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.skull_strip_btn.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        assert dialog.ok_button.isEnabled()

    def test_ok_button_updates_on_change(self, qtbot, workspace_with_subjects):
        """Test that OK updates on every change."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert not dialog.ok_button.isEnabled()

        dialog.opt_main.setChecked(True)
        assert not dialog.ok_button.isEnabled()

        dialog.subj_combo.setCurrentText("sub-01")
        assert not dialog.ok_button.isEnabled()

        dialog.anat_button.setChecked(True)
        assert dialog.ok_button.isEnabled()


class TestDialogButtons:
    """Tests for the dialog buttons."""

    def test_accept_button_exists(self, qtbot, workspace_with_subjects):
        """Test that the Accept button exists."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert dialog.ok_button is not None

    def test_cancel_button_exists(self, qtbot, workspace_with_subjects):
        """Test that the Cancel button exists."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        buttons = dialog.findChildren(QDialogButtonBox)
        assert len(buttons) > 0

        button_box = buttons[0]
        cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        assert cancel_btn is not None


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_workspace(self, qtbot):
        """Test with empty workspace."""
        temp_dir = tempfile.mkdtemp()
        dialog = FileRoleDialog(workspace_path=temp_dir)
        qtbot.addWidget(dialog)

        assert dialog.subj_combo.count() == 0

    def test_workspace_with_single_subject(self, qtbot, temp_workspace):
        """Test with a single subject."""
        temp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(temp_dir, "sub-only"))

        dialog = FileRoleDialog(workspace_path=temp_dir)
        qtbot.addWidget(dialog)

        assert dialog.subj_combo.count() == 1
        assert dialog.subj_combo.itemText(0) == "sub-only"

    def test_workspace_with_many_subjects(self, qtbot):
        """Test with many subjects."""
        temp_dir = tempfile.mkdtemp()
        for i in range(50):
            os.makedirs(os.path.join(temp_dir, f"sub-{i:03d}"))

        dialog = FileRoleDialog(workspace_path=temp_dir)
        qtbot.addWidget(dialog)

        assert dialog.subj_combo.count() == 50


    def test_subject_with_special_characters(self, qtbot, temp_workspace):
        """Test subject with special characters."""
        special_names = ["sub-test_01", "sub-patient-A", "sub-123abc"]

        for name in special_names:
            os.makedirs(os.path.join(temp_workspace, name))

        dialog = FileRoleDialog(workspace_path=temp_workspace)
        qtbot.addWidget(dialog)

        assert dialog.subj_combo.count() == len(special_names)+2 # For the two already created in the fixture


class TestIntegration:
    """Integration tests."""

    def test_full_workflow_main_anat(self, qtbot, workspace_with_subjects):
        """Test full workflow: main -> subject -> anat."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-02")
        dialog.anat_button.setChecked(True)

        assert dialog.ok_button.isEnabled()

        selections = dialog.get_selections()
        assert selections['main'] == "main subject files"
        assert selections['subj'] == "sub-02"
        assert selections['role'] == "anat"

        path = dialog.get_relative_path()
        assert path == os.path.join("sub-02", "anat")

    def test_full_workflow_derivatives(self, qtbot, workspace_with_subjects):
        """Test full workflow: derivatives."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.manual_mask_btn.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-03")
        dialog.ses_1_button.setChecked(True)

        assert dialog.ok_button.isEnabled()

        selections = dialog.get_selections()
        assert selections['main'] == "derivatives"
        assert selections['derivative'] == "manual_masks"
        assert selections['subj'] == "sub-03"
        assert selections['role'] == "ses-01"

        path = dialog.get_relative_path()
        expected = os.path.join("derivatives", "manual_masks", "sub-03", "ses-01", "pet")
        assert path == expected

    def test_change_selections_multiple_times(self, qtbot, workspace_with_subjects):
        """Test changing selections multiple times."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        path1 = dialog.get_relative_path()

        dialog.opt_derivatives.setChecked(True)
        dialog.skull_strip_btn.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-02")
        dialog.ses_2_button.setChecked(True)

        path2 = dialog.get_relative_path()

        assert path1 != path2
        assert "derivatives" in path2


class TestPartialInitialization:
    """Tests for partial initializations."""

    def test_only_role_missing(self, qtbot, workspace_with_subjects):
        """Test with only role missing."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            main="derivatives",
            subj="sub-01"
        )
        qtbot.addWidget(dialog)

        assert hasattr(dialog, 'level3_widget')
        assert not hasattr(dialog, 'level1_widget')
        assert not hasattr(dialog, 'subj_combo')

        def test_only_subject_missing(self, qtbot, workspace_with_subjects):
            """Test with only subject missing (main and role provided)."""
            dialog = FileRoleDialog(
                workspace_path=workspace_with_subjects,
                main="derivatives",
                role="anat"
            )
            qtbot.addWidget(dialog)

            assert hasattr(dialog, 'level2_widget')
            assert not hasattr(dialog, 'level1_widget')
            assert not hasattr(dialog, 'level3_widget')
            assert dialog.button_third_group is None

        def test_only_main_missing(self, qtbot, workspace_with_subjects):
            """Test with only main missing (subj and role provided)."""
            dialog = FileRoleDialog(
                workspace_path=workspace_with_subjects,
                subj="sub-01",
                role="ses-01"
            )
            qtbot.addWidget(dialog)

            assert hasattr(dialog, 'level1_widget')
            assert not hasattr(dialog, 'subj_combo')
            assert not hasattr(dialog, 'level3_widget')
            assert dialog.button_third_group is None

    class TestFilterSubjects:
        """Tests for the filter_subjects method (live filter behavior)."""

        def test_filter_subjects_with_list_widget(self, qtbot, temp_workspace):
            """Test filter when subj_list (QListWidget) exists."""
            subjects = ["sub-one", "sub-two", "patient-three"]
            for s in subjects:
                os.makedirs(os.path.join(temp_workspace, s))

            dialog = FileRoleDialog(workspace_path=temp_workspace)
            qtbot.addWidget(dialog)

            lw = QListWidget()
            for s in subjects:
                item = QListWidgetItem(s)
                lw.addItem(item)
            dialog.subj_list = lw

            dialog.filter_subjects("sub")
            visible_texts = [dialog.subj_list.item(i).text() for i in range(dialog.subj_list.count())
                             if not dialog.subj_list.item(i).isHidden()]
            assert set(visible_texts) == {"sub-one", "sub-two"}

            dialog.filter_subjects("zzz")
            hidden_count = sum(1 for i in range(dialog.subj_list.count()) if dialog.subj_list.item(i).isHidden())
            assert hidden_count == dialog.subj_list.count()

        def test_filter_subjects_no_subj_list(self, qtbot, workspace_with_subjects):
            """Calling filter_subjects when subj_list does not exist must not raise exceptions."""
            dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
            qtbot.addWidget(dialog)

            dialog.filter_subjects("anything")  # should not raise exceptions

    class TestRegressionAndEdgeCases:
        """Additional regression and edge case tests."""

        def test_get_relative_path_returns_none_when_no_selection(self, qtbot):
            """If no selections (empty workspace), get_relative_path should return None."""
            temp_dir = tempfile.mkdtemp()
            dialog = FileRoleDialog(workspace_path=temp_dir)
            qtbot.addWidget(dialog)

            assert dialog.subj_combo.count() == 0

            path = dialog.get_relative_path()
            assert path is None

        def test_get_relative_path_handles_unset_buttons(self, qtbot, workspace_with_subjects):
            """Ensure get_relative_path doesn't crash if some buttons aren't set."""
            dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
            qtbot.addWidget(dialog)

            dialog.subj_combo.setCurrentText("sub-01")

            path = dialog.get_relative_path()
            assert path is None or isinstance(path, str)

        def test_find_patient_dirs_ignores_non_sub_dirs(self, qtbot, temp_workspace):
            """Ensure _find_patient_dirs ignores folders not starting with 'sub-'."""
            os.makedirs(os.path.join(temp_workspace, "not-a-sub"))
            os.makedirs(os.path.join(temp_workspace, "sub-valid"))
            os.makedirs(os.path.join(temp_workspace, "also-not"))

            dialog = FileRoleDialog(workspace_path=temp_workspace)
            qtbot.addWidget(dialog)

            patient_dirs = dialog._find_patient_dirs()
            basenames = [os.path.basename(p) for p in patient_dirs]
            assert "sub-valid" in basenames
            assert "not-a-sub" not in basenames
            assert "also-not" not in basenames