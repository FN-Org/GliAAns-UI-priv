"""
test_skull_strip_thread.py - Test Suite per SkullStripThread

Questa suite testa tutte le funzionalità del thread di skull-stripping:
- Esecuzione FSL BET e HD-BET
- Batch processing di file multipli
- Progress tracking e cancellazione
- Generazione metadata JSON BIDS
- Gestione errori e edge cases
"""

import os
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, call
import pytest
from PyQt6.QtCore import QProcess

from threads.skull_strip_thread import SkullStripThread


class TestSkullStripThreadInitialization:
    """Test per l'inizializzazione di SkullStripThread"""

    def test_init_with_bet(self, temp_workspace):
        """Test inizializzazione con FSL BET"""
        files = [os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii.gz")]
        parameters = {'f_val': 0.5, 'opt_m': True}

        thread = SkullStripThread(
            files=files,
            workspace_path=temp_workspace,
            parameters=parameters,
            has_cuda=False,
            has_bet=True
        )

        assert thread.files == files
        assert thread.workspace_path == temp_workspace
        assert thread.parameters == parameters
        assert thread.has_cuda is False
        assert thread.has_bet is True
        assert thread.is_cancelled is False
        assert thread.success_count == 0
        assert thread.failed_files == []

    def test_init_with_hdbet(self, temp_workspace):
        """Test inizializzazione con HD-BET"""
        files = [os.path.join(temp_workspace, "test.nii")]
        parameters = {}

        thread = SkullStripThread(
            files=files,
            workspace_path=temp_workspace,
            parameters=parameters,
            has_cuda=True,
            has_bet=False
        )

        assert thread.has_cuda is True
        assert thread.has_bet is False

    def test_signals_exist(self, temp_workspace):
        """Verifica che i signal siano definiti correttamente"""
        thread = SkullStripThread([], temp_workspace, {}, False, True)

        assert hasattr(thread, 'progress_updated')
        assert hasattr(thread, 'progress_value_updated')
        assert hasattr(thread, 'file_started')
        assert hasattr(thread, 'file_completed')
        assert hasattr(thread, 'all_completed')


class TestSkullStripThreadCancellation:
    """Test per la cancellazione del thread"""

    def test_cancel_flag_set(self, temp_workspace):
        """Test che il flag di cancellazione venga impostato"""
        thread = SkullStripThread([], temp_workspace, {}, False, True)

        assert thread.is_cancelled is False
        thread.cancel()
        assert thread.is_cancelled is True

    def test_cancel_terminates_process(self, temp_workspace):
        """Test terminazione processo durante cancellazione"""
        thread = SkullStripThread([], temp_workspace, {}, False, True)

        # Mock processo in esecuzione
        mock_process = Mock(spec=QProcess)
        thread.process = mock_process

        thread.cancel()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_cancel_no_process(self, temp_workspace):
        """Test cancellazione senza processo attivo"""
        thread = SkullStripThread([], temp_workspace, {}, False, True)

        # Non dovrebbe sollevare eccezioni
        thread.cancel()
        assert thread.is_cancelled is True

    def test_cancel_process_error_handling(self, temp_workspace):
        """Test gestione errore durante cancellazione processo"""
        thread = SkullStripThread([], temp_workspace, {}, False, True)

        mock_process = Mock()
        mock_process.terminate.side_effect = RuntimeError("Process error")
        thread.process = mock_process

        # Non dovrebbe propagare l'eccezione
        thread.cancel()
        assert thread.is_cancelled is True


class TestBETCommandBuilding:
    """Test per la costruzione comandi FSL BET"""

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_bet_basic_command(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test comando BET di base"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        # Mock processo
        mock_process_instance = Mock()
        mock_process_instance.waitForFinished.return_value = True
        mock_process_instance.exitCode.return_value = 0
        mock_process_instance.readAllStandardError.return_value = b''
        mock_process_instance.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process_instance

        # Crea file di input
        input_file = os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii.gz")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("nifti data")

        parameters = {'f_val': 0.5}
        thread = SkullStripThread([input_file], temp_workspace, parameters, False, True)

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        # Verifica chiamata processo
        mock_process_instance.start.assert_called_once()
        call_args = mock_process_instance.start.call_args[0]

        assert call_args[0] == "bet"
        assert input_file in call_args[1]
        assert "-f" in call_args[1]
        assert "0.5" in call_args[1]

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_bet_with_options(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test comando BET con opzioni avanzate"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-02", "anat", "brain.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        parameters = {
            'f_val': 0.3,
            'opt_m': True,
            'opt_t': True,
            'opt_s': False,
            'opt_o': True
        }

        thread = SkullStripThread([input_file], temp_workspace, parameters, False, True)

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]
        cmd = call_args[1]

        # Verifica opzioni presenti
        assert "-m" in cmd  # opt_m
        assert "-t" in cmd  # opt_t
        assert "-o" in cmd  # opt_o
        assert "-s" not in cmd  # opt_s è False

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_bet_with_center_coordinates(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test comando BET con coordinate centro"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-03", "anat", "scan.nii.gz")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        parameters = {
            'f_val': 0.5,
            'c_x': 128,
            'c_y': 128,
            'c_z': 64
        }

        thread = SkullStripThread([input_file], temp_workspace, parameters, False, True)

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]
        cmd = call_args[1]

        # Verifica coordinate
        assert "-c" in cmd
        assert "128" in cmd or "64" in cmd

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_bet_brain_extracted_option(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test opzione -n per brain extraction"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-04", "anat", "T1.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        parameters = {
            'f_val': 0.5,
            'opt_brain_extracted': False  # Disabilita estrazione mask
        }

        thread = SkullStripThread([input_file], temp_workspace, parameters, False, True)

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]
        cmd = call_args[1]

        assert "-n" in cmd


class TestHDBETCommandBuilding:
    """Test per la costruzione comandi HD-BET"""

    @patch('threads.skull_strip_thread.get_bin_path')
    @patch('threads.skull_strip_thread.QProcess')
    def test_hdbet_basic_command(self, mock_qprocess, mock_get_bin, temp_workspace):
        """Test comando HD-BET di base"""
        mock_get_bin.return_value = "/usr/bin/hd-bet"

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-01", "anat", "brain.nii.gz")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {}, True, False)

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]

        assert call_args[0] == "/usr/bin/hd-bet"
        assert "-i" in call_args[1]
        assert "-o" in call_args[1]

    @patch('threads.skull_strip_thread.get_bin_path')
    @patch('threads.skull_strip_thread.QProcess')
    def test_hdbet_cpu_mode(self, mock_qprocess, mock_get_bin, temp_workspace):
        """Test HD-BET in modalità CPU (senza CUDA)"""
        mock_get_bin.return_value = "/usr/bin/hd-bet"

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-02", "anat", "T1w.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        # has_cuda = False
        thread = SkullStripThread([input_file], temp_workspace, {}, False, False)

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]
        cmd = call_args[1]

        # Verifica opzioni CPU
        assert "-device" in cmd
        assert "cpu" in cmd
        assert "--disable_tta" in cmd

    @patch('threads.skull_strip_thread.get_bin_path')
    @patch('threads.skull_strip_thread.QProcess')
    def test_hdbet_cuda_mode(self, mock_qprocess, mock_get_bin, temp_workspace):
        """Test HD-BET con CUDA"""
        mock_get_bin.return_value = "/usr/bin/hd-bet"

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-03", "anat", "scan.nii.gz")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        # has_cuda = True
        thread = SkullStripThread([input_file], temp_workspace, {}, True, False)

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]
        cmd = call_args[1]

        # NON dovrebbe avere opzioni CPU
        assert "-device" not in cmd or "cpu" not in cmd


class TestOutputGeneration:
    """Test per la generazione output e metadata"""

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_output_directory_creation(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test creazione directory output"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-05", "anat", "brain.nii.gz")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        # Mock shutil.move per simulare file creato
        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped brain")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Verifica directory derivatives creata
        expected_dir = os.path.join(
            temp_workspace, 'derivatives', 'skullstrips', 'sub-05', 'anat'
        )
        assert os.path.exists(expected_dir)

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_json_metadata_creation_bet(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test creazione metadata JSON per BET"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-06", "anat", "T1w.nii.gz")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.4}, False, True)

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Verifica JSON creato
        json_file = os.path.join(
            temp_workspace, 'derivatives', 'skullstrips', 'sub-06', 'anat',
            'T1w_f04_brain.json'
        )

        assert os.path.exists(json_file)

        with open(json_file, 'r') as f:
            metadata = json.load(f)

        assert metadata["SkullStripped"] is True
        assert metadata["Description"] == "Skull-stripped brain image"
        assert "T1w.nii.gz" in metadata["Sources"]
        assert metadata["SkullStrippingMethod"] == "FSL BET"

    @patch('threads.skull_strip_thread.get_bin_path')
    @patch('threads.skull_strip_thread.QProcess')
    def test_json_metadata_creation_hdbet(self, mock_qprocess, mock_get_bin, temp_workspace):
        """Test creazione metadata JSON per HD-BET"""
        mock_get_bin.return_value = "/usr/bin/hd-bet"

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-07", "anat", "brain.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {}, True, False)

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        json_file = os.path.join(
            temp_workspace, 'derivatives', 'skullstrips', 'sub-07', 'anat',
            'brain_hd-bet_brain.json'
        )

        assert os.path.exists(json_file)

        with open(json_file, 'r') as f:
            metadata = json.load(f)

        assert metadata["SkullStrippingMethod"] == "HD-BET"

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_output_filename_format_bet(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test formato nome file output per BET"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-08", "anat", "T1w.nii.gz")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        # f_val = 0.7 -> f07
        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.7}, False, True)

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Verifica nome file contiene f07
        output_file = os.path.join(
            temp_workspace, 'derivatives', 'skullstrips', 'sub-08', 'anat',
            'T1w_f07_brain.nii.gz'
        )

        assert os.path.exists(output_file)


class TestBatchProcessing:
    """Test per il processing batch di file multipli"""

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_multiple_files_processing(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test processamento di file multipli"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        # Crea file multipli
        files = []
        for i in range(1, 4):
            file_path = os.path.join(temp_workspace, f"sub-0{i}", "anat", f"T1w_{i}.nii")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                f.write("data")
            files.append(file_path)

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, True)

        file_started_count = [0]
        file_completed_count = [0]

        thread.file_started.connect(lambda f: file_started_count.__setitem__(0, file_started_count[0] + 1))
        thread.file_completed.connect(lambda f, s, m: file_completed_count.__setitem__(0, file_completed_count[0] + 1))

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Verifica signal emessi per ogni file
        assert file_started_count[0] == 3
        assert file_completed_count[0] == 3
        assert thread.success_count == 3

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_progress_tracking_multiple_files(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test tracking progress con file multipli"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        files = []
        for i in range(5):
            file_path = os.path.join(temp_workspace, f"sub-{i:02d}", "anat", "brain.nii")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                f.write("data")
            files.append(file_path)

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, True)

        progress_values = []
        thread.progress_value_updated.connect(lambda val: progress_values.append(val))

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Verifica progress incrementale
        assert len(progress_values) == 5
        # Progress dovrebbe crescere
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i - 1]

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_all_completed_signal(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test signal all_completed al termine"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        files = []
        for i in range(3):
            file_path = os.path.join(temp_workspace, f"sub-{i:02d}", "anat", "scan.nii")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                f.write("data")
            files.append(file_path)

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, True)

        completed_results = []
        thread.all_completed.connect(lambda count, failed: completed_results.append((count, failed)))

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        assert len(completed_results) == 1
        success_count, failed_files = completed_results[0]
        assert success_count == 3
        assert len(failed_files) == 0


class TestErrorHandling:
    """Test per la gestione degli errori"""

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_process_failure_nonzero_exit(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test gestione errore processo con exit code non zero"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 1  # Exit code di errore
        mock_process.readAllStandardError.return_value = b'BET error: invalid parameters'
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-01", "anat", "broken.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        completed_files = []
        thread.file_completed.connect(lambda f, s, m: completed_files.append((f, s, m)))

        with patch('shutil.rmtree'):
            thread.run()

        # Verifica file segnato come fallito
        assert len(completed_files) == 1
        filename, success, message = completed_files[0]
        assert success is False
        assert "error" in message.lower() or "invalid" in message.lower()
        assert len(thread.failed_files) == 1

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_missing_subject_id(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test gestione file senza subject ID BIDS"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        # File senza struttura BIDS (no sub-XX)
        input_file = os.path.join(temp_workspace, "random_folder", "brain.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        completed_files = []
        thread.file_completed.connect(lambda f, s, m: completed_files.append((f, s, m)))

        thread.run()

        # Dovrebbe fallire per mancanza subject ID
        assert len(completed_files) == 1
        filename, success, message = completed_files[0]
        assert success is False
        assert "Impossibile estrarre" in message or "Cannot extract" in message
        assert len(thread.failed_files) == 1

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_exception_during_processing(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test gestione eccezione generica durante processing"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.start.side_effect = RuntimeError("Process start failed")
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-02", "anat", "test.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        completed_files = []
        thread.file_completed.connect(lambda f, s, m: completed_files.append((f, s, m)))

        with patch('shutil.rmtree'):
            thread.run()

        # Dovrebbe catturare l'eccezione
        assert len(completed_files) == 1
        filename, success, message = completed_files[0]
        assert success is False
        assert "failed" in message.lower() or "error" in message.lower()

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_partial_failure_multiple_files(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test con alcuni file che falliscono e altri che riescono"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        # Mock processo che alterna successo/fallimento
        call_count = [0]

        def get_mock_process():
            mock_process = Mock()
            mock_process.waitForFinished.return_value = True
            # File 0 e 2 successo, file 1 fallimento
            if call_count[0] == 1:
                mock_process.exitCode.return_value = 1
                mock_process.readAllStandardError.return_value = b'Error'
            else:
                mock_process.exitCode.return_value = 0
                mock_process.readAllStandardError.return_value = b''
            mock_process.readAllStandardOutput.return_value = b''
            call_count[0] += 1
            return mock_process

        mock_qprocess.side_effect = get_mock_process

        files = []
        for i in range(3):
            file_path = os.path.join(temp_workspace, f"sub-{i:02d}", "anat", "brain.nii")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                f.write("data")
            files.append(file_path)

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, True)

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Dovrebbe avere 2 successi e 1 fallimento
        assert thread.success_count == 2
        assert len(thread.failed_files) == 1


class TestCancellationDuringProcessing:
    """Test per cancellazione durante il processing"""

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_cancel_during_single_file(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test cancellazione durante processamento file singolo"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()

        # Simula processo lungo che viene cancellato
        def wait_with_cancel(*args):
            if not thread.is_cancelled:
                thread.cancel()
            return True

        mock_process.waitForFinished.side_effect = wait_with_cancel
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-01", "anat", "brain.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        with patch('shutil.rmtree'):
            thread.run()

        # Processo dovrebbe essere killato
        mock_process.kill.assert_called()
        assert thread.is_cancelled is True

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_cancel_stops_batch_processing(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test che la cancellazione fermi il batch"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        files = []
        for i in range(5):
            file_path = os.path.join(temp_workspace, f"sub-{i:02d}", "anat", "brain.nii")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                f.write("data")
            files.append(file_path)

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, True)

        file_count = [0]

        def on_file_started(f):
            file_count[0] += 1
            if file_count[0] == 2:  # Cancella dopo 2° file
                thread.cancel()

        thread.file_started.connect(on_file_started)

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Dovrebbe processare solo 2 file
        assert file_count[0] == 2
        assert thread.success_count < 5


class TestSubjectIDExtraction:
    """Test per l'estrazione del subject ID"""

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_extract_subject_id_standard_bids(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test estrazione subject ID da path BIDS standard"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        # Path BIDS: workspace/sub-XX/anat/file.nii
        input_file = os.path.join(temp_workspace, "sub-123", "anat", "T1w.nii.gz")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")
            # Verifica che output path contenga sub-123
            assert "sub-123" in dst

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        assert thread.success_count == 1

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_extract_subject_id_nested_path(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test estrazione subject ID da path annidato"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        # Path con sottocartelle extra
        input_file = os.path.join(
            temp_workspace, "derivatives", "imported", "sub-456", "anat", "scan.nii"
        )
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")
            assert "sub-456" in dst

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        assert thread.success_count == 1


class TestTempDirectoryHandling:
    """Test per la gestione delle directory temporanee"""

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    @patch('tempfile.mkdtemp')
    def test_temp_directory_created(self, mock_mkdtemp, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test che la directory temporanea venga creata"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")
        temp_dir_path = os.path.join(temp_workspace, "temp_skullstrip")
        mock_mkdtemp.return_value = temp_dir_path
        os.makedirs(temp_dir_path, exist_ok=True)

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-01", "anat", "brain.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        with patch('shutil.move'), patch('shutil.rmtree') as mock_rmtree:
            thread.run()

        # Verifica che temp directory sia stata creata e poi rimossa
        mock_mkdtemp.assert_called()
        mock_rmtree.assert_called()

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_temp_directory_cleanup_on_error(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test pulizia temp directory in caso di errore"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 1  # Errore
        mock_process.readAllStandardError.return_value = b'Error'
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-02", "anat", "brain.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        with patch('shutil.rmtree') as mock_rmtree:
            thread.run()

        # Dovrebbe pulire temp directory anche con errore
        assert mock_rmtree.called

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_temp_directory_cleanup_on_cancel(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test pulizia temp directory su cancellazione"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()

        def wait_and_cancel(*args):
            thread.cancel()
            return True

        mock_process.waitForFinished.side_effect = wait_and_cancel
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-03", "anat", "scan.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        with patch('shutil.rmtree') as mock_rmtree:
            thread.run()

        # Temp directory dovrebbe essere pulita
        assert mock_rmtree.called


class TestEdgeCases:
    """Test per casi limite"""

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_empty_file_list(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test con lista file vuota"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        thread = SkullStripThread([], temp_workspace, {'f_val': 0.5}, False, True)

        # Non dovrebbe sollevare eccezioni
        # Nota: potrebbe causare division by zero in progress_per_file
        try:
            thread.run()
        except ZeroDivisionError:
            pytest.fail("Division by zero con lista vuota")

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_file_with_spaces_in_name(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test file con spazi nel nome"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-01", "anat", "T1 weighted image.nii.gz")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        assert thread.success_count == 1

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_nifti_without_gz_extension(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test file NIfTI non compresso (.nii)"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-04", "anat", "brain.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")
            # Output dovrebbe comunque essere .nii.gz
            assert dst.endswith(".nii.gz")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        assert thread.success_count == 1

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_extreme_f_values(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test con valori estremi di f_val"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        extreme_values = [0.0, 0.1, 0.9, 1.0]

        for f_val in extreme_values:
            input_file = os.path.join(
                temp_workspace, f"sub-f{int(f_val * 10)}", "anat", "brain.nii"
            )
            os.makedirs(os.path.dirname(input_file), exist_ok=True)
            with open(input_file, 'w') as f:
                f.write("data")

            thread = SkullStripThread([input_file], temp_workspace, {'f_val': f_val}, False, True)

            def mock_move(src, dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, 'w') as f:
                    f.write("stripped")

            with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
                thread.run()

            assert thread.success_count == 1


class TestSignalEmissions:
    """Test per le emissioni dei signal"""

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_progress_updated_signal(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test emissione signal progress_updated"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, True)

        progress_messages = []
        thread.progress_updated.connect(lambda msg: progress_messages.append(msg))

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        assert len(progress_messages) > 0
        # Messaggio dovrebbe contenere info su file processato
        assert any("T1w.nii" in msg or "Processing" in msg for msg in progress_messages)

    @patch('threads.skull_strip_thread.setup_fsl_env')
    @patch('threads.skull_strip_thread.QProcess')
    def test_file_started_signal_order(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test ordine emissione signal file_started"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        files = []
        filenames = ["file1.nii", "file2.nii", "file3.nii"]
        for i, fname in enumerate(filenames):
            file_path = os.path.join(temp_workspace, f"sub-{i:02d}", "anat", fname)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                f.write("data")
            files.append(file_path)

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, True)

        started_files = []
        thread.file_started.connect(lambda f: started_files.append(f))

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Verifica ordine
        assert len(started_files) == 3
        assert started_files == filenames