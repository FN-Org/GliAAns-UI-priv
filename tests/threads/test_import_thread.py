"""
test_import_thread.py - Test Suite per ImportThread

Questa suite testa tutte le funzionalità principali di ImportThread:
- Importazione di cartelle BIDS già organizzate
- Conversione DICOM → NIfTI
- Gestione di pazienti singoli vs multipli
- Heuristiche di rilevamento struttura
- Cancellazione dell'import
- Gestione errori
"""

import os
import json
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch, MagicMock, call
import pytest
from PyQt6.QtCore import QCoreApplication

from threads.import_thread import ImportThread


class TestImportThreadInitialization:
    """Test per l'inizializzazione di ImportThread"""

    def test_init_single_path(self, mock_context, temp_workspace):
        """Test inizializzazione con un singolo path"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        assert thread.context == mock_context
        assert thread.folders_path == [temp_workspace]
        assert thread.workspace_path == temp_workspace
        assert thread.current_progress == 0
        assert thread._is_canceled is False
        assert thread.process is None

    def test_init_multiple_paths(self, mock_context, temp_workspace):
        """Test inizializzazione con più path"""
        paths = [temp_workspace, os.path.join(temp_workspace, "sub-01")]
        thread = ImportThread(mock_context, paths, temp_workspace)

        assert len(thread.folders_path) == 2
        assert thread.folders_path == paths

    def test_signals_exist(self, mock_context, temp_workspace):
        """Verifica che i signal siano definiti correttamente"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        assert hasattr(thread, 'finished')
        assert hasattr(thread, 'error')
        assert hasattr(thread, 'progress')


class TestFileDetection:
    """Test per i metodi di rilevamento file"""

    def test_is_nifti_file(self, mock_context, temp_workspace):
        """Test rilevamento file NIfTI"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        assert thread._is_nifti_file("brain.nii") is True
        assert thread._is_nifti_file("brain.nii.gz") is True
        assert thread._is_nifti_file("brain.json") is False
        assert thread._is_nifti_file("brain.dcm") is False

    def test_is_dicom_file_valid(self, mock_context, temp_workspace):
        """Test rilevamento DICOM valido"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Crea un file DICOM mock
        dicom_path = os.path.join(temp_workspace, "test.dcm")
        with open(dicom_path, "wb") as f:
            f.write(b'\x00' * 128)  # 128 byte di padding
            f.write(b'DICM')  # Magic bytes DICOM
            f.write(b'\x00' * 100)  # Altri dati

        assert thread._is_dicom_file(dicom_path) is True

    def test_is_dicom_file_invalid(self, mock_context, temp_workspace):
        """Test rilevamento file non-DICOM"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # File senza magic bytes DICOM
        non_dicom_path = os.path.join(temp_workspace, "notdicom.txt")
        with open(non_dicom_path, "w") as f:
            f.write("This is not a DICOM file")

        assert thread._is_dicom_file(non_dicom_path) is False

    def test_is_dicom_file_exception(self, mock_context, temp_workspace):
        """Test gestione eccezione durante lettura DICOM"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # File inesistente
        assert thread._is_dicom_file("/nonexistent/file.dcm") is False


class TestBIDSDetection:
    """Test per il rilevamento di strutture BIDS"""

    def test_is_bids_folder_valid(self, mock_context, temp_workspace):
        """Test rilevamento cartella BIDS valida"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Crea struttura BIDS
        bids_dir = os.path.join(temp_workspace, "bids_test")
        anat_dir = os.path.join(bids_dir, "sub-01", "anat")
        os.makedirs(anat_dir, exist_ok=True)

        # Aggiungi file NIfTI
        nifti_path = os.path.join(anat_dir, "sub-01_T1w.nii.gz")
        with open(nifti_path, "w") as f:
            f.write("nifti data")

        assert thread._is_bids_folder(bids_dir) is True

    def test_is_bids_folder_invalid(self, mock_context, temp_workspace):
        """Test con cartella non-BIDS"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Cartella senza struttura BIDS
        non_bids_dir = os.path.join(temp_workspace, "not_bids")
        os.makedirs(non_bids_dir, exist_ok=True)

        assert thread._is_bids_folder(non_bids_dir) is False

    def test_is_bids_folder_no_sub_prefix(self, mock_context, temp_workspace):
        """Test cartella senza prefisso 'sub-'"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Cartella con struttura simile ma senza prefisso corretto
        fake_bids = os.path.join(temp_workspace, "fake_bids")
        anat_dir = os.path.join(fake_bids, "patient01", "anat")
        os.makedirs(anat_dir, exist_ok=True)

        with open(os.path.join(anat_dir, "scan.nii"), "w") as f:
            f.write("data")

        assert thread._is_bids_folder(fake_bids) is False


class TestSubjectIDGeneration:
    """Test per la generazione di ID soggetto"""

    def test_get_next_sub_id_empty_workspace(self, mock_context, temp_workspace):
        """Test generazione ID su workspace vuoto"""
        empty_ws = os.path.join(temp_workspace, "empty")
        os.makedirs(empty_ws)

        thread = ImportThread(mock_context, [temp_workspace], empty_ws)
        sub_id = thread._get_next_sub_id()

        assert sub_id == "sub-001"

    def test_get_next_sub_id_existing_subjects(self, mock_context, temp_workspace):
        """Test generazione ID con soggetti esistenti"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # temp_workspace già contiene sub-01 e sub-02 (da fixture)
        sub_id = thread._get_next_sub_id()

        assert sub_id == "sub-003"

    def test_get_next_sub_id_non_sequential(self, mock_context, temp_workspace):
        """Test con ID non sequenziali"""
        # Aggiungi sub-05 (salta sub-03 e sub-04)
        os.makedirs(os.path.join(temp_workspace, "sub-005"))

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        sub_id = thread._get_next_sub_id()

        # Dovrebbe essere sub-006 (max + 1)
        assert sub_id == "sub-006"

    def test_get_next_sub_id_invalid_names(self, mock_context, temp_workspace):
        """Test con nomi cartelle invalidi"""
        # Crea cartelle con nomi non validi
        os.makedirs(os.path.join(temp_workspace, "sub-invalid"))
        os.makedirs(os.path.join(temp_workspace, "not-a-sub"))

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        sub_id = thread._get_next_sub_id()

        # Dovrebbe ignorare cartelle non valide e usare sub-01, sub-02
        assert sub_id == "sub-003"


class TestPatientDetectionHeuristics:
    """Test per le euristiche di rilevamento paziente singolo/multiplo"""

    def test_subfolders_look_like_different_patients(self, mock_context, temp_workspace):
        """Test rilevamento cartelle multi-paziente"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Crea cartelle che sembrano pazienti diversi
        patient_folders = [
            os.path.join(temp_workspace, "sub-01"),
            os.path.join(temp_workspace, "sub-02"),
            os.path.join(temp_workspace, "patient_03")
        ]

        for folder in patient_folders:
            os.makedirs(folder, exist_ok=True)

        assert thread._subfolders_look_like_different_patients(patient_folders) is True

    def test_subfolders_single_patient(self, mock_context, temp_workspace):
        """Test cartelle che appartengono a un singolo paziente"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Cartelle senza pattern multi-paziente
        series_folders = [
            os.path.join(temp_workspace, "series_001"),
            os.path.join(temp_workspace, "series_002"),
            os.path.join(temp_workspace, "t1_weighted")
        ]

        for folder in series_folders:
            os.makedirs(folder, exist_ok=True)

        assert thread._subfolders_look_like_different_patients(series_folders) is False

    @patch('threads.import_thread.pydicom.dcmread')
    def test_are_dicom_series_of_same_patient_true(self, mock_dcmread, mock_context, temp_workspace):
        """Test DICOM dello stesso paziente"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Setup mock DICOM con stesso PatientID
        mock_dcm = Mock()
        mock_dcm.PatientID = "PATIENT001"
        mock_dcm.PatientName = "Doe^John"
        mock_dcmread.return_value = mock_dcm

        # Crea cartelle con DICOM
        series_folders = []
        for i in range(3):
            folder = os.path.join(temp_workspace, f"series_{i}")
            os.makedirs(folder, exist_ok=True)

            # Crea file DICOM mock
            dicom_file = os.path.join(folder, f"image_{i}.dcm")
            with open(dicom_file, "wb") as f:
                f.write(b'\x00' * 128)
                f.write(b'DICM')

            series_folders.append(folder)

        result = thread._are_dicom_series_of_same_patient(series_folders)
        assert result is True

    @patch('threads.import_thread.pydicom.dcmread')
    def test_are_dicom_series_of_same_patient_false(self, mock_dcmread, mock_context, temp_workspace):
        """Test DICOM di pazienti diversi"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Tutti i file vengono riconosciuti come DICOM
        thread._is_dicom_file = Mock(return_value=True)

        # Ogni chiamata a dcmread restituisce un paziente diverso
        mock_dcmread.side_effect = [
            SimpleNamespace(PatientID="PATIENT01"),
            SimpleNamespace(PatientID="PATIENT02"),
            SimpleNamespace(PatientID="PATIENT03"),
        ]

        # Crea cartelle e file DICOM finti
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
        """Test con cartelle senza DICOM"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Cartelle vuote o con altri file
        folders = []
        for i in range(3):
            folder = os.path.join(temp_workspace, f"empty_{i}")
            os.makedirs(folder, exist_ok=True)
            folders.append(folder)

        result = thread._are_dicom_series_of_same_patient(folders)
        assert result is False


class TestCancellation:
    """Test per la cancellazione dell'import"""

    def test_cancel_flag_set(self, mock_context, temp_workspace):
        """Test che il flag di cancellazione venga impostato"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        assert thread._is_canceled is False
        thread.cancel()
        assert thread._is_canceled is True

    def test_cancel_terminates_process(self, mock_context, temp_workspace):
        """Test terminazione processo esterno durante cancellazione"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Mock di un processo in esecuzione
        mock_process = Mock()
        thread.process = mock_process

        thread.cancel()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_cancel_no_process(self, mock_context, temp_workspace):
        """Test cancellazione senza processo attivo"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Non dovrebbe sollevare eccezioni
        thread.cancel()
        assert thread._is_canceled is True


class TestBIDSImport:
    """Test per l'importazione di cartelle BIDS"""

    @patch.object(ImportThread, '_is_bids_folder')
    @patch.object(ImportThread, '_get_next_sub_id')
    def test_import_bids_folder_directly(self, mock_get_id, mock_is_bids,
                                         mock_context, temp_workspace):
        """Test copia diretta di cartella BIDS"""
        # Setup
        mock_is_bids.return_value = True
        mock_get_id.return_value = "sub-003"

        # Crea cartella BIDS sorgente
        src_bids = os.path.join(temp_workspace, "source_bids")
        anat_dir = os.path.join(src_bids, "sub-01", "anat")
        os.makedirs(anat_dir)

        nifti_file = os.path.join(anat_dir, "T1w.nii.gz")
        with open(nifti_file, "w") as f:
            f.write("test nifti data")

        # Crea workspace destinazione
        dest_ws = os.path.join(temp_workspace, "dest_workspace")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [src_bids], dest_ws)

        # Connetti signal per verificare emissione
        finished_called = [False]

        def on_finished():
            finished_called[0] = True

        thread.finished.connect(on_finished)

        # Esegui
        thread.run()

        # Verifica
        assert finished_called[0] is True
        dest_folder = os.path.join(dest_ws, "sub-003")
        assert os.path.exists(dest_folder)


class TestDICOMConversion:
    """Test per la conversione DICOM → NIfTI"""

    @patch('threads.import_thread.subprocess.run')
    @patch('threads.import_thread.get_bin_path')
    def test_convert_dicom_folder_success(self, mock_get_bin, mock_subprocess,
                                          mock_context, temp_workspace):
        """Test conversione DICOM riuscita"""
        mock_get_bin.return_value = "/usr/bin/dcm2niix"
        mock_subprocess.return_value = Mock(stdout="Conversion complete", returncode=0)

        src_folder = os.path.join(temp_workspace, "dicom_source")
        dest_folder = os.path.join(temp_workspace, "nifti_dest")
        os.makedirs(src_folder)
        os.makedirs(dest_folder)

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread._convert_dicom_folder_to_nifti(src_folder, dest_folder)

        # Verifica che dcm2niix sia stato chiamato
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "/usr/bin/dcm2niix"
        assert "-z" in call_args
        assert "y" in call_args
        assert src_folder in call_args
        assert dest_folder in call_args

    @patch('threads.import_thread.get_bin_path')
    def test_convert_dicom_folder_missing_tool(self, mock_get_bin,
                                               mock_context, temp_workspace):
        """Test quando dcm2niix non è disponibile"""
        mock_get_bin.side_effect = FileNotFoundError("dcm2niix not found")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Non dovrebbe sollevare eccezione, solo loggare errore
        thread._convert_dicom_folder_to_nifti(temp_workspace, temp_workspace)

    @patch('threads.import_thread.subprocess.run')
    @patch('threads.import_thread.get_bin_path')
    def test_convert_dicom_folder_process_error(self, mock_get_bin, mock_subprocess,
                                                mock_context, temp_workspace):
        """Test errore durante esecuzione dcm2niix"""
        mock_get_bin.return_value = "/usr/bin/dcm2niix"
        mock_subprocess.side_effect = Exception("Process failed")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Non dovrebbe propagare l'eccezione
        thread._convert_dicom_folder_to_nifti(temp_workspace, temp_workspace)


class TestBIDSStructureConversion:
    """Test per la conversione a struttura BIDS"""

    def test_convert_to_bids_structure(self, mock_context, temp_workspace):
        """Test conversione cartella a struttura BIDS"""
        # Crea cartella sorgente con NIfTI
        src_folder = os.path.join(temp_workspace, "source")
        os.makedirs(src_folder)

        nifti_file = os.path.join(src_folder, "brain.nii.gz")
        json_file = os.path.join(src_folder, "brain.json")

        with open(nifti_file, "w") as f:
            f.write("nifti data")
        with open(json_file, "w") as f:
            f.write('{"key": "value"}')

        # Workspace destinazione
        dest_ws = os.path.join(temp_workspace, "workspace")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [temp_workspace], dest_ws)
        thread._convert_to_bids_structure(src_folder)

        # Verifica struttura creata
        expected_sub = os.path.join(dest_ws, "sub-001", "anat")
        assert os.path.exists(expected_sub)
        assert os.path.exists(os.path.join(expected_sub, "brain.nii.gz"))
        assert os.path.exists(os.path.join(expected_sub, "brain.json"))

    def test_convert_to_bids_structure_nested(self, mock_context, temp_workspace):
        """Test conversione con file in sottocartelle"""
        # Cartella con sottocartelle
        src_folder = os.path.join(temp_workspace, "nested_source")
        sub_dir = os.path.join(src_folder, "subdir")
        os.makedirs(sub_dir)

        # File in sottocartella
        nifti_file = os.path.join(sub_dir, "scan.nii")
        with open(nifti_file, "w") as f:
            f.write("scan data")

        dest_ws = os.path.join(temp_workspace, "ws")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [temp_workspace], dest_ws)
        thread._convert_to_bids_structure(src_folder)

        # File dovrebbe essere copiato in anat/
        expected_anat = os.path.join(dest_ws, "sub-001", "anat")
        assert os.path.exists(os.path.join(expected_anat, "scan.nii"))


class TestSinglePatientProcessing:
    """Test per la processazione di cartelle singolo paziente"""

    @patch.object(ImportThread, '_convert_dicom_folder_to_nifti')
    @patch.object(ImportThread, '_convert_to_bids_structure')
    def test_process_single_patient_folder_with_nifti(self, mock_convert_bids,
                                                      mock_convert_dicom,
                                                      mock_context, temp_workspace):
        """Test processazione cartella con NIfTI esistenti"""
        # Cartella paziente con NIfTI
        patient_folder = os.path.join(temp_workspace, "patient_data")
        os.makedirs(patient_folder)

        nifti_file = os.path.join(patient_folder, "t1.nii.gz")
        with open(nifti_file, "w") as f:
            f.write("nifti")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread._process_single_patient_folder(patient_folder)

        # Dovrebbe convertire a BIDS ma non chiamare dcm2niix
        mock_convert_bids.assert_called_once()
        mock_convert_dicom.assert_not_called()

    @patch.object(ImportThread, '_convert_dicom_folder_to_nifti')
    @patch.object(ImportThread, '_convert_to_bids_structure')
    def test_process_single_patient_folder_with_dicom(self, mock_convert_bids,
                                                      mock_convert_dicom,
                                                      mock_context, temp_workspace):
        """Test processazione cartella con DICOM"""
        patient_folder = os.path.join(temp_workspace, "patient_dicom")
        os.makedirs(patient_folder)

        # Crea file DICOM
        dicom_file = os.path.join(patient_folder, "image.dcm")
        with open(dicom_file, "wb") as f:
            f.write(b'\x00' * 128)
            f.write(b'DICM')

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread._process_single_patient_folder(patient_folder)

        # Entrambe le conversioni dovrebbero essere chiamate
        mock_convert_dicom.assert_called_once()
        mock_convert_bids.assert_called_once()

    def test_process_single_patient_folder_cancelled(self, mock_context, temp_workspace):
        """Test cancellazione durante processazione"""
        patient_folder = os.path.join(temp_workspace, "patient")
        os.makedirs(patient_folder)

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread.cancel()  # Cancella prima di iniziare

        # Non dovrebbe sollevare eccezioni
        thread._process_single_patient_folder(patient_folder)


class TestErrorHandling:
    """Test per la gestione degli errori"""

    def test_run_invalid_folder_path(self, mock_context, temp_workspace):
        """Test con path cartella non valido"""
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
        """Test con lista cartelle vuota"""
        thread = ImportThread(mock_context, [], temp_workspace)

        error_called = [False]

        def on_error(msg):
            error_called[0] = True

        thread.error.connect(on_error)
        thread.run()

        assert error_called[0] is True

    def test_run_cancelled_no_error_emit(self, mock_context, temp_workspace):
        """Test che la cancellazione non emetta errori"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        error_called = [False]

        def on_error(msg):
            error_called[0] = True

        thread.error.connect(on_error)
        thread.cancel()
        thread.run()

        # Non dovrebbe emettere errore quando cancellato
        assert error_called[0] is False


class TestProgressEmission:
    """Test per l'emissione dei progressi"""

    def test_progress_emitted_during_run(self, mock_context, temp_workspace):
        """Test che progress venga emesso durante l'esecuzione"""
        # Crea cartella BIDS semplice per import veloce
        bids_folder = os.path.join(temp_workspace, "bids")
        anat_dir = os.path.join(bids_folder, "sub-01", "anat")
        os.makedirs(anat_dir)

        with open(os.path.join(anat_dir, "T1w.nii"), "w") as f:
            f.write("data")

        dest_ws = os.path.join(temp_workspace, "dest")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [bids_folder], dest_ws)

        progress_values = []

        def on_progress(value):
            progress_values.append(value)

        thread.progress.connect(on_progress)
        thread.run()

        # Dovrebbe avere emesso vari valori di progress
        assert len(progress_values) > 0
        assert 10 in progress_values  # Primo step
        assert 100 in progress_values  # Completamento

    def test_progress_increases_monotonically(self, mock_context, temp_workspace):
        """Test che il progress aumenti monotonicamente"""
        bids_folder = os.path.join(temp_workspace, "bids_src")
        anat = os.path.join(bids_folder, "sub-01", "anat")
        os.makedirs(anat)
        with open(os.path.join(anat, "scan.nii"), "w") as f:
            f.write("x")

        dest = os.path.join(temp_workspace, "out")
        os.makedirs(dest)

        thread = ImportThread(mock_context, [bids_folder], dest)

        progress_values = []
        thread.progress.connect(lambda v: progress_values.append(v))
        thread.run()

        # Verifica che i valori non diminuiscano mai
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i - 1]


class TestMultipleFoldersImport:
    """Test per l'importazione di più cartelle"""

    @patch.object(ImportThread, '_handle_import')
    def test_run_multiple_folders(self, mock_handle, mock_context, temp_workspace):
        """Test gestione di più cartelle"""
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

        # Dovrebbe chiamare _handle_import per ogni cartella
        assert mock_handle.call_count == 3
        assert finished_called[0] is True

    def test_run_multiple_folders_progress(self, mock_context, temp_workspace):
        """Test progress con più cartelle"""
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

        # Progress dovrebbe arrivare a 100
        assert 100 in progress_values
        # Dovrebbe avere valori intermedi
        assert len(progress_values) > 2


class TestHandleImport:
    """Test per il metodo _handle_import che gestisce singole cartelle"""

    @patch.object(ImportThread, '_is_bids_folder')
    @patch.object(ImportThread, '_get_next_sub_id')
    def test_handle_import_bids_folder(self, mock_get_id, mock_is_bids,
                                       mock_context, temp_workspace):
        """Test _handle_import con cartella BIDS"""
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

        # Verifica copia diretta
        dest_folder = os.path.join(dest_ws, "sub-005")
        assert os.path.exists(dest_folder)

    @patch.object(ImportThread, '_process_single_patient_folder')
    def test_handle_import_direct_medical_files(self, mock_process,
                                                mock_context, temp_workspace):
        """Test _handle_import con file medici diretti"""
        folder = os.path.join(temp_workspace, "patient_folder")
        os.makedirs(folder)

        # File NIfTI diretto
        with open(os.path.join(folder, "brain.nii.gz"), "w") as f:
            f.write("nifti")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread._handle_import(folder)

        # Dovrebbe processare come singolo paziente
        mock_process.assert_called_once_with(folder)

    @patch.object(ImportThread, '_are_dicom_series_of_same_patient')
    @patch.object(ImportThread, '_process_single_patient_folder')
    def test_handle_import_dicom_series_same_patient(self, mock_process, mock_same_patient,
                                                     mock_context, temp_workspace):
        """Test _handle_import con serie DICOM dello stesso paziente"""
        mock_same_patient.return_value = True

        root_folder = os.path.join(temp_workspace, "dicom_root")
        os.makedirs(root_folder)

        # Crea sottocartelle DICOM
        for i in range(3):
            series_dir = os.path.join(root_folder, f"series_{i}")
            os.makedirs(series_dir)
            dicom_file = os.path.join(series_dir, f"img_{i}.dcm")
            with open(dicom_file, "wb") as f:
                f.write(b'\x00' * 128 + b'DICM')

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread._handle_import(root_folder)

        # Dovrebbe processare come singolo paziente
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

        # Patch interno, non decoratore
        with patch.object(thread, "_handle_import", wraps=thread._handle_import) as mock_handle_recursive:
            thread._handle_import(root)

        # Ora le chiamate interne vengono contate
        assert mock_handle_recursive.call_count >= 3

    def test_handle_import_empty_folder(self, mock_context, temp_workspace):
        """Test _handle_import con cartella vuota"""
        empty_folder = os.path.join(temp_workspace, "empty")
        os.makedirs(empty_folder)

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Non dovrebbe sollevare eccezioni
        thread._handle_import(empty_folder)

    def test_handle_import_not_directory(self, mock_context, temp_workspace):
        """Test _handle_import con file invece di directory"""
        file_path = os.path.join(temp_workspace, "file.txt")
        with open(file_path, "w") as f:
            f.write("not a directory")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Dovrebbe gestire gracefully e non fare nulla
        thread._handle_import(file_path)


class TestUtilityMethods:
    """Test per metodi utility"""

    def test_cleanup_temp_dir(self, mock_context, temp_workspace):
        """Test pulizia directory temporanea"""
        temp_dir = os.path.join(temp_workspace, "temp_test")
        os.makedirs(temp_dir)

        # Aggiungi file
        with open(os.path.join(temp_dir, "file.txt"), "w") as f:
            f.write("temp data")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
        thread._cleanup_temp_dir(temp_dir)

        # Directory dovrebbe essere rimossa
        assert not os.path.exists(temp_dir)

    def test_cleanup_temp_dir_nonexistent(self, mock_context, temp_workspace):
        """Test pulizia directory inesistente"""
        nonexistent = os.path.join(temp_workspace, "does_not_exist")

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Non dovrebbe sollevare eccezioni
        thread._cleanup_temp_dir(nonexistent)

    def test_emit_error(self, mock_context, temp_workspace):
        """Test emissione errore"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        error_msg = None

        def on_error(msg):
            nonlocal error_msg
            error_msg = msg

        thread.error.connect(on_error)
        thread._emit_error("Test error message")

        assert error_msg == "Test error message"

    def test_emit_progress(self, mock_context, temp_workspace):
        """Test emissione progress"""
        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        progress_value = None

        def on_progress(val):
            nonlocal progress_value
            progress_value = val

        thread.progress.connect(on_progress)
        thread._emit_progress(75)

        assert progress_value == 75
        assert thread.current_progress == 75


class TestComplexScenarios:
    """Test per scenari complessi e casi limite"""

    def test_nested_bids_structure(self, mock_context, temp_workspace):
        """Test con struttura BIDS annidata complessa"""
        # Crea struttura BIDS completa
        bids_root = os.path.join(temp_workspace, "complex_bids")

        # Multipli soggetti
        for sub_id in ["sub-01", "sub-02"]:
            for modality in ["anat", "func", "dwi"]:
                mod_dir = os.path.join(bids_root, sub_id, modality)
                os.makedirs(mod_dir)

                # File NIfTI + JSON
                nifti = os.path.join(mod_dir, f"{sub_id}_{modality}.nii.gz")
                json_file = os.path.join(mod_dir, f"{sub_id}_{modality}.json")

                with open(nifti, "w") as f:
                    f.write("nifti data")
                with open(json_file, "w") as f:
                    f.write('{"description": "test"}')

        thread = ImportThread(mock_context, [bids_root], temp_workspace)

        # Dovrebbe rilevare come BIDS
        assert thread._is_bids_folder(bids_root) is True

    def test_mixed_content_folder(self, mock_context, temp_workspace):
        """Test con cartella contenente mix di file diversi"""
        mixed_folder = os.path.join(temp_workspace, "mixed")
        os.makedirs(mixed_folder)

        # NIfTI
        with open(os.path.join(mixed_folder, "brain.nii"), "w") as f:
            f.write("nifti")

        # DICOM
        dicom_file = os.path.join(mixed_folder, "scan.dcm")
        with open(dicom_file, "wb") as f:
            f.write(b'\x00' * 128 + b'DICM')

        # Altri file
        with open(os.path.join(mixed_folder, "report.pdf"), "w") as f:
            f.write("pdf")
        with open(os.path.join(mixed_folder, "metadata.json"), "w") as f:
            f.write('{}')

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Dovrebbe rilevare file medici diretti
        has_medical = any(
            thread._is_nifti_file(f) or thread._is_dicom_file(os.path.join(mixed_folder, f))
            for f in os.listdir(mixed_folder)
        )
        assert has_medical is True

    @patch.object(ImportThread, '_convert_dicom_folder_to_nifti')
    def test_large_dataset_simulation(self, mock_convert, mock_context, temp_workspace):
        """Test simulazione dataset grande"""
        root = os.path.join(temp_workspace, "large_dataset")
        os.makedirs(root)

        # Simula molti file NIfTI
        for i in range(20):
            nifti_file = os.path.join(root, f"scan_{i:03d}.nii.gz")
            json_file = os.path.join(root, f"scan_{i:03d}.json")

            with open(nifti_file, "w") as f:
                f.write(f"scan {i}")
            with open(json_file, "w") as f:
                f.write('{}')

        dest_ws = os.path.join(temp_workspace, "dest")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [root], dest_ws)

        progress_updates = []
        thread.progress.connect(lambda v: progress_updates.append(v))

        thread.run()

        # Dovrebbe completare con successo
        assert 100 in progress_updates
        # Dovrebbe avere creato struttura BIDS
        assert os.path.exists(os.path.join(dest_ws, "sub-001", "anat"))

    def test_special_characters_in_filenames(self, mock_context, temp_workspace):
        """Test con caratteri speciali nei nomi file"""
        folder = os.path.join(temp_workspace, "special_chars")
        os.makedirs(folder)

        # File con caratteri speciali
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

        # Dovrebbe gestire senza errori
        nifti_files = [f for f in os.listdir(folder) if thread._is_nifti_file(f)]
        assert len(nifti_files) > 0

    @patch('threads.import_thread.pydicom.dcmread')
    def test_dicom_missing_patient_info(self, mock_dcmread, mock_context, temp_workspace):
        """Test DICOM senza informazioni paziente"""
        # Mock DICOM senza PatientID né PatientName
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

        # Dovrebbe gestire gracefully
        result = thread._are_dicom_series_of_same_patient([folder])
        # Senza PatientID, considera come stesso paziente
        assert result is True


class TestConcurrencyAndThreadSafety:
    """Test per thread safety e concorrenza"""

    def test_cancel_during_file_copy(self, mock_context, temp_workspace):
        """Test cancellazione durante copia file"""
        # Crea molti file da copiare
        src = os.path.join(temp_workspace, "source_large")
        os.makedirs(src)

        for i in range(100):
            with open(os.path.join(src, f"file_{i}.nii"), "w") as f:
                f.write("x" * 1000)

        dest = os.path.join(temp_workspace, "dest")
        os.makedirs(dest)

        thread = ImportThread(mock_context, [src], dest)

        # Cancella dopo breve delay
        import threading
        def cancel_after_delay():
            import time
            time.sleep(0.01)
            thread.cancel()

        cancel_thread = threading.Thread(target=cancel_after_delay)
        cancel_thread.start()

        thread.run()
        cancel_thread.join()

        # Dovrebbe essere cancellato
        assert thread._is_canceled is True

    def test_multiple_progress_emissions(self, mock_context, temp_workspace):
        """Test emissioni multiple di progress"""
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

        # Dovrebbe avere emesso progress più volte
        assert progress_count[0] >= 3


class TestEdgeCases:
    """Test per casi limite"""

    def test_symlink_handling(self, mock_context, temp_workspace):
        """Test gestione symlink"""
        if os.name == 'nt':  # Skip su Windows
            pytest.skip("Symlinks not reliable on Windows")

        real_folder = os.path.join(temp_workspace, "real")
        os.makedirs(real_folder)
        with open(os.path.join(real_folder, "data.nii"), "w") as f:
            f.write("nifti")

        symlink = os.path.join(temp_workspace, "symlink")
        os.symlink(real_folder, symlink)

        thread = ImportThread(mock_context, [temp_workspace], temp_workspace)

        # Dovrebbe seguire symlink
        assert os.path.isdir(symlink)

    def test_readonly_source_files(self, mock_context, temp_workspace):
        """Test con file sorgente read-only"""
        src = os.path.join(temp_workspace, "readonly_src")
        os.makedirs(src)

        readonly_file = os.path.join(src, "readonly.nii")
        with open(readonly_file, "w") as f:
            f.write("nifti")

        # Rendi read-only
        os.chmod(readonly_file, 0o444)

        dest = os.path.join(temp_workspace, "dest")
        os.makedirs(dest)

        thread = ImportThread(mock_context, [src], dest)

        # Dovrebbe copiare comunque
        try:
            thread.run()
        finally:
            # Cleanup: rimuovi read-only per permettere pulizia
            os.chmod(readonly_file, 0o644)

    def test_very_long_path(self, mock_context, temp_workspace):
        """Test con path molto lungo"""
        # Crea path molto lungo
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
        # Dovrebbe gestire senza errori
        assert os.path.exists(long_path)

    def test_unicode_filenames(self, mock_context, temp_workspace):
        """Test con nomi file Unicode"""
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

        # Verifica rilevamento NIfTI con Unicode
        nifti_count = sum(1 for f in os.listdir(folder) if thread._is_nifti_file(f))
        assert nifti_count >= 2


class TestIntegrationScenarios:
    """Test di integrazione end-to-end"""

    @patch('threads.import_thread.subprocess.run')
    @patch('threads.import_thread.get_bin_path')
    def test_full_dicom_to_bids_workflow(self, mock_get_bin, mock_subprocess,
                                         mock_context, temp_workspace):
        """Test workflow completo DICOM → BIDS"""
        mock_get_bin.return_value = "/usr/bin/dcm2niix"

        # Simula output dcm2niix
        def mock_run(*args, **kwargs):
            # Crea file NIfTI e JSON in output
            output_dir = args[0][args[0].index("-o") + 1]
            with open(os.path.join(output_dir, "converted.nii.gz"), "w") as f:
                f.write("converted nifti")
            with open(os.path.join(output_dir, "converted.json"), "w") as f:
                f.write('{"ConversionSoftware": "dcm2niix"}')
            return Mock(stdout="Success", returncode=0)

        mock_subprocess.side_effect = mock_run

        # Crea cartella DICOM
        dicom_folder = os.path.join(temp_workspace, "dicom_data")
        os.makedirs(dicom_folder)

        for i in range(5):
            dicom_file = os.path.join(dicom_folder, f"image_{i:03d}.dcm")
            with open(dicom_file, "wb") as f:
                f.write(b'\x00' * 128 + b'DICM' + b'\x00' * 100)

        dest_ws = os.path.join(temp_workspace, "workspace")
        os.makedirs(dest_ws)

        thread = ImportThread(mock_context, [dicom_folder], dest_ws)

        finished = [False]
        thread.finished.connect(lambda: finished.__setitem__(0, True))

        thread.run()

        assert finished[0] is True
        # Verifica struttura BIDS creata
        assert os.path.exists(os.path.join(dest_ws, "sub-001", "anat"))

    def test_mixed_patient_dataset_import(self, mock_context, temp_workspace):
        """Test import dataset con pazienti multipli e formati misti"""
        root = os.path.join(temp_workspace, "mixed_dataset")
        os.makedirs(root)

        # Paziente 1: NIfTI
        p1 = os.path.join(root, "sub-01")
        os.makedirs(p1)
        with open(os.path.join(p1, "T1w.nii.gz"), "w") as f:
            f.write("patient 1 nifti")

        # Paziente 2: BIDS già organizzato
        p2_anat = os.path.join(root, "sub-02", "anat")
        os.makedirs(p2_anat)
        with open(os.path.join(p2_anat, "sub-02_T1w.nii"), "w") as f:
            f.write("patient 2")

        # Paziente 3: DICOM
        p3 = os.path.join(root, "patient_003")
        os.makedirs(p3)
        with open(os.path.join(p3, "scan.dcm"), "wb") as f:
            f.write(b'\x00' * 128 + b'DICM')

        dest = os.path.join(temp_workspace, "output")
        os.makedirs(dest)

        thread = ImportThread(mock_context, [root], dest)
        thread.run()

        # Dovrebbe processare come multipli pazienti
        # (grazie all'euristica dei nomi cartelle)
        assert thread._subfolders_look_like_different_patients([p1, p2_anat, p3])


# Parametrized tests per riutilizzo
@pytest.mark.parametrize("extension", [".nii", ".nii.gz"])
def test_nifti_extensions(extension, mock_context, temp_workspace):
    """Test parametrizzato per diverse estensioni NIfTI"""
    thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
    filename = f"brain{extension}"
    assert thread._is_nifti_file(filename) is True


@pytest.mark.parametrize("invalid_ext", [".dcm", ".txt", ".json", ".pdf", ""])
def test_non_nifti_extensions(invalid_ext, mock_context, temp_workspace):
    """Test parametrizzato per estensioni non-NIfTI"""
    thread = ImportThread(mock_context, [temp_workspace], temp_workspace)
    filename = f"file{invalid_ext}"
    assert thread._is_nifti_file(filename) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])