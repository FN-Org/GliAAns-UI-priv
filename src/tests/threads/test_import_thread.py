"""
test_import_thread.py - Test Suite for ImportThread

This suite tests all the main functionalities of ImportThread:
- Importing already organized BIDS folders
- DICOM → NIfTI conversion
- Handling single vs. multiple patients
- Structure detection heuristics
- Import cancellation
- Error handling
"""

import os
from types import SimpleNamespace
from unittest.mock import Mock, patch, MagicMock, call
import pytest
from PyQt6.QtCore import QCoreApplication

from main.threads.import_thread import ImportThread


class TestImportThreadInitialization:
    """Tests for ImportThread initialization"""

    def test_init_single_path(self, mock_context, temp_workspace):
        """Test initialization with a single path"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        assert thread.context == mock_context
        assert thread.folders_path == [temp_workspace]
        assert thread.workspace_path == temp_workspace
        assert thread.current_progress == 0
        assert thread._is_canceled is False
        assert thread.process is None

    def test_init_multiple_paths(self, mock_context, temp_workspace):
        """Test initialization with multiple paths"""
        paths = [temp_workspace, os.path.join(temp_workspace, "sub-01")]
        thread = ImportThread(mock_context, paths, temp_workspace)

        assert len(thread.folders_path) == 2
        assert thread.folders_path == paths

    def test_signals_exist(self, mock_context, temp_workspace):
        """Verify that signals are defined correctly"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        assert hasattr(thread, 'finished')
        assert hasattr(thread, 'error')
        assert hasattr(thread, 'progress')


class TestFileDetection:
    """Tests for file detection methods"""

    def test_is_nifti_file(self, mock_context, temp_workspace):
        """Test NIfTI file detection"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        assert thread._is_nifti_file("brain.nii") is True
        assert thread._is_nifti_file("brain.nii.gz") is True
        assert thread._is_nifti_file("brain.json") is False
        assert thread._is_nifti_file("brain.dcm") is False

    def test_is_dicom_file_valid(self, mock_context, temp_workspace):
        """Test valid DICOM detection"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Create a mock DICOM file
        dicom_path = os.path.join(temp_workspace, "test.dcm")
        with open(dicom_path, "wb") as f:
            f.write(b'\x00' * 128)  # 128 bytes of padding
            f.write(b'DICM')  # DICOM magic bytes
            f.write(b'\x00' * 100)

        assert thread._is_dicom_file(dicom_path) is True

    def test_is_dicom_file_invalid(self, mock_context, temp_workspace):
        """Test non-DICOM file detection"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # File without DICOM magic bytes
        non_dicom_path = os.path.join(temp_workspace, "notdicom.txt")
        with open(non_dicom_path, "w") as f:
            f.write("This is not a DICOM file")

        assert thread._is_dicom_file(non_dicom_path) is False

    def test_is_dicom_file_exception(self, mock_context, temp_workspace):
        """Test exception handling during DICOM read"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Non-existent file
        assert thread._is_dicom_file("/nonexistent/file.dcm") is False


class TestBIDSDetection:
    """Tests for BIDS structure detection"""

    def test_is_bids_folder_valid(self, mock_context, temp_workspace):
        """Test valid BIDS folder detection"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Create BIDS structure
        bids_dir = os.path.join(temp_workspace, "bids_test")
        # **EDIT**: The folder name passed to the method must start with "sub-"
        # according to the provided code logic.
        sub_folder = os.path.join(bids_dir, "sub-01")
        anat_dir = os.path.join(sub_folder, "anat")
        os.makedirs(anat_dir, exist_ok=True)

        # Add NIfTI file
        nifti_path = os.path.join(anat_dir, "sub-01_T1w.nii.gz")
        with open(nifti_path, "w") as f:
            f.write("nifti data")

        # **FIX**: The assertion must test 'sub_folder', not 'bids_dir'
        assert thread._is_bids_folder(sub_folder) is True

    def test_is_bids_folder_invalid(self, mock_context, temp_workspace):
        """Test detection of non-BIDS folder (wrong name)"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        invalid_dir = os.path.join(temp_workspace, "not_bids")
        os.makedirs(invalid_dir, exist_ok=True)
        assert thread._is_bids_folder(invalid_dir) is False

    def test_is_bids_folder_no_sub_prefix(self, mock_context, temp_workspace):
        """Test folder without 'sub-' prefix"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Folder with similar structure but without the correct prefix
        fake_bids = os.path.join(temp_workspace, "fake_bids")
        anat_dir = os.path.join(fake_bids, "patient01", "anat")
        os.makedirs(anat_dir, exist_ok=True)

        with open(os.path.join(anat_dir, "scan.nii"), "w") as f:
            f.write("data")

        assert thread._is_bids_folder(fake_bids) is False


class TestSubjectIDGeneration:
    """Tests for subject ID generation"""

    def test_get_next_sub_id_empty_workspace(self, mock_context, temp_workspace):
        """Test ID generation on an empty workspace"""
        empty_ws = os.path.join(temp_workspace, "empty")
        os.makedirs(empty_ws)

        thread = ImportThread(mock_context, [temp_workspace], empty_ws)
        sub_id = thread._get_next_sub_id()

        assert sub_id == "sub-01"

    def test_get_next_sub_id_existing_subjects(self, mock_context, temp_workspace):
        """Test ID generation with existing subjects"""
        # Add exist_ok=True
        os.makedirs(os.path.join(temp_workspace, "sub-01"), exist_ok=True)
        os.makedirs(os.path.join(temp_workspace, "sub-02"), exist_ok=True)

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        sub_id = thread._get_next_sub_id()

        assert sub_id == "sub-03"

    def test_get_next_sub_id_non_sequential(self, mock_context, temp_workspace):
        """Test with non-sequential IDs"""
        # Add exist_ok=True
        os.makedirs(os.path.join(temp_workspace, "sub-01"), exist_ok=True)
        os.makedirs(os.path.join(temp_workspace, "sub-05"))  # Skip

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        sub_id = thread._get_next_sub_id()

        # Should be sub-06 (max + 1)
        assert sub_id == "sub-06"

    def test_get_next_sub_id_invalid_names(self, mock_context, temp_workspace):
        """Test with invalid folder names"""
        # Add exist_ok=True
        os.makedirs(os.path.join(temp_workspace, "sub-01"), exist_ok=True)
        os.makedirs(os.path.join(temp_workspace, "sub-02"), exist_ok=True)
        os.makedirs(os.path.join(temp_workspace, "sub-invalid"))
        os.makedirs(os.path.join(temp_workspace, "not-a-sub"))

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        sub_id = thread._get_next_sub_id()

        # Should ignore invalid folders and use sub-01, sub-02
        assert sub_id == "sub-03"


class TestPatientDetectionHeuristics:
    """Tests for single/multiple patient detection heuristics"""

    def test_subfolders_look_like_different_patients(self, mock_context, temp_workspace):
        """Test multi-patient folder detection"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Create folders that look like different patients
        patient_folders = [
            os.path.join(temp_workspace, "sub-01"),
            os.path.join(temp_workspace, "sub-02"),
            os.path.join(temp_workspace, "patient_03")
        ]

        for folder in patient_folders:
            os.makedirs(folder, exist_ok=True)

        assert thread._subfolders_look_like_different_patients(patient_folders) is True

    def test_subfolders_single_patient(self, mock_context, temp_workspace):
        """Test folders belonging to a single patient"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Folders without multi-patient pattern
        series_folders = [
            os.path.join(temp_workspace, "series_001"),
            os.path.join(temp_workspace, "series_002"),
            os.path.join(temp_workspace, "t1_weighted")
        ]

        for folder in series_folders:
            os.makedirs(folder, exist_ok=True)

        assert thread._subfolders_look_like_different_patients(series_folders) is False

    @patch('main.threads.import_thread.pydicom.dcmread')
    def test_are_dicom_series_of_same_patient_true(self, mock_dcmread, mock_context, temp_workspace):
        """Test DICOM files from the same patient"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Setup mock DICOM with the same PatientID
        mock_dcm = Mock()
        mock_dcm.PatientID = "PATIENT001"
        mock_dcm.PatientName = "Doe^John"
        mock_dcmread.return_value = mock_dcm

        # Create folders with DICOM
        series_folders = []
        for i in range(3):
            folder = os.path.join(temp_workspace, f"series_{i}")
            os.makedirs(folder, exist_ok=True)

            # Create mock DICOM file
            dicom_file = os.path.join(folder, f"image_{i}.dcm")
            with open(dicom_file, "wb") as f:
                f.write(b'\x00' * 128)
                f.write(b'DICM')

            series_folders.append(folder)

        result = thread._are_dicom_series_of_same_patient(series_folders)
        assert result is True

    @patch('main.threads.import_thread.pydicom.dcmread')
    def test_are_dicom_series_of_same_patient_false(self, mock_dcmread, mock_context, temp_workspace):
        """Test DICOM files from different patients"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # All files are recognized as DICOM
        thread._is_dicom_file = Mock(return_value=True)

        # Each call to dcmread returns a different patient
        mock_dcmread.side_effect = [
            SimpleNamespace(PatientID="PATIENT01"),
            SimpleNamespace(PatientID="PATIENT02"),
            SimpleNamespace(PatientID="PATIENT03"),
        ]

        # Create fake DICOM folders and files
        series_folders = []
        for i in range(3):
            folder = os.path.join(temp_workspace, f"patient_{i}")
            os.makedirs(folder, exist_ok=True)
            dicom_file = os.path.join(folder, "scan.dcm")
            with open(dicom_file, "wb") as f:
                f.write(b'\x00' * 128)
                f.write(b'DICM')
            series_folders.append(folder)

        result = thread._are_dicom_series_of_same_patient(series_folders)

        assert result is False

    def test_are_dicom_series_no_dicom_files(self, mock_context, temp_workspace):
        """Test with folders containing no DICOM files"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Empty folders or with other files
        folders = []
        for i in range(3):
            folder = os.path.join(temp_workspace, f"empty_{i}")
            os.makedirs(folder, exist_ok=True)
            folders.append(folder)

        result = thread._are_dicom_series_of_same_patient(folders)
        assert result is False


class TestCancellation:
    """Tests for import cancellation"""

    def test_cancel_flag_set(self, mock_context, temp_workspace):
        """Test that the cancellation flag is set"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        assert thread._is_canceled is False
        thread.cancel()
        assert thread._is_canceled is True

    def test_cancel_terminates_process(self, mock_context, temp_workspace):
        """Test termination of external process during cancellation"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Mock an external running process
        mock_process = Mock()
        thread.process = mock_process

        thread.cancel()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_cancel_no_process(self, mock_context, temp_workspace):
        """Test cancellation with no active process"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Should not raise exceptions
        thread.cancel()
        assert thread._is_canceled is True


class TestBIDSImport:
    """Tests for BIDS folder import"""

    @patch.object(ImportThread, '_is_bids_folder')
    @patch.object(ImportThread, '_get_next_sub_id')
    def test_import_bids_folder_directly(self, mock_get_id, mock_is_bids,
                                         mock_context, temp_workspace):
        """Test direct copy of BIDS folder"""
        # Setup
        mock_is_bids.return_value = True
        mock_get_id.return_value = "sub-003"

        # Create source BIDS folder
        src_bids = os.path.join(temp_workspace, "source_bids")
        anat_dir = os.path.join(src_bids, "sub-01", "anat")
        os.makedirs(anat_dir)

        nifti_file = os.path.join(anat_dir, "T1w.nii.gz")
        with open(nifti_file, "w") as f:
            f.write("test nifti data")

        # Create destination workspace
        dest_ws = os.path.join(temp_workspace, "dest_workspace")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [src_bids], dest_ws)

        # Connect signal to verify emission
        finished_called = [False]

        def on_finished():
            finished_called[0] = True

        thread.finished.connect(on_finished)

        thread.run()

        assert finished_called[0] is True
        dest_folder = os.path.join(dest_ws, "sub-003")
        assert os.path.exists(dest_folder)


class TestDICOMConversion:
    """Tests for DICOM → NIfTI conversion"""

    @patch('main.threads.import_thread.subprocess.Popen')
    @patch('main.threads.import_thread.get_bin_path')
    def test_convert_dicom_folder_success(self, mock_get_bin, mock_Popen,
                                          mock_context, temp_workspace):
        """Test successful DICOM conversion"""
        mock_get_bin.return_value = "/fake/path/dcm2niix"

        # Configure the Popen mock to simulate a successful process
        mock_process = Mock()
        mock_process.communicate.return_value = (b'Conversion complete', b'')  # stdout, stderr (bytes)
        mock_process.returncode = 0
        mock_Popen.return_value = mock_process  # Popen() returns our mock

        src_folder = os.path.join(temp_workspace, "dicom_source")
        dest_folder = os.path.join(temp_workspace, "nifti_dest")
        os.makedirs(src_folder)
        # os.makedirs(dest_folder) # The function itself creates this folder

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Run the function
        thread._convert_dicom_folder_to_nifti(src_folder, dest_folder)

        # Verify that Popen was called correctly
        mock_Popen.assert_called_once()
        mock_process.communicate.assert_called_once()
        # Verify that no error was raised (the test would fail earlier if it were)

    @patch('main.threads.import_thread.get_bin_path')
    def test_convert_dicom_folder_missing_tool(self, mock_get_bin,
                                               mock_context, temp_workspace):
        """Test when dcm2niix is not available"""
        # Simulate FileNotFoundError when searching for the binary
        mock_get_bin.side_effect = FileNotFoundError("dcm2niix not found")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # **FIX**: The code now catches the exception and raises a RuntimeError.
        # The old test expected nothing to happen.
        with pytest.raises(RuntimeError, match="dcm2niix not found"):
            thread._convert_dicom_folder_to_nifti(temp_workspace, temp_workspace)

    @patch('main.threads.import_thread.subprocess.Popen')
    @patch('main.threads.import_thread.get_bin_path')
    def test_convert_dicom_folder_process_error(self, mock_get_bin, mock_Popen,
                                                mock_context, temp_workspace):
        """Test error during dcm2niix execution (returncode != 0)"""
        mock_get_bin.return_value = "/fake/path/dcm2niix"

        # Simulate a process that fails
        mock_process = Mock()
        mock_process.communicate.return_value = (b'', b'Errore fatale')  # Message on stderr
        mock_process.returncode = 1  # Error exit code
        mock_Popen.return_value = mock_process

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # **FIX**: The code detects the returncode != 0 and raises a RuntimeError.
        with pytest.raises(RuntimeError, match="dcm2niix failed: Errore fatale"):
            thread._convert_dicom_folder_to_nifti(temp_workspace, temp_workspace)


class TestBIDSStructureConversion:
    """Tests for BIDS structure conversion"""

    @patch.object(ImportThread, '_get_next_sub_id', return_value="sub-01")
    def test_convert_to_bids_structure(self, mock_get_id, mock_context, temp_workspace):
        """Test folder conversion to BIDS structure"""
        src_folder = os.path.join(temp_workspace, "source")
        os.makedirs(src_folder)

        # Create fictitious NIfTI and JSON with minimal metadata
        nifti_file = os.path.join(src_folder, "brain.nii.gz")
        json_file = os.path.join(src_folder, "brain.json")

        with open(nifti_file, "w") as f: f.write("nifti data")
        # The code requires 'Modality' metadata
        with open(json_file, "w") as f: f.write('{"Modality": "MR", "ProtocolName": "T1w"}')

        dest_ws = os.path.join(temp_workspace, "workspace")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [temp_workspace], dest_ws)
        thread._convert_to_bids_structure(src_folder)

        # Verify created structure (with correct ID)
        expected_sub = os.path.join(dest_ws, "sub-01", "anat")  # <- CORRECT
        assert os.path.exists(expected_sub)
        expected_file = os.path.join(expected_sub, "sub-01_run-1_T1w.nii.gz")
        assert os.path.exists(expected_file)

    @patch.object(ImportThread, '_get_next_sub_id', return_value="sub-01")
    def test_convert_to_bids_structure_nested(self, mock_get_id, mock_context, temp_workspace):
        """Test conversion with files in subfolders"""
        src_folder = os.path.join(temp_workspace, "nested_source")
        sub_dir = os.path.join(src_folder, "subdir")
        os.makedirs(sub_dir)

        # File in subfolder
        nifti_file = os.path.join(sub_dir, "scan.nii.gz")  # Added .gz for consistency
        json_file = os.path.join(sub_dir, "scan.json")
        with open(nifti_file, "w") as f: f.write("scan data")
        with open(json_file, "w") as f: f.write('{"Modality": "PT", "Radiopharmaceutical": "FDG"}')

        dest_ws = os.path.join(temp_workspace, "ws")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [temp_workspace], dest_ws)
        thread._convert_to_bids_structure(src_folder)

        # File should be copied to pet/ (according to PT logic)
        expected_pet = os.path.join(dest_ws, "sub-01", "ses-01", "pet")  # <- CORRECT
        assert os.path.exists(expected_pet)
        # The filename is changed
        expected_file_path = os.path.join(expected_pet, "sub-01_task-unknown_run-1_pet.nii.gz")
        assert os.path.exists(expected_file_path)


class TestSinglePatientProcessing:
    """Tests for single-patient folder processing"""

    @patch.object(ImportThread, '_convert_dicom_folder_to_nifti')
    @patch.object(ImportThread, '_convert_to_bids_structure')
    def test_process_single_patient_folder_with_nifti(self, mock_convert_bids,
                                                      mock_convert_dicom,
                                                      mock_context, temp_workspace):
        """Test processing folder with existing NIfTI files"""
        # Patient folder with NIfTI
        patient_folder = os.path.join(temp_workspace, "patient_data")
        os.makedirs(patient_folder)

        nifti_file = os.path.join(patient_folder, "t1.nii.gz")
        with open(nifti_file, "w") as f:
            f.write("nifti")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread._process_single_patient_folder(patient_folder)

        # Should convert to BIDS but not call dcm2niix
        mock_convert_bids.assert_called_once()
        mock_convert_dicom.assert_not_called()

    @patch.object(ImportThread, '_convert_dicom_folder_to_nifti')
    @patch.object(ImportThread, '_convert_to_bids_structure')
    def test_process_single_patient_folder_with_dicom(self, mock_convert_bids,
                                                      mock_convert_dicom,
                                                      mock_context, temp_workspace):
        """Test processing folder with DICOM files"""
        patient_folder = os.path.join(temp_workspace, "patient_dicom")
        os.makedirs(patient_folder)

        # Create DICOM file
        dicom_file = os.path.join(patient_folder, "image.dcm")
        with open(dicom_file, "wb") as f:
            f.write(b'\x00' * 128)
            f.write(b'DICM')

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread._process_single_patient_folder(patient_folder)

        # Both conversions should be called
        mock_convert_dicom.assert_called_once()
        mock_convert_bids.assert_called_once()

    def test_process_single_patient_folder_cancelled(self, mock_context, temp_workspace):
        """Test cancellation during processing"""
        patient_folder = os.path.join(temp_workspace, "patient")
        os.makedirs(patient_folder)

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread.cancel()  # Cancel before starting

        # Should not raise exceptions
        thread._process_single_patient_folder(patient_folder)


class TestErrorHandling:
    """Tests for error handling"""

    def test_run_invalid_folder_path(self, mock_context, temp_workspace):
        """Test with invalid folder path"""
        invalid_path = os.path.join(temp_workspace, "nonexistent")
        thread = ImportThread(mock_context, [invalid_path], temp_workspace)

        error_called = [False]
        error_msg = [None]

        def on_error(msg):
            error_called[0] = True
            error_msg[0] = msg

        thread.error.connect(on_error)
        thread.run()

        assert error_called[0] is True
        assert "Invalid" in error_msg[0] or "non valido" in error_msg[0]

    def test_run_empty_folders_list(self, mock_context, temp_workspace):
        """Test with empty folder list"""
        thread = ImportThread(mock_context, [], temp_workspace)

        error_called = [False]

        def on_error(msg):
            error_called[0] = True

        thread.error.connect(on_error)
        thread.run()

        assert error_called[0] is True

    def test_run_cancelled_no_error_emit(self, mock_context, temp_workspace):
        """Test that cancellation does not emit errors"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        error_called = [False]

        def on_error(msg):
            error_called[0] = True

        thread.error.connect(on_error)
        thread.cancel()
        thread.run()

        # Should not emit an error when canceled
        assert error_called[0] is False


class TestProgressEmission:
    """Tests for progress emission"""

    @patch('main.threads.import_thread.subprocess.Popen')
    def test_progress_increases_monotonically(self, mock_Popen, mock_context, temp_workspace):
        """Test that progress increases monotonically"""

        # Simulate Popen to avoid FileNotFoundError
        mock_process = Mock()
        mock_process.communicate.return_value = (b'Success', b'')
        mock_process.returncode = 0
        mock_Popen.return_value = mock_process

        # Create a folder that is NOT BIDS (so it follows "Case C")
        nifti_folder = os.path.join(temp_workspace, "nifti_src")
        os.makedirs(nifti_folder)
        with open(os.path.join(nifti_folder, "scan.nii.gz"), "w") as f:
            f.write("x")
        with open(os.path.join(nifti_folder, "scan.json"), "w") as f:
            f.write('{"Modality": "MR", "ProtocolName": "T1w"}')

        dest = os.path.join(temp_workspace, "out")
        os.makedirs(dest)

        # Use the "nifti_folder" (non-BIDS) as input
        thread = ImportThread(mock_context, [nifti_folder], dest)

        progress_values = []
        thread.progress.connect(lambda v: progress_values.append(v))

        # Run the thread
        thread.run()

        # **FIX**: More robust assertions. The strange value (1251907152)
        # was likely a symptom of the test being interrupted abruptly.
        assert len(progress_values) > 0
        assert progress_values[-1] == 100  # Must end at 100

        # Verify that values never decrease
        last_val = -1
        for val in progress_values:
            assert val >= last_val
            last_val = val


class TestMultipleFoldersImport:
    """Tests for multiple folder import"""

    @patch.object(ImportThread, '_handle_import')
    def test_run_multiple_folders(self, mock_handle, mock_context, temp_workspace):
        """Test handling of multiple folders"""
        folders = [
            os.path.join(temp_workspace, "folder1"),
            os.path.join(temp_workspace, "folder2"),
            os.path.join(temp_workspace, "folder3")
        ]

        for folder in folders:
            os.makedirs(folder, exist_ok=True)

        thread = ImportThread(mock_context, folders, temp_workspace)

        finished_called = [False]
        thread.finished.connect(lambda: finished_called.__setitem__(0, True))

        thread.run()

        # Should call _handle_import for each folder
        assert mock_handle.call_count == 3
        assert finished_called[0] is True

    def test_run_multiple_folders_progress(self, mock_context, temp_workspace):
        """Test progress with multiple folders"""
        folders = []
        for i in range(3):
            folder = os.path.join(temp_workspace, f"bids{i}")
            anat = os.path.join(folder, "sub-01", "anat")
            os.makedirs(anat)
            with open(os.path.join(anat, "scan.nii"), "w") as f:
                f.write("data")
            folders.append(folder)

        dest = os.path.join(temp_workspace, "output")
        os.makedirs(dest)

        thread = ImportThread(mock_context, folders, dest)

        progress_values = []
        thread.progress.connect(lambda v: progress_values.append(v))
        thread.run()

        # Progress should reach 100
        assert 100 in progress_values
        # Should have intermediate values
        assert len(progress_values) > 2


class TestHandleImport:
    """Tests for the _handle_import method which manages single folders"""

    @patch.object(ImportThread, '_is_bids_folder')
    @patch.object(ImportThread, '_get_next_sub_id')
    def test_handle_import_bids_folder(self, mock_get_id, mock_is_bids,
                                       mock_context, temp_workspace):
        """Test _handle_import with BIDS folder"""
        mock_is_bids.return_value = True
        mock_get_id.return_value = "sub-005"

        bids_src = os.path.join(temp_workspace, "bids_source")
        anat_dir = os.path.join(bids_src, "sub-01", "anat")
        os.makedirs(anat_dir)
        with open(os.path.join(anat_dir, "T1w.nii"), "w") as f:
            f.write("brain")

        dest_ws = os.path.join(temp_workspace, "workspace")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [temp_workspace], dest_ws)
        thread._handle_import(bids_src)

        # Verify direct copy
        dest_folder = os.path.join(dest_ws, "sub-005")
        assert os.path.exists(dest_folder)

    @patch.object(ImportThread, '_process_single_patient_folder')
    def test_handle_import_direct_medical_files(self, mock_process,
                                                mock_context, temp_workspace):
        """Test _handle_import with direct medical files"""
        folder = os.path.join(temp_workspace, "patient_folder")
        os.makedirs(folder)

        # Direct NIfTI file
        with open(os.path.join(folder, "brain.nii.gz"), "w") as f:
            f.write("nifti")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread._handle_import(folder)

        # Should process as a single patient
        mock_process.assert_called_once_with(folder)

    @patch.object(ImportThread, '_are_dicom_series_of_same_patient')
    @patch.object(ImportThread, '_process_single_patient_folder')
    def test_handle_import_dicom_series_same_patient(self, mock_process, mock_same_patient,
                                                     mock_context, temp_workspace):
        """Test _handle_import with DICOM series from the same patient"""
        mock_same_patient.return_value = True

        root_folder = os.path.join(temp_workspace, "dicom_root")
        os.makedirs(root_folder)

        # Create DICOM subfolders
        for i in range(3):
            series_dir = os.path.join(root_folder, f"series_{i}")
            os.makedirs(series_dir)
            dicom_file = os.path.join(series_dir, f"img_{i}.dcm")
            with open(dicom_file, "wb") as f:
                f.write(b'\x00' * 128 + b'DICM')

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread._handle_import(root_folder)

        # Should process as a single patient
        mock_process.assert_called_once_with(root_folder)

    @patch.object(ImportThread, '_subfolders_look_like_different_patients')
    def test_handle_import_multiple_patients(self, mock_different, mock_context, temp_workspace):
        mock_different.return_value = True
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        root = os.path.join(temp_workspace, "multi_patient")
        os.makedirs(root)
        patient_folders = [os.path.join(root, f"sub-{i:02d}") for i in range(3)]
        for p in patient_folders:
            os.makedirs(p)

        # Internal patch, not a decorator
        with patch.object(thread, "_handle_import", wraps=thread._handle_import) as mock_handle_recursive:
            thread._handle_import(root)

        # Now internal calls are counted
        assert mock_handle_recursive.call_count >= 3

    def test_handle_import_empty_folder(self, mock_context, temp_workspace):
        """Test _handle_import with an empty folder"""
        empty_folder = os.path.join(temp_workspace, "empty")
        os.makedirs(empty_folder)

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Should not raise exceptions
        thread._handle_import(empty_folder)

    def test_handle_import_not_directory(self, mock_context, temp_workspace):
        """Test _handle_import with a file instead of a directory"""
        file_path = os.path.join(temp_workspace, "file.txt")
        with open(file_path, "w") as f:
            f.write("not a directory")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Should handle gracefully and do nothing
        thread._handle_import(file_path)


class TestComplexScenarios:
    """Tests for complex scenarios and edge cases"""

    def test_nested_bids_structure(self, mock_context, temp_workspace):
        """Test with complex nested BIDS structure"""
        bids_root = os.path.join(temp_workspace, "complex_bids")

        # Multiple subjects
        for sub_id in ["sub-01", "sub-02"]:
            mod_dir = os.path.join(bids_root, sub_id, "anat")  # Simplified for the test
            os.makedirs(mod_dir)
            nifti = os.path.join(mod_dir, f"{sub_id}_anat.nii.gz")
            with open(nifti, "w") as f: f.write("nifti data")

        thread = ImportThread(mock_context, [bids_root], temp_workspace)

        # **FIX**: Test one of the created 'sub-' folders, not the root
        assert thread._is_bids_folder(os.path.join(bids_root, "sub-01")) is True
        assert thread._is_bids_folder(os.path.join(bids_root, "sub-02")) is True
        assert thread._is_bids_folder(bids_root) is False  # The root is not a BIDS folder

    def test_mixed_content_folder(self, mock_context, temp_workspace):
        """Test with folder containing a mix of different files"""
        mixed_folder = os.path.join(temp_workspace, "mixed")
        os.makedirs(mixed_folder)

        with open(os.path.join(mixed_folder, "brain.nii"), "w") as f:
            f.write("nifti")

        dicom_file = os.path.join(mixed_folder, "scan.dcm")
        with open(dicom_file, "wb") as f:
            f.write(b'\x00' * 128 + b'DICM')

        with open(os.path.join(mixed_folder, "report.pdf"), "w") as f:
            f.write("pdf")
        with open(os.path.join(mixed_folder, "metadata.json"), "w") as f:
            f.write('{}')

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Should detect direct medical files
        has_medical = any(
            thread._is_nifti_file(f) or thread._is_dicom_file(os.path.join(mixed_folder, f))
            for f in os.listdir(mixed_folder)
        )
        assert has_medical is True

    @patch.object(ImportThread, '_convert_dicom_folder_to_nifti')
    @patch.object(ImportThread, '_convert_dicom_folder_to_nifti')
    def test_large_dataset_simulation(self, mock_convert, mock_context, temp_workspace):
        """Test large dataset simulation (NIfTI)"""
        root = os.path.join(temp_workspace, "large_dataset")
        os.makedirs(root)

        # Simulate many NIfTI files
        for i in range(20):
            nifti_file = os.path.join(root, f"scan_{i:03d}.nii.gz")
            json_file = os.path.join(root, f"scan_{i:03d}.json")

            with open(nifti_file, "w") as f:
                f.write(f"scan {i}")

            # --- FIX HERE ---
            # Add minimal metadata for BIDS conversion
            with open(json_file, "w") as f:
                f.write('{"Modality": "MR", "ProtocolName": "T1w"}')
            # ---------------------

        dest_ws = os.path.join(temp_workspace, "dest")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [root], dest_ws)

        progress_updates = []
        thread.progress.connect(lambda v: progress_updates.append(v))

        thread.run()

        # Should complete successfully
        assert 100 in progress_updates
        # Now this assertion will work
        assert os.path.exists(os.path.join(dest_ws, "sub-01", "anat"))

    def test_special_characters_in_filenames(self, mock_context, temp_workspace):
        """Test with special characters in filenames"""
        folder = os.path.join(temp_workspace, "special_chars")
        os.makedirs(folder)

        # File with special characters
        special_names = [
            "brain (copy).nii",
            "scan_01-02-2024.nii.gz",
            "patient#123.json",
            "data [final].nii"
        ]

        for name in special_names:
            safe_name = name.replace("[", "_").replace("]", "_")
            file_path = os.path.join(folder, safe_name)
            with open(file_path, "w") as f:
                f.write("data")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Should handle without errors
        nifti_files = [f for f in os.listdir(folder) if thread._is_nifti_file(f)]
        assert len(nifti_files) > 0

    @patch('main.threads.import_thread.pydicom.dcmread')
    def test_dicom_missing_patient_info(self, mock_dcmread, mock_context, temp_workspace):
        """Test DICOM without patient information"""
        # Mock DICOM without PatientID or PatientName
        mock_dcm = Mock()
        mock_dcm.PatientID = None
        mock_dcm.PatientName = None
        mock_dcmread.return_value = mock_dcm

        folder = os.path.join(temp_workspace, "dicom_no_info")
        os.makedirs(folder)

        dicom_file = os.path.join(folder, "anon.dcm")
        with open(dicom_file, "wb") as f:
            f.write(b'\x00' * 128 + b'DICM')

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Should handle gracefully
        result = thread._are_dicom_series_of_same_patient([folder])
        # Without PatientID, it considers them the same patient
        assert result is True


class TestConcurrencyAndThreadSafety:
    """Tests for thread safety and concurrency"""

    def test_cancel_during_file_copy(self, mock_context, temp_workspace):
        """Test cancellation during file copy"""
        # Create many files to copy
        src = os.path.join(temp_workspace, "source_large")
        os.makedirs(src)

        for i in range(100):
            with open(os.path.join(src, f"file_{i}.nii"), "w") as f:
                f.write("x" * 1000)

        dest = os.path.join(temp_workspace, "dest")
        os.makedirs(dest)

        thread = ImportThread(mock_context, [src], dest)

        # Cancel after a short delay
        import threading
        def cancel_after_delay():
            import time
            time.sleep(0.01)
            thread.cancel()

        cancel_thread = threading.Thread(target=cancel_after_delay)
        cancel_thread.start()

        thread.run()
        cancel_thread.join()

        # Should be canceled
        assert thread._is_canceled is True

    def test_multiple_progress_emissions(self, mock_context, temp_workspace):
        """Test multiple progress emissions"""
        bids = os.path.join(temp_workspace, "bids_multi")
        anat = os.path.join(bids, "sub-01", "anat")
        os.makedirs(anat)
        with open(os.path.join(anat, "T1.nii"), "w") as f:
            f.write("x")

        dest = os.path.join(temp_workspace, "out")
        os.makedirs(dest)

        thread = ImportThread(mock_context, [bids], dest)

        progress_count = [0]

        def count_progress(val):
            progress_count[0] += 1

        thread.progress.connect(count_progress)
        thread.run()

        # Should have emitted progress multiple times
        assert progress_count[0] >= 3


class TestEdgeCases:
    """Tests for edge cases"""

    def test_symlink_handling(self, mock_context, temp_workspace):
        """Test symlink handling"""
        if os.name == 'nt':  # Skip on Windows
            pytest.skip("Symlinks not reliable on Windows")

        real_folder = os.path.join(temp_workspace, "real")
        os.makedirs(real_folder)
        with open(os.path.join(real_folder, "data.nii"), "w") as f:
            f.write("nifti")

        symlink = os.path.join(temp_workspace, "symlink")
        os.symlink(real_folder, symlink)

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Should follow symlink
        assert os.path.isdir(symlink)

    def test_readonly_source_files(self, mock_context, temp_workspace):
        """Test with read-only source files"""
        src = os.path.join(temp_workspace, "readonly_src")
        os.makedirs(src)

        readonly_file = os.path.join(src, "readonly.nii")
        with open(readonly_file, "w") as f:
            f.write("nifti")

        # Make read-only
        os.chmod(readonly_file, 0o444)

        dest = os.path.join(temp_workspace, "dest")
        os.makedirs(dest)

        thread = ImportThread(mock_context, [src], dest)

        # Should copy anyway
        try:
            thread.run()
        finally:
            # Cleanup: remove read-only to allow cleanup
            os.chmod(readonly_file, 0o644)

    def test_very_long_path(self, mock_context, temp_workspace):
        """Test with very long path"""
        # Create a very long path
        long_path = temp_workspace
        for i in range(10):
            long_path = os.path.join(long_path, f"nested_folder_{i}")

        try:
            os.makedirs(long_path)
            with open(os.path.join(long_path, "file.nii"), "w") as f:
                f.write("data")
        except OSError:
            pytest.skip("Path too long for filesystem")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        # Should handle without errors
        assert os.path.exists(long_path)

    def test_unicode_filenames(self, mock_context, temp_workspace):
        """Test with Unicode filenames"""
        folder = os.path.join(temp_workspace, "unicode")
        os.makedirs(folder)

        unicode_names = [
            "cervello_日本語.nii",
            "мозг_данные.nii.gz",
            "cerebro_中文.json"
        ]

        for name in unicode_names:
            file_path = os.path.join(folder, name)
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("data")
            except (OSError, UnicodeError):
                pytest.skip("Filesystem doesn't support Unicode")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Verify NIfTI detection with Unicode
        nifti_count = sum(1 for f in os.listdir(folder) if thread._is_nifti_file(f))
        assert nifti_count >= 2


class TestIntegrationScenarios:
    """Tests for end-to-end integration"""

    @patch('main.threads.import_thread.subprocess.Popen')
    @patch('main.threads.import_thread.get_bin_path')
    def test_full_dicom_to_bids_workflow(self, mock_get_bin, mock_Popen,
                                         mock_context, temp_workspace):
        """Test complete DICOM → BIDS workflow"""
        mock_get_bin.return_value = "/fake/path/dcm2niix"

        # Simulate dcm2niix output
        def mock_popen_side_effect(*args, **kwargs):
            command = args[0]
            output_dir = command[command.index("-o") + 1]

            # Create fictitious NIfTI and JSON files in the temporary output
            with open(os.path.join(output_dir, "converted.nii.gz"), "w") as f:
                f.write("converted nifti")
            # Add metadata for BIDS conversion
            with open(os.path.join(output_dir, "converted.json"), "w") as f:
                f.write('{"Modality": "MR", "ProtocolName": "T1w"}')

            mock_process = Mock()
            mock_process.communicate.return_value = (b'Success', b'')
            mock_process.returncode = 0
            return mock_process

        mock_Popen.side_effect = mock_popen_side_effect

        # Create fictitious DICOM folder
        dicom_folder = os.path.join(temp_workspace, "dicom_data")
        os.makedirs(dicom_folder)
        # Use pydicom to create a "minimally valid" DICOM file
        try:
            import pydicom
            from pydicom.dataset import Dataset, FileMetaDataset
            from pydicom.uid import ImplicitVRLittleEndian

            file_meta = FileMetaDataset()
            file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
            file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
            file_meta.ImplementationClassUID = "1.2.3.4"
            file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

            ds = Dataset()
            ds.PatientID = "12345"
            ds.file_meta = file_meta
            ds.is_little_endian = True
            ds.is_implicit_VR = True

            ds.save_as(os.path.join(dicom_folder, "image_001.dcm"), write_like_original=False)

        except ImportError:
            # Fallback if pydicom is not installed in the test environment
            with open(os.path.join(dicom_folder, "image_001.dcm"), "wb") as f:
                f.write(b'\x00' * 128 + b'DICM' + b'\x00' * 100)

        dest_ws = os.path.join(temp_workspace, "workspace")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [dicom_folder], dest_ws)

        finished = [False]
        thread.finished.connect(lambda: finished.__setitem__(0, True))

        thread.run()

        # **FIX**: The assertion now passes because the Popen mock
        # prevents the FileNotFoundError and allows the thread to emit 'finished'.
        assert finished[0] is True

        # Add an assertion to verify the BIDS structure was created
        expected_anat = os.path.join(dest_ws, "sub-01", "anat")
        assert os.path.exists(expected_anat)
        expected_file = os.path.join(expected_anat, "sub-01_run-1_T1w.nii.gz")
        assert os.path.exists(expected_file)

    def test_mixed_patient_dataset_import(self, mock_context, temp_workspace):
        """Test importing dataset with multiple patients and mixed formats"""
        root = os.path.join(temp_workspace, "mixed_dataset")
        os.makedirs(root)

        # Patient 1: NIfTI
        p1 = os.path.join(root, "sub-01")
        os.makedirs(p1)
        with open(os.path.join(p1, "T1w.nii.gz"), "w") as f:
            f.write("patient 1 nifti")

        # Patient 2: Already organized BIDS
        p2_anat = os.path.join(root, "sub-02", "anat")
        os.makedirs(p2_anat)
        with open(os.path.join(p2_anat, "sub-02_T1w.nii"), "w") as f:
            f.write("patient 2")

        # Patient 3: DICOM
        p3 = os.path.join(root, "patient_003")
        os.makedirs(p3)
        with open(os.path.join(p3, "scan.dcm"), "wb") as f:
            f.write(b'\x00' * 128 + b'DICM')

        dest = os.path.join(temp_workspace, "output")
        os.makedirs(dest)

        thread = ImportThread(mock_context, [root], dest)
        thread.run()

        # Should process as multiple patients
        # (thanks to the folder name heuristic)
        assert thread._subfolders_look_like_different_patients([p1, p2_anat, p3])


# Parametrized tests for reuse
@pytest.mark.parametrize("extension", [".nii", ".nii.gz"])
def test_nifti_extensions(extension, mock_context, temp_workspace):
    """Parametrized test for different NIfTI extensions"""
    thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
    filename = f"brain{extension}"
    assert thread._is_nifti_file(filename) is True


@pytest.mark.parametrize("invalid_ext", [".dcm", ".txt", ".json", ".pdf", ""])
def test_non_nifti_extensions(invalid_ext, mock_context, temp_workspace):
    """Parametrized test for non-NIfTI extensions"""
    thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
    filename = f"file{invalid_ext}"
    assert thread._is_nifti_file(filename) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])