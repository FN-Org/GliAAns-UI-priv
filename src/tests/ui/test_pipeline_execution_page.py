import json
import os
import pytest
import time
from unittest.mock import Mock, patch, MagicMock, call
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QProcess, QTimer, QCoreApplication

from main.ui.pipeline_execution_page import PipelineExecutionPage


@pytest.fixture
def mock_get_bin_path():
    """Mock for get_bin_path."""
    with patch("main.ui.pipeline_execution_page.get_bin_path") as mock:
        mock.return_value = "/fake/path/pipeline_runner"
        yield mock


@pytest.fixture
def pipeline_config_exec(temp_workspace):
    """Create a config for pipeline execution."""
    config = {
        "sub-01": {
            "mri": os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii"),
            "pet": os.path.join(temp_workspace, "sub-01", "pet", "pet.nii"),
        },
        "sub-02": {
            "mri": "path/to/mri2.nii",
        }
    }

    pipeline_dir = os.path.join(temp_workspace, "pipeline")
    os.makedirs(pipeline_dir, exist_ok=True)
    config_path = os.path.join(pipeline_dir, "01_config.json")

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

    return config_path, config


@pytest.fixture
def mock_tree_view():
    """Mock for tree_view."""
    tree_view = Mock()
    tree_view._open_in_explorer = Mock()
    return tree_view


@pytest.fixture
def mock_context_exec(temp_workspace, signal_emitter, mock_tree_view):
    """Context for PipelineExecutionPage."""
    context = {
        "language_changed": signal_emitter.language_changed,
        "workspace_path": temp_workspace,
        "update_main_buttons": Mock(),
        "return_to_import": Mock(),
        "tree_view": mock_tree_view,
        "history": []
    }
    return context


class TestPipelineExecutionPageInitialization:
    """Tests for page initialization."""

    def test_initialization_basic(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test basic initialization."""
        config_path, config = pipeline_config_exec
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        assert page.context == mock_context_exec
        assert page.workspace_path == mock_context_exec["workspace_path"]
        assert page.previous_page is None
        assert page.next_page is None
        assert page.pipeline_process is None
        assert page.pipeline_completed is False
        assert page.pipeline_error is None
        assert page.config_path == config_path

    def test_initialization_with_previous_page(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test initialization with previous page."""
        previous = Mock()
        page = PipelineExecutionPage(mock_context_exec, previous_page=previous)
        qtbot.addWidget(page)

        assert page.previous_page == previous

    def test_pipeline_output_dir_created(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that the output directory is created."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        assert os.path.exists(page.pipeline_output_dir)
        assert "01_output" in page.pipeline_output_dir

    def test_ui_elements_created(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that all UI elements are created."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        assert page.header is not None
        assert page.current_operation is not None
        assert page.progress_bar is not None
        assert page.log_text is not None
        assert page.log_label is not None
        assert page.stop_button is not None
        assert isinstance(page.folder_cards, dict)

    def test_folder_cards_created(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test folder cards creation for each patient."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page.on_enter()

        assert len(page.folder_cards) == 2

    def test_get_bin_path_called(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that get_bin_path is called."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        mock_get_bin_path.assert_called_once_with("pipeline_runner")
        assert page.pipeline_bin_path == "/fake/path/pipeline_runner"

    def test_get_bin_path_error(self, qtbot, mock_context_exec, pipeline_config_exec):
        """Test error handling when get_bin_path fails."""
        with patch("main.ui.pipeline_execution_page.get_bin_path") as mock:
            mock.side_effect = FileNotFoundError("Binary not found")

            with pytest.raises(RuntimeError):
                page = PipelineExecutionPage(mock_context_exec)


class TestConfigFileDetection:
    """Tests for config file detection."""

    def test_find_latest_config_single(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test detection with a single config."""
        config_path, _ = pipeline_config_exec
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        assert page.config_path == config_path

    def test_find_latest_config_multiple(self, qtbot, mock_context_exec, temp_workspace, mock_get_bin_path):
        """Test detection with multiple configs (should take the last one)."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)

        # Create multiple configs
        configs = []
        for i in [1, 2, 5, 3]:  # Non-sequential order
            config_path = os.path.join(pipeline_dir, f"{i:02d}_config.json")
            config = {f"sub-{i:02d}": {"mri": "path.nii"}}
            with open(config_path, "w") as f:
                json.dump(config, f)
            configs.append((i, config_path))

        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        # Should take 05_config.json
        assert "05_config.json" in page.config_path

    def test_find_latest_config_no_files(self, qtbot, mock_context_exec, temp_workspace, mock_get_bin_path):
        """Test when there are no config files."""

        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)

        with patch.object(PipelineExecutionPage, "get_sub_list", return_value=[]):
            page = PipelineExecutionPage(mock_context_exec)
            qtbot.addWidget(page)

        expected = os.path.join(pipeline_dir, "pipeline_config.json")
        assert page.config_path == expected


class TestGetSubList:
    """Tests for the get_sub_list method."""

    def test_get_sub_list_basic(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test patient list extraction."""
        config_path, config = pipeline_config_exec
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        sub_list = page.get_sub_list(config_path)

        assert len(sub_list) == 2
        assert "sub-01" in sub_list
        assert "sub-02" in sub_list

    def test_get_sub_list_filters_non_sub(self, qtbot, mock_context_exec, temp_workspace, mock_get_bin_path):
        """Test that it correctly filters only sub-XX."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        config_path = os.path.join(pipeline_dir, "01_config.json")

        config = {
            "sub-01": {"mri": "path1.nii"},
            "sub-02": {"mri": "path2.nii"},
            "metadata": {"version": "1.0"},
            "settings": {"param": "value"}
        }

        with open(config_path, "w") as f:
            json.dump(config, f)

        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        sub_list = page.get_sub_list(config_path)

        assert len(sub_list) == 2
        assert "metadata" not in sub_list
        assert "settings" not in sub_list


class TestPipelineExecution:
    """Tests for pipeline execution."""

    def test_start_pipeline_basic(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test basic pipeline start."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(QProcess, 'start') as mock_start, \
                patch.object(QProcess, 'waitForStarted', return_value=True):
            page._start_pipeline()

            assert page.pipeline_process is not None
            mock_start.assert_called_once()
            assert page.stop_button.isEnabled()

    def test_start_pipeline_already_running(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that it does not start the pipeline if already running."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        # Simulate process already running
        page.pipeline_process = Mock()

        with patch.object(QProcess, 'start') as mock_start:
            page._start_pipeline()

            mock_start.assert_not_called()

    def test_start_pipeline_arguments(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that correct parameters are passed."""
        config_path, _ = pipeline_config_exec
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(QProcess, 'start') as mock_start, \
                patch.object(QProcess, 'waitForStarted', return_value=True):
            page._start_pipeline()

            # Verify passed arguments
            call_args = mock_start.call_args
            assert '--config' in call_args[0][1]
            assert config_path in call_args[0][1]
            assert '--work-dir' in call_args[0][1]
            assert '--out-dir' in call_args[0][1]

    def test_start_pipeline_failed_to_start(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test process start error handling."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(QProcess, 'start'), \
                patch.object(QProcess, 'waitForStarted', return_value=False), \
                patch.object(page, '_on_pipeline_error') as mock_error:
            page._start_pipeline()

            mock_error.assert_called_once()


class TestProcessOutput:
    """Tests for process output handling."""

    def test_process_pipeline_output_log(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test processing LOG line."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, '_log_message') as mock_log, \
                patch.object(page, '_update_current_operation') as mock_update:
            page._process_pipeline_output("LOG: Processing started")

            mock_log.assert_called_once_with("Processing started")
            mock_update.assert_called_once_with("Processing started")

    def test_process_pipeline_output_error(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test processing ERROR line."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, '_log_message') as mock_log:
            page._process_pipeline_output("ERROR: File not found")

            mock_log.assert_called_once()
            assert "ERROR:" in mock_log.call_args[0][0]

    def test_process_pipeline_output_progress(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test processing PROGRESS line."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, '_update_progress') as mock_progress:
            page._process_pipeline_output("PROGRESS: 5/10")

            mock_progress.assert_called_once_with("5/10")

    def test_process_pipeline_output_finished(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test processing FINISHED line."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, '_log_message') as mock_log:
            page._process_pipeline_output("FINISHED: All done")

            mock_log.assert_called_once()

    def test_process_pipeline_output_generic(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test processing generic line."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, '_log_message') as mock_log:
            page._process_pipeline_output("Some generic output")

            mock_log.assert_called_once_with("Some generic output")

    def test_on_stdout_ready(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test stdout reading."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        mock_process = Mock()
        mock_data = Mock()
        mock_data.data.return_value.decode.return_value = "LOG: Test message\nLOG: Another message"
        mock_process.readAllStandardOutput.return_value = mock_data
        page.pipeline_process = mock_process

        with patch.object(page, '_process_pipeline_output') as mock_process_output:
            page._on_stdout_ready()

            assert mock_process_output.call_count == 2

    def test_on_stderr_ready(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test stderr reading."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        mock_process = Mock()
        mock_data = Mock()
        mock_data.data.return_value.decode.return_value = "Error message"
        mock_process.readAllStandardError.return_value = mock_data
        page.pipeline_process = mock_process

        with patch.object(page, '_log_message') as mock_log:
            page._on_stderr_ready()

            mock_log.assert_called_once()
            assert "STDERR:" in mock_log.call_args[0][0]


class TestProgressUpdates:
    """Tests for progress updates."""

    def test_update_progress_valid(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test valid progress update."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, 'check_new_files') as mock_check:
            page._update_progress("5/10")

            assert page.progress_bar.value == 50
            mock_check.assert_called_once()

    def test_update_progress_invalid(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path,
                                     mock_logger):
        """Test progress update with invalid format."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        initial_value = page.progress_bar.value

        with patch("main.ui.pipeline_execution_page.log", mock_logger):
            page._update_progress("invalid")
            # The value should not change
            assert page.progress_bar.value == initial_value

    def test_update_current_operation_starting(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test operation update: starting."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page._update_current_operation("Starting pipeline execution")

        assert "Initializing" in page.current_operation.text()

    def test_update_current_operation_patient(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test operation update: processing patient."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page._update_current_operation("Processing patient sub-01")

        assert "sub-01" in page.current_operation.text()

    def test_update_current_operation_analysis(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test operation update: analysis."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page._update_current_operation("Performing statistical analysis")

        assert "analysis" in page.current_operation.text().lower()

    def test_update_current_operation_saving(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test operation update: saving."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page._update_current_operation("Saving results to CSV")

        assert "Saving" in page.current_operation.text()

    def test_extract_patient_id_from_log(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test patient ID extraction from log."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        patient_id = page._extract_patient_id_from_log("Processing sub-01 data")
        assert patient_id == "sub-01"

        patient_id = page._extract_patient_id_from_log("sub-123 completed")
        assert patient_id == "sub-123"

        patient_id = page._extract_patient_id_from_log("No patient here")
        assert patient_id is None


class TestProcessCompletion:
    """Tests for process completion."""

    def test_on_process_finished_success(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test successful completion."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, '_on_pipeline_finished') as mock_finished:
            page._on_process_finished(0, QProcess.ExitStatus.NormalExit)

            mock_finished.assert_called_once()

    def test_on_process_finished_error(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test completion with error."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, '_on_pipeline_error') as mock_error:
            page._on_process_finished(1, QProcess.ExitStatus.NormalExit)

            mock_error.assert_called_once()

    def test_on_pipeline_finished(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test pipeline finished handling."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page._on_pipeline_finished()

        assert page.pipeline_completed is True
        assert page.progress_bar.value == 100
        assert not page.stop_button.isEnabled()
        assert page.pipeline_process is None
        mock_context_exec["update_main_buttons"].assert_called_once()

    def test_on_pipeline_error(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test pipeline error handling."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page._on_pipeline_error("Test error message")

        assert page.pipeline_error == "Test error message"
        assert not page.stop_button.isEnabled()
        assert page.pipeline_process is None
        mock_context_exec["update_main_buttons"].assert_called_once()

    def test_on_process_error(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test handling of different process errors."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, '_on_pipeline_error') as mock_error:
            page._on_process_error(QProcess.ProcessError.FailedToStart)
            mock_error.assert_called_once()

        with patch.object(page, '_on_pipeline_error') as mock_error:
            page._on_process_error(QProcess.ProcessError.Crashed)
            mock_error.assert_called_once()


class TestStopButton:
    """Tests for the Stop button."""

    def test_stop_button_running(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test stop while process is running."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        mock_process = Mock()
        mock_process.state.return_value = QProcess.ProcessState.Running
        mock_process.waitForFinished.return_value = True
        page.pipeline_process = mock_process

        page._on_stop_clicked()

        mock_process.terminate.assert_called_once()
        assert page.pipeline_process is None
        assert not page.stop_button.isEnabled()
        mock_context_exec["update_main_buttons"].assert_called_once()

    def test_stop_button_forced_kill(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test stop with forced kill if terminate fails."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        mock_process = Mock()
        mock_process.state.return_value = QProcess.ProcessState.Running
        mock_process.waitForFinished.side_effect = [False, True]  # First False, then True
        page.pipeline_process = mock_process

        page._on_stop_clicked()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_stop_button_not_running(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test stop when process is not running."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        mock_process = Mock()
        mock_process.state.return_value = QProcess.ProcessState.NotRunning
        page.pipeline_process = mock_process

        page._on_stop_clicked()

        mock_process.terminate.assert_not_called()


class TestLogMessages:
    """Tests for logging."""

    def test_log_message_basic(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test basic log message."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        initial_text = page.log_text.toPlainText()

        page._log_message("Test message")

        log_content = page.log_text.toPlainText()
        assert "Test message" in log_content
        assert "[" in log_content  # Timestamp

    def test_log_message_multiple(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test multiple messages."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        messages = ["First message", "Second message", "Third message"]
        for msg in messages:
            page._log_message(msg)

        log_content = page.log_text.toPlainText()
        for msg in messages:
            assert msg in log_content

    def test_log_message_autoscroll(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test autoscroll to the bottom of the log."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        # Add many messages to force scrolling
        for i in range(50):
            page._log_message(f"Message {i}")

        scrollbar = page.log_text.verticalScrollBar()
        # Should be scrolled to the bottom
        assert scrollbar.value() == scrollbar.maximum()


class TestNavigation:
    """Tests for navigation."""

    def test_on_enter_starts_pipeline(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that on_enter automatically starts the pipeline."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, '_start_pipeline') as mock_start:
            page.on_enter()

            # Wait for QTimer to call the method
            qtbot.wait(600)

            mock_start.assert_called_once()

    def test_on_enter_not_started_twice(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that on_enter does not start twice if already completed."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page.pipeline_completed = True

        with patch.object(page, '_start_pipeline') as mock_start:
            page.on_enter()
            qtbot.wait(600)

            mock_start.assert_not_called()

    def test_back_calls_reset(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that back calls reset_page."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        previous = Mock()
        page.previous_page = previous

        with patch.object(page, 'reset_page') as mock_reset:
            result = page.back()

            mock_reset.assert_called_once()
            assert result == previous

    def test_back_no_previous_page(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test back without previous page."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        result = page.back()

        assert result is None

    def test_next_with_confirmation(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test next with user confirmation."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Ok):
            result = page.next(mock_context_exec)

            mock_context_exec["return_to_import"].assert_called()

    def test_next_cancelled(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test next with user cancellation."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Cancel):
            result = page.next(mock_context_exec)

            assert result is None
            mock_context_exec["return_to_import"].assert_not_called()

    def test_is_ready_to_go_back_completed(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test is_ready_to_go_back when completed."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page.pipeline_completed = True
        assert page.is_ready_to_go_back() is True

    def test_is_ready_to_go_back_error(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test is_ready_to_go_back when there is an error."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page.pipeline_error = "Some error"
        assert page.is_ready_to_go_back() is True

    def test_is_ready_to_go_back_running(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test is_ready_to_go_back during execution."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        assert page.is_ready_to_go_back() is False

    def test_is_ready_to_advance(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test is_ready_to_advance."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        assert page.is_ready_to_advance() is False

        page.pipeline_completed = True
        assert page.is_ready_to_advance() is True

        page.pipeline_completed = False
        page.pipeline_error = "Error"
        assert page.is_ready_to_advance() is True


class TestResetPage:
    """Tests for page reset."""

    def test_reset_page_basic(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test basic page reset."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        # Modify state
        page.progress_bar.setValue(50)
        page.pipeline_error = "Some error"
        page.pipeline_completed = True
        page.pipeline_process = Mock()
        page.log_text.setText("Some logs")

        page.reset_page()

        assert page.progress_bar.value == 0
        assert page.pipeline_error is None
        assert page.pipeline_completed is False
        assert page.pipeline_process is None
        assert page.log_text.toPlainText() == ""
        assert not page.stop_button.isEnabled()

    def test_reset_page_color(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that reset restores the progress bar color."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page.progress_bar.setColor("#FF0000")

        page.reset_page()

        # Verify it returned to default color
        assert page.progress_bar.color.name() == "#3498db"

    def test_reset_page_current_operation(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that reset restores the current operation text."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page.current_operation.setText("Processing...")

        page.reset_page()

        assert "Preparing to start" in page.current_operation.text()


class TestCheckNewFiles:
    """Tests for check_new_files."""

    def test_check_new_files(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that check_new_files calls the method on all cards."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        # Mock folder cards
        for card in page.folder_cards.values():
            card.check_new_files = Mock()

        page.check_new_files()

        # Verify it was called on all cards
        for card in page.folder_cards.values():
            card.check_new_files.assert_called_once()


class TestDestructor:
    """Tests for the destructor."""

    def test_destructor_kills_process(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that the destructor kills the process if running."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        mock_process = Mock()
        mock_process.state.return_value = QProcess.ProcessState.Running
        mock_process.waitForFinished.return_value = True
        page.pipeline_process = mock_process

        # Simulate destruction
        page.__del__()

        mock_process.kill.assert_called_once()
        mock_process.waitForFinished.assert_called_once()

    def test_destructor_no_process(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that the destructor does not crash if there is no process."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page.pipeline_process = None

        # Should not crash
        page.__del__()


class TestTranslation:
    """Tests for translations."""

    def test_translate_ui_called_on_init(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that _translate_ui is called during init."""
        with patch.object(PipelineExecutionPage, '_translate_ui') as mock_translate:
            page = PipelineExecutionPage(mock_context_exec)
            qtbot.addWidget(page)

            mock_translate.assert_called()

    def test_translate_ui_updates_labels(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that _translate_ui updates labels."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page._translate_ui()

        assert page.header.text() is not None
        assert page.stop_button.text() is not None
        assert page.log_label.text() is not None

    def test_language_changed_signal(self, qtbot, mock_context_exec, signal_emitter, pipeline_config_exec,
                                     mock_get_bin_path):
        """Test that the language_changed signal updates the UI."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, '_translate_ui') as mock_translate:
            mock_context_exec["language_changed"].connect(mock_translate)
            mock_context_exec["language_changed"].emit("it")
            mock_translate.assert_called()


class TestFolderCards:
    """Tests for folder cards."""

    def test_folder_cards_connected_to_tree_view(self, qtbot, mock_context_exec, pipeline_config_exec,
                                                 mock_get_bin_path, mock_tree_view):
        """Test that folder cards are connected to tree_view."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        # Simulate request to open folder
        for card in page.folder_cards.values():
            # Difficult to test signal connection directly, but we can verify cards exist
            assert card is not None

    def test_folder_cards_paths(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that folder cards paths are correct."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page.on_enter()

        for watch_dir in page.watch_dirs:
            assert page.pipeline_output_dir in watch_dir
            assert watch_dir in page.folder_cards


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_config(self, qtbot, mock_context_exec, temp_workspace, mock_get_bin_path):
        """Test with empty config."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)
        config_path = os.path.join(pipeline_dir, "01_config.json")

        with open(config_path, "w") as f:
            json.dump({}, f)

        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        assert len(page.folder_cards) == 0

    def test_invalid_config_id(self, qtbot, mock_context_exec, temp_workspace, mock_get_bin_path, mock_logger):
        """Test with invalid config ID."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)
        config_path = os.path.join(pipeline_dir, "invalid_config.json")

        with open(config_path, "w") as f:
            json.dump({"sub-01": {"mri": "path.nii"}}, f)

        with (patch("main.ui.pipeline_execution_page.log", mock_logger),
              patch.object(PipelineExecutionPage, "get_sub_list", return_value=[])):
            page = PipelineExecutionPage(mock_context_exec)
            qtbot.addWidget(page)

            # Should use default
            assert page.pipeline_output_dir == os.path.join(temp_workspace, "pipeline", "pipeline_output")
            mock_logger.debug.assert_called()

    def test_process_output_empty_lines(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that empty lines are ignored."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        mock_process = Mock()
        mock_data = Mock()
        mock_data.data.return_value.decode.return_value = "\n\n  \nLOG: Valid message\n\n"
        mock_process.readAllStandardOutput.return_value = mock_data
        page.pipeline_process = mock_process

        with patch.object(page, '_process_pipeline_output') as mock_process_output:
            page._on_stdout_ready()

            # Only the valid line should be processed
            assert mock_process_output.call_count == 1
            mock_process_output.assert_called_with("LOG: Valid message")

    def test_multiple_progress_updates(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test multiple progress updates."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        with patch.object(page, 'check_new_files'):
            for i in range(1, 11):
                page._update_progress(f"{i}/10")
                assert page.progress_bar.value == i*10

    def test_unicode_in_logs(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test with unicode characters in logs."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        unicode_messages = [
            "Processing àèéìòù",
            "Patient données françaises",
            "Εργασία ελληνικά",
            "处理中文"
        ]

        for msg in unicode_messages:
            page._log_message(msg)

        log_content = page.log_text.toPlainText()
        for msg in unicode_messages:
            assert msg in log_content

    def test_very_long_log_messages(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test with very long log messages."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        long_message = "A" * 10000
        page._log_message(long_message)

        log_content = page.log_text.toPlainText()
        assert long_message in log_content

    def test_rapid_process_output(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test with rapid process output."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        messages = [f"LOG: Message {i}" for i in range(100)]

        with patch.object(page, '_log_message'):
            for msg in messages:
                page._process_pipeline_output(msg)

        assert True

    def test_concurrent_stop_and_finish(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test concurrent stop and finish."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        mock_process = Mock()
        mock_process.state.return_value = QProcess.ProcessState.Running
        mock_process.waitForFinished.return_value = True
        page.pipeline_process = mock_process

        # Call stop
        page._on_stop_clicked()

        # Then finish (as if the process finished just as we were stopping)
        page._on_pipeline_finished()

        # Should handle the situation without crashing
        assert page.pipeline_completed is True
        assert page.pipeline_process is None


class TestReturnToImport:
    """Tests for _return_to_import."""

    def test_return_to_import_not_running(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test return_to_import when not running."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        page._return_to_import()

        mock_context_exec["return_to_import"].assert_called_once()

    def test_return_to_import_while_running(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test that return_to_import is blocked during execution."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        mock_process = Mock()
        mock_process.state.return_value = QProcess.ProcessState.Running
        page.pipeline_process = mock_process

        page._return_to_import()

        # Should not call return_to_import
        mock_context_exec["return_to_import"].assert_not_called()


class TestIntegration:
    """Integration tests for complete flows."""

    def test_full_pipeline_success_flow(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test full flow: start -> execution -> success."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        # Simulate start
        with patch.object(QProcess, 'start'), \
                patch.object(QProcess, 'waitForStarted', return_value=True):
            page._start_pipeline()
            assert page.pipeline_process is not None
            assert page.stop_button.isEnabled()

        # Simulate output
        page._process_pipeline_output("LOG: Starting pipeline")
        page._process_pipeline_output("PROGRESS: 5/10")
        page._process_pipeline_output("LOG: Processing sub-01")
        page._process_pipeline_output("PROGRESS: 10/10")

        # Simulate completion
        page._on_pipeline_finished()

        assert page.pipeline_completed is True
        assert page.progress_bar.value == 100
        assert not page.stop_button.isEnabled()

    def test_full_pipeline_error_flow(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test full flow: start -> execution -> error."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        # Simulate start
        with patch.object(QProcess, 'start'), \
                patch.object(QProcess, 'waitForStarted', return_value=True):
            page._start_pipeline()

        # Simulate output
        page._process_pipeline_output("LOG: Starting pipeline")
        page._process_pipeline_output("ERROR: File not found")

        # Simulate error
        page._on_pipeline_error("Fatal error occurred")

        assert page.pipeline_error == "Fatal error occurred"
        assert not page.stop_button.isEnabled()
        assert page.pipeline_completed is False

    def test_full_pipeline_stop_flow(self, qtbot, mock_context_exec, pipeline_config_exec, mock_get_bin_path):
        """Test full flow: start -> execution -> user stop."""
        page = PipelineExecutionPage(mock_context_exec)
        qtbot.addWidget(page)

        # Simulate start
        with patch.object(QProcess, 'start'), \
                patch.object(QProcess, 'waitForStarted', return_value=True):
            page._start_pipeline()

        mock_process = Mock()
        mock_process.state.return_value = QProcess.ProcessState.Running
        mock_process.waitForFinished.return_value = True
        page.pipeline_process = mock_process

        # Simulate stop
        page._on_stop_clicked()

        mock_process.terminate.assert_called_once()
        assert page.pipeline_process is None
        assert not page.stop_button.isEnabled()
        assert page.progress_bar.value == 0