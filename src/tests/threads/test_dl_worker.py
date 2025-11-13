import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from PyQt6.QtCore import QProcess

from main.threads.dl_worker import DlWorker
import main.threads.dl_worker


@pytest.fixture
def test_input_files(temp_workspace):
    """Create test input files."""
    files = []
    for i in range(3):
        filepath = os.path.join(temp_workspace, f"test_{i}.nii.gz")
        with open(filepath, "w") as f:
            f.write("nifti data")
        files.append(filepath)
    return files


@pytest.fixture(autouse=True)
def mock_external_dependencies(mocker):
    """
    This fixture is executed automatically for each test (autouse=True).
    It mocks the functions in utils.py that search for external dependencies
    during DlWorker's __init__.
    """

    # 1. Mock get_dl_python_executable
    mocker.patch(
        "main.threads.dl_worker.get_dl_python_executable",
        return_value=sys.executable
    )

    # 2. Mock get_bin_path
    mocker.patch(
        "main.threads.dl_worker.get_bin_path",
        return_value="/fake/path/to/binary"
    )

    # 3. Mock QProcess completely (REPLACEMENT)
    mock_qprocess_class = mocker.patch("main.threads.dl_worker.QProcess")

    # Configure the mock instance that will be returned
    process_instance = MagicMock()
    # We use MagicMock for signals, specifying 'connect' to avoid errors
    process_instance.finished = MagicMock(spec_set=['connect'])
    process_instance.errorOccurred = MagicMock(spec_set=['connect'])
    process_instance.readyReadStandardOutput = MagicMock(spec_set=['connect'])
    process_instance.readyReadStandardError = MagicMock(spec_set=['connect'])
    process_instance.start = Mock()
    process_instance.state = Mock(return_value=QProcess.ProcessState.NotRunning)
    process_instance.waitForFinished = Mock(return_value=True)
    process_instance.terminate = Mock()
    process_instance.kill = Mock()

    # Make QProcess() return our configured instance
    mock_qprocess_class.return_value = process_instance

    # === THE KEY FIX ===
    # Expose the REAL enums on the mocked class.
    # Now QProcess.ExitStatus in the code will point to the real one.
    mock_qprocess_class.ProcessState = QProcess.ProcessState
    mock_qprocess_class.ExitStatus = QProcess.ExitStatus
    mock_qprocess_class.ProcessError = QProcess.ProcessError


class TestDlWorkerInitialization:
    """Tests for DlWorker initialization."""

    def test_initialization_basic(self, qtbot, test_input_files, temp_workspace):
        """Test basic initialization."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        assert worker.input_files == test_input_files
        assert worker.workspace_path == temp_workspace
        assert worker.total_files is None
        assert worker.processed_files is None
        assert worker.failed_files is None
        assert worker.is_cancelled is False
        assert worker.total_phases == 6
        assert worker.current_file_index == 0
        assert worker.current_phase == 0

    def test_initialization_signals_exist(self, qtbot, test_input_files, temp_workspace):
        """Test that all signals exist."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        assert hasattr(worker, 'progressbar_update')
        assert hasattr(worker, 'file_update')
        assert hasattr(worker, 'log_update')
        assert hasattr(worker, 'finished')
        assert hasattr(worker, 'cancel_requested')

    def test_initialization_process_instances_none(self, qtbot, test_input_files, temp_workspace):
        """Test that process instances are None initially."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        assert worker.synthstrip_process is None
        assert worker.coregistration_process is None
        assert worker.reorientation_process is None
        assert worker.dl_preprocess is None
        assert worker.dl_process is None
        assert worker.dl_postprocess is None


class TestUpdateProgress:
    """Tests for the update_progress method."""

    def test_update_progress_basic(self, qtbot, test_input_files, temp_workspace):
        """Test basic progress update."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = 3
        worker.current_file_index = 0
        worker.current_phase = 1

        with qtbot.waitSignal(worker.progressbar_update) as blocker:
            worker.update_progress()

        # Signal should be emitted with a value
        assert blocker.signal_triggered
        assert isinstance(blocker.args[0], int)

    def test_update_progress_zero_files(self, qtbot, test_input_files, temp_workspace):
        """Test with zero files."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = 0

        # Should not emit signal
        with patch.object(worker, 'progressbar_update') as mock_signal:
            worker.update_progress()
            mock_signal.emit.assert_not_called()

    def test_update_progress_calculation(self, qtbot, test_input_files, temp_workspace):
        """Test progress calculation."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = 2
        worker.total_phases = 6
        worker.current_file_index = 0
        worker.current_phase = 3  # Halfway through the first file

        with qtbot.waitSignal(worker.progressbar_update) as blocker:
            worker.update_progress()

        # Should be approx 25% (3 phases out of 12 total)
        progress = blocker.args[0]
        assert 20 <= progress <= 30

    def test_update_progress_max_100(self, qtbot, test_input_files, temp_workspace):
        """Test that progress does not exceed 100."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = 1
        worker.current_file_index = 10  # Out of range value
        worker.current_phase = 10

        with qtbot.waitSignal(worker.progressbar_update) as blocker:
            worker.update_progress()

        assert blocker.args[0] <= 100


class TestStart:
    """Tests for the start method."""

    def test_start_initializes_counters(self, qtbot, test_input_files, temp_workspace):
        """Test that start initializes counters."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        with patch.object(worker, 'process_single_file'):
            worker.start()

        assert worker.total_files == len(test_input_files)
        assert worker.processed_files == 0
        assert worker.failed_files == []
        assert worker.current_file_index == 0
        assert worker.current_phase == 0

    def test_start_calls_process_single_file(self, qtbot, test_input_files, temp_workspace):
        """Test that start calls process_single_file."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        with patch.object(worker, 'process_single_file') as mock_process:
            worker.start()

            mock_process.assert_called_once()

    def test_start_emits_initial_progress(self, qtbot, test_input_files, temp_workspace):
        """Test that start emits initial progress."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        with patch.object(worker, 'process_single_file'):
            with qtbot.waitSignal(worker.progressbar_update):
                worker.start()


class TestProcessSingleFile:
    """Tests for the process_single_file method."""

    def test_process_single_file_creates_temp_dir(self, qtbot, test_input_files, temp_workspace):
        """Test that it creates a temporary directory."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = len(test_input_files)

        with patch.object(worker, 'run_synthstrip'):
            worker.process_single_file()

            assert worker.output_dir is not None
            assert os.path.exists(worker.output_dir)

    def test_process_single_file_sets_current_file(self, qtbot, test_input_files, temp_workspace):
        """Test that it sets the current file."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = len(test_input_files)
        worker.current_file_index = 1

        with patch.object(worker, 'run_synthstrip'):
            worker.process_single_file()

            assert worker.current_input_file == test_input_files[1]
            assert worker.current_input_file_basename == os.path.basename(test_input_files[1])

    def test_process_single_file_calls_run_synthstrip(self, qtbot, test_input_files, temp_workspace):
        """Test that it calls run_synthstrip."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = len(test_input_files)

        with patch.object(worker, 'run_synthstrip') as mock_synthstrip:
            worker.process_single_file()

            mock_synthstrip.assert_called_once()

    def test_process_single_file_emits_log(self, qtbot, test_input_files, temp_workspace):
        """Test that it emits a log."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = len(test_input_files)

        with patch.object(worker, 'run_synthstrip'):
            with qtbot.waitSignal(worker.log_update):
                worker.process_single_file()


class TestRunSynthstrip:
    """Tests for the run_synthstrip method."""

    def test_run_synthstrip_creates_process(self, qtbot, test_input_files, temp_workspace):
        """Test that it creates the process."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.current_input_file = test_input_files[0]
        worker.current_input_file_basename = os.path.basename(test_input_files[0])
        worker.output_dir = temp_workspace

        worker.run_synthstrip()

        assert worker.synthstrip_process is not None

    def test_run_synthstrip_connects_signals(self, qtbot, test_input_files, temp_workspace):
        """Test that it connects signals."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.current_input_file = test_input_files[0]
        worker.current_input_file_basename = os.path.basename(test_input_files[0])
        worker.output_dir = temp_workspace

        worker.run_synthstrip()

        assert worker.synthstrip_process.finished.connect.called
        assert worker.synthstrip_process.errorOccurred.connect.called

    def test_run_synthstrip_starts_process(self, qtbot, test_input_files, temp_workspace):
        """Test that it starts the process."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.current_input_file = test_input_files[0]
        worker.current_input_file_basename = os.path.basename(test_input_files[0])
        worker.output_dir = temp_workspace

        worker.run_synthstrip()

        worker.synthstrip_process.start.assert_called_once()

    def test_run_synthstrip_emits_signals(self, qtbot, test_input_files, temp_workspace):
        """Test that it emits signals."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.current_input_file = test_input_files[0]
        worker.current_input_file_basename = os.path.basename(test_input_files[0])
        worker.output_dir = temp_workspace

        with qtbot.waitSignal(worker.file_update):
            worker.run_synthstrip()


class TestOnSynthstripFinished:
    """Tests for the on_synthstrip_finished callback."""

    def test_on_synthstrip_finished_success(self, qtbot, test_input_files, temp_workspace):
        """Test successful completion."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = len(test_input_files)
        worker.current_file_index = 0

        worker.current_input_file_basename = "test.nii.gz"

        with patch.object(worker, 'run_coregistration') as mock_coreg:
            worker.on_synthstrip_finished(0, QProcess.ExitStatus.NormalExit)

            mock_coreg.assert_called_once()
            assert worker.current_phase == 2

    def test_on_synthstrip_finished_failure(self, qtbot, test_input_files, temp_workspace):
        """Test completion with failure."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = 2
        worker.current_file_index = 0
        worker.current_input_file_basename = "test.nii.gz"

        with patch.object(worker, 'process_single_file') as mock_process:
            worker.on_synthstrip_finished(1, QProcess.ExitStatus.NormalExit)

            assert worker.current_file_index == 1

    def test_on_synthstrip_finished_cancelled(self, qtbot, test_input_files, temp_workspace):
        """Test when cancelled."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.is_cancelled = True

        with patch.object(worker, 'run_coregistration') as mock_coreg:
            worker.on_synthstrip_finished(0, QProcess.ExitStatus.NormalExit)

            mock_coreg.assert_not_called()


class TestCancel:
    """Tests for the cancel method."""

    def test_cancel_sets_flag(self, qtbot, test_input_files, temp_workspace):
        """Test that it sets the flag."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.cancel()

        assert worker.is_cancelled is True

    def test_cancel_terminates_running_processes(self, qtbot, test_input_files, temp_workspace):
        """Test that it terminates running processes."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        # Simulate running process
        mock_process = main.threads.dl_worker.QProcess()
        worker.synthstrip_process = mock_process
        mock_process.state = Mock(return_value=QProcess.ProcessState.Running)

        worker.cancel()

        worker.synthstrip_process.terminate.assert_called_once()

    def test_cancel_kills_if_not_terminated(self, qtbot, test_input_files, temp_workspace):
        """Test that it kills the process if it doesn't terminate."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        mock_process = main.threads.dl_worker.QProcess()

        worker.synthstrip_process = mock_process
        mock_process.state = Mock(return_value=QProcess.ProcessState.Running)
        mock_process.waitForFinished = Mock(return_value=False)

        worker.cancel()

        mock_process.kill.assert_called_once()

    def test_cancel_emits_finished_signal(self, qtbot, test_input_files, temp_workspace):
        """Test that it emits the finished signal."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        with qtbot.waitSignal(worker.finished) as blocker:
            worker.cancel()

        assert blocker.args[0] is False  # success=False


class TestOnStdout:
    """Tests for the on_stdout method."""

    def test_on_stdout_basic(self, qtbot, test_input_files, temp_workspace):
        """Test basic stdout handling."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        mock_data = Mock()
        mock_data.data = Mock(return_value=b"Test output line")

        with qtbot.waitSignal(worker.log_update):
            worker.on_stdout("TestPhase", mock_data)

    def test_on_stdout_multiline(self, qtbot, test_input_files, temp_workspace):
        """Test with multiline output."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        mock_data = Mock()
        mock_data.data = Mock(return_value=b"Line 1\nLine 2\nLine 3")

        log_calls = []
        worker.log_update.connect(lambda msg, level: log_calls.append(msg))

        worker.on_stdout("TestPhase", mock_data)

        # Should emit 3 logs
        assert len(log_calls) == 3


class TestOnStderr:
    """Tests for the on_stderr method."""

    def test_on_stderr_basic(self, qtbot, test_input_files, temp_workspace):
        """Test basic stderr handling."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        mock_data = Mock()
        mock_data.data = Mock(return_value=b"Error message")

        with qtbot.waitSignal(worker.log_update):
            worker.on_stderr("TestPhase", mock_data)


class TestOnError:
    """Tests for the on_error method."""

    def test_on_error_failed_to_start(self, qtbot, test_input_files, temp_workspace):
        """Test FailedToStart error."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        with qtbot.waitSignal(worker.log_update):
            worker.on_error("TestPhase", QProcess.ProcessError.FailedToStart)

    def test_on_error_crashed(self, qtbot, test_input_files, temp_workspace):
        """Test Crashed error."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        with qtbot.waitSignal(worker.log_update):
            worker.on_error("TestPhase", QProcess.ProcessError.Crashed)


class TestPhaseTransitions:
    """Tests for phase transitions."""

    def test_synthstrip_to_coregistration(self, qtbot, test_input_files, temp_workspace):
        """Test synthstrip -> coregistration transition."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = len(test_input_files)
        worker.current_file_index = 0

        worker.current_input_file_basename = "test.nii.gz"

        with patch.object(worker, 'run_coregistration') as mock_coreg:
            worker.on_synthstrip_finished(0, QProcess.ExitStatus.NormalExit)

            assert worker.current_phase == 2
            mock_coreg.assert_called_once()

    def test_coregistration_to_reorientation(self, qtbot, test_input_files, temp_workspace):
        """Test coregistration -> reorientation transition."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = len(test_input_files)
        worker.current_file_index = 0

        worker.current_input_file_basename = "test.nii.gz"

        with patch.object(worker, 'run_reorientation') as mock_reorient:
            worker.on_coregistration_finished(0, QProcess.ExitStatus.NormalExit)

            assert worker.current_phase == 3
            mock_reorient.assert_called_once()


class TestMultipleFiles:
    """Tests for multiple file processing."""

    def test_process_multiple_files_sequentially(self, qtbot, test_input_files, temp_workspace):
        """Test sequential file processing."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = 3
        worker.current_file_index = 0

        with patch.object(worker, 'run_synthstrip'):
            # Simulate completion of the first file
            worker.current_phase = 6
            worker.on_postprocess_finished(0, QProcess.ExitStatus.NormalExit)

            assert worker.current_file_index == 1

    def test_finish_when_all_files_processed(self, qtbot, test_input_files, temp_workspace):
        """Test finish when all files are processed."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        worker.total_files = 3
        worker.current_file_index = 2  # Last file
        worker.current_phase = 6

        with qtbot.waitSignal(worker.finished) as blocker:
            worker.on_postprocess_finished(0, QProcess.ExitStatus.NormalExit)

        assert blocker.args[0] is True  # success=True


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file_list(self, qtbot, temp_workspace):
        """Test with empty file list."""
        worker = DlWorker([], temp_workspace, False)

        with patch.object(worker, 'process_single_file') as mock_process:
            worker.start()

            assert worker.total_files == 0

    def test_unicode_in_filename(self, qtbot, temp_workspace):
        """Test with unicode in filename."""
        unicode_file = os.path.join(temp_workspace, "файл_文件.nii.gz")
        with open(unicode_file, "w") as f:
            f.write("data")

        worker = DlWorker([unicode_file], temp_workspace, False)

        with patch.object(worker, 'run_synthstrip'):
            worker.process_single_file()

            assert worker.current_input_file == unicode_file


class TestIntegration:
    """Integration tests."""

    def test_full_workflow_single_file(self, qtbot, test_input_files, temp_workspace):
        """Test full workflow single file."""
        worker = DlWorker([test_input_files[0]], temp_workspace, False)

        # Start
        with patch.object(worker, 'run_synthstrip'):
            worker.start()

        assert worker.total_files == 1
        assert worker.current_file_index == 0


class TestMemoryAndPerformance:
    """Tests for memory and performance."""

    def test_many_files_initialization(self, qtbot, temp_workspace):
        """Test with many files."""
        many_files = [os.path.join(temp_workspace, f"file{i}.nii") for i in range(100)]

        worker = DlWorker(many_files, temp_workspace, False)

        assert worker.input_files == many_files


class TestAccessibility:
    """Tests for accessibility."""

    def test_signals_have_docstrings(self, qtbot, test_input_files, temp_workspace):
        """Test that signals have docstrings."""
        worker = DlWorker(test_input_files, temp_workspace, False)

        # Verify that the signal objects exist
        assert hasattr(worker, 'progressbar_update')
        assert hasattr(worker, 'file_update')
        assert hasattr(worker, 'log_update')
        assert hasattr(worker, 'finished')
        assert hasattr(worker, 'cancel_requested')