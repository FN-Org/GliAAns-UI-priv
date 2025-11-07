import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch
from PyQt6 import QtCore
from PyQt6.QtCore import QSettings
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMessageBox, QPushButton

from main.ui.patient_selection_page import PatientSelectionPage


@pytest.fixture
def patient_page(qtbot, mock_context):
    """Fixture that creates and returns a PatientSelectionPage instance."""
    previous_page = Mock()
    page = PatientSelectionPage(mock_context, previous_page)
    qtbot.addWidget(page)
    return page


class TestPatientSelectionPageSetup:
    """Tests for PatientSelectionPage initialization."""

    def test_page_initialization(self, patient_page):
        """Ensure page initializes correctly."""
        assert patient_page.workspace_path is not None
        assert patient_page.selected_patients == set()
        assert isinstance(patient_page.patient_buttons, dict)

    def test_title_created(self, patient_page):
        """Ensure title label is created."""
        assert patient_page.title is not None
        assert patient_page.title.text() != ""

    def test_select_buttons_created(self, patient_page):
        """Ensure select/deselect all buttons exist."""
        assert patient_page.select_all_btn is not None
        assert patient_page.deselect_all_btn is not None

    def test_scroll_area_created(self, patient_page):
        """Ensure scroll area and grid layout are initialized."""
        assert patient_page.scroll_area is not None
        assert patient_page.grid_layout is not None

    def test_column_count_default(self, patient_page):
        """Ensure default column count is valid."""
        assert patient_page.column_count >= 1


class TestPatientSelectionPagePatientLoading:
    """Tests for patient loading and directory scanning."""

    @pytest.fixture
    def temp_workspace(self):
        """Temporary workspace for testing patient directories."""
        temp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(temp_dir, "sub-01", "anat"))
        os.makedirs(os.path.join(temp_dir, "sub-02", "pet"))
        os.makedirs(os.path.join(temp_dir, "sub-03", "anat"))
        os.makedirs(os.path.join(temp_dir, "derivatives", "sub-01"))
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_find_patient_dirs(self, patient_page):
        """Check that patient directories are correctly found."""
        patient_dirs = patient_page._find_patient_dirs()
        assert len(patient_dirs) == 3
        patient_ids = [os.path.basename(d) for d in patient_dirs]
        assert "sub-01" in patient_ids
        assert "sub-02" in patient_ids
        assert "sub-03" in patient_ids

    def test_find_patient_dirs_ignores_derivatives(self, patient_page):
        """Ensure derivatives folder is ignored."""
        patient_dirs = patient_page._find_patient_dirs()
        for path in patient_dirs:
            assert "derivatives" not in path

    def test_load_patients_creates_buttons(self, patient_page):
        """Check that a button is created for each patient."""
        assert len(patient_page.patient_buttons) == 3
        assert "sub-01" in patient_page.patient_buttons
        assert "sub-02" in patient_page.patient_buttons
        assert "sub-03" in patient_page.patient_buttons

    def test_load_patients_adds_to_grid(self, patient_page):
        """Ensure patient widgets are added to the grid layout."""
        assert patient_page.grid_layout.count() >= 3


class TestPatientSelectionPageSelection:
    """Tests for patient selection logic."""

    def test_toggle_patient_select(self, patient_page):
        """Select a single patient."""
        button = patient_page.patient_buttons["sub-01"]
        patient_page._toggle_patient("sub-01", True, button)
        assert "sub-01" in patient_page.selected_patients
        assert button.text() != "Select"

    def test_toggle_patient_deselect(self, patient_page):
        """Deselect a previously selected patient."""
        button = patient_page.patient_buttons["sub-01"]
        patient_page._toggle_patient("sub-01", True, button)
        patient_page._toggle_patient("sub-01", False, button)
        assert "sub-01" not in patient_page.selected_patients

    def test_toggle_updates_main_buttons(self, patient_page):
        """Ensure toggling updates main buttons."""
        button = patient_page.patient_buttons["sub-01"]
        patient_page._toggle_patient("sub-01", True, button)
        patient_page.context["update_main_buttons"].assert_called()

    def test_select_all_patients(self, patient_page):
        """Select all patients at once."""
        patient_page._select_all_patients()
        assert len(patient_page.selected_patients) == 2
        for button in patient_page.patient_buttons.values():
            assert button.isChecked()

    def test_deselect_all_patients(self, patient_page):
        """Deselect all patients."""
        patient_page._select_all_patients()
        patient_page._deselect_all_patients()
        assert len(patient_page.selected_patients) == 0
        for button in patient_page.patient_buttons.values():
            assert not button.isChecked()

    def test_get_selected_patients(self, patient_page):
        """Retrieve selected patient list."""
        patient_page.selected_patients = {"sub-01", "sub-02"}
        selected = patient_page.get_selected_patients()
        assert isinstance(selected, list)
        assert len(selected) == 2
        assert "sub-01" in selected
        assert "sub-02" in selected


class TestPatientSelectionPageReadiness:
    """Tests for readiness logic."""

    def test_not_ready_without_selection(self, patient_page):
        """Page is not ready without selection."""
        patient_page.selected_patients.clear()
        assert not patient_page.is_ready_to_advance()

    def test_ready_with_selection(self, patient_page):
        """Page is ready when patients are selected."""
        patient_page.selected_patients.add("sub-01")
        assert patient_page.is_ready_to_advance()

    def test_can_go_back(self, patient_page):
        """Page should always allow going back."""
        assert patient_page.is_ready_to_go_back()


class TestPatientSelectionPageNavigation:
    """Tests for page navigation."""

    def test_back_returns_previous_page(self, patient_page):
        """Back should return previous page."""
        result = patient_page.back()
        assert result == patient_page.previous_page
        patient_page.previous_page.on_enter.assert_called_once()

    def test_next_without_cleanup(self, patient_page):
        """Advance without cleanup confirmation."""
        patient_page.selected_patients = {"sub-01", "sub-02"}
        with patch('main.ui.patient_selection_page.ToolSelectionPage') as MockPage:
            mock_page_instance = Mock()
            MockPage.return_value = mock_page_instance
            result = patient_page.next(patient_page.context)
            assert result is not None
            mock_page_instance.on_enter.assert_called_once()

    def test_next_with_cleanup_confirmed(self, patient_page, monkeypatch, temp_workspace):
        """Confirm cleanup before advancing."""
        patient_page.selected_patients = {"sub-01"}
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        with patch('main.ui.patient_selection_page.ToolSelectionPage') as MockPage:
            MockPage.return_value = Mock()
            result = patient_page.next(patient_page.context)
            assert not os.path.exists(os.path.join(temp_workspace, "sub-02"))
            assert os.path.exists(os.path.join(temp_workspace, "sub-01"))

    def test_next_with_cleanup_cancelled(self, patient_page, monkeypatch):
        """Cancel cleanup confirmation."""
        patient_page.selected_patients = {"sub-01"}
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.No)
        result = patient_page.next(patient_page.context)
        assert result is None

    def test_next_creates_tool_selection_page(self, patient_page):
        """Ensure ToolSelectionPage is created on next."""
        patient_page.selected_patients = {"sub-01", "sub-02"}
        with patch('main.ui.patient_selection_page.ToolSelectionPage') as MockPage:
            mock_page_instance = Mock()
            MockPage.return_value = mock_page_instance
            patient_page.next(patient_page.context)
            MockPage.assert_called_once()
            assert mock_page_instance in patient_page.context["history"]


class TestPatientSelectionPageCleanup:
    """Tests for cleanup operations."""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(temp_dir, "sub-01", "anat"))
        os.makedirs(os.path.join(temp_dir, "sub-02", "pet"))
        os.makedirs(os.path.join(temp_dir, "derivatives", "pipeline1", "sub-01"))
        os.makedirs(os.path.join(temp_dir, "derivatives", "pipeline1", "sub-02"))
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def patient_page(self, qtbot, mock_context):
        page = PatientSelectionPage(mock_context, Mock())
        qtbot.addWidget(page)
        return page

    def test_cleanup_removes_unselected_patients(self, patient_page, monkeypatch, temp_workspace):
        """Ensure unselected patients are deleted."""
        patient_page.selected_patients = {"sub-01"}
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        with patch('main.ui.patient_selection_page.ToolSelectionPage'):
            patient_page.next(patient_page.context)
            assert os.path.exists(os.path.join(temp_workspace, "sub-01"))
            assert not os.path.exists(os.path.join(temp_workspace, "sub-02"))

    def test_cleanup_removes_from_derivatives(self, patient_page, monkeypatch, temp_workspace):
        """Ensure cleanup also removes from derivatives."""
        patient_page.selected_patients = {"sub-01"}
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        with patch('main.ui.patient_selection_page.ToolSelectionPage'):
            patient_page.next(patient_page.context)
            assert not os.path.exists(os.path.join(temp_workspace, "derivatives", "pipeline1", "sub-02"))
            assert os.path.exists(os.path.join(temp_workspace, "derivatives", "pipeline1", "sub-01"))

    def test_cleanup_handles_errors(self, patient_page, monkeypatch):
        """Ensure cleanup errors are handled gracefully."""
        patient_page.selected_patients = {"sub-01"}
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        with patch('main.ui.patient_selection_page.ToolSelectionPage'), \
                patch('main.ui.patient_selection_page.shutil.rmtree', side_effect=Exception("Delete error")):
            result = patient_page.next(patient_page.context)
            assert result is not None


class TestPatientSelectionPageLayout:
    """Tests for dynamic layout behavior."""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        for i in range(6):
            os.makedirs(os.path.join(temp_dir, f"sub-{i:02d}"))
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_update_column_count_wide(self, patient_page):
        """Ensure column count updates for wide window."""
        patient_page.scroll_area.resize(800, 400)
        patient_page._update_column_count()
        assert patient_page.column_count >= 1

    def test_update_column_count_narrow(self, patient_page):
        """Ensure narrow view results in 1 column."""
        with patch.object(patient_page.scroll_area.viewport(), 'width', return_value=200):
            patient_page._update_column_count()
            assert patient_page.column_count == 1

    def test_resize_event_updates_columns(self, patient_page):
        """Ensure resize event triggers column update."""
        from PyQt6.QtGui import QResizeEvent
        from PyQt6.QtCore import QSize
        event = QResizeEvent(QSize(800, 600), QSize(400, 600))
        patient_page.resizeEvent(event)
        assert patient_page.column_count >= 1

    def test_reload_patient_grid_maintains_selection(self, patient_page):
        """Ensure reloading grid preserves selected patients."""
        patient_page.selected_patients = {"sub-00", "sub-01"}
        patient_page._reload_patient_grid()
        assert "sub-00" in patient_page.selected_patients
        assert "sub-01" in patient_page.selected_patients


class TestPatientSelectionPageReset:
    """Tests for page reset behavior."""

    def test_reset_page_clears_selections(self, patient_page):
        """Reset should clear selected patients."""
        patient_page.selected_patients = {"sub-001", "sub-002"}
        patient_page.reset_page()
        assert len(patient_page.selected_patients) == 0

    def test_reset_page_clears_buttons(self, patient_page):
        """Reset should reload patient buttons."""
        initial_buttons = len(patient_page.patient_buttons)
        patient_page.reset_page()
        assert len(patient_page.patient_buttons) == initial_buttons

    def test_on_enter_maintains_selections(self, patient_page):
        """on_enter should preserve selections."""
        patient_page.selected_patients = {"sub-01"}
        patient_page.on_enter()
        assert "sub-01" in patient_page.selected_patients


class TestPatientSelectionPageTranslation:
    """Tests for UI translation updates."""

    def test_translate_ui_updates_title(self, patient_page):
        """Ensure title text updates after translation."""
        patient_page._translate_ui()
        assert patient_page.title.text() != ""

    def test_translate_ui_updates_buttons(self, patient_page):
        """Ensure button labels update after translation."""
        patient_page._translate_ui()
        assert patient_page.select_all_btn.text() != ""
        assert patient_page.deselect_all_btn.text() != ""


class TestPatientSelectionPageIntegration:
    """Integration tests for full user workflows."""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        for i in range(3):
            patient_id = f"sub-{i:02d}"
            os.makedirs(os.path.join(temp_dir, patient_id, "anat"))
            os.makedirs(os.path.join(temp_dir, patient_id, "pet"))
        os.makedirs(os.path.join(temp_dir, "derivatives"))
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_full_workflow_select_and_advance(self, patient_page, monkeypatch, temp_workspace):
        """Full flow: load patients, select all, and advance."""
        assert len(patient_page.patient_buttons) == 3
        patient_page._select_all_patients()
        assert len(patient_page.selected_patients) == 3
        assert patient_page.is_ready_to_advance()
        with patch('main.ui.patient_selection_page.ToolSelectionPage') as MockPage:
            MockPage.return_value = Mock()
            result = patient_page.next(patient_page.context)
            assert result is not None

    def test_full_workflow_with_cleanup(self, patient_page, monkeypatch, temp_workspace):
        """Full flow with cleanup confirmation."""
        button = patient_page.patient_buttons["sub-00"]
        patient_page._toggle_patient("sub-00", True, button)
        assert len(patient_page.selected_patients) == 1
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        with patch('main.ui.patient_selection_page.ToolSelectionPage'):
            result = patient_page.next(patient_page.context)
            assert os.path.exists(os.path.join(temp_workspace, "sub-00"))
            assert not os.path.exists(os.path.join(temp_workspace, "sub-01"))
            assert not os.path.exists(os.path.join(temp_workspace, "sub-02"))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
