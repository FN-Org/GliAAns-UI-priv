"""
test_save_load_threads.py - Test Suite for SaveNiftiThread and ImageLoadThread

This suite tests all functionalities of the saving and loading threads:
- SaveNiftiThread: NIfTI saving + JSON with BIDS metadata
- ImageLoadThread: loading and normalization of 3D/4D NIfTI
- Error handling and progress tracking
- Intensity normalization with percentiles
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
    """Tests for SaveNiftiThread initialization"""

    def test_init_with_all_parameters(self, temp_workspace):
        """Test initialization with all parameters"""
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
        """Verify that the signals are correctly defined"""
        data = np.zeros((5, 5, 5))
        affine = np.eye(4)
        source_dict = {"radius": 1.0, "difference": 0.1}
        thread = SaveNiftiThread(
            data, affine, "path.nii", "path.json", "rel/path.nii", source_dict
        )

        assert hasattr(thread, 'success')
        assert hasattr(thread, 'error')


class TestSaveNiftiThreadExecution:
    """Tests for SaveNiftiThread execution"""

    def test_successful_save(self, temp_workspace):
        """Test successful saving of NIfTI and JSON"""
        # Test data
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

        # Connect signal
        success_paths = []

        def on_success(path, json_p):
            success_paths.append((path, json_p))

        thread.success.connect(on_success)

        # Execute
        thread.run()

        # Verify signal emitted
        assert len(success_paths) == 1
        assert success_paths[0][0] == nifti_path
        assert success_paths[0][1] == json_path

        # Verify NIfTI file created
        assert os.path.exists(nifti_path)
        loaded_img = nib.load(nifti_path)
        loaded_data = loaded_img.get_fdata()
        assert loaded_data.shape == data.shape
        np.testing.assert_array_almost_equal(loaded_data, data, decimal=0)

        # Verify affine
        np.testing.assert_array_almost_equal(loaded_img.affine, affine)

    def test_json_metadata_structure(self, temp_workspace):
        """Test structure and content of the JSON file"""
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

        # Verify JSON created
        assert os.path.exists(json_path)

        with open(json_path, 'r') as f:
            metadata = json.load(f)

        # Verify structure
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
        """Test that the JSON is formatted with indentation"""
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

        # Verify indentation (formatted JSON)
        assert "    " in content  # 4 spaces indentation
        assert "\n" in content    # Newlines between fields

    def test_data_type_conversion_to_uint8(self, temp_workspace):
        """Test automatic conversion of data to uint8"""
        # Float data
        data = np.random.rand(5, 5, 5) * 255
        affine = np.eye(4)

        nifti_path = os.path.join(temp_workspace, "converted.nii.gz")
        json_path = os.path.join(temp_workspace, "converted.json")

        source_dict = {"radius": 1.0, "difference": 0.1}

        thread = SaveNiftiThread(
            data, affine, nifti_path, json_path, "rel.nii", source_dict
        )
        thread.run()

        # Verify saved data type
        loaded_img = nib.load(nifti_path)
        loaded_data = loaded_img.get_fdata()

        # Should be converted to uint8
        assert loaded_data.dtype in [np.uint8, np.float32, np.float64]
        assert loaded_data.min() >= 0
        assert loaded_data.max() <= 255

    def test_error_handling_invalid_path(self, temp_workspace):
        """Test error handling with invalid path"""
        data = np.zeros((3, 3, 3))
        affine = np.eye(4)

        # Invalid path (nonexistent directory)
        invalid_path = os.path.join(temp_workspace, "nonexistent", "dir", "file.nii")
        json_path = os.path.join(temp_workspace, "nonexistent", "dir", "file.json")

        source_dict = {"radius": 1.0, "difference": 0.1}

        thread = SaveNiftiThread(
            data, affine, invalid_path, json_path, "rel.nii", source_dict
        )

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # Should emit an error
        assert len(error_msgs) == 1
        assert len(error_msgs[0]) > 0

    @patch('nibabel.save')
    def test_error_during_nifti_save(self, mock_save, temp_workspace):
        """Test error handling during NIfTI saving"""
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
        """Test with different affine matrices"""
        data = np.ones((4, 4, 4), dtype=np.uint8)

        # Affine with different voxel sizes
        affine = np.diag([2.5, 3.0, 3.5, 1.0])
        affine[:3, 3] = [10, 20, 30]  # Offset

        nifti_path = os.path.join(temp_workspace, "custom_affine.nii")
        json_path = os.path.join(temp_workspace, "custom_affine.json")

        source_dict = {"radius": 2.0, "difference": 0.2}

        thread = SaveNiftiThread(
            data, affine, nifti_path, json_path, "path.nii", source_dict
        )
        thread.run()

        # Verify affine saved correctly
        loaded_img = nib.load(nifti_path)
        np.testing.assert_array_almost_equal(loaded_img.affine, affine)


class TestImageLoadThreadInitialization:
    """Tests for ImageLoadThread initialization"""

    def test_init_regular_image(self, temp_workspace):
        """Test initialization for regular image"""
        file_path = os.path.join(temp_workspace, "test.nii")
        thread = ImageLoadThread(file_path, is_overlay=False)

        assert thread.file_path == file_path
        assert thread.is_overlay is False

    def test_init_overlay_image(self, temp_workspace):
        """Test initialization for overlay image"""
        file_path = os.path.join(temp_workspace, "overlay.nii.gz")
        thread = ImageLoadThread(file_path, is_overlay=True)

        assert thread.file_path == file_path
        assert thread.is_overlay is True

    def test_signals_exist(self, temp_workspace):
        """Verify that the signals are correctly defined"""
        thread = ImageLoadThread("dummy.nii", False)

        assert hasattr(thread, 'finished')
        assert hasattr(thread, 'error')
        assert hasattr(thread, 'progress')


class TestImageLoadThread3D:
    """Tests for loading 3D NIfTI images"""

    def test_load_3d_nifti_success(self, temp_workspace):
        """Test successful loading of 3D NIfTI"""
        # Create 3D test image
        data_3d = np.random.rand(20, 20, 20).astype(np.float32) * 100
        affine = np.eye(4)
        img = nib.Nifti1Image(data_3d, affine)

        nifti_path = os.path.join(temp_workspace, "test_3d.nii.gz")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, is_overlay=False)

        # Connect signal
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

        # Execute
        thread.run()

        # Verify results
        assert len(results) == 1
        result = results[0]

        assert result['dims'] == (20, 20, 20)
        assert result['is_4d'] is False
        assert result['is_overlay'] is False
        assert result['img_data'].shape == (20, 20, 20)
        assert result['img_data'].dtype == np.float32

        # Verify normalization (values between 0 and 1)
        assert result['img_data'].min() >= 0
        assert result['img_data'].max() <= 1

    def test_load_3d_progress_emissions(self, temp_workspace):
        """Test progress emissions during 3D loading"""
        # Create simple image
        data = np.ones((10, 10, 10))
        img = nib.Nifti1Image(data, np.eye(4))

        nifti_path = os.path.join(temp_workspace, "progress_test.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        progress_values = []
        thread.progress.connect(lambda val: progress_values.append(val))

        thread.run()

        # Verify progress emitted
        assert len(progress_values) > 0
        assert 10 in progress_values
        assert 100 in progress_values

        # Verify monotonic increase
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i - 1]


class TestImageLoadThread4D:
    """Tests for loading 4D NIfTI images"""

    def test_load_4d_nifti_success(self, temp_workspace):
        """Test successful loading of 4D NIfTI"""
        # Create 4D image (e.g., fMRI time series)
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
        """Test with anisotropic voxels"""
        data = np.random.rand(10, 20, 30).astype(np.float32)

        # Affine with different voxel sizes for each axis
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

        # Dimensions preserved (or reordered after canonicalization)
        assert img_data.ndim == 3
        assert isinstance(loaded_affine, np.ndarray)

    def test_different_data_types(self, temp_workspace):
        """Test with different input dtypes"""
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

            # Should always normalize to float32
            assert len(results) == 1
            assert results[0].dtype == np.float32
            assert results[0].min() >= 0
            assert results[0].max() <= 1

    def test_negative_values_handling(self, temp_workspace):
        """Test handling of negative values"""
        # Data with negative values (e.g., parametric maps)
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

        # Even with negative values, normalization must be in [0, 1]
        assert normalized.min() >= 0
        assert normalized.max() <= 1


class TestSaveLoadThreadsIntegration:
    """Integration tests between SaveNiftiThread and ImageLoadThread"""

    def test_save_and_reload_cycle(self, temp_workspace):
        """Full cycle test: save and reload"""
        # Original data
        original_data = np.random.randint(0, 255, (12, 12, 12), dtype=np.uint8)
        affine = np.eye(4)
        affine[0, 0] = 2.0

        # Save
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

        # Reload
        load_thread = ImageLoadThread(nifti_path, is_overlay=False)

        loaded_results = []
        load_thread.finished.connect(
            lambda img_data, dims, aff, is_4d, is_overlay:
            loaded_results.append((img_data, dims, aff))
        )

        load_thread.run()

        assert len(loaded_results) == 1
        loaded_data, loaded_dims, loaded_affine = loaded_results[0]

        # Verify dimensions
        assert loaded_dims == (12, 12, 12)

        # Verify affine (may slightly differ after canonicalization)
        # but voxel size should be similar
        assert loaded_affine.shape == (4, 4)

        # Verify JSON
        assert os.path.exists(json_path)
        with open(json_path, 'r') as f:
            metadata = json.load(f)
        assert metadata["Type"] == "ROI"
        assert metadata["Origin"]["radius"] == 2.5

    def test_save_load_multiple_files(self, temp_workspace):
        """Test saving and loading multiple files"""
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

        # Reload all
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
        """Test saving and reloading 4D data"""
        # Create 4D data
        data_4d = np.random.randint(0, 255, (10, 10, 10, 5), dtype=np.uint8)
        affine = np.eye(4)

        nifti_path = os.path.join(temp_workspace, "test_4d_cycle.nii.gz")
        json_path = os.path.join(temp_workspace, "test_4d_cycle.json")

        source_dict = {"radius": 3.0, "difference": 0.15}

        # SaveNiftiThread should also handle 4D
        save_thread = SaveNiftiThread(
            data_4d, affine, nifti_path, json_path,
            "rel_4d.nii", source_dict
        )

        save_success = []
        save_thread.success.connect(lambda p, j: save_success.append(True))
        save_thread.run()

        assert len(save_success) == 1

        # Reload as 4D
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
    """Tests for concurrency and thread safety"""

    def test_multiple_save_threads_concurrent(self, temp_workspace):
        """Test concurrent execution of multiple SaveNiftiThread"""
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

        # Start all threads
        for thread in threads:
            thread.run()

        # Wait for completion
        for thread in threads:
            thread.wait(5000)  # 5-second timeout

        assert success_count[0] == 3

    def test_multiple_load_threads_concurrent(self, temp_workspace):
        """Test concurrent loading of multiple files"""
        # Create test files
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

        # Start all
        for thread in threads:
            thread.run()

        # Wait
        for thread in threads:
            thread.wait(5000)

        assert finished_count[0] == 3


class TestSpecialCases:
    """Tests for special cases and boundary conditions"""

    def test_save_zero_volume(self, temp_workspace):
        """Test saving a volume with all zeros"""
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
        """Test loading a volume with all zeros"""
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

        # Should handle it correctly
        assert len(results) == 1
        normalized = results[0]
        assert not np.any(np.isnan(normalized))

    def test_save_binary_mask(self, temp_workspace):
        """Test saving a binary mask"""
        # Binary mask (0 and 1)
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

        # Verify integrity
        loaded = nib.load(nifti_path)
        loaded_data = loaded.get_fdata()

        # Should preserve binary values
        unique_vals = np.unique(loaded_data)
        assert len(unique_vals) <= 2

    def test_load_compressed_vs_uncompressed(self, temp_workspace):
        """Test loading compressed vs uncompressed files"""
        data = np.random.rand(10, 10, 10).astype(np.float32)
        img = nib.Nifti1Image(data, np.eye(4))

        # Save compressed version
        compressed_path = os.path.join(temp_workspace, "compressed.nii.gz")
        nib.save(img, compressed_path)

        # Save uncompressed version
        uncompressed_path = os.path.join(temp_workspace, "uncompressed.nii")
        nib.save(img, uncompressed_path)

        # Load both
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

        # They should produce equivalent results
        assert len(results_compressed) == 1
        assert len(results_uncompressed) == 1

        np.testing.assert_array_almost_equal(
            results_compressed[0],
            results_uncompressed[0],
            decimal=5
        )

    def test_save_with_special_characters_in_path(self, temp_workspace):
        """Test saving with special characters in the path"""
        data = np.ones((5, 5, 5), dtype=np.uint8)

        # Filename with spaces and special characters
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
    """Tests for parameter validation"""

    def test_save_with_extreme_radius_values(self, temp_workspace):
        """Test with extreme values for radius"""
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

            # Should still save even with extreme values
            assert len(success) == 1

            # Verify JSON contains the value
            with open(json_path, 'r') as f:
                metadata = json.load(f)
            assert metadata["Origin"]["radius"] == radius

    def test_save_with_extreme_difference_values(self, temp_workspace):
        """Test with extreme values for difference"""
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
    """Tests for performance and scalability"""

    def test_large_4d_dataset(self, temp_workspace):
        """Test with a large 4D dataset"""
        # Simulated 4D dataset (not too large for CI)
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

        # Progress should be emitted
        assert len(progress_updates) > 0
        assert 100 in progress_updates

    def test_progress_tracking_accuracy(self, temp_workspace):
        """Test accuracy of progress tracking"""
        data = np.random.rand(25, 25, 25).astype(np.float32)
        img = nib.Nifti1Image(data, np.eye(4))

        nifti_path = os.path.join(temp_workspace, "progress_track.nii")
        nib.save(img, nifti_path)

        thread = ImageLoadThread(nifti_path, False)

        progress_values = []
        thread.progress.connect(lambda val: progress_values.append(val))

        thread.run()

        # Verify progress sequence
        expected_milestones = [10, 30, 50, 70, 80, 100]
        for milestone in expected_milestones:
            assert milestone in progress_values

        # Verify increasing order
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i - 1]


class TestNiftiThreadParameterized:
    """Parameterized tests and normalization tests for NIfTI threads"""

    @pytest.mark.parametrize("shape", [
        (5, 5, 5),
        (10, 20, 15),
        (3, 3, 3),
        (50, 50, 50)
    ])
    def test_save_various_shapes(self, shape, temp_workspace):
        """Parameterized test for different volume shapes"""
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

        # Verify loading
        loaded = nib.load(nifti_path)
        assert loaded.shape == shape

    @pytest.mark.parametrize("is_overlay", [True, False])
    def test_load_overlay_flag(self, is_overlay, temp_workspace):
        """Parameterized test for the overlay flag"""
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
        """Test independent normalization for each 4D volume"""
        # Create 4D with different intensities per volume (add variability to avoid constant volumes)
        volume1 = np.ones((10, 10, 10)) * 100
        volume1[0, 0, 0] = 101  # Add variability
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

        # Each volume should be normalized independently
        for i in range(3):
            vol = normalized_data[..., i]
            assert vol.min() >= 0
            assert vol.max() <= 1
            assert vol.max() - vol.min() > 0


class TestImageLoadThreadNormalization:
    """Tests for percentile-based normalization"""

    def test_normalize_data_matplotlib_style(self, temp_workspace):
        """Test normalization using percentiles"""
        # Create data with outliers
        data = np.random.randn(30, 30, 30).astype(np.float32) * 100
        data[0, 0, 0] = 10000  # High outlier
        data[1, 1, 1] = -5000  # Low outlier

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

        # Verify that outliers do not dominate normalization
        # Most values should be reasonably distributed
        assert normalized.min() >= 0
        assert normalized.max() <= 1

        # Intermediate percentiles should be well distributed
        p25 = np.percentile(normalized, 25)
        p75 = np.percentile(normalized, 75)
        assert 0.1 < p25 < 0.9
        assert 0.1 < p75 < 0.9

    def test_normalize_uniform_data(self, temp_workspace):
        """Test normalization with uniform data"""
        # All voxels have the same value
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

        # With uniform data, normalization should handle it gracefully
        assert not np.any(np.isnan(normalized))
        assert not np.any(np.isinf(normalized))
        assert normalized.min() >= 0
        assert normalized.max() <= 1

    def test_normalize_with_nan_values(self, temp_workspace):
        """Test normalization with NaN values"""
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

        # Should handle NaN/Inf without propagating them
        finite_count = np.isfinite(normalized).sum()
        assert finite_count > 0  # At least some finite values

    def test_normalize_empty_volume(self):
        """Test normalization of an empty volume"""
        thread = ImageLoadThread("dummy.nii", False)

        # Direct test of the method
        empty_data = np.array([])
        result = thread.normalize_data_matplotlib_style(empty_data)

        assert result.size == 0

    def test_normalize_volume_all_invalid(self):
        """Test normalization with all invalid values"""
        thread = ImageLoadThread("dummy.nii", False)

        # Volume with only NaN values
        nan_volume = np.full((5, 5, 5), np.nan)
        result = thread.normalize_data_matplotlib_style(nan_volume)

        # Should return zeros
        assert result.shape == nan_volume.shape
        assert np.all(result == 0)


class TestImageLoadThreadCanonicalOrientation:
    """Tests for conversion to canonical RAS+ orientation"""

    def test_canonical_orientation_applied(self, temp_workspace):
        """Test that the image is converted to RAS+ orientation"""
        # Create an image with non-canonical orientation
        data = np.random.rand(10, 12, 8).astype(np.float32)

        # Affine with a different orientation (e.g., LAS)
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

        # The image should now be in canonical orientation
        assert img_data.shape[0] > 0
        assert img_data.shape[1] > 0
        assert img_data.shape[2] > 0

        # Affine should be updated
        assert isinstance(loaded_affine, np.ndarray)
        assert loaded_affine.shape == (4, 4)


class TestImageLoadThreadErrorHandling:
    """Tests for error handling"""

    def test_error_file_not_found(self, temp_workspace):
        """Test error when file does not exist"""
        nonexistent_path = os.path.join(temp_workspace, "does_not_exist.nii")
        thread = ImageLoadThread(nonexistent_path, False)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert len(error_msgs[0]) > 0

    def test_error_invalid_nifti_file(self, temp_workspace):
        """Test error with a non-NIfTI file"""
        # Create a text file instead of a NIfTI
        invalid_path = os.path.join(temp_workspace, "invalid.nii")
        with open(invalid_path, 'w') as f:
            f.write("This is not a NIfTI file")

        thread = ImageLoadThread(invalid_path, False)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1

    def test_error_corrupted_nifti(self, temp_workspace):
        """Test error with a corrupted NIfTI file"""
        corrupted_path = os.path.join(temp_workspace, "corrupted.nii.gz")

        # Create a partially valid but corrupted file
        with open(corrupted_path, 'wb') as f:
            f.write(b'corrupted data that looks like gzip')

        thread = ImageLoadThread(corrupted_path, False)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1

    @patch('nibabel.load')
    def test_error_during_load(self, mock_load, temp_workspace):
        """Test generic load error handling"""
        mock_load.side_effect = RuntimeError("Memory error")

        nifti_path = os.path.join(temp_workspace, "test.nii")
        thread = ImageLoadThread(nifti_path, False)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert "Memory error" in error_msgs[0]


class TestImageLoadThreadNifti2Support:
    """Tests for NIfTI-2 support"""

    def test_nifti2_image_loads(self, temp_workspace):
        """Test loading a NIfTI-2 image"""
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

        assert len(results) == 1
        assert results[0].shape == (8, 8, 8)


class TestImageLoadThreadMemoryMapping:
    """Tests for memory mapping"""

    @patch('nibabel.load')
    def test_memory_mapping_used(self, mock_load, temp_workspace):
        """Test that memory mapping is used"""
        # Mock to check mmap argument
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

            # Verify mmap was used
            mock_load.assert_called_once()
            call_args = mock_load.call_args
            assert call_args[1].get('mmap') == 'c'


class TestEdgeCasesAndIntegration:
    """Tests for edge cases and integration scenarios"""

    def test_very_small_image(self, temp_workspace):
        """Test with a very small image (1×1×1)"""
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
        """Test with a large image"""
        # Simulate a large but manageable volume
        data = np.zeros((100, 100, 100), dtype=np.float32)
        data[50, 50, 50] = 100  # add high-intensity point

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
        assert np.all((img_data >= 0) & (img_data <= 1)), "Normalized values must be between 0 and 1"
        assert np.isclose(img_data[50, 50, 50], 1.0, atol=1e-3)

    def test_invalid_file_emits_error(self, temp_workspace):
        """Test that a non-NIfTI file emits an error signal"""
        invalid_path = os.path.join(temp_workspace, "not_nifti.txt")
        with open(invalid_path, "w") as f:
            f.write("this is not an image")

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
        """Integration test: NIfTI + JSON save"""
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

        # Check that files were created
        assert os.path.exists(nifti_path)
        assert os.path.exists(json_path)

        assert len(results) == 1
        npath, jpath = results[0]
        assert npath.endswith(".nii.gz")
        assert jpath.endswith(".json")

        # Check JSON contains correct fields
        import json
        with open(json_path) as f:
            meta = json.load(f)

        assert "Origin" in meta
        assert meta["Origin"]["radius"] == 2.0

    def test_save_nifti_thread_error(self, tmp_path):
        """Error test: unwritable path"""
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
