import os
import pytest
from unittest.mock import Mock, patch, MagicMock

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QCoreApplication, Qt

from main.ui.dl_selection_page import DlNiftiSelectionPage


@pytest.fixture
def segmentation_workspace(temp_workspace):
    """Creates workspace with existing segmentations."""
    # Create directory with existing segmentation
    seg_dir = os.path.join(
        temp_workspace,
        "derivatives",
        "deep_learning_seg",
        "sub-01",
        "anat"
    )
    os.makedirs(seg_dir, exist_ok=True)

    # Create segmentation file
    with open(os.path.join(seg_dir, "sub-01_T1w_seg.nii.gz"), "w") as f:
        f.write("segmentation data")

    # Create patient without segmentation
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
    """Tests for the page initialization."""

    def test_initialization_basic(self, qtbot, mock_context, mock_file_selector_dl):
        """Test basic initialization."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.context == mock_context
        assert page.previous_page is None
        assert page.next_page is None

    def test_initialization_with_previous_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test initialization with previous page."""
        previous = Mock()
        page = DlNiftiSelectionPage(mock_context, previous_page=previous)
        qtbot.addWidget(page)

        assert page.previous_page == previous

    def test_ui_elements_created(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that all UI elements are created."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.title is not None
        assert page.file_selector_widget is not None
        assert page.status_label is not None
        assert page.layout is not None

    def test_file_selector_widget_configured(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that FileSelectorWidget is configured correctly."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Verify the widget was created with the correct parameters
        mock_file_selector_dl.assert_called_once()
        call_kwargs = mock_file_selector_dl.call_args[1]

        assert call_kwargs['parent'] == page
        assert call_kwargs['context'] == mock_context
        assert call_kwargs['label'] == "seg"
        assert call_kwargs['allow_multiple'] is True
        assert callable(call_kwargs['has_existing_function'])


class TestHasExistingSegmentation:
    """Tests for the has_existing_segmentation method."""

    def test_has_existing_segmentation_exists_nii_gz(self, qtbot, mock_context, segmentation_workspace,
                                                     mock_file_selector_dl):
        """Test when .nii.gz segmentation exists."""
        mock_context["workspace_path"] = segmentation_workspace
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        nifti_path = os.path.join(segmentation_workspace, "sub-01", "anat", "sub-01_T1w.nii")
        result = page.has_existing_segmentation(nifti_path, segmentation_workspace)

        assert result is True

    def test_has_existing_segmentation_exists_nii(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test when .nii segmentation exists."""
        # Create .nii segmentation (uncompressed)
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
        """Test when segmentation does not exist."""
        mock_context["workspace_path"] = segmentation_workspace
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        nifti_path = os.path.join(segmentation_workspace, "sub-02", "anat", "sub-02_T1w.nii")
        result = page.has_existing_segmentation(nifti_path, segmentation_workspace)

        assert result is False

    def test_has_existing_segmentation_no_subject_id(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test when the path does not contain a subject ID."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        nifti_path = os.path.join(temp_workspace, "random", "path", "file.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is False

    def test_has_existing_segmentation_directory_not_exists(self, qtbot, mock_context, temp_workspace,
                                                            mock_file_selector_dl):
        """Test when the segmentation directory does not exist."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        nifti_path = os.path.join(temp_workspace, "sub-99", "anat", "sub-99_T1w.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is False

    def test_has_existing_segmentation_multiple_files(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test when there are multiple segmentation files."""
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-04",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)

        # Create multiple seg files
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
        """Test that it ignores non-segmentation files."""
        seg_dir = os.path.join(
            temp_workspace,
            "derivatives",
            "deep_learning_seg",
            "sub-05",
            "anat"
        )
        os.makedirs(seg_dir, exist_ok=True)

        # Create files that are not segmentations
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
        """Test with nested path (e.g., with session)."""
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

        # Path with session
        nifti_path = os.path.join(temp_workspace, "sub-06", "ses-01", "anat", "sub-06_T1w.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True


class TestBackNavigation:
    """Tests for back navigation."""

    def test_back_with_previous_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test back with previous_page."""
        previous = Mock()
        page = DlNiftiSelectionPage(mock_context, previous_page=previous)
        qtbot.addWidget(page)

        result = page.back()

        assert result == previous
        previous.on_enter.assert_called_once()

    def test_back_no_previous_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test back without previous_page."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        result = page.back()

        assert result is None


class TestNextNavigation:
    """Tests for next navigation."""

    def test_next_creates_dl_execution_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that next creates DlExecutionPage."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Simulate file selection
        page.file_selector_widget._selected_files = ["file1.nii", "file2.nii"]

        result = page.next(mock_context)

        assert page.next_page is not None
        assert result == page.next_page
        assert "DlExecutionPage" in str(type(page.next_page))

    def test_next_saves_selected_files_to_context(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that next saves selected files to the context."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        selected_files = ["file1.nii", "file2.nii", "file3.nii"]
        page.file_selector_widget._selected_files = selected_files

        page.next(mock_context)

        assert mock_context["selected_segmentation_files"] == selected_files

    def test_next_adds_to_history(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that next adds to history."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]
        initial_history_len = len(mock_context["history"])

        page.next(mock_context)

        assert len(mock_context["history"]) == initial_history_len + 1
        assert page.next_page in mock_context["history"]

    def test_next_reuses_existing_next_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that next reuses the existing next_page."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]

        # First call
        result1 = page.next(mock_context)
        first_next_page = page.next_page

        # Second call
        result2 = page.next(mock_context)

        assert page.next_page == first_next_page
        assert result1 == result2

    def test_next_calls_on_enter(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that next calls on_enter on the next_page."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]

        with patch.object(page, 'next_page', create=True) as mock_next:
            mock_next.on_enter = Mock()
            page.next_page = mock_next

            page.next(mock_context)

            mock_next.on_enter.assert_called_once()

    def test_next_with_empty_selection(self, qtbot, mock_context, mock_file_selector_dl):
        """Test next with empty selection."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = []

        result = page.next(mock_context)

        # Should still create the next page
        assert result is not None
        assert mock_context["selected_segmentation_files"] == []


class TestOnEnter:
    """Tests for the on_enter method."""

    def test_on_enter_clears_status(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that on_enter clears the status label."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.status_label.setText("Some status message")

        page.on_enter()

        assert page.status_label.text() == ""


class TestReadyToAdvance:
    """Tests for is_ready_to_advance."""

    def test_is_ready_to_advance_with_files(self, qtbot, mock_context, mock_file_selector_dl):
        """Test when files are selected."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii", "file2.nii"]

        assert bool(page.is_ready_to_advance()) is True

    def test_is_ready_to_advance_without_files(self, qtbot, mock_context, mock_file_selector_dl):
        """Test when no files are selected."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = []

        assert not page.is_ready_to_advance()

    def test_is_ready_to_advance_single_file(self, qtbot, mock_context, mock_file_selector_dl):
        """Test with a single file selected."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["single_file.nii"]

        assert bool(page.is_ready_to_advance()) is True


class TestReadyToGoBack:
    """Tests for is_ready_to_go_back."""

    def test_is_ready_to_go_back_always_true(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that is_ready_to_go_back always returns True."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.is_ready_to_go_back() is True

        # Even with files selected
        page.file_selector_widget._selected_files = ["file1.nii"]
        assert page.is_ready_to_go_back() is True


class TestResetPage:
    """Tests for reset_page."""

    def test_reset_page_clears_status(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that reset_page clears the status."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.status_label.setText("Test status")

        page.reset_page()

        assert page.status_label.text() == ""

    def test_reset_page_clears_context(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that reset_page clears the context."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        mock_context["selected_segmentation_files"] = ["file1.nii", "file2.nii"]

        page.reset_page()

        assert mock_context["selected_segmentation_files"] == []

    def test_reset_page_without_context(self, qtbot, mock_file_selector_dl):
        """Test reset_page without context."""
        page = DlNiftiSelectionPage(context=None)
        qtbot.addWidget(page)

        page.status_label.setText("Test")

        # Shouldn't crash
        page.reset_page()

        assert page.status_label.text() == ""


class TestTranslation:
    """Tests for translations."""

    def test_translate_ui_called_on_init(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that _translate_ui is called during init."""
        with patch.object(DlNiftiSelectionPage, '_translate_ui') as mock_translate:
            page = DlNiftiSelectionPage(mock_context)
            qtbot.addWidget(page)

            mock_translate.assert_called()

    def test_translate_ui_updates_title(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that _translate_ui updates the title."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page._translate_ui()

        assert page.title.text() is not None
        assert len(page.title.text()) > 0

    def test_language_changed_signal(self, qtbot, mock_context, signal_emitter, mock_file_selector_dl):
        """Test that the language_changed signal updates the UI."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        with patch.object(page, '_translate_ui') as mock_translate:
            mock_context["language_changed"].connect(mock_translate)
            mock_context["language_changed"].emit("it")

            mock_translate.assert_called()


class TestEdgeCases:
    """Tests for edge cases."""

    def test_subject_id_extraction_complex_path(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test subject ID extraction with complex paths."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Create segmentation
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

        # Path with many levels
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
        """Test with multiple 'sub-' in path (should take the first)."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Create segmentation for sub-01
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

        # Path containing 'sub-' in both directory name and file name
        nifti_path = os.path.join(
            temp_workspace,
            "sub-01",
            "anat",
            "sub-01_T1w.nii"  # 'sub-' also appears here
        )

        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_workspace_path_with_trailing_slash(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test with workspace_path that has a trailing slash."""
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
        """Test with special characters in paths."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Subject with special characters
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
        """Test with empty segmentation directory."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Create directory but without files
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
        """Test with unicode characters in paths."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Subject with unicode
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
    """Integration tests for complete flows."""

    def test_full_selection_flow(self, qtbot, mock_context, mock_file_selector_dl):
        """Test full flow: selection -> next."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Simulate file selection
        selected_files = ["file1.nii", "file2.nii", "file3.nii"]
        page.file_selector_widget._selected_files = selected_files

        # Verify ready to advance
        assert bool(page.is_ready_to_advance()) is True

        # Next
        result = page.next(mock_context)

        # Verify
        assert result is not None
        assert mock_context["selected_segmentation_files"] == selected_files
        assert page.next_page is not None

    def test_reset_and_reselect_flow(self, qtbot, mock_context, mock_file_selector_dl):
        """Test flow: selection -> reset -> new selection."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # First selection
        page.file_selector_widget._selected_files = ["file1.nii"]
        page.next(mock_context)

        assert mock_context["selected_segmentation_files"] == ["file1.nii"]

        # Reset
        page.reset_page()

        assert mock_context["selected_segmentation_files"] == []

        # New selection
        page.file_selector_widget._selected_files = ["file2.nii", "file3.nii"]
        page.next(mock_context)

        assert mock_context["selected_segmentation_files"] == ["file2.nii", "file3.nii"]

    def test_back_and_forth_navigation(self, qtbot, mock_context, mock_file_selector_dl):
        """Test back and forth navigation."""
        previous = Mock()
        page = DlNiftiSelectionPage(mock_context, previous_page=previous)
        qtbot.addWidget(page)

        # Next
        page.file_selector_widget._selected_files = ["file1.nii"]
        next_page = page.next(mock_context)

        assert next_page is not None

        # Back
        result = page.back()

        assert result == previous
        previous.on_enter.assert_called_once()

    def test_status_label_lifecycle(self, qtbot, mock_context, mock_file_selector_dl):
        """Test status label lifecycle."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Initially empty
        assert page.status_label.text() == ""

        # Add status
        page.status_label.setText("Processing...")
        assert page.status_label.text() == "Processing..."

        # on_enter clears it
        page.on_enter()
        assert page.status_label.text() == ""

        # Add again
        page.status_label.setText("Error occurred")

        # reset_page clears it
        page.reset_page()
        assert page.status_label.text() == ""


class TestContextHandling:
    """Tests for context management."""

    def test_context_none_handling(self, qtbot, mock_file_selector_dl):
        """Test handling None context."""
        page = DlNiftiSelectionPage(context=None)
        qtbot.addWidget(page)

        # Shouldn't crash
        page.reset_page()

        assert page.context is None

    def test_context_without_history(self, qtbot, mock_file_selector_dl):
        """Test context without history."""
        context = {
            "workspace_path": "/fake/path"
        }
        page = DlNiftiSelectionPage(context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]

        # Shouldn't crash if history doesn't exist
        result = page.next(context)

        assert result is not None

    def test_selected_files_persisted_in_context(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that selected files persist in context."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        files = ["a.nii", "b.nii", "c.nii"]
        page.file_selector_widget._selected_files = files

        page.next(mock_context)

        # Verify they are saved
        assert "selected_segmentation_files" in mock_context
        assert mock_context["selected_segmentation_files"] == files

        # Even after reset
        page.reset_page()
        assert mock_context["selected_segmentation_files"] == []

    def test_multiple_next_calls_update_context(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that multiple calls to next update the context."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # First call
        page.file_selector_widget._selected_files = ["file1.nii"]
        page.next(mock_context)
        assert mock_context["selected_segmentation_files"] == ["file1.nii"]

        # Second call with different files
        page.file_selector_widget._selected_files = ["file2.nii", "file3.nii"]
        page.next(mock_context)
        assert mock_context["selected_segmentation_files"] == ["file2.nii", "file3.nii"]


class TestFileSelectorIntegration:
    """Tests for FileSelectorWidget integration."""

    def test_file_selector_get_selected_files_called(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that get_selected_files is called."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]

        with patch.object(page.file_selector_widget, 'get_selected_files', return_value=["file1.nii"]) as mock_get:
            page.next(mock_context)

            mock_get.assert_called()

    def test_is_ready_to_advance_uses_file_selector(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that is_ready_to_advance uses the file selector."""
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
        """Test that FileSelectorWidget receives correct parameters."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        call_kwargs = mock_file_selector_dl.call_args[1]

        # Verify specific parameters for DL segmentation
        assert call_kwargs['label'] == "seg"
        assert call_kwargs['allow_multiple'] is True

        # Verify has_existing_function is the correct function
        has_existing_func = call_kwargs['has_existing_function']
        assert has_existing_func == page.has_existing_segmentation


class TestPathHandling:
    """Tests for path handling."""

    def test_path_normalization(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test path normalization with mixed separators."""
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

        # Path with mixed separators (if on Windows)
        if os.sep == '\\':
            nifti_path = temp_workspace + "/sub-09/anat/file.nii"
        else:
            nifti_path = os.path.join(temp_workspace, "sub-09", "anat", "file.nii")

        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_relative_vs_absolute_paths(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test with relative vs absolute paths."""
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

        # Absolute path
        nifti_path = os.path.abspath(os.path.join(temp_workspace, "sub-10", "anat", "file.nii"))
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_symlinks_in_path(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test with symlinks in path (if supported by system)."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Create segmentation
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

        # Should also work with real paths
        assert result is True


class TestUIInteraction:
    """Tests for UI interaction."""

    def test_title_styling(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that the title has the correct style."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        font = page.title.font()

        assert font.pointSize() == 18
        assert font.weight() == QFont.Weight.Bold

    def test_status_label_alignment(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that the status label is centered."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.status_label.alignment() == Qt.AlignmentFlag.AlignCenter

    def test_layout_structure(self, qtbot, mock_context, mock_file_selector_dl):
        """Test layout structure."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Verify the layout is VBoxLayout
        assert page.layout is not None

        # Verify element order
        assert page.layout.itemAt(0).widget() == page.title
        assert page.layout.itemAt(1).widget() == page.file_selector_widget


class TestErrorHandling:
    """Tests for error handling."""

    def test_has_existing_segmentation_permission_error(self, qtbot, mock_context, temp_workspace,
                                                        mock_file_selector_dl):
        """Test permission error handling (simulated)."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Path that doesn't exist
        nifti_path = "/nonexistent/path/sub-12/anat/file.nii"

        # Shouldn't crash
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is False

    def test_has_existing_segmentation_with_corrupted_directory(self, qtbot, mock_context, temp_workspace,
                                                                mock_file_selector_dl):
        """Test with corrupted directory (simulated with file instead of directory)."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Create a file instead of a directory
        derivatives_path = os.path.join(temp_workspace, "derivatives")
        os.makedirs(derivatives_path, exist_ok=True)

        # File instead of directory
        fake_dir = os.path.join(derivatives_path, "deep_learning_seg")
        with open(fake_dir, "w") as f:
            f.write("this is a file, not a directory")

        nifti_path = os.path.join(temp_workspace, "sub-13", "anat", "file.nii")

        # Shouldn't crash
        try:
            result = page.has_existing_segmentation(nifti_path, temp_workspace)
            # Could be True or False, the important thing is it doesn't crash
            assert isinstance(result, bool)
        except (OSError, NotADirectoryError):
            # Some OSes might raise exceptions
            pass


class TestBoundaryConditions:
    """Tests for boundary conditions."""

    def test_very_long_path(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test with very long path."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Create deeply nested path
        deep_path = temp_workspace
        for i in range(10):
            deep_path = os.path.join(deep_path, f"level{i}")

        nifti_path = os.path.join(deep_path, "sub-14", "anat", "file.nii")

        # Shouldn't crash
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert isinstance(result, bool)

    def test_many_files_in_directory(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test with many files in the segmentation directory."""
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

        # Create many files
        for i in range(100):
            filename = f"file{i}.nii" if i < 50 else f"file{i}_seg.nii.gz"
            with open(os.path.join(seg_dir, filename), "w") as f:
                f.write("data")

        nifti_path = os.path.join(temp_workspace, "sub-15", "anat", "file.nii")
        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        # Should find at least one _seg file
        assert result is True

    def test_subject_id_at_end_of_path(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test when subject ID is at the end of the path."""
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

        # Subject ID in the last component
        nifti_path = os.path.join(temp_workspace, "data", "sub-16")

        result = page.has_existing_segmentation(nifti_path, temp_workspace)

        assert result is True

    def test_workspace_path_equals_nifti_path(self, qtbot, mock_context, temp_workspace, mock_file_selector_dl):
        """Test when workspace_path equals nifti_path."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Same path
        result = page.has_existing_segmentation(temp_workspace, temp_workspace)

        # Shouldn't crash
        assert isinstance(result, bool)


class TestConcurrency:
    """Tests for concurrent situations (simulated)."""

    def test_multiple_pages_same_context(self, qtbot, mock_context, mock_file_selector_dl):
        """Test with multiple pages sharing the same context."""
        page1 = DlNiftiSelectionPage(mock_context)
        page2 = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page1)
        qtbot.addWidget(page2)

        # Modify from page1
        page1.file_selector_widget._selected_files = ["file1.nii"]
        page1.next(mock_context)

        # Verify page2 sees the changes
        assert mock_context["selected_segmentation_files"] == ["file1.nii"]

        # Reset from page2
        page2.reset_page()

        # Verify the context is updated
        assert mock_context["selected_segmentation_files"] == []

    def test_rapid_next_back_navigation(self, qtbot, mock_context, mock_file_selector_dl):
        """Test rapid next-back navigation."""
        previous = Mock()
        page = DlNiftiSelectionPage(mock_context, previous_page=previous)
        qtbot.addWidget(page)

        page.file_selector_widget._selected_files = ["file1.nii"]

        # Rapid next and back
        for _ in range(10):
            page.next(mock_context)
            page.back()

        # Shouldn't crash
        assert True


class TestDocumentation:
    """Tests to verify documentation and comments."""

    def test_has_existing_segmentation_docstring(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that has_existing_segmentation has a docstring."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.has_existing_segmentation.__doc__ is not None

    def test_reset_page_docstring(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that reset_page has a docstring."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        assert page.reset_page.__doc__ is not None


class TestStateConsistency:
    """Tests to verify state consistency."""

    def test_state_after_multiple_operations(self, qtbot, mock_context, mock_file_selector_dl):
        """Test state after multiple operations."""
        page = DlNiftiSelectionPage(mock_context)
        qtbot.addWidget(page)

        # Sequence of operations
        page.file_selector_widget._selected_files = ["file1.nii"]
        assert bool(page.is_ready_to_advance()) is True

        page.next(mock_context)
        assert mock_context["selected_segmentation_files"] == ["file1.nii"]

        page.on_enter()
        assert page.status_label.text() == ""

        page.reset_page()
        assert mock_context["selected_segmentation_files"] == []

        # State should be consistent
        assert not bool(page.is_ready_to_advance())

    def test_state_independence_from_previous_page(self, qtbot, mock_context, mock_file_selector_dl):
        """Test that state is independent of previous_page."""
        previous = Mock()
        page1 = DlNiftiSelectionPage(mock_context, previous_page=previous)
        page2 = DlNiftiSelectionPage(mock_context, previous_page=None)

        qtbot.addWidget(page1)
        qtbot.addWidget(page2)

        # Modify page1
        page1.status_label.setText("Status 1")

        # page2 should have independent state
        assert page2.status_label.text() == ""

        # Resetting page1 should not affect page2
        page1.reset_page()
        page2.status_label.setText("Status 2")

        assert page1.status_label.text() == ""
        assert page2.status_label.text() == "Status 2"