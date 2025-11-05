"""
test_save_load_threads.py - Test Suite per SaveNiftiThread e ImageLoadThread

Questa suite testa tutte le funzionalità dei thread di salvataggio e caricamento:
- SaveNiftiThread: salvataggio NIfTI + JSON con metadata BIDS
- ImageLoadThread: caricamento e normalizzazione NIfTI 3D/4D
- Gestione errori e progress tracking
- Normalizzazione intensità con percentili
"""

import json
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
import pytest
import numpy as np
import nibabel as nib

from main.threads.nifti_utils_threads import SaveNiftiThread, ImageLoadThread


class TestSaveNiftiThreadInitialization:
    """Test per l'inizializzazione di SaveNiftiThread"""

    def test_init_with_all_parameters(self, temp_workspace):
        """Test inizializzazione con tutti i parametri"""
        data = np.random.rand(10, 10, 10)
        affine = np.eye(4)
        path = os.path.join(temp_workspace, "output.nii.gz")
        json_path = os.path.join(temp_workspace, "output.json")
        relative_path = "sub-01/anat/T1w.nii.gz"
        radius = 5.0
        difference = 0.3
        source_dict = {"radius": radius, "difference": difference}

        thread = SaveNiftiThread(
            data=data,
            affine=affine,
            path=path,
            json_path=json_path,
            relative_path=relative_path,
            source_dict=source_dict
        )

        assert thread.data is data
        assert np.array_equal(thread.affine, affine)
        assert thread.path == path
        assert thread.json_path == json_path
        assert thread.relative_path == relative_path
        assert thread.source_dict["radius"] == radius
        assert thread.source_dict["difference"] == difference

    def test_signals_exist(self, temp_workspace):
        """Verifica che i signal siano definiti correttamente"""
        data = np.zeros((5, 5, 5))
        affine = np.eye(4)
        source_dict = {"radius": 1.0, "difference": 0.1}
        thread = SaveNiftiThread(
            data, affine, "path.nii", "path.json", "rel/path.nii", source_dict
        )

        assert hasattr(thread, 'success')
        assert hasattr(thread, 'error')


class TestSaveNiftiThreadExecution:
    """Test per l'esecuzione di SaveNiftiThread"""

    def test_successful_save(self, temp_workspace):
        """Test salvataggio riuscito di NIfTI e JSON"""
        # Dati di test
        data = np.random.randint(0, 255, (10, 10, 10), dtype=np.uint8)
        affine = np.eye(4)
        affine[0, 0] = 2.0  # Voxel size

        nifti_path = os.path.join(temp_workspace, "mask.nii.gz")
        json_path = os.path.join(temp_workspace, "mask.json")
        relative_path = "sub-01/anat/T1w.nii.gz"

        radius = 3.5
        difference = 0.25
        source_dict = {"radius": radius, "difference": difference}

        thread = SaveNiftiThread(
            data=data,
            affine=affine,
            path=nifti_path,
            json_path=json_path,
            relative_path=relative_path,
            source_dict=source_dict
        )

        # Connetti signal
        success_paths = []

        def on_success(path, json_p):
            success_paths.append((path, json_p))

        thread.success.connect(on_success)

        # Esegui
        thread.run()

        # Verifica signal emesso
        assert len(success_paths) == 1
        assert success_paths[0][0] == nifti_path
        assert success_paths[0][1] == json_path

        # Verifica file NIfTI creato
        assert os.path.exists(nifti_path)
        loaded_img = nib.load(nifti_path)
        loaded_data = loaded_img.get_fdata()
        assert loaded_data.shape == data.shape
        np.testing.assert_array_almost_equal(loaded_data, data, decimal=0)

        # Verifica affine
        np.testing.assert_array_almost_equal(loaded_img.affine, affine)

    def test_json_metadata_structure(self, temp_workspace):
        """Test struttura e contenuto del file JSON"""
        data = np.ones((5, 5, 5), dtype=np.uint8)
        affine = np.eye(4)

        nifti_path = os.path.join(temp_workspace, "roi.nii.gz")
        json_path = os.path.join(temp_workspace, "roi.json")
        relative_path = "sub-02/anat/brain.nii.gz"
        radius = 4.2
        difference = 0.15
        source_dict = {"radius": radius, "difference": difference}

        thread = SaveNiftiThread(
            data, affine, nifti_path, json_path, relative_path, source_dict
        )
        thread.run()

        # Verifica JSON creato
        assert os.path.exists(json_path)

        with open(json_path, 'r') as f:
            metadata = json.load(f)

        # Verifica struttura
        assert "Type" in metadata
        assert metadata["Type"] == "ROI"

        assert "Sources" in metadata
        assert isinstance(metadata["Sources"], list)
        assert len(metadata["Sources"]) == 1
        assert metadata["Sources"][0] == f"bids:{relative_path}"

        assert "Description" in metadata
        assert "roi mask" in metadata["Description"].lower()

        assert "Origin" in metadata
        params = metadata["Origin"]
        assert params["radius"] == radius
        assert params["difference"] == difference

    def test_json_indentation(self, temp_workspace):
        """Test che il JSON sia formattato con indentazione"""
        data = np.zeros((3, 3, 3), dtype=np.uint8)
        affine = np.eye(4)

        nifti_path = os.path.join(temp_workspace, "test.nii")
        json_path = os.path.join(temp_workspace, "test.json")

        radius = 1.0
        difference = 0.1
        source_dict = {"radius": radius, "difference": difference}

        thread = SaveNiftiThread(
            data, affine, nifti_path, json_path, "path.nii", source_dict
        )
        thread.run()

        with open(json_path, 'r') as f:
            content = f.read()

        # Verifica indentazione (JSON formattato)
        assert "    " in content  # 4 spazi di indentazione
        assert "\n" in content  # Newline tra campi

    def test_data_type_conversion_to_uint8(self, temp_workspace):
        """Test conversione automatica dati a uint8"""
        # Dati float
        data = np.random.rand(5, 5, 5) * 255
        affine = np.eye(4)

        nifti_path = os.path.join(temp_workspace, "converted.nii.gz")
        json_path = os.path.join(temp_workspace, "converted.json")

        source_dict = {"radius": 1.0, "difference": 0.1}

        thread = SaveNiftiThread(
            data, affine, nifti_path, json_path, "rel.nii", source_dict
        )
        thread.run()

        # Verifica tipo dato salvato
        loaded_img = nib.load(nifti_path)
        loaded_data = loaded_img.get_fdata()

        # Dovrebbe essere convertito a uint8
        assert loaded_data.dtype in [np.uint8, np.float32, np.float64]
        # I valori dovrebbero essere nell'intervallo uint8
        assert loaded_data.min() >= 0
        assert loaded_data.max() <= 255

    def test_error_handling_invalid_path(self, temp_workspace):
        """Test gestione errore con path non valido"""
        data = np.zeros((3, 3, 3))
        affine = np.eye(4)

        # Path non valido (directory inesistente)
        invalid_path = os.path.join(temp_workspace, "nonexistent", "dir", "file.nii")
        json_path = os.path.join(temp_workspace, "nonexistent", "dir", "file.json")

        source_dict = {"radius": 1.0, "difference": 0.1}

        thread = SaveNiftiThread(
            data, affine, invalid_path, json_path, "rel.nii", source_dict
        )

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # Dovrebbe emettere errore
        assert len(error_msgs) == 1
        assert len(error_msgs[0]) > 0

    @patch('nibabel.save')
    def test_error_during_nifti_save(self, mock_save, temp_workspace):
        """Test gestione errore durante salvataggio NIfTI"""
        mock_save.side_effect = IOError("Disk full")

        data = np.zeros((3, 3, 3))
        affine = np.eye(4)

        nifti_path = os.path.join(temp_workspace, "fail.nii")
        json_path = os.path.join(temp_workspace, "fail.json")

        source_dict = {"radius": 1.0, "difference": 0.1}

        thread = SaveNiftiThread(
            data, affine, nifti_path, json_path, "rel.nii", source_dict
        )

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert "Disk full" in error_msgs[0]

    def test_different_affine_matrices(self, temp_workspace):
        """Test con diverse matrici affine"""
        data = np.ones((4, 4, 4), dtype=np.uint8)

        # Affine con voxel size diversi
        affine = np.diag([2.5, 3.0, 3.5, 1.0])
        affine[:3, 3] = [10, 20, 30]  # Offset

        nifti_path = os.path.join(temp_workspace, "custom_affine.nii")
        json_path = os.path.join(temp_workspace, "custom_affine.json")

        source_dict = {"radius": 2.0, "difference": 0.2}

        thread = SaveNiftiThread(
            data, affine, nifti_path, json_path, "path.nii", source_dict
        )
        thread.run()

        # Verifica affine salvata correttamente
        loaded_img = nib.load(nifti_path)
        np.testing.assert_array_almost_equal(loaded_img.affine, affine)


class TestImageLoadThreadInitialization:
    """Test per l'inizializzazione di ImageLoadThread"""

    def test_init_regular_image(self, temp_workspace):
        """Test inizializzazione per immagine regolare"""
        file_path = os.path.join(temp_workspace, "test.nii")
        thread = ImageLoadThread(file_path, is_overlay=False)

        assert thread.file_path == file_path
        assert thread.is_overlay is False

    def test_init_overlay_image(self, temp_workspace):
        """Test inizializzazione per immagine overlay"""
        file_path = os.path.join(temp_workspace, "overlay.nii.gz")
        thread = ImageLoadThread(file_path, is_overlay=True)

        assert thread.file_path == file_path
        assert thread.is_overlay is True

    def test_signals_exist(self, temp_workspace):
        """Verifica che i signal siano definiti correttamente"""
        thread = ImageLoadThread("dummy.nii", False)

        assert hasattr(thread, 'finished')
        assert hasattr(thread, 'error')
        assert hasattr(thread, 'progress')


class TestImageLoadThread3D:
    """Test per il caricamento di immagini NIfTI 3D"""

    def test_load_3d_nifti_success(self, temp_workspace):
        """Test caricamento riuscito di NIfTI 3D"""
        # Crea immagine 3D di test
        data_3d = np.random.rand(20, 20, 20).astype(np.float32) * 100
        affine = np.eye(4)
        img = nib.Nifti1Image(data_3d, affine)

        nifti_path = os.path.join(temp_workspace, "test_3d.nii.gz")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, is_overlay=False)

        # Connetti signal
        results = []

        def on_finished(img_data, dims, aff, is_4d, is_overlay):
            results.append({
                'img_data': img_data,
                'dims': dims,
                'affine': aff,
                'is_4d': is_4d,
                'is_overlay': is_overlay
            })

        thread.finished.connect(on_finished)

        # Esegui
        thread.run()

        # Verifica risultati
        assert len(results) == 1
        result = results[0]

        assert result['dims'] == (20, 20, 20)
        assert result['is_4d'] is False
        assert result['is_overlay'] is False
        assert result['img_data'].shape == (20, 20, 20)
        assert result['img_data'].dtype == np.float32

        # Verifica normalizzazione (valori tra 0 e 1)
        assert result['img_data'].min() >= 0
        assert result['img_data'].max() <= 1

    def test_load_3d_progress_emissions(self, temp_workspace):
        """Test emissione progress durante caricamento 3D"""
        # Crea immagine semplice
        data = np.ones((10, 10, 10))
        img = nib.Nifti1Image(data, np.eye(4))

        nifti_path = os.path.join(temp_workspace, "progress_test.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        progress_values = []
        thread.progress.connect(lambda val: progress_values.append(val))

        thread.run()

        # Verifica progress emesso
        assert len(progress_values) > 0
        assert 10 in progress_values
        assert 100 in progress_values

        # Verifica crescita monotonica
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i - 1]


class TestImageLoadThread4D:
    """Test per il caricamento di immagini NIfTI 4D"""

    def test_load_4d_nifti_success(self, temp_workspace):
        """Test caricamento riuscito di NIfTI 4D"""
        # Crea immagine 4D (es. fMRI time series)
        data_4d = np.random.rand(15, 15, 15, 10).astype(np.float32) * 50
        affine = np.eye(4)
        img = nib.Nifti1Image(data_4d, affine)

        nifti_path = os.path.join(temp_workspace, "test_4d.nii.gz")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, is_overlay=True)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append((img_data, dims))
        )

        thread.run()

        assert len(results) == 1
        img_data, dims = results[0]
        assert dims == (15, 15, 15, 10)
        assert img_data.shape == (15, 15, 15, 10)

    def test_anisotropic_voxels(self, temp_workspace):
        """Test con voxel anisotropici"""
        data = np.random.rand(10, 20, 30).astype(np.float32)

        # Affine con voxel size diversi per ogni asse
        affine = np.diag([0.5, 1.0, 2.0, 1.0])

        img = nib.Nifti1Image(data, affine)
        nifti_path = os.path.join(temp_workspace, "anisotropic.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append((img_data, aff))
        )

        thread.run()

        assert len(results) == 1
        img_data, loaded_affine = results[0]

        # Dimensioni preservate (o riordinate da canonicalizzazione)
        assert img_data.ndim == 3
        assert isinstance(loaded_affine, np.ndarray)

    def test_different_data_types(self, temp_workspace):
        """Test con diversi dtype di input"""
        dtypes_to_test = [np.uint8, np.int16, np.float32, np.float64]

        for dtype in dtypes_to_test:
            data = (np.random.rand(8, 8, 8) * 100).astype(dtype)
            img = nib.Nifti1Image(data, np.eye(4))

            nifti_path = os.path.join(temp_workspace, f"dtype_{dtype.__name__}.nii")
            nib.save(img, nifti_path)

            thread = ImageLoadThread(nifti_path, False)

            results = []
            thread.finished.connect(
                lambda img_data, dims, aff, is_4d, is_overlay:
                results.append(img_data)
            )

            thread.run()

            # Dovrebbe sempre normalizzare a float32
            assert len(results) == 1
            assert results[0].dtype == np.float32
            assert results[0].min() >= 0
            assert results[0].max() <= 1

    def test_negative_values_handling(self, temp_workspace):
        """Test gestione valori negativi"""
        # Dati con valori negativi (es. mappe parametriche)
        data = np.random.randn(15, 15, 15).astype(np.float32)

        img = nib.Nifti1Image(data, np.eye(4))
        nifti_path = os.path.join(temp_workspace, "negative_values.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append(img_data)
        )

        thread.run()

        normalized = results[0]

        # Anche con valori negativi, normalizzazione a [0, 1]
        assert normalized.min() >= 0
        assert normalized.max() <= 1


class TestSaveLoadThreadsIntegration:
    """Test di integrazione tra SaveNiftiThread e ImageLoadThread"""

    def test_save_and_reload_cycle(self, temp_workspace):
        """Test ciclo completo: salva e ricarica"""
        # Dati originali
        original_data = np.random.randint(0, 255, (12, 12, 12), dtype=np.uint8)
        affine = np.eye(4)
        affine[0, 0] = 2.0

        # Salva
        nifti_path = os.path.join(temp_workspace, "cycle_test.nii.gz")
        json_path = os.path.join(temp_workspace, "cycle_test.json")

        radius = 2.5
        difference = 0.2
        source_dict = {"radius": radius, "difference": difference}

        save_thread = SaveNiftiThread(
            data=original_data,
            affine=affine,
            path=nifti_path,
            json_path=json_path,
            relative_path="sub-01/anat/T1w.nii.gz",
            source_dict=source_dict
        )

        save_success = []
        save_thread.success.connect(
            lambda p, j: save_success.append(True)
        )

        save_thread.run()
        assert len(save_success) == 1

        # Ricarica
        load_thread = ImageLoadThread(nifti_path, is_overlay=False)

        loaded_results = []
        load_thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            loaded_results.append((img_data, dims, aff))
        )

        load_thread.run()

        assert len(loaded_results) == 1
        loaded_data, loaded_dims, loaded_affine = loaded_results[0]

        # Verifica dimensioni
        assert loaded_dims == (12, 12, 12)

        # Verifica affine (può essere leggermente diversa dopo canonical)
        # ma dovrebbe avere voxel size simile
        assert loaded_affine.shape == (4, 4)

        # Verifica JSON
        assert os.path.exists(json_path)
        with open(json_path, 'r') as f:
            metadata = json.load(f)
        assert metadata["Type"] == "ROI"
        assert metadata["Origin"]["radius"] == 2.5

    def test_save_load_multiple_files(self, temp_workspace):
        """Test salvataggio e caricamento di più file"""
        num_files = 5
        saved_paths = []

        for i in range(num_files):
            data = np.random.randint(0, 100, (8, 8, 8), dtype=np.uint8)
            nifti_path = os.path.join(temp_workspace, f"multi_{i}.nii")
            json_path = os.path.join(temp_workspace, f"multi_{i}.json")

            source_dict = {"radius": float(i), "difference": float(i) * 0.1}

            save_thread = SaveNiftiThread(
                data, np.eye(4), nifti_path, json_path,
                f"path_{i}.nii", source_dict
            )
            save_thread.run()
            saved_paths.append(nifti_path)

        # Ricarica tutti
        for path in saved_paths:
            load_thread = ImageLoadThread(path, False)

            results = []
            load_thread.finished.connect(
                lambda img_data, dims, aff, is_4d, is_overlay:
                results.append(True)
            )

            load_thread.run()
            assert len(results) == 1

    def test_save_4d_reload_as_4d(self, temp_workspace):
        """Test salvataggio e ricarico di dati 4D"""
        # Crea dati 4D
        data_4d = np.random.randint(0, 255, (10, 10, 10, 5), dtype=np.uint8)
        affine = np.eye(4)

        nifti_path = os.path.join(temp_workspace, "test_4d_cycle.nii.gz")
        json_path = os.path.join(temp_workspace, "test_4d_cycle.json")

        source_dict = {"radius": 3.0, "difference": 0.15}

        # SaveNiftiThread dovrebbe gestire anche 4D
        save_thread = SaveNiftiThread(
            data_4d, affine, nifti_path, json_path,
            "rel_4d.nii", source_dict
        )

        save_success = []
        save_thread.success.connect(lambda p, j: save_success.append(True))
        save_thread.run()

        assert len(save_success) == 1

        # Ricarica come 4D
        load_thread = ImageLoadThread(nifti_path, False)

        results = []
        load_thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append((dims, is_4d))
        )

        load_thread.run()

        dims, is_4d = results[0]
        assert len(dims) == 4
        assert is_4d is True


class TestConcurrencyAndThreadSafety:
    """Test per concorrenza e thread safety"""

    def test_multiple_save_threads_concurrent(self, temp_workspace):
        """Test esecuzione concorrente di più SaveNiftiThread"""
        threads = []
        success_count = [0]

        def on_success(p, j):
            success_count[0] += 1

        for i in range(3):
            data = np.ones((5, 5, 5), dtype=np.uint8) * i
            nifti_path = os.path.join(temp_workspace, f"concurrent_save_{i}.nii")
            json_path = os.path.join(temp_workspace, f"concurrent_save_{i}.json")

            source_dict = {"radius": 1.0, "difference": 0.1}

            thread = SaveNiftiThread(
                data, np.eye(4), nifti_path, json_path,
                f"path_{i}.nii", source_dict
            )
            thread.success.connect(on_success)
            threads.append(thread)

        # Avvia tutti i thread
        for thread in threads:
            thread.run()

        # Attendi completamento
        for thread in threads:
            thread.wait(5000)  # 5 secondi timeout

        assert success_count[0] == 3

    def test_multiple_load_threads_concurrent(self, temp_workspace):
        """Test caricamento concorrente di più file"""
        # Crea file di test
        file_paths = []
        for i in range(3):
            data = np.random.rand(6, 6, 6).astype(np.float32)
            img = nib.Nifti1Image(data, np.eye(4))
            path = os.path.join(temp_workspace, f"concurrent_load_{i}.nii")
            nib.save(img, path)
            file_paths.append(path)

        threads = []
        finished_count = [0]

        def on_finished(img_data, dims, aff, is_4d, is_overlay):
            finished_count[0] += 1

        for path in file_paths:
            thread = ImageLoadThread(path, False)
            thread.finished.connect(on_finished)
            threads.append(thread)

        # Avvia tutti
        for thread in threads:
            thread.run()

        # Attendi
        for thread in threads:
            thread.wait(5000)

        assert finished_count[0] == 3


class TestSpecialCases:
    """Test per casi speciali e boundary conditions"""

    def test_save_zero_volume(self, temp_workspace):
        """Test salvataggio volume con tutti zeri"""
        data = np.zeros((10, 10, 10), dtype=np.uint8)
        nifti_path = os.path.join(temp_workspace, "all_zeros.nii")
        json_path = os.path.join(temp_workspace, "all_zeros.json")

        source_dict = {"radius": 1.0, "difference": 0.1}

        thread = SaveNiftiThread(
            data, np.eye(4), nifti_path, json_path,
            "zeros.nii", source_dict
        )

        success = []
        thread.success.connect(lambda p, j: success.append(True))
        thread.run()

        assert len(success) == 1
        assert os.path.exists(nifti_path)

    def test_load_zero_volume(self, temp_workspace):
        """Test caricamento volume con tutti zeri"""
        data = np.zeros((8, 8, 8))
        img = nib.Nifti1Image(data, np.eye(4))

        nifti_path = os.path.join(temp_workspace, "zeros_load.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append(img_data)
        )

        thread.run()

        # Dovrebbe gestire correttamente
        assert len(results) == 1
        normalized = results[0]
        assert not np.any(np.isnan(normalized))

    def test_save_binary_mask(self, temp_workspace):
        """Test salvataggio maschera binaria"""
        # Maschera binaria (0 e 1)
        mask = np.random.randint(0, 2, (15, 15, 15), dtype=np.uint8)

        nifti_path = os.path.join(temp_workspace, "binary_mask.nii.gz")
        json_path = os.path.join(temp_workspace, "binary_mask.json")

        source_dict = {"radius": 0.0, "difference": 0.0}

        thread = SaveNiftiThread(
            mask, np.eye(4), nifti_path, json_path,
            "mask.nii", source_dict
        )

        success = []
        thread.success.connect(lambda p, j: success.append(True))
        thread.run()

        assert len(success) == 1

        # Verifica integrità
        loaded = nib.load(nifti_path)
        loaded_data = loaded.get_fdata()

        # Dovrebbe preservare valori binari
        unique_vals = np.unique(loaded_data)
        assert len(unique_vals) <= 2

    def test_load_compressed_vs_uncompressed(self, temp_workspace):
        """Test caricamento file compressi vs non compressi"""
        data = np.random.rand(10, 10, 10).astype(np.float32)
        img = nib.Nifti1Image(data, np.eye(4))

        # Salva versione compressa
        compressed_path = os.path.join(temp_workspace, "compressed.nii.gz")
        nib.save(img, compressed_path)

        # Salva versione non compressa
        uncompressed_path = os.path.join(temp_workspace, "uncompressed.nii")
        nib.save(img, uncompressed_path)

        # Carica entrambi
        results_compressed = []
        thread_compressed = ImageLoadThread(compressed_path, False)
        thread_compressed.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results_compressed.append(img_data)
        )
        thread_compressed.run()

        results_uncompressed = []
        thread_uncompressed = ImageLoadThread(uncompressed_path, False)
        thread_uncompressed.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results_uncompressed.append(img_data)
        )
        thread_uncompressed.run()

        # Dovrebbero dare risultati equivalenti
        assert len(results_compressed) == 1
        assert len(results_uncompressed) == 1

        np.testing.assert_array_almost_equal(
            results_compressed[0],
            results_uncompressed[0],
            decimal=5
        )

    def test_save_with_special_characters_in_path(self, temp_workspace):
        """Test salvataggio con caratteri speciali nel path"""
        data = np.ones((5, 5, 5), dtype=np.uint8)

        # Nome file con spazi e caratteri speciali
        nifti_path = os.path.join(temp_workspace, "test file (copy) #1.nii")
        json_path = os.path.join(temp_workspace, "test file (copy) #1.json")

        source_dict = {"radius": 1.0, "difference": 0.1}

        thread = SaveNiftiThread(
            data, np.eye(4), nifti_path, json_path,
            "relative/path.nii", source_dict
        )

        success = []
        thread.success.connect(lambda p, j: success.append(True))
        thread.run()

        assert len(success) == 1
        assert os.path.exists(nifti_path)


class TestParameterValidation:
    """Test validazione parametri"""

    def test_save_with_extreme_radius_values(self, temp_workspace):
        """Test con valori estremi per radius"""
        data = np.ones((5, 5, 5), dtype=np.uint8)

        extreme_radii = [0.0, 100.0, 1e6, -5.0]

        for radius in extreme_radii:
            nifti_path = os.path.join(temp_workspace, f"radius_{radius}.nii")
            json_path = os.path.join(temp_workspace, f"radius_{radius}.json")

            difference = 0.1
            source_dict = {"radius": radius, "difference": difference}

            thread = SaveNiftiThread(
                data, np.eye(4), nifti_path, json_path,
                "path.nii", source_dict
            )

            success = []
            thread.success.connect(lambda p, j: success.append(True))
            thread.run()

            # Dovrebbe salvare anche con valori estremi
            assert len(success) == 1

            # Verifica JSON contiene il valore
            with open(json_path, 'r') as f:
                metadata = json.load(f)
            assert metadata["Origin"]["radius"] == radius

    def test_save_with_extreme_difference_values(self, temp_workspace):
        """Test con valori estremi per difference"""
        data = np.ones((5, 5, 5), dtype=np.uint8)

        extreme_diffs = [0.0, 1.0, 10.0, -1.0]

        for diff in extreme_diffs:
            nifti_path = os.path.join(temp_workspace, f"diff_{diff}.nii")
            json_path = os.path.join(temp_workspace, f"diff_{diff}.json")

            source_dict = {"radius": 1.0, "difference": diff}

            thread = SaveNiftiThread(
                data, np.eye(4), nifti_path, json_path,
                "path.nii", source_dict
            )

            success = []
            thread.success.connect(lambda p, j: success.append(True))
            thread.run()

            assert len(success) == 1

            with open(json_path, 'r') as f:
                metadata = json.load(f)
            assert metadata["Origin"]["difference"] == diff


class TestPerformanceAndScalability:
    """Test per performance e scalabilità"""

    def test_large_4d_dataset(self, temp_workspace):
        """Test con dataset 4D grande"""
        # Dataset 4D simulato (non troppo grande per CI)
        data_4d = np.random.rand(40, 40, 40, 20).astype(np.float32)
        img = nib.Nifti1Image(data_4d, np.eye(4))

        nifti_path = os.path.join(temp_workspace, "large_4d.nii.gz")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        progress_updates = []

        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append(dims)
        )
        thread.progress.connect(lambda val: progress_updates.append(val))

        thread.run()

        assert len(results) == 1
        assert results[0] == (40, 40, 40, 20)

        # Progress dovrebbe essere emesso
        assert len(progress_updates) > 0
        assert 100 in progress_updates

    def test_progress_tracking_accuracy(self, temp_workspace):
        """Test accuratezza tracking progress"""
        data = np.random.rand(25, 25, 25).astype(np.float32)
        img = nib.Nifti1Image(data, np.eye(4))

        nifti_path = os.path.join(temp_workspace, "progress_track.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        progress_values = []
        thread.progress.connect(lambda val: progress_values.append(val))

        thread.run()

        # Verifica sequenza progress
        expected_milestones = [10, 30, 50, 70, 80, 100]
        for milestone in expected_milestones:
            assert milestone in progress_values

        # Verifica ordine crescente
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i - 1]


class TestNiftiThreadParameterized:
    """Test parametrizzati e di normalizzazione per i thread NIfTI"""

    @pytest.mark.parametrize("shape", [
        (5, 5, 5),
        (10, 20, 15),
        (3, 3, 3),
        (50, 50, 50)
    ])
    def test_save_various_shapes(self, shape, temp_workspace):
        """Test parametrizzato per diverse forme di volumi"""
        data = np.random.randint(0, 255, shape, dtype=np.uint8)
        nifti_path = os.path.join(temp_workspace, f"shape_{'x'.join(map(str, shape))}.nii")
        json_path = nifti_path.replace('.nii', '.json')

        source_dict = {"radius": 1.0, "difference": 0.1}

        thread = SaveNiftiThread(
            data, np.eye(4), nifti_path, json_path,
            "path.nii", source_dict
        )

        success = []
        thread.success.connect(lambda p, j: success.append(True))
        thread.run()

        assert len(success) == 1

        # Verifica caricamento
        loaded = nib.load(nifti_path)
        assert loaded.shape == shape

    @pytest.mark.parametrize("is_overlay", [True, False])
    def test_load_overlay_flag(self, is_overlay, temp_workspace):
        """Test parametrizzato per flag overlay"""
        data = np.random.rand(8, 8, 8).astype(np.float32)
        img = nib.Nifti1Image(data, np.eye(4))

        nifti_path = os.path.join(temp_workspace, f"overlay_{is_overlay}.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, is_overlay=is_overlay)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_ov:
            results.append(is_ov)
        )

        thread.run()

        assert len(results) == 1
        assert results[0] == is_overlay

    def test_load_4d_normalization_per_volume(self, temp_workspace):
        """Test normalizzazione indipendente per ogni volume 4D"""
        # Crea 4D con volumi a intensità diverse (con variabilità per evitare volumi costanti)
        volume1 = np.ones((10, 10, 10)) * 100
        volume1[0, 0, 0] = 101  # Aggiungi variabilità
        volume2 = np.ones((10, 10, 10)) * 200
        volume2[0, 0, 0] = 201
        volume3 = np.ones((10, 10, 10)) * 50
        volume3[0, 0, 0] = 51

        data_4d = np.stack([volume1, volume2, volume3], axis=-1)
        img = nib.Nifti1Image(data_4d, np.eye(4))

        nifti_path = os.path.join(temp_workspace, "4d_norm.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append(img_data)
        )

        thread.run()

        normalized_data = results[0]

        # Ogni volume dovrebbe essere normalizzato indipendentemente
        for i in range(3):
            vol = normalized_data[..., i]
            assert vol.min() >= 0
            assert vol.max() <= 1
            assert vol.max() - vol.min() > 0


class TestImageLoadThreadNormalization:
    """Test per la normalizzazione basata su percentili"""

    def test_normalize_data_matplotlib_style(self, temp_workspace):
        """Test normalizzazione con percentili"""
        # Crea dati con outlier
        data = np.random.randn(30, 30, 30).astype(np.float32) * 100
        data[0, 0, 0] = 10000  # Outlier alto
        data[1, 1, 1] = -5000  # Outlier basso

        img = nib.Nifti1Image(data, np.eye(4))
        nifti_path = os.path.join(temp_workspace, "outliers.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append(img_data)
        )

        thread.run()

        normalized = results[0]

        # Verifica che outlier non dominino la normalizzazione
        # La maggior parte dei valori dovrebbe essere ben distribuita
        assert normalized.min() >= 0
        assert normalized.max() <= 1

        # Percentili intermedi dovrebbero essere ben distribuiti
        p25 = np.percentile(normalized, 25)
        p75 = np.percentile(normalized, 75)
        assert 0.1 < p25 < 0.9
        assert 0.1 < p75 < 0.9

    def test_normalize_uniform_data(self, temp_workspace):
        """Test normalizzazione con dati uniformi"""
        # Tutti i voxel hanno lo stesso valore
        data = np.ones((10, 10, 10)) * 42.0
        img = nib.Nifti1Image(data, np.eye(4))

        nifti_path = os.path.join(temp_workspace, "uniform.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append(img_data)
        )

        thread.run()

        normalized = results[0]

        # Con dati uniformi, la normalizzazione dovrebbe gestire gracefully
        assert not np.any(np.isnan(normalized))
        assert not np.any(np.isinf(normalized))
        assert normalized.min() >= 0
        assert normalized.max() <= 1

    def test_normalize_with_nan_values(self, temp_workspace):
        """Test normalizzazione con valori NaN"""
        data = np.random.rand(10, 10, 10).astype(np.float32)
        data[5, 5, 5] = np.nan
        data[3, 3, 3] = np.inf

        img = nib.Nifti1Image(data, np.eye(4))
        nifti_path = os.path.join(temp_workspace, "with_nan.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append(img_data)
        )

        thread.run()

        normalized = results[0]

        # Dovrebbe gestire NaN/Inf senza propagarli
        finite_count = np.isfinite(normalized).sum()
        assert finite_count > 0  # Almeno alcuni valori finiti

    def test_normalize_empty_volume(self):
        """Test normalizzazione volume vuoto"""
        thread = ImageLoadThread("dummy.nii", False)

        # Test diretto del metodo
        empty_data = np.array([])
        result = thread.normalize_data_matplotlib_style(empty_data)

        assert result.size == 0

    def test_normalize_volume_all_invalid(self):
        """Test normalizzazione con tutti valori invalidi"""
        thread = ImageLoadThread("dummy.nii", False)

        # Volume con solo NaN
        nan_volume = np.full((5, 5, 5), np.nan)
        result = thread.normalize_data_matplotlib_style(nan_volume)

        # Dovrebbe restituire zeri
        assert result.shape == nan_volume.shape
        assert np.all(result == 0)


class TestImageLoadThreadCanonicalOrientation:
    """Test per la conversione a orientamento canonico RAS+"""

    def test_canonical_orientation_applied(self, temp_workspace):
        """Test che l'immagine venga convertita a RAS+"""
        # Crea immagine con orientamento non-canonico
        data = np.random.rand(10, 12, 8).astype(np.float32)

        # Affine con orientamento diverso (es. LAS)
        affine = np.array([
            [-2, 0, 0, 10],
            [0, 2, 0, 20],
            [0, 0, 2, 30],
            [0, 0, 0, 1]
        ])

        img = nib.Nifti1Image(data, affine)
        nifti_path = os.path.join(temp_workspace, "non_canonical.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append((img_data, aff))
        )

        thread.run()

        img_data, loaded_affine = results[0]

        # L'immagine dovrebbe essere in orientamento canonico
        # (potrebbe cambiare dimensioni se riordinata)
        assert img_data.shape[0] > 0
        assert img_data.shape[1] > 0
        assert img_data.shape[2] > 0

        # Affine dovrebbe essere modificata
        assert isinstance(loaded_affine, np.ndarray)
        assert loaded_affine.shape == (4, 4)


class TestImageLoadThreadErrorHandling:
    """Test per la gestione degli errori"""

    def test_error_file_not_found(self, temp_workspace):
        """Test errore con file inesistente"""
        nonexistent_path = os.path.join(temp_workspace, "does_not_exist.nii")
        thread = ImageLoadThread(nonexistent_path, False)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert len(error_msgs[0]) > 0

    def test_error_invalid_nifti_file(self, temp_workspace):
        """Test errore con file non-NIfTI"""
        # Crea file di testo invece di NIfTI
        invalid_path = os.path.join(temp_workspace, "invalid.nii")
        with open(invalid_path, 'w') as f:
            f.write("This is not a NIfTI file")

        thread = ImageLoadThread(invalid_path, False)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1

    def test_error_corrupted_nifti(self, temp_workspace):
        """Test errore con NIfTI corrotto"""
        corrupted_path = os.path.join(temp_workspace, "corrupted.nii.gz")

        # Crea file parzialmente valido ma corrotto
        with open(corrupted_path, 'wb') as f:
            f.write(b'corrupted data that looks like gzip')

        thread = ImageLoadThread(corrupted_path, False)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1

    @patch('nibabel.load')
    def test_error_during_load(self, mock_load, temp_workspace):
        """Test gestione errore generico durante caricamento"""
        mock_load.side_effect = RuntimeError("Memory error")

        nifti_path = os.path.join(temp_workspace, "test.nii")
        thread = ImageLoadThread(nifti_path, False)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert "Memory error" in error_msgs[0]


class TestImageLoadThreadNifti2Support:
    """Test per il supporto NIfTI-2"""

    def test_nifti2_image_loads(self, temp_workspace):
        """Test caricamento immagine NIfTI-2"""
        # Crea immagine NIfTI-2
        data = np.random.rand(8, 8, 8).astype(np.float32)
        affine = np.eye(4)
        img = nib.Nifti2Image(data, affine)

        nifti_path = os.path.join(temp_workspace, "test_nifti2.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append(img_data)
        )

        thread.run()

        # Dovrebbe caricare correttamente
        assert len(results) == 1
        assert results[0].shape == (8, 8, 8)


class TestImageLoadThreadMemoryMapping:
    """Test per memory mapping"""

    @patch('nibabel.load')
    def test_memory_mapping_used(self, mock_load, temp_workspace):
        """Test che memory mapping sia utilizzato"""
        # Mock per verificare parametro mmap
        mock_img = Mock(spec=nib.Nifti1Image)
        mock_img.header.get_data_shape.return_value = (10, 10, 10)
        mock_img.affine = np.eye(4)
        mock_img.dataobj = np.zeros((10, 10, 10))

        mock_canonical = Mock()
        mock_canonical.header.get_data_shape.return_value = (10, 10, 10)
        mock_canonical.affine = np.eye(4)
        mock_canonical.dataobj = np.zeros((10, 10, 10))

        with patch('nibabel.as_closest_canonical', return_value=mock_canonical):
            mock_load.return_value = mock_img

            thread = ImageLoadThread("dummy.nii", False)
            thread.run()

            # Verifica che load sia stato chiamato con mmap
            mock_load.assert_called_once()
            call_args = mock_load.call_args
            assert call_args[1].get('mmap') == 'c'


class TestEdgeCasesAndIntegration:
    """Test per casi limite e scenari di integrazione"""

    def test_very_small_image(self, temp_workspace):
        """Test con immagine molto piccola (1x1x1)"""
        data = np.array([[[42.0]]])
        img = nib.Nifti1Image(data, np.eye(4))

        nifti_path = os.path.join(temp_workspace, "tiny.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append(img_data)
        )

        thread.run()

        assert len(results) == 1
        assert results[0].shape == (1, 1, 1)
        assert np.isclose(results[0][0, 0, 0], 0.0) or np.isclose(results[0][0, 0, 0], 1.0)

    def test_large_dimensions(self, temp_workspace):
        """Test con immagine di grandi dimensioni"""
        # Simula un volume grande, ma gestibile
        data = np.zeros((100, 100, 100), dtype=np.float32)
        data[50, 50, 50] = 100  # aggiunge un punto ad alta intensità

        img = nib.Nifti1Image(data, np.eye(4))
        nifti_path = os.path.join(temp_workspace, "large.nii.gz")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        results = []
        thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            results.append((img_data, dims, is_4d))
        )

        thread.run()

        assert len(results) == 1
        img_data, dims, is_4d = results[0]

        assert dims == (100, 100, 100)
        assert not is_4d
        assert img_data.shape == (100, 100, 100)
        assert np.all((img_data >= 0) & (img_data <= 1)), "I valori normalizzati devono stare tra 0 e 1"
        assert np.isclose(img_data[50, 50, 50], 1.0, atol=1e-3)

    def test_invalid_file_emits_error(self, temp_workspace):
        """Test che un file non NIfTI emetta il segnale di errore"""
        invalid_path = os.path.join(temp_workspace, "not_nifti.txt")
        with open(invalid_path, "w") as f:
            f.write("questa non è un'immagine")

        thread = ImageLoadThread(invalid_path, False)

        errors = []
        thread.error.connect(lambda msg: errors.append(msg))

        thread.run()

        assert len(errors) == 1
        assert any(keyword in errors[0] for keyword in [
            "Not a valid NIfTI",
            "No such file",
            "Cannot work out file type"
        ])

    def test_save_nifti_thread_success(self, temp_workspace):
        """Test d’integrazione: salvataggio NIfTI + JSON"""
        data = np.ones((5, 5, 5), dtype=np.uint8)
        affine = np.eye(4)
        nifti_path = os.path.join(temp_workspace, "roi.nii.gz")
        json_path = os.path.join(temp_workspace, "roi.json")

        radius = 2.0
        difference = 0.5
        source_dict = {"radius": radius, "difference": difference}

        thread = SaveNiftiThread(
            data=data,
            affine=affine,
            path=nifti_path,
            json_path=json_path,
            relative_path="sub-01/anat/T1w.nii.gz",
            source_dict=source_dict
        )

        results = []
        thread.success.connect(lambda npath, jpath: results.append((npath, jpath)))

        thread.run()

        # Controlla che i file siano stati creati
        assert os.path.exists(nifti_path)
        assert os.path.exists(json_path)

        assert len(results) == 1
        npath, jpath = results[0]
        assert npath.endswith(".nii.gz")
        assert jpath.endswith(".json")

        # Controlla che il JSON contenga i campi corretti
        import json
        with open(json_path) as f:
            meta = json.load(f)

        assert "Origin" in meta
        assert meta["Origin"]["radius"] == 2.0

    def test_save_nifti_thread_error(self, tmp_path):
        """Test di errore: percorso non scrivibile"""
        bad_path = "/invalid/path/roi.nii.gz"
        json_path = os.path.join(tmp_path, "roi.json")

        radius = 1.0
        difference = 0.2
        source_dict = {"radius": radius, "difference": difference}

        thread = SaveNiftiThread(
            data=np.ones((2, 2, 2)),
            affine=np.eye(4),
            path=bad_path,
            json_path=json_path,
            relative_path="sub-01/anat/T1w.nii.gz",
            source_dict=source_dict
        )

        errors = []
        thread.error.connect(lambda msg: errors.append(msg))

        thread.run()

        assert len(errors) == 1
        assert isinstance(errors[0], str)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])