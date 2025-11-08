import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import QSettings, pyqtSignal, QObject

from main.ui.nifti_mask_selection_page import MaskNiftiSelectionPage

@pytest.fixture
def mask_page(qtbot, mock_context, mock_file_selector_mask):
    previous_page = Mock()
    page = MaskNiftiSelectionPage(mock_context, previous_page)
    qtbot.addWidget(page)
    return page

class TestNiftiMaskSelectionPageSetup:
    """Tests for NiftiMaskSelectionPage initialization"""

    def test_page_initialization(self, mask_page):
        """Test correct initialization"""
        assert mask_page.context is not None
        assert mask_page.previous_page is not None
        assert mask_page.selected_file is None

    def test_title_created(self, mask_page):
        """Test title creation"""
        assert mask_page.title is not None
        assert mask_page.title.text() != ""

    def test_file_selector_created(self, mask_page):
        """Test file selector creation"""
        assert mask_page.file_selector_widget is not None

    def test_viewer_button_created(self, mask_page):
        """Test viewer button creation"""
        assert mask_page.viewer_button is not None
        assert not mask_page.viewer_button.isEnabled()  # Disabled initially


class TestNiftiMaskSelectionPageExistingMask:
    """Tests for checking existing masks"""

    def test_has_existing_manual_mask(self, mask_page, temp_workspace):
        """Test detection of existing manual mask"""
        nifti_path = os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii")

        result = mask_page.has_existing_mask(nifti_path, temp_workspace)

        assert result == True

    def test_has_no_existing_mask(self, mask_page, temp_workspace):
        """Test when mask does not exist"""
        nifti_path = os.path.join(temp_workspace, "sub-03", "anat", "T1w.nii")

        result = mask_page.has_existing_mask(nifti_path, temp_workspace)

        assert result == False

    def test_has_existing_mask_no_subject_id(self, mask_page, temp_workspace):
        """Test behavior without subject ID"""
        nifti_path = os.path.join(temp_workspace, "invalid", "T1w.nii")

        result = mask_page.has_existing_mask(nifti_path, temp_workspace)

        assert result == False

    def test_has_existing_mask_empty_directory(self, mask_page, temp_workspace):
        """Test behavior with empty directory"""
        # Create directory but without files
        empty_dir = os.path.join(temp_workspace, "derivatives", "manual_masks", "sub-04", "anat")
        os.makedirs(empty_dir)

        nifti_path = os.path.join(temp_workspace, "sub-04", "anat", "T1w.nii")

        result = mask_page.has_existing_mask(nifti_path, temp_workspace)

        assert result == False


class TestNiftiMaskSelectionPageViewer:
    """Tests for opening NIfTI viewer"""

    def test_open_nifti_viewer_calls_context(self, mask_page):
        """Test that open_nifti_viewer calls the context"""
        test_file = "/path/to/scan.nii"
        mask_page.file_selector_widget.get_selected_files = Mock(
            return_value=[test_file]
        )

        mask_page.open_nifti_viewer()

        mask_page.context["open_nifti_viewer"].assert_called_once_with(test_file)

    def test_open_nifti_viewer_uses_last_file(self, mask_page):
        """Test that it uses the last selected file"""
        files = ["/path/file1.nii", "/path/file2.nii"]
        mask_page.file_selector_widget.get_selected_files = Mock(
            return_value=files
        )

        mask_page.open_nifti_viewer()

        # Should use the last file
        mask_page.context["open_nifti_viewer"].assert_called_once_with(files[-1])

    def test_open_nifti_viewer_handles_error(self, mask_page):
        """Test error handling"""
        mask_page.file_selector_widget.get_selected_files = Mock(
            side_effect=Exception("Test error")
        )

        # Should not raise exception
        mask_page.open_nifti_viewer()


class TestNiftiMaskSelectionPageReadiness:
    """Tests for advancement logic"""

    def test_not_ready_to_advance(self, mask_page):
        """Test that advancing is not ready"""
        assert not mask_page.is_ready_to_advance()

    def test_ready_to_go_back(self, mask_page):
        """Test that going back is ready"""
        assert mask_page.is_ready_to_go_back()


class TestNiftiMaskSelectionPageNavigation:
    """Tests for navigation"""

    def test_back_returns_previous_page(self, mask_page):
        """Test return to previous page"""
        result = mask_page.back()

        assert result == mask_page.previous_page
        mask_page.previous_page.on_enter.assert_called_once()

    def test_back_returns_none_without_previous(self, mask_page):
        """Test return None without previous page"""
        mask_page.previous_page = None

        result = mask_page.back()

        assert result is None


class TestNiftiMaskSelectionPageReset:
    """Tests for page reset"""

    def test_reset_clears_selected_file(self, mask_page):
        """Test that reset clears the selected file"""
        mask_page.selected_file = "/path/to/file.nii"

        mask_page.reset_page()

        assert mask_page.selected_file is None

    def test_reset_calls_clear_selected_files(self, mask_page):
        """Test that reset calls clear_selected_files"""
        mask_page.reset_page()

        mask_page.file_selector_widget.clear_selected_files.assert_called_once()

    def test_reset_disables_viewer_button(self, mask_page):
        """Test that reset disables the viewer button"""
        mask_page.viewer_button.setEnabled(True)

        mask_page.reset_page()

        assert not mask_page.viewer_button.isEnabled()


class TestNiftiMaskSelectionPageTranslation:
    """Tests for translations"""

    def test_translate_ui_updates_title(self, mask_page):
        """Test title update"""
        mask_page._translate_ui()
        assert mask_page.title.text() != ""

    def test_translate_ui_updates_button(self, mask_page):
        """Test button update"""
        mask_page._translate_ui()
        assert mask_page.viewer_button.text() != ""

class TestNiftiMaskSelectionPageOnEnter:
    """Tests for on_enter"""

    def test_on_enter_does_nothing(self, mask_page):
        """Test that on_enter does not cause errors"""
        # Should execute without errors
        mask_page.on_enter()


# Integration tests
class TestNiftiMaskSelectionPageIntegration:
    """Integration tests"""

    def test_full_workflow(self, mask_page, temp_workspace):
        """Test full workflow"""
        # Test initial state
        assert mask_page.selected_file is None
        assert not mask_page.viewer_button.isEnabled()

        # Simulate file selection
        test_file = os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii")
        mask_page.file_selector_widget.get_selected_files = Mock(
            return_value=[test_file]
        )

        # Open viewer
        mask_page.open_nifti_viewer()
        mask_page.context["open_nifti_viewer"].assert_called_once_with(test_file)

        # Reset
        mask_page.reset_page()
        assert mask_page.selected_file is None

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])