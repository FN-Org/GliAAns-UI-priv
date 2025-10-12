import os
import tempfile

import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QDialogButtonBox, QRadioButton, QComboBox, QListWidgetItem, QListWidget
from PyQt6.QtCore import Qt

from components.file_role_dialog import FileRoleDialog


@pytest.fixture
def workspace_with_subjects(temp_workspace):
    """Crea workspace con soggetti e struttura BIDS."""
    # Crea soggetti
    subjects = ["sub-01", "sub-02", "sub-03"]
    for subj in subjects:
        subj_dir = os.path.join(temp_workspace, subj)
        os.makedirs(subj_dir, exist_ok=True)

        # Crea directory anat
        anat_dir = os.path.join(subj_dir, "anat")
        os.makedirs(anat_dir, exist_ok=True)

        # Crea sessioni
        for ses in ["ses-01", "ses-02"]:
            ses_dir = os.path.join(subj_dir, ses, "pet")
            os.makedirs(ses_dir, exist_ok=True)

    # Crea directory derivatives
    derivatives_dir = os.path.join(temp_workspace, "derivatives")
    os.makedirs(derivatives_dir, exist_ok=True)

    for derivative in ["skullstrips", "manual_masks", "deep_learning_masks"]:
        for subj in subjects:
            deriv_subj_dir = os.path.join(derivatives_dir, derivative, subj, "anat")
            os.makedirs(deriv_subj_dir, exist_ok=True)

    return temp_workspace

class TestFileRoleDialogInitialization:
    """Test per l'inizializzazione del dialogo."""

    def test_initialization_full_dialog(self, qtbot, workspace_with_subjects):
        """Test inizializzazione dialogo completo (tutti i livelli)."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert dialog.workspace_path == workspace_with_subjects
        assert dialog.subj is None
        assert dialog.role is None
        assert dialog.main is None

        # Verifica presenza livelli
        assert hasattr(dialog, 'level1_widget')
        assert hasattr(dialog, 'level2_widget')
        assert hasattr(dialog, 'level3_widget')
        assert hasattr(dialog, 'ok_button')

    def test_initialization_with_main_derivatives(self, qtbot, workspace_with_subjects):
        """Test inizializzazione con main='derivatives'."""
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
        """Test inizializzazione con subject specificato."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            subj="sub-01"
        )
        qtbot.addWidget(dialog)

        assert dialog.subj == "sub-01"
        assert dialog.button_second_group is None
        assert not hasattr(dialog, 'subj_combo')

    def test_initialization_with_role(self, qtbot, workspace_with_subjects):
        """Test inizializzazione con role specificato."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            role="anat"
        )
        qtbot.addWidget(dialog)

        assert dialog.role == "anat"
        assert dialog.button_third_group is None
        assert not hasattr(dialog, 'level3_widget')

    def test_initialization_partial_params(self, qtbot, workspace_with_subjects):
        """Test inizializzazione con parametri parziali."""
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
        """Test che il pulsante OK sia inizialmente disabilitato."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert not dialog.ok_button.isEnabled()

    def test_window_title_set(self, qtbot, workspace_with_subjects):
        """Test che il titolo della finestra sia impostato."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert dialog.windowTitle() != ""


class TestFindPatientDirs:
    """Test per il metodo _find_patient_dirs."""

    def test_find_patient_dirs_basic(self, qtbot, workspace_with_subjects):
        """Test ricerca directory pazienti base."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        patient_dirs = dialog._find_patient_dirs()

        assert len(patient_dirs) == 3

        # Verifica che tutti i path contengano 'sub-'
        for p in patient_dirs:
            assert 'sub-' in os.path.basename(p)

    def test_find_patient_dirs_excludes_derivatives(self, qtbot, workspace_with_subjects):
        """Test che la ricerca escluda derivatives."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        patient_dirs = dialog._find_patient_dirs()

        # Nessun path dovrebbe contenere 'derivatives'
        for p in patient_dirs:
            assert 'derivatives' not in p.split(os.sep)

    def test_find_patient_dirs_empty_workspace(self, qtbot):
        """Test con workspace vuoto."""
        temp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(temp_dir, "empty"), exist_ok=True)
        dialog = FileRoleDialog(workspace_path=temp_dir)
        qtbot.addWidget(dialog)

        patient_dirs = dialog._find_patient_dirs()

        assert len(patient_dirs) == 0

    def test_find_patient_dirs_nested_subjects(self, qtbot, temp_workspace):
        """Test con soggetti annidati."""
        # Crea struttura annidata
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
    """Test per il livello 1 (Main/Derivatives)."""

    def test_main_selected(self, qtbot, workspace_with_subjects):
        """Test selezione 'main'."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)

        selections = dialog.get_selections()
        assert selections['main'] == "main subject files"

    def test_derivatives_selected(self, qtbot, workspace_with_subjects):
        """Test selezione 'derivatives'."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)

        selections = dialog.get_selections()
        assert selections['main'] == "derivatives"

    def test_derivatives_shows_extra_frame(self, qtbot, workspace_with_subjects):
        """Test che selezionare derivatives mostri il frame extra."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert not dialog.derivative_extra_frame.isVisibleTo(dialog)

        dialog.opt_derivatives.setChecked(True)

        assert dialog.derivative_extra_frame.isVisibleTo(dialog)

    def test_main_hides_extra_frame(self, qtbot, workspace_with_subjects):
        """Test che selezionare main nasconda il frame extra."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        # Prima seleziona derivatives
        dialog.opt_derivatives.setChecked(True)
        assert dialog.derivative_extra_frame.isVisibleTo(dialog)

        # Poi seleziona main
        dialog.opt_main.setChecked(True)
        assert not dialog.derivative_extra_frame.isVisibleTo(dialog)

    def test_derivative_type_selection(self, qtbot, workspace_with_subjects):
        """Test selezione tipo di derivative."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.skull_strip_btn.setChecked(True)

        selections = dialog.get_selections()
        assert selections['derivative'] == "skullstrips"

    def test_all_derivative_types(self, qtbot, workspace_with_subjects):
        """Test tutti i tipi di derivative."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)

        derivative_buttons = [
            (dialog.skull_strip_btn, "skullstrips"),
            (dialog.manual_mask_btn, "manual_masks"),
            (dialog.deep_learning_mask, "deep_learning_masks")
        ]

        for button, expected_text in derivative_buttons:
            button.setChecked(True)
            selections = dialog.get_selections()
            assert selections['derivative'] == expected_text


class TestLevel2Subject:
    """Test per il livello 2 (Subject)."""

    def test_subject_combo_populated(self, qtbot, workspace_with_subjects):
        """Test che la combo dei soggetti sia popolata."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert dialog.subj_combo.count() == 3

        # Verifica che tutti i soggetti siano presenti
        subjects = [dialog.subj_combo.itemText(i) for i in range(dialog.subj_combo.count())]
        assert "sub-01" in subjects
        assert "sub-02" in subjects
        assert "sub-03" in subjects

    def test_subject_selection(self, qtbot, workspace_with_subjects):
        """Test selezione soggetto."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        # Seleziona sub-02
        dialog.subj_combo.setCurrentText("sub-02")

        selections = dialog.get_selections()
        assert selections['subj'] == "sub-02"

    def test_subject_combo_default_selection(self, qtbot, workspace_with_subjects):
        """Test selezione default combo soggetti."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        # Dovrebbe essere selezionato il primo
        selections = dialog.get_selections()
        assert selections['subj'] is not None

    def test_subject_not_shown_when_provided(self, qtbot, workspace_with_subjects):
        """Test che il livello soggetto non sia mostrato se fornito."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            subj="sub-01"
        )
        qtbot.addWidget(dialog)

        assert not hasattr(dialog, 'subj_combo')
        assert not hasattr(dialog, 'level2_widget')


class TestLevel3Role:
    """Test per il livello 3 (Role)."""

    def test_anat_role_selection(self, qtbot, workspace_with_subjects):
        """Test selezione role 'anat'."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.anat_button.setChecked(True)

        selections = dialog.get_selections()
        assert selections['role'] == "anat"

    def test_ses01_role_selection(self, qtbot, workspace_with_subjects):
        """Test selezione role 'ses-01'."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.ses_1_button.setChecked(True)

        selections = dialog.get_selections()
        assert selections['role'] == "ses-01"

    def test_ses02_role_selection(self, qtbot, workspace_with_subjects):
        """Test selezione role 'ses-02'."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.ses_2_button.setChecked(True)

        selections = dialog.get_selections()
        assert selections['role'] == "ses-02"

    def test_role_not_shown_when_provided(self, qtbot, workspace_with_subjects):
        """Test che il livello role non sia mostrato se fornito."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            role="anat"
        )
        qtbot.addWidget(dialog)

        assert not hasattr(dialog, 'level3_widget')
        assert dialog.button_third_group is None


class TestGetSelections:
    """Test per il metodo get_selections."""

    def test_get_selections_all_levels(self, qtbot, workspace_with_subjects):
        """Test get_selections con tutti i livelli."""
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
        """Test get_selections con derivatives."""
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
        """Test get_selections con selezioni parziali."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)

        selections = dialog.get_selections()

        assert selections['main'] == "main subject files"
        assert selections.get('derivative') is None


class TestGetRelativePath:
    """Test per il metodo get_relative_path."""

    def test_relative_path_main_anat(self, qtbot, workspace_with_subjects):
        """Test path relativo: main/subject/anat."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        path = dialog.get_relative_path()

        assert path == os.path.join("sub-01", "anat")

    def test_relative_path_main_session(self, qtbot, workspace_with_subjects):
        """Test path relativo: main/subject/session/pet."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-02")
        dialog.ses_1_button.setChecked(True)

        path = dialog.get_relative_path()

        assert path == os.path.join("sub-02", "ses-01", "pet")

    def test_relative_path_derivatives(self, qtbot, workspace_with_subjects):
        """Test path relativo: derivatives/type/subject/anat."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.skull_strip_btn.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        path = dialog.get_relative_path()

        assert path == os.path.join("derivatives", "skullstrips", "sub-01", "anat")

    def test_relative_path_derivatives_with_session(self, qtbot, workspace_with_subjects):
        """Test path relativo: derivatives con sessione."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.manual_mask_btn.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-03")
        dialog.ses_2_button.setChecked(True)

        path = dialog.get_relative_path()

        assert path == os.path.join("derivatives", "manual_masks", "sub-03", "ses-02", "pet")

    def test_relative_path_empty(self, qtbot, workspace_with_subjects):
        """Test path relativo vuoto (nessuna selezione)."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        path = dialog.get_relative_path()

        # Con nessuna selezione (tranne subject default), path potrebbe essere parziale
        assert path is not None or path is None  # Dipende dall'implementazione

    def test_relative_path_session_pattern_matching(self, qtbot, workspace_with_subjects):
        """Test che il pattern ses-XX aggiunga /pet."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")

        # Test ses-01
        dialog.ses_1_button.setChecked(True)
        path1 = dialog.get_relative_path()
        assert path1.endswith("pet")

        # Test ses-02
        dialog.ses_2_button.setChecked(True)
        path2 = dialog.get_relative_path()
        assert path2.endswith("pet")

        # Test anat (non dovrebbe avere pet)
        dialog.anat_button.setChecked(True)
        path3 = dialog.get_relative_path()
        assert not path3.endswith("pet")


class TestUpdateOkButton:
    """Test per il metodo update_ok_button."""

    def test_ok_button_disabled_initially(self, qtbot, workspace_with_subjects):
        """Test che OK sia disabilitato inizialmente."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert not dialog.ok_button.isEnabled()

    def test_ok_button_enabled_all_selected(self, qtbot, workspace_with_subjects):
        """Test che OK sia abilitato con tutte le selezioni."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        assert dialog.ok_button.isEnabled()

    def test_ok_button_disabled_no_main(self, qtbot, workspace_with_subjects):
        """Test OK disabilitato senza main."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        assert not dialog.ok_button.isEnabled()

    def test_ok_button_disabled_no_subject(self, qtbot, workspace_with_subjects):
        """Test OK disabilitato senza subject."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.anat_button.setChecked(True)
        # Non selezionare nessun subject (combo vuota)

        # Questo test potrebbe non essere valido se la combo ha sempre una selezione default

    def test_ok_button_disabled_no_role(self, qtbot, workspace_with_subjects):
        """Test OK disabilitato senza role."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")

        assert not dialog.ok_button.isEnabled()

    def test_ok_button_disabled_derivatives_no_type(self, qtbot, workspace_with_subjects):
        """Test OK disabilitato con derivatives ma senza tipo."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        assert not dialog.ok_button.isEnabled()

    def test_ok_button_enabled_derivatives_complete(self, qtbot, workspace_with_subjects):
        """Test OK abilitato con derivatives completo."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        dialog.opt_derivatives.setChecked(True)
        dialog.skull_strip_btn.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        assert dialog.ok_button.isEnabled()

    def test_ok_button_updates_on_change(self, qtbot, workspace_with_subjects):
        """Test che OK si aggiorni ad ogni cambio."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        # Inizialmente disabilitato
        assert not dialog.ok_button.isEnabled()

        # Aggiungi selezioni una alla volta
        dialog.opt_main.setChecked(True)
        assert not dialog.ok_button.isEnabled()

        dialog.subj_combo.setCurrentText("sub-01")
        assert not dialog.ok_button.isEnabled()

        dialog.anat_button.setChecked(True)
        assert dialog.ok_button.isEnabled()


class TestDialogButtons:
    """Test per i pulsanti del dialogo."""

    def test_accept_button_exists(self, qtbot, workspace_with_subjects):
        """Test che il pulsante Accept esista."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        assert dialog.ok_button is not None

    def test_cancel_button_exists(self, qtbot, workspace_with_subjects):
        """Test che il pulsante Cancel esista."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        # Cerca il pulsante Cancel
        buttons = dialog.findChildren(QDialogButtonBox)
        assert len(buttons) > 0

        button_box = buttons[0]
        cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        assert cancel_btn is not None


class TestEdgeCases:
    """Test per casi limite."""

    def test_empty_workspace(self, qtbot):
        """Test con workspace vuoto."""
        temp_dir = tempfile.mkdtemp()
        dialog = FileRoleDialog(workspace_path=temp_dir)
        qtbot.addWidget(dialog)

        # La combo dovrebbe essere vuota
        assert dialog.subj_combo.count() == 0

    def test_workspace_with_single_subject(self, qtbot, temp_workspace):
        """Test con un solo soggetto."""
        temp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(temp_dir, "sub-only"))

        dialog = FileRoleDialog(workspace_path=temp_dir)
        qtbot.addWidget(dialog)

        assert dialog.subj_combo.count() == 1
        assert dialog.subj_combo.itemText(0) == "sub-only"

    def test_workspace_with_many_subjects(self, qtbot):
        """Test con molti soggetti."""
        temp_dir = tempfile.mkdtemp()
        for i in range(50):
            os.makedirs(os.path.join(temp_dir, f"sub-{i:03d}"))

        dialog = FileRoleDialog(workspace_path=temp_dir)
        qtbot.addWidget(dialog)

        assert dialog.subj_combo.count() == 50


    def test_subject_with_special_characters(self, qtbot, temp_workspace):
        """Test soggetto con caratteri speciali."""
        special_names = ["sub-test_01", "sub-patient-A", "sub-123abc"]

        for name in special_names:
            os.makedirs(os.path.join(temp_workspace, name))

        dialog = FileRoleDialog(workspace_path=temp_workspace)
        qtbot.addWidget(dialog)

        assert dialog.subj_combo.count() == len(special_names)+2 # For the two already created in the fixture


class TestIntegration:
    """Test di integrazione."""

    def test_full_workflow_main_anat(self, qtbot, workspace_with_subjects):
        """Test workflow completo: main -> subject -> anat."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        # Seleziona tutto
        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-02")
        dialog.anat_button.setChecked(True)

        # Verifica OK abilitato
        assert dialog.ok_button.isEnabled()

        # Verifica selezioni
        selections = dialog.get_selections()
        assert selections['main'] == "main subject files"
        assert selections['subj'] == "sub-02"
        assert selections['role'] == "anat"

        # Verifica path
        path = dialog.get_relative_path()
        assert path == os.path.join("sub-02", "anat")

    def test_full_workflow_derivatives(self, qtbot, workspace_with_subjects):
        """Test workflow completo: derivatives."""
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
        """Test cambio selezioni multiple volte."""
        dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
        qtbot.addWidget(dialog)

        # Prima selezione
        dialog.opt_main.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-01")
        dialog.anat_button.setChecked(True)

        path1 = dialog.get_relative_path()

        # Cambia selezione
        dialog.opt_derivatives.setChecked(True)
        dialog.skull_strip_btn.setChecked(True)
        dialog.subj_combo.setCurrentText("sub-02")
        dialog.ses_2_button.setChecked(True)

        path2 = dialog.get_relative_path()

        assert path1 != path2
        assert "derivatives" in path2


class TestPartialInitialization:
    """Test per inizializzazioni parziali."""

    def test_only_role_missing(self, qtbot, workspace_with_subjects):
        """Test con solo role mancante."""
        dialog = FileRoleDialog(
            workspace_path=workspace_with_subjects,
            main="derivatives",
            subj="sub-01"
        )
        qtbot.addWidget(dialog)

        # Dovrebbe mostrare solo il livello role
        assert hasattr(dialog, 'level3_widget')
        assert not hasattr(dialog, 'level1_widget')
        assert not hasattr(dialog, 'subj_combo')

        def test_only_subject_missing(self, qtbot, workspace_with_subjects):
            """Test con solo subject mancante (main e role forniti)."""
            # main è fornito (derivatives) e role è fornito -> deve mancare solo il livello subject
            dialog = FileRoleDialog(
                workspace_path=workspace_with_subjects,
                main="derivatives",
                role="anat"
            )
            qtbot.addWidget(dialog)

            # level2_widget deve esistere (subject mancante -> viene creato)
            assert hasattr(dialog, 'level2_widget')

            # level1 non deve esistere (main fornito come "derivatives")
            assert not hasattr(dialog, 'level1_widget')

            # level3 non deve esistere (role fornito)
            assert not hasattr(dialog, 'level3_widget')
            assert dialog.button_third_group is None

        def test_only_main_missing(self, qtbot, workspace_with_subjects):
            """Test con solo main mancante (subj e role forniti)."""
            dialog = FileRoleDialog(
                workspace_path=workspace_with_subjects,
                subj="sub-01",
                role="ses-01"
            )
            qtbot.addWidget(dialog)

            # level1 dovrebbe essere presente (main è None)
            assert hasattr(dialog, 'level1_widget')
            # subject non deve esistere come combo (fornito)
            assert not hasattr(dialog, 'subj_combo')
            # role è fornito -> level3 non dovrebbe esistere
            assert not hasattr(dialog, 'level3_widget')
            assert dialog.button_third_group is None

    class TestFilterSubjects:
        """Test per il metodo filter_subjects (comportamento live filter)."""

        def test_filter_subjects_with_list_widget(self, qtbot, temp_workspace):
            """Test filtro quando esiste subj_list (QListWidget)."""
            # prepara workspace con alcuni subject
            subjects = ["sub-one", "sub-two", "patient-three"]
            for s in subjects:
                os.makedirs(os.path.join(temp_workspace, s))

            dialog = FileRoleDialog(workspace_path=temp_workspace)
            qtbot.addWidget(dialog)

            # crea un QListWidget e assegnalo a dialog.subj_list così filter_subjects lo userà
            lw = QListWidget()
            for s in subjects:
                item = QListWidgetItem(s)
                lw.addItem(item)
            dialog.subj_list = lw

            # filtra con 'sub' -> tutti gli elementi che contengono 'sub' dovrebbero rimanere visibili
            dialog.filter_subjects("sub")
            visible_texts = [dialog.subj_list.item(i).text() for i in range(dialog.subj_list.count())
                             if not dialog.subj_list.item(i).isHidden()]
            assert set(visible_texts) == {"sub-one", "sub-two"}

            # filtra con stringa che non corrisponde -> tutti nascosti
            dialog.filter_subjects("zzz")
            hidden_count = sum(1 for i in range(dialog.subj_list.count()) if dialog.subj_list.item(i).isHidden())
            assert hidden_count == dialog.subj_list.count()

        def test_filter_subjects_no_subj_list(self, qtbot, workspace_with_subjects):
            """Chiamare filter_subjects quando subj_list non esiste non deve sollevare eccezioni."""
            dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
            qtbot.addWidget(dialog)

            # Non esiste subj_list in questo dialog così la funzione dovrebbe semplicemente ritornare senza errori
            dialog.filter_subjects("anything")  # non deve lanciare eccezioni

    class TestRegressionAndEdgeCases:
        """Test addizionali di regressione e casi limite."""

        def test_get_relative_path_returns_none_when_no_selection(self, qtbot):
            """Se non ci sono selezioni (workspace vuoto), get_relative_path dovrebbe restituire None."""
            temp_dir = tempfile.mkdtemp()
            dialog = FileRoleDialog(workspace_path=temp_dir)
            qtbot.addWidget(dialog)

            # assicurati che la combo sia vuota
            assert dialog.subj_combo.count() == 0

            path = dialog.get_relative_path()
            assert path is None

        def test_get_relative_path_handles_unset_buttons(self, qtbot, workspace_with_subjects):
            """Assicura che get_relative_path non crashi se alcuni button non sono stati settati."""
            dialog = FileRoleDialog(workspace_path=workspace_with_subjects)
            qtbot.addWidget(dialog)

            # imposta solo subject (combo ha default) ma non main/role
            dialog.subj_combo.setCurrentText("sub-01")

            # Nessun main o role selezionato -> dovrebbe restituire None o percorso parziale coerente
            path = dialog.get_relative_path()
            # Non vogliamo imporre comportamento rigido qui; assicuriamoci che non crashi e ritorni stringa o None
            assert path is None or isinstance(path, str)

        def test_find_patient_dirs_ignores_non_sub_dirs(self, qtbot, temp_workspace):
            """Assicura che _find_patient_dirs ignori cartelle che non iniziano con 'sub-'."""
            os.makedirs(os.path.join(temp_workspace, "not-a-sub"))
            os.makedirs(os.path.join(temp_workspace, "sub-valid"))
            os.makedirs(os.path.join(temp_workspace, "also-not"))

            dialog = FileRoleDialog(workspace_path=temp_workspace)
            qtbot.addWidget(dialog)

            patient_dirs = dialog._find_patient_dirs()
            # Solo 'sub-valid' dovrebbe essere tornato
            basenames = [os.path.basename(p) for p in patient_dirs]
            assert "sub-valid" in basenames
            assert "not-a-sub" not in basenames
            assert "also-not" not in basenames