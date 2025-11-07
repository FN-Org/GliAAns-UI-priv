import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, call
from PyQt6.QtCore import QSettings, pyqtSignal, QObject
from PyQt6.QtWidgets import QMessageBox

from main.ui.skull_stripping_page import SkullStrippingPage

@pytest.fixture
def skull_page(qtbot, mock_context, mock_file_selector):
    with patch('subprocess.run', return_value=Mock(returncode=0)):
        previous_page = Mock()
        page = SkullStrippingPage(mock_context, previous_page)
        qtbot.addWidget(page)
        page.show()
        return page

class TestSkullStrippingPageSetup:
    """Tests for SkullStrippingPage initialization"""

    def test_page_initialization(self, skull_page):
        """Test correct initialization"""
        assert skull_page.context is not None
        assert skull_page.previous_page is not None
        assert skull_page.worker is None
        assert skull_page.canceled == False

    def test_title_created(self, skull_page):
        """Test title creation"""
        assert skull_page.title is not None
        assert skull_page.title.text() != ""

    def test_file_selector_created(self, skull_page):
        """Test file selector creation"""
        assert skull_page.file_selector_widget is not None

    def test_run_button_created(self, skull_page):
        """Test run button creation"""
        assert skull_page.run_button is not None
        assert not skull_page.run_button.isEnabled()  # Disabled initially

    def test_cancel_button_created(self, skull_page):
        """Test cancel button creation"""
        assert skull_page.cancel_button is not None
        assert not skull_page.cancel_button.isVisible()  # Hidden initially

    def test_progress_bar_created(self, skull_page):
        """Test progress bar creation"""
        assert skull_page.progress_bar is not None
        assert not skull_page.progress_bar.isVisible()  # Hidden initially

    @patch('subprocess.run', return_value=Mock(returncode=0))
    def test_bet_detected_when_available(self, mock_run, qtbot, mock_context, mock_file_selector):
        """Test BET detection when available"""
        page = SkullStrippingPage(mock_context, Mock())
        qtbot.addWidget(page)

        assert page.has_bet == True

    @patch('subprocess.run', side_effect=FileNotFoundError())
    def test_bet_not_detected_when_unavailable(self, mock_run, qtbot, mock_context, mock_file_selector):
        """Test that BET is not detected when unavailable"""
        page = SkullStrippingPage(mock_context, Mock())
        qtbot.addWidget(page)

        assert page.has_bet == False


class TestSkullStrippingPageBETParameters:
    """Tests for BET parameters"""

    def test_f_parameter_default(self, skull_page):
        """Test default value for f parameter"""
        assert skull_page.f_spinbox.value() == 0.50

    def test_f_parameter_range(self, skull_page):
        """Test range for f parameter"""
        assert skull_page.f_spinbox.minimum() == 0.0
        assert skull_page.f_spinbox.maximum() == 1.0

    def test_g_parameter_default(self, skull_page):
        """Test default value for g parameter"""
        assert skull_page.g_spinbox.value() == 0.0

    def test_coordinate_parameters_default(self, skull_page):
        """Test default coordinate values"""
        assert skull_page.c_x_spinbox.value() == 0
        assert skull_page.c_y_spinbox.value() == 0
        assert skull_page.c_z_spinbox.value() == 0

    def test_brain_extracted_checkbox_default(self, skull_page):
        """Test that brain extracted is checked by default"""
        assert skull_page.opt_brain_extracted.isChecked()

    def test_other_checkboxes_default(self, skull_page):
        """Test that other checkboxes are unchecked by default"""
        assert not skull_page.opt_m.isChecked()
        assert not skull_page.opt_t.isChecked()
        assert not skull_page.opt_s.isChecked()
        assert not skull_page.opt_o.isChecked()


class TestSkullStrippingPageAdvancedOptions:
    """Tests for advanced options"""

    def test_advanced_options_hidden_initially(self, skull_page):
        """Test that advanced options are hidden initially"""
        assert not skull_page.advanced_box.isVisible()

    def test_toggle_advanced_shows_options(self, skull_page):
        """Test that toggle shows advanced options"""
        skull_page.advanced_btn.setChecked(True)
        skull_page.toggle_advanced()  # call the function directly
        assert skull_page.advanced_box.isVisible()

    def test_toggle_advanced_hides_options(self, skull_page, qtbot):
        """Test that toggle hides advanced options"""
        # First show
        skull_page.advanced_btn.setChecked(True)
        skull_page.toggle_advanced()
        assert skull_page.advanced_box.isVisible()

        # Then hide
        skull_page.advanced_btn.setChecked(False)
        skull_page.toggle_advanced()
        assert not skull_page.advanced_box.isVisible()

    def test_toggle_updates_button_text(self, skull_page):
        """Test that toggle updates the button text"""
        initial_text = skull_page.advanced_btn.text()

        skull_page.advanced_btn.setChecked(True)
        skull_page.toggle_advanced()

        assert skull_page.advanced_btn.text() != initial_text


class TestSkullStrippingPageProcessing:
    """Tests for processing"""

    def test_run_without_files_shows_warning(self, skull_page, monkeypatch):
        """Test warning when no files are present"""
        skull_page.file_selector_widget.get_selected_files = Mock(return_value=[])

        warning_shown = False

        def mock_warning(*args, **kwargs):
            nonlocal warning_shown
            warning_shown = True

        monkeypatch.setattr(QMessageBox, 'warning', mock_warning)

        skull_page.run_bet()
        assert warning_shown

    @patch('main.ui.skull_stripping_page.SkullStripThread')
    def test_run_creates_worker_thread(self, MockThread, skull_page):
        """Test worker thread creation"""
        skull_page.file_selector_widget.get_selected_files = Mock(
            return_value=['/path/to/file.nii']
        )

        mock_worker = Mock()
        MockThread.return_value = mock_worker

        skull_page.run_bet()

        MockThread.assert_called_once()
        mock_worker.start.assert_called_once()

    @patch('main.ui.skull_stripping_page.SkullStripThread')
    def test_run_shows_progress_bar(self, MockThread, skull_page, qtbot):
        """Test that run shows the progress bar"""
        skull_page.file_selector_widget.get_selected_files = Mock(
            return_value=['/path/to/file.nii']
        )

        mock_worker = Mock()
        MockThread.return_value = mock_worker

        with qtbot.waitSignal(skull_page.processing, timeout=1000):
            skull_page.run_bet()

        assert skull_page.progress_bar.isVisible()

    def test_set_processing_mode_true(self, skull_page):
        """Test set_processing_mode(True)"""
        skull_page.set_processing_mode(True)

        assert not skull_page.run_button.isVisible()
        assert skull_page.cancel_button.isVisible()

    def test_cancel_processing(self, skull_page):
        """Test processing cancellation"""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        skull_page.worker = mock_worker

        skull_page.cancel_processing()

        assert skull_page.canceled == True
        mock_worker.cancel.assert_called_once()


class TestSkullStrippingPageProgressCallbacks:
    """Tests for progress callbacks"""

    def test_on_progress_updated(self, skull_page):
        """Test progress message update"""
        test_message = "Processing file 1 of 3"
        skull_page.on_progress_updated(test_message)

        assert skull_page.status_label.text() == test_message

    def test_on_progress_value_updated(self, skull_page):
        """Test progress bar value update"""
        skull_page.on_progress_value_updated(50)

        assert skull_page.progress_bar.value() == 50

    def test_on_all_completed_success(self, skull_page):
        """Test completion callback on success"""
        skull_page.on_all_completed(3, [])

        assert not skull_page.progress_bar.isVisible()
        assert "3" in skull_page.status_label.text()

    def test_on_all_completed_with_failures(self, skull_page):
        """Test completion callback with failures"""
        failed_files = ['/path/file1.nii', '/path/file2.nii']
        skull_page.on_all_completed(1, failed_files)

        assert not skull_page.progress_bar.isVisible()
        status_text = skull_page.status_label.text()
        assert "1" in status_text  # Successes

    def test_on_all_completed_all_failed(self, skull_page):
        """Test callback when all fail"""
        failed_files = ['/path/file1.nii', '/path/file2.nii']
        skull_page.on_all_completed(0, failed_files)

        assert not skull_page.progress_bar.isVisible()
        assert "failed" in skull_page.status_label.text().lower()

    def test_on_worker_finished(self, skull_page, qtbot):
        """Test worker finished callback"""
        mock_worker = Mock()
        skull_page.worker = mock_worker

        with qtbot.waitSignal(skull_page.processing, timeout=1000):
            skull_page.on_worker_finished()

        skull_page.context["update_main_buttons"].assert_called()


class TestSkullStrippingPageExistingCheck:
    """Tests for existing skull strip check"""
    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        # Create structure with existing skull strip
        subject_dir = os.path.join(temp_dir, "derivatives", "skullstrips", "sub-01", "anat")
        os.makedirs(subject_dir)
        with open(os.path.join(subject_dir, "brain.nii.gz"), "w") as f:
            f.write("test")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_has_existing_skull_strip_true(self, skull_page, temp_workspace):
        """Test detection of existing skull strip"""
        nifti_path = os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii")

        result = skull_page.has_existing_skull_strip(nifti_path, temp_workspace)

        assert result == True

    def test_has_existing_skull_strip_false(self, skull_page, temp_workspace):
        """Test when skull strip does not exist"""
        nifti_path = os.path.join(temp_workspace, "sub-02", "anat", "T1w.nii")

        result = skull_page.has_existing_skull_strip(nifti_path, temp_workspace)

        assert result == False

    def test_has_existing_skull_strip_no_subject_id(self, skull_page, temp_workspace):
        """Test behavior without subject ID"""
        nifti_path = os.path.join(temp_workspace, "invalid", "T1w.nii")

        result = skull_page.has_existing_skull_strip(nifti_path, temp_workspace)

        assert result == False


class TestSkullStrippingPageNavigation:
    """Tests for navigation"""

    def test_back_returns_previous_page(self, skull_page):
        """Test return to previous page"""
        result = skull_page.back()
        assert result == skull_page.previous_page
        skull_page.previous_page.on_enter.assert_called_once()

    def test_back_blocked_during_processing(self, skull_page, monkeypatch):
        """Test that back is blocked during processing"""
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
        """Test that advancing is not ready"""
        assert not skull_page.is_ready_to_advance()

    def test_is_ready_to_go_back_true_when_idle(self, skull_page):
        """Test that going back is ready when idle"""
        assert skull_page.is_ready_to_go_back()

    def test_is_ready_to_go_back_false_during_processing(self, skull_page):
        """Test that going back is not ready during processing"""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        skull_page.worker = mock_worker

        assert not skull_page.is_ready_to_go_back()


class TestSkullStrippingPageReset:
    """Tests for page reset"""

    def test_reset_clears_files(self, skull_page):
        """Test that reset clears files"""
        skull_page.reset_page()
        skull_page.file_selector_widget.clear_selected_files.assert_called_once()

    def test_reset_parameters(self, skull_page):
        """Test that reset restores parameters"""
        # Modify parameters
        skull_page.f_spinbox.setValue(0.7)
        skull_page.g_spinbox.setValue(0.5)

        # Reset
        skull_page.reset_page()

        # Verify default values
        assert skull_page.f_spinbox.value() == 0.50
        assert skull_page.g_spinbox.value() == 0.0

    def test_reset_checkboxes(self, skull_page):
        """Test that reset restores checkboxes"""
        # Modify checkboxes
        skull_page.opt_m.setChecked(True)
        skull_page.opt_t.setChecked(True)

        # Reset
        skull_page.reset_page()

        # Verify default values
        assert skull_page.opt_brain_extracted.isChecked()
        assert not skull_page.opt_m.isChecked()
        assert not skull_page.opt_t.isChecked()

    def test_reset_hides_progress_bar(self, skull_page):
        """Test that reset hides progress bar"""
        skull_page.progress_bar.setVisible(True)

        skull_page.reset_page()

        assert not skull_page.progress_bar.isVisible()

    def test_reset_cancels_running_worker(self, skull_page):
        """Test that reset cancels a running worker"""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        skull_page.worker = mock_worker

        skull_page.reset_page()

        mock_worker.cancel.assert_called_once()
        mock_worker.wait.assert_called_once()


class TestSkullStrippingPageTranslation:
    """Tests for translations"""

    def test_translate_ui_updates_title(self, skull_page):
        """Test title update"""
        skull_page._translate_ui()
        assert skull_page.title.text() != ""

    def test_translate_ui_updates_buttons(self, skull_page):
        """Test buttons update"""
        skull_page._translate_ui()
        assert skull_page.run_button.text() != ""
        assert skull_page.cancel_button.text() != ""


# Integration tests
class TestSkullStrippingPageIntegration:
    """Integration tests"""

    @patch('main.ui.skull_stripping_page.SkullStripThread')
    def test_full_processing_workflow(self, MockThread, skull_page, qtbot):
        """Test full processing workflow"""
        # Setup
        skull_page.file_selector_widget.get_selected_files = Mock(
            return_value=['/path/file.nii']
        )

        mock_worker = Mock()
        MockThread.return_value = mock_worker

        # Start processing
        with qtbot.waitSignal(skull_page.processing, timeout=1000):
            skull_page.run_bet()

        # Verify processing state
        assert skull_page.progress_bar.isVisible()
        assert skull_page.cancel_button.isVisible()
        assert not skull_page.run_button.isVisible()

        # Simulate completion
        with qtbot.waitSignal(skull_page.processing, timeout=1000):
            skull_page.on_worker_finished()

        # Verify final state
        assert not skull_page.cancel_button.isVisible()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])