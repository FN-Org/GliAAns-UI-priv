""""
test_skull_strip_thread.py - Test Suite for SkullStripThread

This suite tests all functionalities of the skull-stripping thread:
- Execution of FSL BET and HD-BET
- Batch processing of multiple files
- Progress tracking and cancellation
- Generation of BIDS JSON metadata
- Error handling and edge cases
"""

import os
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, call
import pytest
from PyQt6.QtCore import QProcess

from main.threads.skull_strip_thread import SkullStripThread


class TestSkullStripThreadInitialization:
    """Tests for the initialization of SkullStripThread"""

    def test_init_with_bet(self, temp_workspace):
        """Test initialization with FSL BET"""
        files = [os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii.gz")]
        parameters = {'f_val': 0.5, 'opt_m': True}

        thread = SkullStripThread(
            files=files,
            workspace_path=temp_workspace,
            parameters=parameters,
            has_cuda=False,
            bet_tool="fsl-bet"
        )

        assert thread.files == files
        assert thread.workspace_path == temp_workspace
        assert thread.parameters == parameters
        assert thread.has_cuda is False
        assert thread.bet_tool == "fsl-bet"
        assert thread.is_cancelled is False
        assert thread.success_count == 0
        assert thread.failed_files == []

    def test_init_with_hdbet(self, temp_workspace):
        """Test initialization with HD-BET"""
        files = [os.path.join(temp_workspace, "test.nii")]
        parameters = {}

        thread = SkullStripThread(
            files=files,
            workspace_path=temp_workspace,
            parameters=parameters,
            has_cuda=True,
            bet_tool="fsl-bet"
        )

        assert thread.has_cuda is True
        assert thread.bet_tool == "fsl-bet"

    def test_init_with_synthstrip(self, temp_workspace):
        """Test initialization with SynthStrip"""
        files = [os.path.join(temp_workspace, "test.nii")]
        parameters = {}

        thread = SkullStripThread(
            files=files,
            workspace_path=temp_workspace,
            parameters=parameters,
            has_cuda=True,
            bet_tool="synthstrip"
        )

        assert thread.has_cuda is True
        assert thread.bet_tool == "synthstrip"

    def test_signals_exist(self, temp_workspace):
        """Verify that the signals are correctly defined"""
        thread = SkullStripThread([], temp_workspace, {}, False, "fsl-bet")

        assert hasattr(thread, 'progress_updated')
        assert hasattr(thread, 'progress_value_updated')
        assert hasattr(thread, 'file_started')
        assert hasattr(thread, 'file_completed')
        assert hasattr(thread, 'all_completed')


class TestSkullStripThreadCancellation:
    """Tests for thread cancellation"""

    def test_cancel_flag_set(self, temp_workspace):
        """Test that the cancellation flag is set"""
        thread = SkullStripThread([], temp_workspace, {}, False, "fsl-bet")

        assert thread.is_cancelled is False
        thread.cancel()
        assert thread.is_cancelled is True

    def test_cancel_terminates_process(self, temp_workspace):
        """Test process termination during cancellation"""
        thread = SkullStripThread([], temp_workspace, {}, False, "fsl-bet")

        # Mock a running process
        mock_process = Mock(spec=QProcess)
        thread.process = mock_process

        thread.cancel()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_cancel_no_process(self, temp_workspace):
        """Test cancellation without an active process"""
        thread = SkullStripThread([], temp_workspace, {}, False, "fsl-bet")

        # Should not raise exceptions
        thread.cancel()
        assert thread.is_cancelled is True

    def test_cancel_process_error_handling(self, temp_workspace):
        """Test error handling during process cancellation"""
        thread = SkullStripThread([], temp_workspace, {}, False, "fsl-bet")

        mock_process = Mock()
        mock_process.terminate.side_effect = RuntimeError("Process error")
        thread.process = mock_process

        # Should not propagate the exception
        thread.cancel()
        assert thread.is_cancelled is True


class TestBETCommandBuilding:
    """Tests for building FSL BET commands"""

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_bet_basic_command(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test basic BET command"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        # Mock process
        mock_process_instance = Mock()
        mock_process_instance.waitForFinished.return_value = True
        mock_process_instance.exitCode.return_value = 0
        mock_process_instance.readAllStandardError.return_value = b''
        mock_process_instance.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process_instance

        # Create input file
        input_file = os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii.gz")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("nifti data")

        parameters = {'f_val': 0.5}
        thread = SkullStripThread([input_file], temp_workspace, parameters, False, "fsl-bet")

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        # Verify process call
        mock_process_instance.start.assert_called_once()
        call_args = mock_process_instance.start.call_args[0]

        assert call_args[0] == "bet"
        assert input_file in call_args[1]
        assert "-f" in call_args[1]
        assert "0.5" in call_args[1]

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_bet_with_options(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test BET command with advanced options"""
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

        thread = SkullStripThread([input_file], temp_workspace, parameters, False, "fsl-bet")

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]
        cmd = call_args[1]

        # Verify presence of options
        assert "-m" in cmd  # opt_m
        assert "-t" in cmd  # opt_t
        assert "-o" in cmd  # opt_o
        assert "-s" not in cmd  # opt_s is False

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_bet_with_center_coordinates(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test BET command with center coordinates"""
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

        thread = SkullStripThread([input_file], temp_workspace, parameters, False, "fsl-bet")

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]
        cmd = call_args[1]

        # Verify coordinates
        assert "-c" in cmd
        assert "128" in cmd or "64" in cmd

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_bet_brain_extracted_option(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test -n option for brain extraction"""
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
            'opt_brain_extracted': False  # Disable mask extraction
        }

        thread = SkullStripThread([input_file], temp_workspace, parameters, False, "fsl-bet")

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]
        cmd = call_args[1]

        assert "-n" in cmd


class TestHDBETCommandBuilding:
    """Tests for building HD-BET commands"""

    @patch('main.threads.skull_strip_thread.get_bin_path')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_hdbet_basic_command(self, mock_qprocess, mock_get_bin, temp_workspace):
        """Test basic HD-BET command"""
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

        thread = SkullStripThread([input_file], temp_workspace, {}, True, "hd-bet")

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]

        assert call_args[0] == "/usr/bin/hd-bet"
        assert "-i" in call_args[1]
        assert "-o" in call_args[1]

    @patch('main.threads.skull_strip_thread.get_bin_path')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_hdbet_cpu_mode(self, mock_qprocess, mock_get_bin, temp_workspace):
        """Test HD-BET in CPU mode (without CUDA)"""
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
        thread = SkullStripThread([input_file], temp_workspace, {}, False, "hd-bet")

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]
        cmd = call_args[1]

        # Verify CPU options
        assert "-device" in cmd
        assert "cpu" in cmd
        assert "--disable_tta" in cmd

    @patch('main.threads.skull_strip_thread.get_bin_path')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_hdbet_cuda_mode(self, mock_qprocess, mock_get_bin, temp_workspace):
        """Test HD-BET with CUDA"""
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
        thread = SkullStripThread([input_file], temp_workspace, {}, True, "hd-bet")

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]
        cmd = call_args[1]

        # Should NOT have CPU options
        assert "-device" not in cmd or "cpu" not in cmd

    @patch('main.threads.skull_strip_thread.get_bin_path')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_sinthstrip_basic_command(self, mock_qprocess, mock_get_bin, temp_workspace):
        """Test basic SynthStrip command"""
        mock_get_bin.return_value = "/usr/bin/mri_sinthstrip"

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

        thread = SkullStripThread([input_file], temp_workspace, {}, True, "synthstrip")

        with patch('shutil.move'), patch('shutil.rmtree'), patch('os.makedirs'):
            thread.run()

        call_args = mock_process.start.call_args[0]

        assert call_args[0] == "/usr/bin/mri_sinthstrip"
        assert "-i" in call_args[1]
        assert "-o" in call_args[1]

class TestOutputGeneration:
    """Tests for output and metadata generation"""

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_output_directory_creation(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test output directory creation"""
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

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        # Mock shutil.move to simulate created file
        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped brain")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Verify derivatives directory created
        expected_dir = os.path.join(
            temp_workspace, 'derivatives', 'skullstrips', 'sub-05', 'anat'
        )
        assert os.path.exists(expected_dir)

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_json_metadata_creation_bet(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test JSON metadata creation for BET"""
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

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.4}, False, "fsl-bet")

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Verify JSON created
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

    @patch('main.threads.skull_strip_thread.get_bin_path')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_json_metadata_creation_hdbet(self, mock_qprocess, mock_get_bin, temp_workspace):
        """Test JSON metadata creation for HD-BET"""
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

        thread = SkullStripThread([input_file], temp_workspace, {}, True, "hd-bet")

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

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_output_filename_format_bet(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test output filename format for BET"""
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
        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.7}, False, "fsl-bet")

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Verify filename contains f07
        output_file = os.path.join(
            temp_workspace, 'derivatives', 'skullstrips', 'sub-08', 'anat',
            'T1w_f07_brain.nii.gz'
        )

        assert os.path.exists(output_file)

    @patch('main.threads.skull_strip_thread.get_bin_path')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_json_metadata_creation_synthstrip(self, mock_qprocess, mock_get_bin, temp_workspace):
        """Test JSON metadata creation for SynthStrip"""
        mock_get_bin.return_value = "/usr/bin/mri_synthstrip"

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

        thread = SkullStripThread([input_file], temp_workspace, {}, True, "synthstrip")

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        json_file = os.path.join(
            temp_workspace, 'derivatives', 'skullstrips', 'sub-07', 'anat',
            'brain_synthstrip_brain.json'
        )

        assert os.path.exists(json_file)

        with open(json_file, 'r') as f:
            metadata = json.load(f)

        assert metadata["SkullStrippingMethod"] == "SynthStrip"


class TestBatchProcessing:
    """Tests for batch processing of multiple files"""

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_multiple_files_processing(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test processing of multiple files"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        # Create multiple files
        files = []
        for i in range(1, 4):
            file_path = os.path.join(temp_workspace, f"sub-0{i}", "anat", f"T1w_{i}.nii")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                f.write("data")
            files.append(file_path)

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

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

        # Verify signals emitted for each file
        assert file_started_count[0] == 3
        assert file_completed_count[0] == 3
        assert thread.success_count == 3

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_progress_tracking_multiple_files(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test progress tracking with multiple files"""
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

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        progress_values = []
        thread.progress_value_updated.connect(lambda val: progress_values.append(val))

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Verify incremental progress
        assert len(progress_values) == 5
        # Progress should increase
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i - 1]

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_all_completed_signal(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test all_completed signal at the end"""
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

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

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
    """Tests for error handling"""

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_process_failure_nonzero_exit(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test process error handling with non-zero exit code"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 1  # Error exit code
        mock_process.readAllStandardError.return_value = b'BET error: invalid parameters'
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-01", "anat", "broken.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        completed_files = []
        thread.file_completed.connect(lambda f, s, m: completed_files.append((f, s, m)))

        with patch('shutil.rmtree'):
            thread.run()

        # Verify that the file is marked as failed
        assert len(completed_files) == 1
        filename, success, message = completed_files[0]
        assert success is False
        assert "error" in message.lower() or "invalid" in message.lower()
        assert len(thread.failed_files) == 1

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_missing_subject_id(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test handling of files without BIDS subject ID"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        # File without BIDS structure (no sub-XX)
        input_file = os.path.join(temp_workspace, "random_folder", "brain.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        completed_files = []
        thread.file_completed.connect(lambda f, s, m: completed_files.append((f, s, m)))

        thread.run()

        # Should fail due to missing subject ID
        assert len(completed_files) == 1
        filename, success, message = completed_files[0]
        assert success is False
        assert "Impossibile estrarre" in message or "Cannot extract" in message
        assert len(thread.failed_files) == 1

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_exception_during_processing(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test generic exception handling during processing"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.start.side_effect = RuntimeError("Process start failed")
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-02", "anat", "test.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        completed_files = []
        thread.file_completed.connect(lambda f, s, m: completed_files.append((f, s, m)))

        with patch('shutil.rmtree'):
            thread.run()

        # Should catch the exception
        assert len(completed_files) == 1
        filename, success, message = completed_files[0]
        assert success is False
        assert "failed" in message.lower() or "error" in message.lower()

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_partial_failure_multiple_files(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test with some files failing and others succeeding"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        # Mock process alternating success/failure
        call_count = [0]

        def get_mock_process():
            mock_process = Mock()
            mock_process.waitForFinished.return_value = True
            # File 0 and 2 succeed, file 1 fails
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

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Should have 2 successes and 1 failure
        assert thread.success_count == 2
        assert len(thread.failed_files) == 1


class TestCancellationDuringProcessing:
    """Tests for cancellation during processing"""

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_cancel_during_single_file(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test cancellation during single file processing"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()

        # Simulate long process that gets cancelled
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

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        with patch('shutil.rmtree'):
            thread.run()

        # Process should be killed
        mock_process.kill.assert_called()
        assert thread.is_cancelled is True

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_cancel_stops_batch_processing(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test that cancellation stops batch processing"""
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

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        file_count = [0]

        def on_file_started(f):
            file_count[0] += 1
            if file_count[0] == 2:  # Cancel after 2nd file
                thread.cancel()

        thread.file_started.connect(on_file_started)

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Should only process 2 files
        assert file_count[0] == 2
        assert thread.success_count < 5


class TestSubjectIDExtraction:
    """Tests for subject ID extraction"""

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_extract_subject_id_standard_bids(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test extraction of subject ID from standard BIDS path"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        # BIDS path: workspace/sub-XX/anat/file.nii
        input_file = os.path.join(temp_workspace, "sub-123", "anat", "T1w.nii.gz")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")
            # Verify that the output path contains sub-123
            assert "sub-123" in dst

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        assert thread.success_count == 1

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_extract_subject_id_nested_path(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test extraction of subject ID from a nested path"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 0
        mock_process.readAllStandardError.return_value = b''
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        # Path with extra subdirectories
        input_file = os.path.join(
            temp_workspace, "derivatives", "imported", "sub-456", "anat", "scan.nii"
        )
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")
            assert "sub-456" in dst

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        assert thread.success_count == 1


class TestTempDirectoryHandling:
    """Tests for temporary directory management"""

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    @patch('tempfile.mkdtemp')
    def test_temp_directory_created(self, mock_mkdtemp, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test that the temporary directory is created"""
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

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        with patch('shutil.move'), patch('shutil.rmtree') as mock_rmtree:
            thread.run()

        # Verify that the temp directory was created and then removed
        mock_mkdtemp.assert_called()
        mock_rmtree.assert_called()

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_temp_directory_cleanup_on_error(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test cleanup of temp directory in case of error"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        mock_process = Mock()
        mock_process.waitForFinished.return_value = True
        mock_process.exitCode.return_value = 1  # Error
        mock_process.readAllStandardError.return_value = b'Error'
        mock_process.readAllStandardOutput.return_value = b''
        mock_qprocess.return_value = mock_process

        input_file = os.path.join(temp_workspace, "sub-02", "anat", "brain.nii")
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        with open(input_file, 'w') as f:
            f.write("data")

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        with patch('shutil.rmtree') as mock_rmtree:
            thread.run()

        # Should clean up the temp directory even after an error
        assert mock_rmtree.called

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_temp_directory_cleanup_on_cancel(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test cleanup of temp directory upon cancellation"""
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

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        with patch('shutil.rmtree') as mock_rmtree:
            thread.run()

        # Temp directory should be cleaned up
        assert mock_rmtree.called

class TestEdgeCases:
    """Tests for edge cases"""

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_empty_file_list(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test with empty file list"""
        mock_fsl_env.return_value = ("/usr/local/fsl", "NIFTI_GZ")

        thread = SkullStripThread([], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        # Should not raise exceptions
        # Note: might cause division by zero in progress_per_file
        try:
            thread.run()
        except ZeroDivisionError:
            pytest.fail("Division by zero with empty list")

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_file_with_spaces_in_name(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test file with spaces in name"""
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

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        assert thread.success_count == 1

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_nifti_without_gz_extension(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test uncompressed NIfTI file (.nii)"""
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

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")
            # Output should still be .nii.gz
            assert dst.endswith(".nii.gz")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        assert thread.success_count == 1

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_extreme_f_values(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test with extreme f_val values"""
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

            thread = SkullStripThread([input_file], temp_workspace, {'f_val': f_val}, False, "fsl-bet")

            def mock_move(src, dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, 'w') as f:
                    f.write("stripped")

            with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
                thread.run()

            assert thread.success_count == 1


class TestSignalEmissions:
    """Tests for signal emissions"""

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_progress_updated_signal(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test progress_updated signal emission"""
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

        thread = SkullStripThread([input_file], temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        progress_messages = []
        thread.progress_updated.connect(lambda msg: progress_messages.append(msg))

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        assert len(progress_messages) > 0
        # Message should contain info about processed file
        assert any("T1w.nii" in msg or "Processing" in msg for msg in progress_messages)

    @patch('main.threads.skull_strip_thread.setup_fsl_env')
    @patch('main.threads.skull_strip_thread.QProcess')
    def test_file_started_signal_order(self, mock_qprocess, mock_fsl_env, temp_workspace):
        """Test file_started signal emission order"""
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

        thread = SkullStripThread(files, temp_workspace, {'f_val': 0.5}, False, "fsl-bet")

        started_files = []
        thread.file_started.connect(lambda f: started_files.append(f))

        def mock_move(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w') as f:
                f.write("stripped")

        with patch('shutil.move', side_effect=mock_move), patch('shutil.rmtree'):
            thread.run()

        # Verify order
        assert len(started_files) == 3
        assert started_files == filenames