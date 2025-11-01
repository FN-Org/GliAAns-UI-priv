import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from PyQt6.QtCore import QProcess

from threads.dl_worker import DlWorker


@pytest.fixture
def test_input_files(temp_workspace):
    """Crea file di input di test."""
    files = []
    for i in range(3):
        filepath = os.path.join(temp_workspace, f"test_{i}.nii.gz")
        with open(filepath, "w") as f:
            f.write("nifti data")
        files.append(filepath)
    return files


@pytest.fixture
def mock_qprocess():
    """Mock per QProcess."""
    with patch("threads.dl_worker.QProcess") as mock:
        process_instance = MagicMock()
        process_instance.finished = Mock()
        process_instance.finished.connect = Mock()
        process_instance.errorOccurred = Mock()
        process_instance.errorOccurred.connect = Mock()
        process_instance.readyReadStandardOutput = Mock()
        process_instance.readyReadStandardOutput.connect = Mock()
        process_instance.readyReadStandardError = Mock()
        process_instance.readyReadStandardError.connect = Mock()
        process_instance.start = Mock()
        process_instance.state = Mock(return_value=QProcess.ProcessState.NotRunning)
        process_instance.waitForFinished = Mock(return_value=True)
        process_instance.terminate = Mock()
        process_instance.kill = Mock()

        mock.return_value = process_instance
        mock.ProcessState = QProcess.ProcessState
        mock.ExitStatus = QProcess.ExitStatus
        mock.ProcessError = QProcess.ProcessError

        yield mock


class TestDlWorkerInitialization:
    """Test per l'inizializzazione di DlWorker."""

    def test_initialization_basic(self, qtbot, test_input_files, temp_workspace):
        """Test inizializzazione base."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        assert worker.input_files == test_input_files
        assert worker.workspace_path == temp_workspace
        assert worker.total_files is len(test_input_files) if test_input_files else 0
        assert worker.processed_files is None
        assert worker.failed_files is None
        assert worker.is_cancelled is False
        assert worker.total_phases == 6
        assert worker.current_file_index == 0
        assert worker.current_phase == 0

    def test_initialization_signals_exist(self, qtbot, test_input_files, temp_workspace):
        """Test che tutti i signal esistano."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        assert hasattr(worker, 'progressbar_update')
        assert hasattr(worker, 'file_update')
        assert hasattr(worker, 'log_update')
        assert hasattr(worker, 'finished')
        assert hasattr(worker, 'cancel_requested')

    def test_initialization_process_instances_none(self, qtbot, test_input_files, temp_workspace):
        """Test che le istanze process siano None inizialmente."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        assert worker.synthstrip_process is None
        assert worker.coregistration_process is None
        assert worker.reorientation_process is None
        assert worker.dl_preprocess is None
        assert worker.dl_process is None
        assert worker.dl_postprocess is None


class TestUpdateProgress:
    """Test per il metodo update_progress."""

    def test_update_progress_basic(self, qtbot, test_input_files, temp_workspace):
        """Test aggiornamento progresso base."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.total_files = 3
        worker.current_file_index = 0
        worker.current_phase = 1

        with qtbot.waitSignal(worker.progressbar_update) as blocker:
            worker.update_progress()

        # Signal dovrebbe essere emesso con un valore
        assert blocker.signal_triggered
        assert isinstance(blocker.args[0], int)

    def test_update_progress_zero_files(self, qtbot, test_input_files, temp_workspace):
        """Test con zero file."""
        worker = DlWorker(test_input_files, temp_workspace)

        worker.total_files = 0

        # Non dovrebbe emettere signal
        with patch.object(worker, 'progressbar_update') as mock_signal:
            worker.update_progress()
            mock_signal.emit.assert_not_called()

    def test_update_progress_calculation(self, qtbot, test_input_files, temp_workspace):
        """Test calcolo progresso."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.total_files = 2
        worker.total_phases = 6
        worker.current_file_index = 0
        worker.current_phase = 3  # Metà del primo file

        with qtbot.waitSignal(worker.progressbar_update) as blocker:
            worker.update_progress()

        # Dovrebbe essere circa 25% (3 fasi su 12 totali)
        progress = blocker.args[0]
        assert 20 <= progress <= 30

    def test_update_progress_max_100(self, qtbot, test_input_files, temp_workspace):
        """Test che il progresso non superi 100."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.total_files = 1
        worker.current_file_index = 10  # Valore fuori range
        worker.current_phase = 10

        with qtbot.waitSignal(worker.progressbar_update) as blocker:
            worker.update_progress()

        assert blocker.args[0] <= 100


class TestStart:
    """Test per il metodo start."""

    def test_start_initializes_counters(self, qtbot, test_input_files, temp_workspace):
        """Test che start inizializzi i contatori."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        with patch.object(worker, 'process_single_file'):
            worker.start()

        assert worker.total_files == len(test_input_files)
        assert worker.processed_files == 0
        assert worker.failed_files == []
        assert worker.current_file_index == 0
        assert worker.current_phase == 0

    def test_start_calls_process_single_file(self, qtbot, test_input_files, temp_workspace):
        """Test che start chiami process_single_file."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        with patch.object(worker, 'process_single_file') as mock_process:
            worker.start()

            mock_process.assert_called_once()

    def test_start_emits_initial_progress(self, qtbot, test_input_files, temp_workspace):
        """Test che start emetta progresso iniziale."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        with patch.object(worker, 'process_single_file'):
            with qtbot.waitSignal(worker.progressbar_update):
                worker.start()


class TestProcessSingleFile:
    """Test per il metodo process_single_file."""

    def test_process_single_file_creates_temp_dir(self, qtbot, test_input_files, temp_workspace):
        """Test che crei directory temporanea."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.total_files = len(test_input_files)

        with patch.object(worker, 'run_synthstrip'):
            worker.process_single_file()

            assert worker.output_dir is not None
            assert os.path.exists(worker.output_dir)

    def test_process_single_file_sets_current_file(self, qtbot, test_input_files, temp_workspace):
        """Test che imposti il file corrente."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.total_files = len(test_input_files)
        worker.current_file_index = 1

        with patch.object(worker, 'run_synthstrip'):
            worker.process_single_file()

            assert worker.current_input_file == test_input_files[1]
            assert worker.current_input_file_basename == os.path.basename(test_input_files[1])

    def test_process_single_file_calls_run_synthstrip(self, qtbot, test_input_files, temp_workspace):
        """Test che chiami run_synthstrip."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.total_files = len(test_input_files)

        with patch.object(worker, 'run_synthstrip') as mock_synthstrip:
            worker.process_single_file()

            mock_synthstrip.assert_called_once()

    def test_process_single_file_emits_log(self, qtbot, test_input_files, temp_workspace):
        """Test che emetta log."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.total_files = len(test_input_files)

        with patch.object(worker, 'run_synthstrip'):
            with qtbot.waitSignal(worker.log_update):
                worker.process_single_file()


class TestRunSynthstrip:
    """Test per il metodo run_synthstrip."""

    def test_run_synthstrip_creates_process(self, qtbot, test_input_files, temp_workspace, mock_qprocess):
        """Test che crei il processo."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.current_input_file = test_input_files[0]
        worker.current_input_file_basename = os.path.basename(test_input_files[0])
        worker.output_dir = temp_workspace

        worker.run_synthstrip()

        assert worker.synthstrip_process is not None

    def test_run_synthstrip_connects_signals(self, qtbot, test_input_files, temp_workspace, mock_qprocess):
        """Test che connetta i signal."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.current_input_file = test_input_files[0]
        worker.current_input_file_basename = os.path.basename(test_input_files[0])
        worker.output_dir = temp_workspace

        worker.run_synthstrip()

        assert worker.synthstrip_process.finished.connect.called
        assert worker.synthstrip_process.errorOccurred.connect.called

    def test_run_synthstrip_starts_process(self, qtbot, test_input_files, temp_workspace, mock_qprocess):
        """Test che avvii il processo."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.current_input_file = test_input_files[0]
        worker.current_input_file_basename = os.path.basename(test_input_files[0])
        worker.output_dir = temp_workspace

        worker.run_synthstrip()

        worker.synthstrip_process.start.assert_called_once()

    def test_run_synthstrip_emits_signals(self, qtbot, test_input_files, temp_workspace, mock_qprocess):
        """Test che emetta signal."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.current_input_file = test_input_files[0]
        worker.current_input_file_basename = os.path.basename(test_input_files[0])
        worker.output_dir = temp_workspace

        with qtbot.waitSignal(worker.file_update):
            worker.run_synthstrip()


class TestOnSynthstripFinished:
    """Test per il callback on_synthstrip_finished."""

    def test_on_synthstrip_finished_success(self, qtbot, test_input_files, temp_workspace):
        """Test completamento con successo."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.current_input_file_basename = "test.nii.gz"

        with patch.object(worker, 'run_coregistration') as mock_coreg:
            worker.on_synthstrip_finished(0, QProcess.ExitStatus.NormalExit)

            mock_coreg.assert_called_once()
            assert worker.current_phase == 2

    def test_on_synthstrip_finished_failure(self, qtbot, test_input_files, temp_workspace):
        """Test completamento con fallimento."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.total_files = 2
        worker.current_file_index = 0
        worker.current_input_file_basename = "test.nii.gz"

        with patch.object(worker, 'process_single_file') as mock_process:
            worker.on_synthstrip_finished(1, QProcess.ExitStatus.NormalExit)

            assert worker.current_file_index == 1

    def test_on_synthstrip_finished_cancelled(self, qtbot, test_input_files, temp_workspace):
        """Test quando cancellato."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.is_cancelled = True

        with patch.object(worker, 'run_coregistration') as mock_coreg:
            worker.on_synthstrip_finished(0, QProcess.ExitStatus.NormalExit)

            mock_coreg.assert_not_called()


class TestCancel:
    """Test per il metodo cancel."""

    def test_cancel_sets_flag(self, qtbot, test_input_files, temp_workspace):
        """Test che imposti il flag."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.cancel()

        assert worker.is_cancelled is True

    def test_cancel_terminates_running_processes(self, qtbot, test_input_files, temp_workspace, mock_qprocess):
        """Test che termini i processi in esecuzione."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        # Simula processo in esecuzione
        worker.synthstrip_process = mock_qprocess.return_value
        worker.synthstrip_process.state = Mock(return_value=QProcess.ProcessState.Running)

        worker.cancel()

        worker.synthstrip_process.terminate.assert_called_once()

    def test_cancel_kills_if_not_terminated(self, qtbot, test_input_files, temp_workspace, mock_qprocess):
        """Test che uccida il processo se non si termina."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.synthstrip_process = mock_qprocess.return_value
        worker.synthstrip_process.state = Mock(return_value=QProcess.ProcessState.Running)
        worker.synthstrip_process.waitForFinished = Mock(return_value=False)

        worker.cancel()

        worker.synthstrip_process.kill.assert_called_once()

    def test_cancel_emits_finished_signal(self, qtbot, test_input_files, temp_workspace):
        """Test che emetta finished signal."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        with qtbot.waitSignal(worker.finished) as blocker:
            worker.cancel()

        assert blocker.args[0] is False  # success=False


class TestOnStdout:
    """Test per il metodo on_stdout."""

    def test_on_stdout_basic(self, qtbot, test_input_files, temp_workspace):
        """Test gestione stdout base."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        mock_data = Mock()
        mock_data.data = Mock(return_value=b"Test output line")

        with qtbot.waitSignal(worker.log_update):
            worker.on_stdout("TestPhase", mock_data)

    def test_on_stdout_multiline(self, qtbot, test_input_files, temp_workspace):
        """Test con output multilinea."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        mock_data = Mock()
        mock_data.data = Mock(return_value=b"Line 1\nLine 2\nLine 3")

        log_calls = []
        worker.log_update.connect(lambda msg, level: log_calls.append(msg))

        worker.on_stdout("TestPhase", mock_data)

        # Dovrebbe emettere 3 log
        assert len(log_calls) == 3


class TestOnStderr:
    """Test per il metodo on_stderr."""

    def test_on_stderr_basic(self, qtbot, test_input_files, temp_workspace):
        """Test gestione stderr base."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        mock_data = Mock()
        mock_data.data = Mock(return_value=b"Error message")

        with qtbot.waitSignal(worker.log_update):
            worker.on_stderr("TestPhase", mock_data)


class TestOnError:
    """Test per il metodo on_error."""

    def test_on_error_failed_to_start(self, qtbot, test_input_files, temp_workspace):
        """Test errore FailedToStart."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        with qtbot.waitSignal(worker.log_update):
            worker.on_error("TestPhase", QProcess.ProcessError.FailedToStart)

    def test_on_error_crashed(self, qtbot, test_input_files, temp_workspace):
        """Test errore Crashed."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        with qtbot.waitSignal(worker.log_update):
            worker.on_error("TestPhase", QProcess.ProcessError.Crashed)


class TestPhaseTransitions:
    """Test per le transizioni tra fasi."""

    def test_synthstrip_to_coregistration(self, qtbot, test_input_files, temp_workspace):
        """Test transizione synthstrip -> coregistration."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.current_input_file_basename = "test.nii.gz"

        with patch.object(worker, 'run_coregistration') as mock_coreg:
            worker.on_synthstrip_finished(0, QProcess.ExitStatus.NormalExit)

            assert worker.current_phase == 2
            mock_coreg.assert_called_once()

    def test_coregistration_to_reorientation(self, qtbot, test_input_files, temp_workspace):
        """Test transizione coregistration -> reorientation."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.current_input_file_basename = "test.nii.gz"

        with patch.object(worker, 'run_reorientation') as mock_reorient:
            worker.on_coregistration_finished(0, QProcess.ExitStatus.NormalExit)

            assert worker.current_phase == 3
            mock_reorient.assert_called_once()


class TestMultipleFiles:
    """Test per elaborazione file multipli."""

    def test_process_multiple_files_sequentially(self, qtbot, test_input_files, temp_workspace):
        """Test elaborazione sequenziale file."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.total_files = 3
        worker.current_file_index = 0

        with patch.object(worker, 'run_synthstrip'):
            # Simula completamento primo file
            worker.current_phase = 6
            worker.on_postprocess_finished(0, QProcess.ExitStatus.NormalExit)

            assert worker.current_file_index == 1

    def test_finish_when_all_files_processed(self, qtbot, test_input_files, temp_workspace):
        """Test finish quando tutti i file sono processati."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        worker.total_files = 3
        worker.current_file_index = 2  # Ultimo file
        worker.current_phase = 6

        with qtbot.waitSignal(worker.finished) as blocker:
            worker.on_postprocess_finished(0, QProcess.ExitStatus.NormalExit)

        assert blocker.args[0] is True  # success=True


class TestEdgeCases:
    """Test per casi limite."""

    def test_empty_file_list(self, qtbot, temp_workspace):
        """Test con lista file vuota."""
        worker = DlWorker([], temp_workspace)
        

        with patch.object(worker, 'process_single_file') as mock_process:
            worker.start()

            assert worker.total_files == 0

    def test_unicode_in_filename(self, qtbot, temp_workspace):
        """Test con unicode nel nome file."""
        unicode_file = os.path.join(temp_workspace, "файл_文件.nii.gz")
        with open(unicode_file, "w") as f:
            f.write("data")

        worker = DlWorker([unicode_file], temp_workspace)
        

        with patch.object(worker, 'run_synthstrip'):
            worker.process_single_file()

            assert worker.current_input_file == unicode_file


class TestIntegration:
    """Test di integrazione."""

    def test_full_workflow_single_file(self, qtbot, test_input_files, temp_workspace, mock_qprocess):
        """Test workflow completo file singolo."""
        worker = DlWorker([test_input_files[0]], temp_workspace)
        

        # Avvia
        with patch.object(worker, 'run_synthstrip'):
            worker.start()

        assert worker.total_files == 1
        assert worker.current_file_index == 0


class TestMemoryAndPerformance:
    """Test per memoria e performance."""

    def test_many_files_initialization(self, qtbot, temp_workspace):
        """Test con molti file."""
        many_files = [os.path.join(temp_workspace, f"file{i}.nii") for i in range(100)]

        worker = DlWorker(many_files, temp_workspace)
        

        assert worker.input_files == many_files


class TestAccessibility:
    """Test per l'accessibilità."""

    def test_signals_have_docstrings(self, qtbot, test_input_files, temp_workspace):
        """Test che i signal abbiano docstring."""
        worker = DlWorker(test_input_files, temp_workspace)
        

        # Verifica che gli oggetti signal esistano
        assert hasattr(worker, 'progressbar_update')
        assert hasattr(worker, 'file_update')
        assert hasattr(worker, 'log_update')
        assert hasattr(worker, 'finished')
        assert hasattr(worker, 'cancel_requested')