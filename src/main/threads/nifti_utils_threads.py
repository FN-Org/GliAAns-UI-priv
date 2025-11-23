import json
import nibabel as nib
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal, QCoreApplication
from logger import get_logger


log = get_logger()

class SaveNiftiThread(QThread):
    """
    Background thread for saving a NIfTI image and its associated metadata
    to disk in BIDS-like format.

    This class prevents the UI from freezing during file write operations
    by running the saving process in a separate thread.

    Signals:
        success (str, str): Emitted when both the NIfTI and JSON files are successfully saved.
                            Provides the paths to the saved files.
        error (str): Emitted when an error occurs during saving.

    Args:
        data (np.ndarray): The voxel data to be saved as a NIfTI image.
        affine (np.ndarray): The affine transformation matrix for spatial orientation.
        path (str): Output file path for the NIfTI image.
        json_path (str): Output file path for the JSON metadata file.
        relative_path (str): Relative path reference (used for the "Sources" field in JSON).
        radius (float): Region growing radius parameter.
        difference (float): Intensity difference threshold parameter.
    """

    success = pyqtSignal(str, str)
    """**Signal(str, str):** Emitted when an operation completes successfully.  
    Parameters:  
    - `str`: Name or identifier of the completed task.  
    - `str`: Success message or additional details.  
    """

    error = pyqtSignal(str)
    """**Signal(str):** Emitted when an error occurs during an operation.  
    Parameters:  
    - `str`: Description of the error or failure reason.  
    """

    def __init__(self, data, affine, path, json_path, relative_path,source_dict):
        super().__init__()
        self.data = data
        self.affine = affine
        self.path = path
        self.relative_path = relative_path
        self.source_dict = source_dict
        self.json_path = json_path

    def run(self):
        """
        Executes the file-saving process in a background thread.

        The method saves the NIfTI image using `nibabel`, then creates and writes
        a companion JSON file describing the ROI (Region of Interest) with
        user-specified parameters.

        Emits:
            - success(path, json_path): On successful save.
            - error(message): If an exception occurs.
        """
        try:
            log.debug(f"Save nifti in {self.path}")
            # Save the NIfTI file
            nib.save(nib.Nifti1Image(self.data.astype(np.uint8), self.affine), self.path)

            log.debug("Preparing json")
            json_dict = {
                "Type": "ROI",
                "Sources": [f"bids:{self.relative_path}"],
                "Description": "ROI mask",
                "Origin": self.source_dict
            }

            log.debug("Writing json")
            # Write the JSON metadata
            with open(self.json_path, "w") as json_file:
                json.dump(json_dict, json_file, indent=4)
            log.debug("Send success")
            # Notify the main thread of success
            self.success.emit(self.path, self.json_path)

        except Exception as e:
            # Emit error message if something goes wrong
            self.error.emit(str(e))


class ImageLoadThread(QThread):
    """
    Thread for loading and normalizing large NIfTI files without blocking the UI.

    This class supports both 3D and 4D NIfTI volumes and includes
    robust normalization based on percentile scaling similar to matplotlib's
    default image scaling behavior.

    Signals:
        finished (object, object, object, bool, bool): Emitted when loading completes successfully.
            Contains (img_data, dims, affine, is_4d, is_overlay).
        error (str): Emitted if an error occurs during file loading.
        progress (int): Emits loading progress updates (0–100).

    Args:
        file_path (str): Path to the NIfTI file to load.
        is_overlay (bool): Flag indicating whether the file is an overlay image.
    """

    finished = pyqtSignal(object, object, object, bool, bool)
    """**Signal(object, object, object, bool, bool):**  
    Emitted when the file is successifully loaded.  

    Parameters:  
    - `object`: img_data.  
    - `object`: dims.
    - `object`: affine. 
    - `bool`: is_4d. 
    - `bool`: is_overlay.  
    """

    error = pyqtSignal(str)
    """**Signal(str):**  
    Emitted when an error occurs during the deep learning execution.  

    Parameters:  
    - `str`: Description or message detailing the error.  
    """

    progress = pyqtSignal(int)
    """**Signal(int):**  
    Emitted to report progress updates during execution.  

    Parameters:  
    - `int`: Current progress percentage (0–100).  
    """

    def __init__(self, file_path, is_overlay):
        super().__init__()
        self.file_path = file_path
        self.is_overlay = is_overlay

    def run(self):
        """
        Loads and normalizes a NIfTI image in a background thread.

        Steps:
            1. Load image using memory mapping to minimize RAM usage.
            2. Verify the file is a valid NIfTI image.
            3. Canonicalize to RAS+ orientation.
            4. Normalize data using percentile scaling.
            5. Emit the finished signal with image data and metadata.
        """
        try:
            self.progress.emit(10)

            # Load image (memory-mapped to avoid heavy RAM use)
            img = nib.load(self.file_path, mmap="c")
            self.progress.emit(30)

            if not isinstance(img, (nib.Nifti1Image, nib.Nifti2Image)):
                raise ValueError(QCoreApplication.translate("Threads", "Not a valid NIfTI file"))

            # Convert to canonical orientation (RAS+)
            canonical_img = nib.as_closest_canonical(img)
            self.progress.emit(50)

            dims = canonical_img.header.get_data_shape()
            is_4d = len(dims) == 4
            affine = canonical_img.affine

            self.progress.emit(70)
            log.debug("Load voxel data")
            # Load voxel data
            img_data = np.asanyarray(canonical_img.dataobj, dtype=np.float32)
            self.progress.emit(80)

            log.debug("Normalize image intensities")
            # Normalize image intensities
            img_data = self.normalize_data_matplotlib_style(img_data)

            self.progress.emit(100)
            log.debug("Emit finished signal with image data and metadata.")
            # Emit the results to the main thread
            self.finished.emit(img_data, dims, affine, is_4d, self.is_overlay)

        except Exception as e:
            # Report any errors encountered
            self.error.emit(str(e))

    def normalize_data_matplotlib_style(self, data):
        """
        Normalize NIfTI data using robust percentile scaling (0.5th–99.5th percentiles).

        This approach is similar to how matplotlib normalizes image intensities,
        providing consistent visual scaling even for datasets with outliers.

        Args:
            data (np.ndarray): The 3D or 4D voxel intensity data.

        Returns:
            np.ndarray: Normalized float32 data with intensity values scaled to [0, 1].
        """

        if data.size == 0:
            return data

        def normalize_volume(volume):
            """Normalize a single 3D volume to [0, 1] using percentile-based contrast stretching."""
            valid_data = volume[np.isfinite(volume)]
            if valid_data.size == 0:
                return np.zeros_like(volume, dtype=np.float32)

            vmin, vmax = np.percentile(valid_data, [0.1, 99.9])
            if vmax <= vmin:
                vmax = vmin + 1.0

            return np.clip((volume - vmin) / (vmax - vmin), 0, 1).astype(np.float32)

        # Handle both 3D and 4D volumes
        if data.ndim == 4:
            normalized = np.empty_like(data, dtype=np.float32)
            for i in range(data.shape[3]):
                normalized[..., i] = normalize_volume(data[..., i])
        else:
            normalized = normalize_volume(data)

        return normalized
