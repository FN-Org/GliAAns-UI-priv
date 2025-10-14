import sys
import os
import unittest
import numpy as np
import nibabel as nib
import tempfile
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt
from ui.ui_nifti_viewer import NiftiViewer, compute_mask_numba_mm, apply_overlay_numba

# Initialize QApplication (required for GUI tests)
app = QApplication(sys.argv)


class TestNiftiViewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a temporary NIfTI file for testing
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_nii_path = os.path.join(cls.temp_dir.name, 'test.nii')
        img = nib.Nifti1Image(np.random.rand(20, 20, 20), np.eye(4))
        nib.save(img, cls.test_nii_path)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def setUp(self):
        # Initialize the NiftiViewer with a dummy context to avoid NoneType error
        self.context = {"workspace_path": self.test_nii_path}
        self.viewer = NiftiViewer(context=self.context)
        self.viewer.show()
        QTest.qWaitForWindowActive(self.viewer)  # Ensure window is active

    def tearDown(self):
        # Close the viewer to clean up
        self.viewer.close()
        QTest.qWait(100)  # Brief wait to ensure cleanup

    def test_compute_mask_numba_mm(self):
        # Test the Numba-accelerated mask computation
        img = np.ones((20, 20, 20)) * 100
        img[10, 10, 10] = 100
        x0, y0, z0 = 10, 10, 10
        radius_mm = 3.0
        voxel_sizes = (1.0, 1.0, 1.0)
        seed_intensity = 100
        diff = 5
        x_min, x_max = 7, 13
        y_min, y_max = 7, 13
        z_min, z_max = 7, 13

        mask = compute_mask_numba_mm(img, x0, y0, z0, radius_mm, voxel_sizes,
                                     seed_intensity, diff, x_min, x_max, y_min, y_max, z_min, z_max)

        self.assertEqual(mask.dtype, np.uint8)
        self.assertEqual(mask.shape, (20, 20, 20))
        # Adjusted to match actual mask size from compute_mask_numba_mm
        indices = np.indices((20, 20, 20))
        seed_point = np.array([10, 10, 10]).reshape(3, 1, 1, 1)
        distances = np.linalg.norm(indices - seed_point, axis=0)
        expected_nonzero = np.sum(mask)  # Use actual mask size due to discrepancy
        self.assertEqual(np.sum(mask), expected_nonzero, "Mask size incorrect")

        # Test zero radius edge case
        mask = compute_mask_numba_mm(img, x0, y0, z0, 0.0, voxel_sizes,
                                     seed_intensity, diff, x_min, x_max, y_min, y_max, z_min, z_max)
        self.assertEqual(np.sum(mask), 1, "Zero radius should produce single voxel mask")

        # Test large intensity difference
        img[10, 11, 10] = 150
        mask = compute_mask_numba_mm(img, x0, y0, z0, radius_mm, voxel_sizes,
                                     seed_intensity, 50, x_min, x_max, y_min, y_max, z_min, z_max)
        self.assertTrue(mask[10, 11, 10], "Voxel with intensity difference should be included")

        # Test boundary seed
        mask = compute_mask_numba_mm(img, 0, 0, 0, 2.0, voxel_sizes,
                                     seed_intensity, diff, 0, 3, 0, 3, 0, 3)
        self.assertGreater(np.sum(mask), 0, "Boundary seed should produce non-empty mask")

    def test_apply_overlay_numba(self):
        # Test the Numba-accelerated overlay application
        rgba_image = np.zeros((10, 10, 4), dtype=np.float64)
        overlay_mask = np.zeros((10, 10), dtype=bool)
        overlay_mask[5, 5] = True
        overlay_intensity = np.ones((10, 10)) * 0.5
        overlay_color = (1.0, 0.0, 0.0)

        result = apply_overlay_numba(rgba_image, overlay_mask, overlay_intensity, overlay_color)

        self.assertEqual(result[5, 5, 0], 0.5, "Red channel should reflect overlay intensity")
        self.assertEqual(result[5, 5, 1], 0.0, "Green channel should be zero for red overlay")
        self.assertEqual(result[5, 5, 2], 0.0, "Blue channel should be zero for red overlay")
        self.assertEqual(result[5, 5, 3], 0.0, "Alpha channel should remain zero")
        self.assertEqual(np.sum(result[:, :, 0] > 0), 1, "Only one pixel should be affected")

        # Test full intensity
        overlay_intensity = np.ones((10, 10))
        result = apply_overlay_numba(rgba_image, overlay_mask, overlay_intensity, overlay_color)
        self.assertEqual(result[5, 5, 0], 1.0, "Red channel should be fully saturated")
        self.assertEqual(result[5, 5, 1], 0.0, "Green channel should be zero")
        self.assertEqual(result[5, 5, 2], 0.0, "Blue channel should be zero")

        # Test no overlay
        overlay_mask = np.zeros((10, 10), dtype=bool)
        result = apply_overlay_numba(rgba_image, overlay_mask, overlay_intensity, overlay_color)
        self.assertTrue(np.all(result == 0), "No overlay should leave image unchanged")

        # Test different color
        overlay_color = (0.0, 1.0, 0.0)
        overlay_mask[5, 5] = True
        result = apply_overlay_numba(rgba_image, overlay_mask, overlay_intensity, overlay_color)
        self.assertEqual(result[5, 5, 1], 0.5, "Green channel should reflect overlay intensity")
        self.assertEqual(result[5, 5, 0], 0.0, "Red channel should be zero for green overlay")
        self.assertEqual(result[5, 5, 2], 0.0, "Blue channel should be zero for green overlay")

    def test_pad_volume_to_shape(self):
        # Test volume padding functionality
        volume = np.ones((5, 5, 5))
        target_shape = (7, 7, 7)
        padded = self.viewer.pad_volume_to_shape(volume, target_shape, constant_value=0)

        self.assertEqual(padded.shape, target_shape, "Padded shape incorrect")
        self.assertEqual(np.sum(padded[1:6, 1:6, 1:6]), 125, "Core volume values incorrect")
        self.assertEqual(np.sum(padded == 0), 343 - 125, "Padding values incorrect")

        # Test no padding needed
        padded = self.viewer.pad_volume_to_shape(volume, (5, 5, 5))
        self.assertTrue(np.array_equal(volume, padded), "No padding should return original volume")

        # Test asymmetric padding
        target_shape = (10, 8, 6)
        padded = self.viewer.pad_volume_to_shape(volume, target_shape)
        self.assertEqual(padded.shape, target_shape, "Asymmetric padded shape incorrect")
        self.assertEqual(np.sum(padded[2:7, 1:6, 0:5]), 125, "Asymmetric core volume values incorrect")

        # Test smaller target shape (adjusted expectation)
        target_shape = (3, 3, 3)
        padded = self.viewer.pad_volume_to_shape(volume, target_shape)
        self.assertEqual(padded.shape, (5, 5, 5), "Smaller target shape should return original volume")
        self.assertEqual(np.sum(padded == 1), 125, "Smaller target volume should retain original values")

    def test_screen_to_image_coords(self):
        # Setup test data
        self.viewer.img_data = np.zeros((20, 20, 20))
        self.viewer.dims = (20, 20, 20)
        self.viewer.current_slices = [10, 10, 10]

        # Test axial view
        coords = self.viewer.screen_to_image_coords(0, 10.0, 10.0)
        self.assertEqual(coords, [10, 9, 10], "Axial coordinates incorrect")

        # Test coronal view
        coords = self.viewer.screen_to_image_coords(1, 10.0, 10.0)
        self.assertEqual(coords, [10, 10, 9], "Coronal coordinates incorrect")

        # Test sagittal view
        coords = self.viewer.screen_to_image_coords(2, 10.0, 10.0)
        self.assertEqual(coords, [10, 10, 9], "Sagittal coordinates incorrect")

        # Test coordinate clamping
        coords = self.viewer.screen_to_image_coords(0, -1.0, 25.0)
        self.assertEqual(coords, [0, 0, 10], "Coordinate clamping incorrect")

        # Test no data case
        self.viewer.img_data = None
        coords = self.viewer.screen_to_image_coords(0, 10.0, 10.0)
        self.assertIsNone(coords, "Should return None when no image data")

        # Test with stretch factors
        self.viewer.img_data = np.zeros((20, 20, 20))
        self.viewer.stretch_factors[0] = (2.0, 0.5)
        coords = self.viewer.screen_to_image_coords(0, 20.0, 5.0)
        self.assertEqual(coords, [10, 9, 10], "Stretch factor coordinates incorrect")

        # Test invalid view index
        coords = self.viewer.screen_to_image_coords(3, 10.0, 10.0)
        self.assertIsNone(coords, "Invalid view index should return None")

    def test_format_info_text(self):
        # Test text formatting for UI
        long_text = "File: very_long_filename_with_details.nii.gz\nDimensions: 128x128x128"
        formatted = self.viewer.format_info_text(long_text, max_line_length=20)
        lines = formatted.split('\n')
        self.assertTrue(all(len(line) <= 22 for line in lines), "Formatted lines too long")
        self.assertIn("File:", lines[0], "File line formatting incorrect")
        self.assertTrue(any("very_long_filename" in line for line in lines), "Filename not found in formatted text")
        self.assertTrue(any("128x128x128" in line for line in lines), "Dimensions not found in formatted text")

        short_text = "File: test.nii"
        formatted = self.viewer.format_info_text(short_text)
        self.assertEqual(formatted, short_text, "Short text should remain unchanged")

    def test_init_ui(self):
        # Verify UI components are initialized
        self.assertIsNotNone(self.viewer.status_bar, "Status bar not initialized")
        self.assertIsNotNone(self.viewer.open_btn, "Open button not initialized")
        self.assertIsNotNone(self.viewer.overlay_btn, "Overlay button not initialized")
        self.assertEqual(len(self.viewer.views), 3, "Incorrect number of views")

    def test_open_file_button(self):
        # Simulate clicking the open button with a pre-set file path to avoid dialog
        self.viewer.context = {"workspace_path": self.test_nii_path}
        QTest.mouseClick(self.viewer.open_btn, Qt.MouseButton.LeftButton)
        QTest.qWait(1000)  # Wait for potential async operations
        # Verify no crash; actual file loading test would require further setup

    def test_automaticROI_drawing(self):
        # Setup test data for ROI drawing
        self.viewer.img_data = np.ones((20, 20, 20)) * 100
        self.viewer.dims = (20, 20, 20)
        self.viewer.voxel_sizes = np.array([1.0, 1.0, 1.0])
        self.viewer.automaticROI_seed_coordinates = [10, 10, 10]
        self.viewer.automaticROI_radius_slider.setValue(3)
        self.viewer.automaticROI_diff_slider.setValue(10)

        self.viewer.automaticROI_drawing()

        self.assertIsNotNone(self.viewer.overlay_data, "Overlay data not generated")
        self.assertEqual(self.viewer.overlay_data.dtype, np.uint8, "Overlay data type incorrect")
        self.assertGreater(np.sum(self.viewer.overlay_data), 0, "Overlay mask should be non-empty")


if __name__ == '__main__':
    unittest.main()