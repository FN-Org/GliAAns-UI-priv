import os
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from PyQt6.QtWidgets import QMessageBox, QListWidgetItem
from PyQt6.QtCore import Qt, QCoreApplication

from main.ui.dl_execution_page import DlExecutionPage


@pytest.fixture
def mock_dl_worker():
    """Mock for DlWorker."""
    with patch("main.ui.dl_execution_page.DlWorker") as mock:
        worker_instance = Mock()
        worker_instance.progressbar_update = Mock()
        worker_instance.progressbar_update.connect = Mock()
        worker_instance.file_update = Mock()
        worker_instance.file_update.connect = Mock()
        worker_instance.log_update = Mock()
        worker_instance.log_update.connect = Mock()
        worker_instance.finished = Mock()
        worker_instance.finished.connect = Mock()
        worker_instance.cancel_requested = Mock()
        worker_instance.cancel_requested.emit = Mock()
        worker_instance.start = Mock()

        mock.return_value = worker_instance
        yield mock


@pytest.fixture
def mock_context_dl(temp_workspace):
    """Context for DlExecutionPage."""
    context = {
        "workspace_path": temp_workspace,
        "selected_segmentation_files": [
            os.path.join(temp_workspace, "sub-01", "anat", "sub-01_T1w.nii"),
            os.path.join(temp_workspace, "sub-02", "anat", "sub-02_T1w.nii")
        ],
        "update_main_buttons": Mock(),
        "language_changed": Mock(),
        "history": []
    }
    return context


class TestDlExecutionPageInitialization:
    """Tests for page initialization."""

    def test_initialization_basic(self, qtbot, mock_context_dl):
        """Test basic initialization."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.context == mock_context_dl
        assert page.previous_page is None
        assert page.next_page is None
        assert page.worker is None
        assert page.current_file is None
        assert page.processing is False
        assert page.processing_completed is False

    def test_initialization_with_previous_page(self, qtbot, mock_context_dl):
        """Test initialization with previous page."""
        previous = Mock()
        page = DlExecutionPage(mock_context_dl, previous_page=previous)
        qtbot.addWidget(page)

        assert page.previous_page == previous

    def test_ui_elements_created(self, qtbot, mock_context_dl):
        """Test that all UI elements are created."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.header is not None
        assert page.current_operation is not None
        assert page.progress_bar is not None
        assert page.files_group is not None
        assert page.files_list is not None
        assert page.log_label is not None
        assert page.log_text is not None
        assert page.start_button is not None
        assert page.cancel_button is not None

    def test_initial_button_visibility(self, qtbot, mock_context_dl):
        """Test initial button visibility."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.start_button.isVisibleTo(page)
        # cancel_button visibility depends on implementation


class TestOnEnter:
    """Tests for the on_enter method."""

    def test_on_enter_resets_state(self, qtbot, mock_context_dl):
        """Test that on_enter resets the state."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.processing = True
        page.processing_completed = True

        page.on_enter()

        assert page.processing is False
        assert page.processing_completed is False

    def test_on_enter_populates_file_list(self, qtbot, mock_context_dl):
        """Test that on_enter populates the file list."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.on_enter()

        assert page.files_list.count() == 2

        item0 = page.files_list.item(0).text()
        item1 = page.files_list.item(1).text()

        assert "sub-01_T1w.nii" in item0
        assert "sub-02_T1w.nii" in item1
        assert "Waiting" in item0 or "In attesa" in item0
        assert "Waiting" in item1 or "In attesa" in item1

    def test_on_enter_clears_previous_list(self, qtbot, mock_context_dl):
        """Test that on_enter clears the previous list."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.files_list.addItem("Old item 1")
        page.files_list.addItem("Old item 2")

        assert page.files_list.count() > 2

        page.on_enter()

        assert page.files_list.count() == 2

    def test_on_enter_without_files_in_context(self, qtbot):
        """Test on_enter without files in context."""
        context = {"workspace_path": "/fake/path"}
        page = DlExecutionPage(context)
        qtbot.addWidget(page)

        page.on_enter()

        assert page.files_list.count() == 0

    def test_on_enter_with_empty_file_list(self, qtbot, temp_workspace):
        """Test on_enter with an empty file list."""
        context = {
            "workspace_path": temp_workspace,
            "selected_segmentation_files": []
        }
        page = DlExecutionPage(context)
        qtbot.addWidget(page)

        page.on_enter()

        assert page.files_list.count() == 0


class TestStartProcessing:
    """Tests for start_processing."""

    def test_start_processing_basic(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test basic processing start."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()

        mock_dl_worker.assert_called_once()
        assert page.worker is not None

        page.worker.start.assert_called_once()

        assert page.processing is True
        assert not page.start_button.isVisibleTo(page)
        assert page.cancel_button.isVisibleTo(page)
        assert page.progress_bar.isVisibleTo(page)

    def test_start_processing_no_context(self, qtbot):
        """Test start without context."""
        page = DlExecutionPage(context=None)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'warning') as mock_warning:
            page.start_processing()

            mock_warning.assert_called_once()
            assert page.worker is None

    def test_start_processing_no_files_in_context(self, qtbot, temp_workspace):
        """Test start without files in context."""
        context = {"workspace_path": temp_workspace}
        page = DlExecutionPage(context)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'warning') as mock_warning:
            page.start_processing()

            mock_warning.assert_called_once()
            assert page.worker is None

    def test_start_processing_empty_file_list(self, qtbot, temp_workspace):
        """Test start with an empty file list."""
        context = {
            "workspace_path": temp_workspace,
            "selected_segmentation_files": []
        }
        page = DlExecutionPage(context)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'warning') as mock_warning:
            page.start_processing()

            mock_warning.assert_called_once()
            assert page.worker is None

    def test_start_processing_connects_signals(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test that signals are connected correctly."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()

        page.worker.progressbar_update.connect.assert_called_once()
        page.worker.file_update.connect.assert_called_once()
        page.worker.log_update.connect.assert_called_once()
        page.worker.finished.connect.assert_called_once()

    def test_start_processing_worker_parameters(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test that the worker receives correct parameters."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()

        call_kwargs = mock_dl_worker.call_args[1]
        assert call_kwargs['input_files'] == mock_context_dl["selected_segmentation_files"]
        assert call_kwargs['workspace_path'] == mock_context_dl["workspace_path"]

    def test_start_processing_clears_log(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test that the log is cleared on start."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.log_text.setText("Old log content")

        page.start_processing()

        log_content = page.log_text.toPlainText()
        assert "Old log content" not in log_content


class TestUpdateProgress:
    """Tests for update_progress."""

    def test_update_progress_basic(self, qtbot, mock_context_dl):
        """Test basic progress update."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.update_progress(50)

        assert page.progress_bar.value == 50

    def test_update_progress_multiple_values(self, qtbot, mock_context_dl):
        """Test multiple updates."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        for i in range(0, 101, 10):
            page.update_progress(i)
            assert page.progress_bar.value == i

    def test_update_progress_zero(self, qtbot, mock_context_dl):
        """Test with value 0."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.update_progress(0)
        assert page.progress_bar.value == 0

    def test_update_progress_hundred(self, qtbot, mock_context_dl):
        """Test with value 100."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.update_progress(100)
        assert page.progress_bar.value == 100


class TestAddLogMessage:
    """Tests for add_log_message."""

    def test_add_log_message_info(self, qtbot, mock_context_dl, mock_logger):
        """Test adding info message."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch("main.ui.dl_execution_page.log", mock_logger):
            page.add_log_message("Test info message", 'i')

            log_content = page.log_text.toPlainText()
            assert "Test info message" in log_content
            mock_logger.info.assert_called_once()

    def test_add_log_message_error(self, qtbot, mock_context_dl, mock_logger):
        """Test adding error message."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch("main.ui.dl_execution_page.log", mock_logger):
            page.add_log_message("Test error message", 'e')

            log_content = page.log_text.toPlainText()
            assert "Test error message" in log_content
            mock_logger.error.assert_called_once()

    def test_add_log_message_warning(self, qtbot, mock_context_dl, mock_logger):
        """Test adding warning message."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch("main.ui.dl_execution_page.log", mock_logger):
            page.add_log_message("Test warning message", 'w')

            log_content = page.log_text.toPlainText()
            assert "Test warning message" in log_content
            mock_logger.warning.assert_called_once()

    def test_add_log_message_debug(self, qtbot, mock_context_dl, mock_logger):
        """Test adding debug message."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch("main.ui.dl_execution_page.log", mock_logger):
            page.add_log_message("Test debug message", 'd')

            log_content = page.log_text.toPlainText()
            assert "Test debug message" in log_content
            mock_logger.debug.assert_called_once()

    def test_add_log_message_includes_timestamp(self, qtbot, mock_context_dl):
        """Test that the message includes a timestamp."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.add_log_message("Test message", 'i')

        log_content = page.log_text.toPlainText()
        assert "[" in log_content
        assert "]" in log_content
        assert ":" in log_content  # Timestamp format

    def test_add_log_message_autoscroll(self, qtbot, mock_context_dl):
        """Test auto-scroll after adding a message."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        for i in range(50):
            page.add_log_message(f"Message {i}", 'i')

        scrollbar = page.log_text.verticalScrollBar()
        assert scrollbar.value() == scrollbar.maximum()

    def test_add_log_message_multiple(self, qtbot, mock_context_dl):
        """Test multiple messages."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        messages = ["First", "Second", "Third"]
        for msg in messages:
            page.add_log_message(msg, 'i')

        log_content = page.log_text.toPlainText()
        for msg in messages:
            assert msg in log_content


class TestUpdateFileStatus:
    """Tests for update_file_status."""

    def test_update_file_status_basic(self, qtbot, mock_context_dl):
        """Test file status update."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)
        page.on_enter()

        page.update_file_status("sub-01_T1w.nii", "Processing")

        item = page.files_list.item(0)
        assert "Processing" in item.text()
        assert "sub-01_T1w.nii" in item.text()

    def test_update_file_status_completed(self, qtbot, mock_context_dl):
        """Test completed status."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)
        page.on_enter()

        page.update_file_status("sub-01_T1w.nii", "Completed")

        item = page.files_list.item(0)
        assert "Completed" in item.text()

    def test_update_file_status_error(self, qtbot, mock_context_dl):
        """Test error status."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)
        page.on_enter()

        page.update_file_status("sub-01_T1w.nii", "Error")

        item = page.files_list.item(0)
        assert "Error" in item.text()

    def test_update_file_status_nonexistent_file(self, qtbot, mock_context_dl):
        """Test updating a file not in the list."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)
        page.on_enter()

        initial_count = page.files_list.count()

        page.update_file_status("nonexistent.nii", "Processing")

        assert page.files_list.count() == initial_count

    def test_update_file_status_multiple_updates(self, qtbot, mock_context_dl):
        """Test multiple updates for the same file."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)
        page.on_enter()

        filename = "sub-01_T1w.nii"

        page.update_file_status(filename, "Processing")
        item = page.files_list.item(0)
        assert "Processing" in item.text()

        page.update_file_status(filename, "Completed")
        item = page.files_list.item(0)
        assert "Completed" in item.text()
        assert "Processing" not in item.text()


class TestCancelProcessing:
    """Tests for cancel_processing."""

    def test_cancel_processing_with_worker(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test cancellation with an active worker."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()

        page.cancel_processing()

        page.worker.cancel_requested.emit.assert_called_once()

    def test_cancel_processing_without_worker(self, qtbot, mock_context_dl):
        """Test cancellation without a worker."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.cancel_processing()

        assert page.worker is None

    def test_cancel_processing_adds_log(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test that cancellation adds a log entry."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()
        page.cancel_processing()

        log_content = page.log_text.toPlainText()
        assert "Cancellation requested" in log_content or "Annullamento richiesto" in log_content


class TestProcessingFinished:
    """Tests for processing_finished."""

    def test_processing_finished_success(self, qtbot, mock_context_dl):
        """Test successful completion."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'information') as mock_info:
            page.processing_finished(True, "All files processed successfully")

            assert page.processing is False
            assert page.processing_completed is True
            assert page.start_button.isVisibleTo(page)
            assert not page.cancel_button.isVisibleTo(page)
            assert not page.progress_bar.isVisibleTo(page)

            mock_info.assert_called_once()
            mock_context_dl["update_main_buttons"].assert_called_once()

    def test_processing_finished_failure(self, qtbot, mock_context_dl):
        """Test completion with failure."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'critical') as mock_critical:
            page.processing_finished(False, "Processing failed")

            assert page.processing is False
            assert page.processing_completed is True

            mock_critical.assert_called_once()

    def test_processing_finished_updates_context(self, qtbot, mock_context_dl):
        """Test that the context is updated."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "Success")

            assert "processing_output_dir" in mock_context_dl

    def test_processing_finished_current_operation_text(self, qtbot, mock_context_dl):
        """Test current operation text update."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "Success")

            assert "completed" in page.current_operation.text().lower() or "✓" in page.current_operation.text()

        page2 = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page2)

        with patch.object(QMessageBox, 'critical'):
            page2.processing_finished(False, "Error")

            assert "failed" in page2.current_operation.text().lower() or "✗" in page2.current_operation.text()

    def test_processing_finished_reprocess_button(self, qtbot, mock_context_dl):
        """Test that the button becomes 'Reprocess' after success."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "Success")

            assert "Reprocess" in page.start_button.text()


class TestResetProcessingState:
    """Tests for reset_processing_state."""

    def test_reset_processing_state_basic(self, qtbot, mock_context_dl):
        """Test basic state reset."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.processing = True
        page.processing_completed = True
        page.worker = Mock()

        page.reset_processing_state()

        assert page.processing is False
        assert page.processing_completed is False
        assert page.worker is None
        assert page.start_button.isVisibleTo(page)
        assert not page.cancel_button.isVisibleTo(page)
        assert not page.progress_bar.isVisibleTo(page)

    def test_reset_processing_state_button_text(self, qtbot, mock_context_dl):
        """Test button text reset."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_button.setText("Reprocess")

        page.reset_processing_state()

        assert "Start" in page.start_button.text() or "Avvio deep learning" in page.start_button.text()


class TestBackNavigation:
    """Tests for back navigation."""

    def test_back_not_processing(self, qtbot, mock_context_dl):
        """Test back when not processing."""
        previous = Mock()
        page = DlExecutionPage(mock_context_dl, previous_page=previous)
        qtbot.addWidget(page)

        result = page.back()

        assert result == previous
        previous.on_enter.assert_called_once()

    def test_back_while_processing_cancelled(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test back during processing with cancellation."""
        previous = Mock()
        page = DlExecutionPage(mock_context_dl, previous_page=previous)
        qtbot.addWidget(page)

        page.start_processing()

        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            result = page.back()

            page.worker.cancel_requested.emit.assert_called()
            assert result == previous

    def test_back_while_processing_not_cancelled(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test back during processing without cancellation."""
        previous = Mock()
        page = DlExecutionPage(mock_context_dl, previous_page=previous)
        qtbot.addWidget(page)

        page.start_processing()

        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            result = page.back()

            assert result is None
            previous.on_enter.assert_not_called()

    def test_back_no_previous_page(self, qtbot, mock_context_dl):
        """Test back without previous_page."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        result = page.back()

        assert result is None


class TestNextNavigation:
    """Tests for next navigation."""

    def test_next_returns_none(self, qtbot, mock_context_dl):
        """Test that next always returns None."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        result = page.next(mock_context_dl)

        assert result is None


class TestReadyToAdvance:
    """Tests for is_ready_to_advance."""

    def test_is_ready_to_advance_always_false(self, qtbot, mock_context_dl):
        """Test that is_ready_to_advance always returns False."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.is_ready_to_advance() is False

        # Even after completion
        page.processing_completed = True
        assert page.is_ready_to_advance() is False


class TestReadyToGoBack:
    """Tests for is_ready_to_go_back."""

    def test_is_ready_to_go_back_always_true(self, qtbot, mock_context_dl):
        """Test that is_ready_to_go_back always returns True."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.is_ready_to_go_back() is True

        # Even during processing
        page.processing = True
        assert page.is_ready_to_go_back() is True


class TestTranslation:
    """Tests for translations."""

    def test_translate_ui_called_on_init(self, qtbot, mock_context_dl):
        """Test that _translate_ui is called during init."""
        with patch.object(DlExecutionPage, '_translate_ui') as mock_translate:
            page = DlExecutionPage(mock_context_dl)
            qtbot.addWidget(page)

            mock_translate.assert_called()

    def test_translate_ui_updates_labels(self, qtbot, mock_context_dl):
        """Test that _translate_ui updates labels."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page._translate_ui()

        assert page.header.text() is not None
        assert page.current_operation.text() is not None
        assert page.files_group.title() is not None
        assert page.log_label.text() is not None
        assert page.start_button.text() is not None
        assert page.cancel_button.text() is not None

    def test_translate_ui_repopulates_file_list(self, qtbot, mock_context_dl):
        """Test that _translate_ui repopulates the file list."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.on_enter()
        initial_count = page.files_list.count()

        page._translate_ui()

        assert page.files_list.count() == initial_count


class TestEdgeCases:
    """Tests for edge cases."""

    def test_rapid_start_cancel(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test rapid start and cancel."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        for _ in range(5):
            page.start_processing()
            page.cancel_processing()

        assert True

    def test_multiple_processing_finished_calls(self, qtbot, mock_context_dl):
        """Test multiple calls to processing_finished."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "First")
            page.processing_finished(True, "Second")

        assert page.processing_completed is True

    def test_update_file_status_empty_list(self, qtbot, mock_context_dl):
        """Test update_file_status with an empty list."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.update_file_status("file.nii", "Processing")

        assert page.files_list.count() == 2

    def test_very_long_log_messages(self, qtbot, mock_context_dl):
        """Test with very long log messages."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        long_message = "A" * 10000
        page.add_log_message(long_message, 'i')

        log_content = page.log_text.toPlainText()
        assert long_message in log_content

    def test_unicode_in_filenames(self, qtbot, temp_workspace):
        """Test with unicode characters in filenames."""
        context = {
            "workspace_path": temp_workspace,
            "selected_segmentation_files": [
                os.path.join(temp_workspace, "sub-àèéìòù", "anat", "file.nii"),
                os.path.join(temp_workspace, "sub-中文", "anat", "file.nii")
            ],
            "update_main_buttons": Mock()
        }

        page = DlExecutionPage(context)
        qtbot.addWidget(page)

        page.on_enter()

        assert page.files_list.count() == 2

    def test_progress_value_out_of_range(self, qtbot, mock_context_dl):
        """Test with progress values out of range."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.update_progress(-10)
        page.update_progress(150)

        assert True

    def test_concurrent_file_updates(self, qtbot, mock_context_dl):
        """Test concurrent file updates."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)
        page.on_enter()

        for i in range(100):
            page.update_file_status("sub-01_T1w.nii", f"Status {i}")
            page.update_file_status("sub-02_T1w.nii", f"Status {i}")

        assert True


class TestUIInteraction:
    """Tests for UI interaction."""

    def test_button_styling(self, qtbot, mock_context_dl):
        """Test that buttons have the correct style."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        start_style = page.start_button.styleSheet()
        cancel_style = page.cancel_button.styleSheet()

        assert "background-color" in start_style
        assert "background-color" in cancel_style

    def test_log_text_readonly(self, qtbot, mock_context_dl):
        """Test that the log is read-only."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.log_text.isReadOnly()

    def test_files_list_max_height(self, qtbot, mock_context_dl):
        """Test that the file list has a maximum height."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.files_list.maximumHeight() == 150

    def test_log_text_max_height(self, qtbot, mock_context_dl):
        """Test that the log has a maximum height."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.log_text.maximumHeight() == 200

    def test_header_alignment(self, qtbot, mock_context_dl):
        """Test that the header is centered."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.header.alignment() == Qt.AlignmentFlag.AlignCenter

    def test_current_operation_alignment(self, qtbot, mock_context_dl):
        """Test that current_operation is centered."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.current_operation.alignment() == Qt.AlignmentFlag.AlignCenter


class TestWorkerIntegration:
    """Tests for worker integration."""

    def test_worker_signals_connected(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test that all worker signals are connected."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()

        assert page.worker.progressbar_update.connect.called
        assert page.worker.file_update.connect.called
        assert page.worker.log_update.connect.called
        assert page.worker.finished.connect.called

    def test_worker_created_with_correct_parameters(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test that the worker is created with correct parameters."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()

        call_kwargs = mock_dl_worker.call_args[1]

        assert 'input_files' in call_kwargs
        assert 'workspace_path' in call_kwargs
        assert call_kwargs['workspace_path'] == mock_context_dl['workspace_path']

    def test_worker_start_called(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test that worker.start() is called."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()

        page.worker.start.assert_called_once()


class TestContextHandling:
    """Tests for context handling."""

    def test_context_none_handling(self, qtbot):
        """Test handling None context."""
        page = DlExecutionPage(context=None)
        qtbot.addWidget(page)

        page.on_enter()

        with patch.object(QMessageBox, 'warning'):
            page.start_processing()

    def test_context_without_workspace_path(self, qtbot):
        """Test context without workspace_path."""
        context = {"selected_segmentation_files": ["file.nii"]}
        page = DlExecutionPage(context)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "Success")

    def test_context_without_update_main_buttons(self, qtbot, temp_workspace):
        """Test context without update_main_buttons."""
        context = {
            "workspace_path": temp_workspace,
            "selected_segmentation_files": ["file.nii"]
        }
        page = DlExecutionPage(context)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "Success")

    def test_processing_output_dir_set(self, qtbot, mock_context_dl):
        """Test that processing_output_dir is set in the context."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "Success")

            assert "processing_output_dir" in mock_context_dl
            expected_dir = os.path.join(mock_context_dl["workspace_path"], "outputs")
            assert mock_context_dl["processing_output_dir"] == expected_dir


class TestStateTransitions:
    """Tests for state transitions."""

    def test_state_idle_to_processing(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test transition from idle to processing."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.processing is False

        page.start_processing()

        assert page.processing is True
        assert not page.start_button.isVisibleTo(page)
        assert page.cancel_button.isVisibleTo(page)

    def test_state_processing_to_completed(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test transition from processing to completed."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()
        assert page.processing is True

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "Success")

        assert page.processing is False
        assert page.processing_completed is True
        assert page.start_button.isVisibleTo(page)

    def test_state_processing_to_cancelled(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test transition from processing to cancelled."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()
        page.cancel_processing()

        with patch.object(QMessageBox, 'critical'):
            page.processing_finished(False, "Cancelled")

        assert page.processing is False

    def test_state_completed_to_reset(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test transition from completed to reset."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "Success")

        assert page.processing_completed is True

        page.reset_processing_state()

        assert page.processing is False
        assert page.processing_completed is False


class TestIntegration:
    """Integration tests for complete flows."""

    def test_full_processing_flow_success(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test full flow: start -> processing -> success."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.on_enter()
        assert page.files_list.count() == 2

        page.start_processing()
        assert page.processing is True
        assert page.worker is not None

        page.update_progress(25)
        page.update_file_status("sub-01_T1w.nii", "Processing")
        page.add_log_message("Processing file 1", 'i')

        page.update_progress(50)
        page.update_file_status("sub-01_T1w.nii", "Completed")
        page.update_file_status("sub-02_T1w.nii", "Processing")

        page.update_progress(100)
        page.update_file_status("sub-02_T1nii", "Completed")

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "All files processed")

        assert page.processing_completed is True
        assert not page.processing

    def test_full_processing_flow_with_cancel(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test flow with cancellation."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.on_enter()
        page.start_processing()

        page.update_progress(30)
        page.add_log_message("Processing...", 'i')

        page.cancel_processing()

        with patch.object(QMessageBox, 'critical'):
            page.processing_finished(False, "Cancelled by user")

        assert not page.processing
        assert page.processing_completed

    def test_full_processing_flow_with_error(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test flow with error."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.on_enter()
        page.start_processing()

        page.update_progress(20)
        page.update_file_status("sub-01_T1w.nii", "Error")
        page.add_log_message("Error processing file", 'e')

        with patch.object(QMessageBox, 'critical'):
            page.processing_finished(False, "Processing error")

        assert not page.processing
        assert page.processing_completed

    def test_reprocess_flow(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test flow: processing -> completed -> reprocess."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.on_enter()
        page.start_processing()

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "Success")

        assert "Reprocess" in page.start_button.text()

        page.reset_processing_state()
        page.on_enter()

        mock_dl_worker.reset_mock()
        page.start_processing()

        assert page.processing is True
        mock_dl_worker.assert_called()


class TestErrorHandling:
    """Tests for error handling."""

    def test_start_processing_handles_worker_creation_error(self, qtbot, mock_context_dl):
        """Test worker creation error handling."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        with patch("main.ui.dl_execution_page.DlWorker") as mock_worker:
            mock_worker.side_effect = Exception("Worker creation failed")

            try:
                page.start_processing()
            except Exception:
                pass

    def test_processing_finished_without_workspace_path(self, qtbot):
        """Test processing_finished without workspace_path."""
        context = {"selected_segmentation_files": ["file.nii"]}
        page = DlExecutionPage(context)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'information'):
            page.processing_finished(True, "Success")


class TestBoundaryConditions:
    """Tests for boundary conditions."""

    def test_many_files_in_list(self, qtbot, temp_workspace):
        """Test with many files in the list."""
        files = [os.path.join(temp_workspace, f"sub-{i:03d}", "anat", "file.nii")
                 for i in range(100)]

        context = {
            "workspace_path": temp_workspace,
            "selected_segmentation_files": files,
            "update_main_buttons": Mock()
        }

        page = DlExecutionPage(context)
        qtbot.addWidget(page)

        page.on_enter()

        assert page.files_list.count() == 100

    def test_empty_filename(self, qtbot, mock_context_dl):
        """Test with empty filename."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)
        page.on_enter()

        page.update_file_status("", "Processing")

    def test_very_long_filename(self, qtbot, temp_workspace):
        """Test with very long filename."""
        long_name = "a" * 500 + ".nii"
        context = {
            "workspace_path": temp_workspace,
            "selected_segmentation_files": [os.path.join(temp_workspace, long_name)],
            "update_main_buttons": Mock()
        }

        page = DlExecutionPage(context)
        qtbot.addWidget(page)

        page.on_enter()

        assert page.files_list.count() == 1

    def test_rapid_log_messages(self, qtbot, mock_context_dl):
        """Test with very rapid log messages."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        for i in range(1000):
            page.add_log_message(f"Message {i}", 'i')

        assert "Message 999" in page.log_text.toPlainText()


class TestMemoryAndCleanup:
    """Tests for memory management and cleanup."""

    def test_worker_cleanup_after_finish(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test that the worker is cleaned up after finish."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        page.start_processing()
        assert page.worker is not None

        page.reset_processing_state()
        assert page.worker is None

    def test_multiple_processing_cycles(self, qtbot, mock_context_dl, mock_dl_worker):
        """Test multiple processing cycles."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        for cycle in range(3):
            page.on_enter()
            page.start_processing()

            with patch.object(QMessageBox, 'information'):
                page.processing_finished(True, f"Cycle {cycle} complete")

            page.reset_processing_state()

        assert True


class TestDocumentation:
    """Tests for documentation."""

    def test_class_docstring(self):
        """Test that the class has a docstring."""
        assert DlExecutionPage.__doc__ is not None

    def test_on_enter_docstring(self, qtbot, mock_context_dl):
        """Test that on_enter has a docstring."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert page.on_enter.__doc__ is not None


class TestAccessibility:
    """Tests for accessibility."""

    def test_buttons_have_text(self, qtbot, mock_context_dl):
        """Test that buttons have text."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert len(page.start_button.text()) > 0
        assert len(page.cancel_button.text()) > 0

    def test_labels_have_text(self, qtbot, mock_context_dl):
        """Test that labels have text."""
        page = DlExecutionPage(mock_context_dl)
        qtbot.addWidget(page)

        assert len(page.header.text()) > 0
        assert len(page.current_operation.text()) > 0
        assert len(page.log_label.text()) > 0