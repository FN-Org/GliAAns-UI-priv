import sys
import os
import unittest
import numpy as np
import nibabel as nib
import tempfile
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt, QEventLoop, QTimer
from unittest.mock import patch, MagicMock

from main.ui.nifti_viewer import NiftiViewer, compute_mask_numba_mm, apply_overlay_numba

app = QApplication(sys.argv)


class TestNiftiViewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(cls.temp_dir.name,'sub-01'), exist_ok=True)
        cls.test_nii_path = os.path.join(cls.temp_dir.name,'sub-01', 'test.nii')
        img = nib.Nifti1Image(np.random.rand(20, 20, 20), np.eye(4))
        nib.save(img, cls.test_nii_path)

        cls.test_4d_nii_path = os.path.join(cls.temp_dir.name,'sub-01', 'test4d.nii')
        img4d = nib.Nifti1Image(np.random.rand(20, 20, 20, 10), np.eye(4))
        nib.save(img4d, cls.test_4d_nii_path)

        cls.test_overlay_path = os.path.join(cls.temp_dir.name,'sub-01','overlay.nii')
        overlay = nib.Nifti1Image(np.random.rand(20, 20, 20), np.eye(4))
        nib.save(overlay, cls.test_overlay_path)

        cls.test_save_dir = os.path.join(cls.temp_dir.name, 'derivatives/manual_masks/sub-01/anat')
        os.makedirs(cls.test_save_dir, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def setUp(self):
        self.context = {"workspace_path": self.temp_dir.name}
        self.viewer = NiftiViewer(context=self.context)
        self.viewer.show()
        QTest.qWaitForWindowActive(self.viewer)

    def tearDown(self):
        self.viewer.close()
        QTest.qWait(100)

    def test_compute_mask_numba_mm(self):
        img = np.ones((20, 20, 20)) * 100
        img[10, 10, 10] = 100
        x0, y0, z0 = 10, 10, 10
        radius_mm = 3.0
        voxel_sizes = (1.0, 1.0, 1.0)  # Use tuple for function call
        seed_intensity = 100
        diff = 5
        x_min, x_max = 7, 13
        y_min, y_max = 7, 13
        z_min, z_max = 7, 13

        mask = compute_mask_numba_mm(img, x0, y0, z0, radius_mm, voxel_sizes,
                                     seed_intensity, diff, x_min, x_max, y_min, y_max, z_min, z_max)

        self.assertEqual(mask.dtype, np.uint8)
        self.assertEqual(mask.shape, (20, 20, 20))
        indices = np.indices((20, 20, 20))
        seed_point = np.array([x0, y0, z0]).reshape(3, 1, 1, 1)


        mask = compute_mask_numba_mm(img, x0, y0, z0, 0.0, voxel_sizes,
                                     seed_intensity, diff, x_min, x_max, y_min, y_max, z_min, z_max)
        self.assertEqual(np.sum(mask), 1, "Zero radius should produce single voxel mask")

        img[10, 11, 10] = 150
        mask = compute_mask_numba_mm(img, x0, y0, z0, radius_mm, voxel_sizes,
                                     seed_intensity, 50, x_min, x_max, y_min, y_max, z_min, z_max)
        self.assertTrue(mask[10, 11, 10], "Voxel with intensity difference should be included")

        mask = compute_mask_numba_mm(img, 0, 0, 0, 2.0, voxel_sizes,
                                     seed_intensity, diff, 0, 3, 0, 3, 0, 3)
        self.assertGreater(np.sum(mask), 0, "Boundary seed should produce non-empty mask")

    def test_apply_overlay_numba(self):
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

        overlay_intensity = np.ones((10, 10))
        result = apply_overlay_numba(rgba_image, overlay_mask, overlay_intensity, overlay_color)
        self.assertEqual(result[5, 5, 0], 1.0, "Red channel should be fully saturated")
        self.assertEqual(result[5, 5, 1], 0.0, "Green channel should be zero")
        self.assertEqual(result[5, 5, 2], 0.0, "Blue channel should be zero")

        overlay_mask = np.zeros((10, 10), dtype=bool)
        result = apply_overlay_numba(rgba_image, overlay_mask, overlay_intensity, overlay_color)
        self.assertTrue(np.all(result == rgba_image), "No overlay should leave image unchanged")

        rgba_image = np.zeros((10, 10, 4), dtype=np.float64)
        overlay_color = (0.0, 1.0, 0.0)
        overlay_intensity = np.ones((10, 10)) * 0.5
        overlay_mask[5, 5] = True
        result = apply_overlay_numba(rgba_image, overlay_mask, overlay_intensity, overlay_color)

        self.assertEqual(result[5, 5, 0], 0.0, "Red channel should be zero for green overlay")
        self.assertEqual(result[5, 5, 1], 0.5, "Green channel should reflect overlay intensity")
        self.assertEqual(result[5, 5, 2], 0.0, "Blue channel should be zero for green overlay")

    def test_pad_volume_to_shape(self):
        volume = np.ones((5, 5, 5))
        target_shape = (7, 7, 7)
        padded = self.viewer.pad_volume_to_shape(volume, target_shape, constant_value=0)

        self.assertEqual(padded.shape, target_shape, "Padded shape incorrect")
        self.assertEqual(np.sum(padded[1:6, 1:6, 1:6]), 125, "Core volume values incorrect")
        self.assertEqual(np.sum(padded == 0), 343 - 125, "Padding values incorrect")

        padded = self.viewer.pad_volume_to_shape(volume, (5, 5, 5))
        self.assertTrue(np.array_equal(volume, padded), "No padding should return original volume")

        target_shape = (10, 8, 6)
        padded = self.viewer.pad_volume_to_shape(volume, target_shape)
        self.assertEqual(padded.shape, target_shape, "Asymmetric padded shape incorrect")
        self.assertEqual(np.sum(padded[2:7, 1:6, 0:5]), 125, "Asymmetric core volume values incorrect")

        target_shape = (3, 3, 3)
        padded = self.viewer.pad_volume_to_shape(volume, target_shape)
        self.assertEqual(padded.shape, (5, 5, 5), "Smaller target shape should return original volume")
        self.assertEqual(np.sum(padded == 1), 125, "Smaller target volume should retain original values")

    def test_screen_to_image_coords(self):
        self.viewer.img_data = np.zeros((20, 20, 20))
        self.viewer.dims = (20, 20, 20)
        self.viewer.current_slices = [10, 10, 10]

        coords = self.viewer.screen_to_image_coords(0, 10.0, 10.0)
        self.assertEqual(coords, [10, 9, 10], "Axial coordinates incorrect")

        coords = self.viewer.screen_to_image_coords(1, 10.0, 10.0)
        self.assertEqual(coords, [10, 10, 9], "Coronal coordinates incorrect")

        coords = self.viewer.screen_to_image_coords(2, 10.0, 10.0)
        self.assertEqual(coords, [10, 10, 9], "Sagittal coordinates incorrect")

        coords = self.viewer.screen_to_image_coords(0, -1.0, 25.0)
        self.assertEqual(coords, [0, 0, 10], "Coordinate clamping incorrect")

        self.viewer.img_data = None
        coords = self.viewer.screen_to_image_coords(0, 10.0, 10.0)
        self.assertIsNone(coords, "Should return None when no image data")

        self.viewer.img_data = np.zeros((20, 20, 20))
        self.viewer.stretch_factors[0] = (2.0, 0.5)
        coords = self.viewer.screen_to_image_coords(0, 20.0, 5.0)
        self.assertEqual(coords, [10, 9, 10], "Stretch factor coordinates incorrect")

        coords = self.viewer.screen_to_image_coords(3, 10.0, 10.0)
        self.assertIsNone(coords, "Invalid view index should return None")

    def test_format_info_text(self):
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
        self.assertIsNotNone(self.viewer.status_bar, "Status bar not initialized")
        self.assertIsNotNone(self.viewer.open_btn, "Open button not initialized")
        self.assertIsNotNone(self.viewer.overlay_btn, "Overlay button not initialized")
        self.assertEqual(len(self.viewer.views), 3, "Incorrect number of views")

    def test_open_file_button(self):
        QTest.mouseClick(self.viewer.open_btn, Qt.MouseButton.LeftButton)
        QTest.qWait(1000)

    def test_automaticROI_drawing(self):
        self.viewer.img_data = np.ones((20, 20, 20)) * 100
        self.viewer.dims = (20, 20, 20)
        self.viewer.voxel_sizes = np.array([1.0, 1.0, 1.0])
        self.viewer.automaticROI_seed_coordinates = [10, 10, 10]
        self.viewer.automaticROI_radius_slider.setValue(3)
        self.viewer.automaticROI_diff_slider.setValue(10)

        self.viewer.automaticROI_drawing()

        self.assertIsNotNone(self.viewer.automaticROI_data, "Overlay data not generated")
        self.assertEqual(self.viewer.automaticROI_data.dtype, np.uint8, "Overlay data type incorrect")
        self.assertGreater(np.sum(self.viewer.automaticROI_data), 0, "Overlay mask should be non-empty")

    # Additional tests to improve coverage

    @patch('components.nifti_file_dialog.NiftiFileDialog.get_files')
    def test_load_file(self, mock_get_files):
        mock_get_files.return_value = [self.test_nii_path]
        self.viewer.open_file()
        loop = QEventLoop()
        QTimer.singleShot(1000, loop.quit)
        loop.exec()

        self.assertIsNotNone(self.viewer.img_data, "Image data should be loaded after file load")
        self.assertEqual(self.viewer.dims, (20, 20, 20), "Dimensions incorrect")
        self.assertFalse(self.viewer.is_4d, "Should be 3D data")

    @patch('components.nifti_file_dialog.NiftiFileDialog.get_files')
    def test_load_4d_file(self, mock_get_files):
        mock_get_files.return_value = [self.test_4d_nii_path]
        self.viewer.open_file()
        loop = QEventLoop()
        QTimer.singleShot(1000, loop.quit)
        loop.exec()

        self.assertIsNotNone(self.viewer.img_data, "4D image data should be loaded")
        self.assertEqual(self.viewer.dims, (20, 20, 20, 10), "4D dimensions incorrect")
        self.assertTrue(self.viewer.is_4d, "Should be 4D data")
        self.assertTrue(self.viewer.time_group.isVisible(), "Time group should be visible for 4D")

    @patch('components.nifti_file_dialog.NiftiFileDialog.get_files')
    def test_load_overlay(self, mock_get_files):
        # Load base first
        mock_get_files.return_value = [self.test_nii_path]
        self.viewer.open_file()
        loop = QEventLoop()
        QTimer.singleShot(1000, loop.quit)
        loop.exec()

        # Load overlay
        mock_get_files.return_value = [self.test_overlay_path]
        self.viewer.open_file(is_overlay=True)
        QTimer.singleShot(1000, loop.quit)
        loop.exec()

        self.assertIsNotNone(self.viewer.overlay_data, "Overlay data should be loaded")
        self.assertTrue(self.viewer.overlay_checkbox.isChecked(), "Overlay checkbox should be checked")

    def test_automaticROI_clicked(self):
        # Load data first
        self.viewer.open_file(self.test_nii_path)
        loop = QEventLoop()
        QTimer.singleShot(1000, loop.quit)
        loop.exec()

        self.viewer.automaticROIbtn.setEnabled(True)  # Enable button
        QTest.mouseClick(self.viewer.automaticROIbtn, Qt.MouseButton.LeftButton)
        QTest.qWait(500)

        self.assertTrue(self.viewer.automaticROI_overlay, "Automatic ROI overlay should be enabled")
        self.assertIsNotNone(self.viewer.automaticROI_data, "Automatic ROI data should be generated after ROI click")

    @patch('PyQt6.QtWidgets.QMessageBox.exec')
    @patch('os.makedirs')
    def test_automaticROI_save(self, mock_makedirs, mock_msgbox_exec):
        # Load data and generate ROI
        self.viewer.open_file(self.test_nii_path)
        loop = QEventLoop()
        QTimer.singleShot(1000, loop.quit)
        loop.exec()

        self.viewer.automaticROI_seed_coordinates = [10, 10, 10]
        self.viewer.automaticROI_overlay = True
        self.viewer.automaticROI_radius_slider.setValue(3)
        self.viewer.automaticROI_diff_slider.setValue(10)
        self.viewer.automaticROI_drawing()

        # Mock confirmation dialog to accept
        mock_msgbox_exec.return_value = QMessageBox.StandardButton.Yes

        # Simulate save button click
        self.viewer.ROI_save_btn.setEnabled(True)
        QTest.mouseClick(self.viewer.ROI_save_btn, Qt.MouseButton.LeftButton)
        QTest.qWait(500)

        self.assertTrue(mock_makedirs.called, "Save directory should be created")

    def test_resize_event(self):
        with patch.object(self.viewer.views[0], 'fitInView') as mock_fitInView:
            QTest.qWait(500)
            self.viewer.resize(1200, 800)
            QTest.qWait(500)
            self.assertTrue(mock_fitInView.called, "Views should be fitted on resize")

    def test_colormap_changed(self):
        # Simulate changing colormap
        self.viewer.colormap_combo.setCurrentText('viridis')
        QTest.qWait(500)

        self.assertEqual(self.viewer.colormap, 'viridis', "Colormap should be changed")

    def test_slice_changed(self):
        # Load data
        self.viewer.open_file(self.test_nii_path)
        loop = QEventLoop()
        QTimer.singleShot(1000, loop.quit)
        loop.exec()

        # Change slice for axial
        self.viewer.slice_sliders[0].setValue(5)
        QTest.qWait(500)

        self.assertEqual(self.viewer.current_slices[0], 5, "Slice should be changed")
        self.assertEqual(self.viewer.current_coordinates[2], 5, "Coordinates should be updated")

    def test_time_changed(self):
        # Load 4D data
        self.viewer.open_file(self.test_4d_nii_path)
        loop = QEventLoop()
        QTimer.singleShot(1000, loop.quit)
        loop.exec()

        # Change time
        self.viewer.time_slider.setValue(5)
        QTest.qWait(500)

        self.assertEqual(self.viewer.current_time, 5, "Time should be changed")

    def test_update_coordinates(self):
        # Load data
        self.viewer.open_file(self.test_nii_path)
        loop = QEventLoop()
        QTimer.singleShot(1000, loop.quit)
        loop.exec()

        # Call update_coordinates for axial view
        self.viewer.update_coordinates(0, 10.0, 10.0)
        QTest.qWait(500)

        self.assertTrue(self.viewer.coord_label.text().startswith("Coordinates:"), "Coordinate label should be updated")

    def test_update_cross_view_lines(self):
        self.viewer.open_file(self.test_nii_path)
        loop = QEventLoop()
        QTimer.singleShot(1000, loop.quit)
        loop.exec()

        # Mock set_crosshair_position for all views
        mock_crosshair_positions = []
        for view in self.viewer.views:
            mock_crosshair = patch.object(view, 'set_crosshair_position')
            mock_crosshair_positions.append(mock_crosshair.start())

        self.viewer.update_cross_view_lines()
        QTest.qWait(500)

        for mock_crosshair in mock_crosshair_positions:
            self.assertTrue(mock_crosshair.called, "Crosshair position should be updated")

        # Clean up mocks
        for _ in mock_crosshair_positions:
            patch.stopall()

    def test_translate_ui(self):
        # Call _translate_ui
        self.viewer._translate_ui()
        QTest.qWait(500)

        self.assertEqual(self.viewer.windowTitle(), "NIfTI Image Viewer", "Window title should be translated")

    def test_close_event(self):
        # Simulate close event
        mock_event = MagicMock()
        self.viewer.closeEvent(mock_event)
        QTest.qWait(500)

        self.assertTrue(mock_event.accept.called, "Close event should be accepted")
        self.assertIsNone(self.viewer.img_data, "Image data should be cleared")


if __name__ == '__main__':
    unittest.main()
