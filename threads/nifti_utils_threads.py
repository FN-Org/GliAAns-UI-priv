import json

import nibabel as nib
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal, QCoreApplication


class SaveNiftiThread(QThread):
    success = pyqtSignal(str,str)
    error = pyqtSignal(str)

    def __init__(self,data,affine,path,json_path,relative_path,radius,difference):
        super().__init__()
        self.data = data
        self.affine = affine
        self.path = path
        self.relative_path = relative_path
        self.radius = radius
        self.difference = difference
        self.json_path = json_path

    def run(self):
        try:
            # Salva la NIfTI
            nib.save(nib.Nifti1Image(self.data.astype(np.uint8), self.affine), self.path)

            # Costruisci il JSON BIDS-like
            json_dict = {
                "Type": "ROI",
                "Sources": [f"bids:{self.relative_path}"],
                "Description": "Automatic ROI using intensity threshold-based region growing.",
                "AutomaticRoiParameters": {
                    "radius": self.radius,
                    "difference": self.difference
                }
            }

            with open(self.json_path, "w") as json_file:
                json.dump(json_dict, json_file, indent=4)

            self.success.emit(self.path, self.json_path)
        except Exception as e:
            self.error.emit(str(e))


class ImageLoadThread(QThread):
    """Thread for loading large NIfTI files without blocking the UI - VERSIONE OTTIMIZZATA"""
    finished = pyqtSignal(object, object, object, bool, bool)  # img_data, dims, affine, is_4d, is_overlay
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, file_path, is_overlay):
        super().__init__()
        self.file_path = file_path
        self.is_overlay = is_overlay

    def run(self):
        try:
            self.progress.emit(10)

            # Caricamento con memory mapping (non blocca RAM finché non serve)
            img = nib.load(self.file_path, mmap="c")
            self.progress.emit(30)

            if not isinstance(img, (nib.Nifti1Image, nib.Nifti2Image)):
                raise ValueError(QCoreApplication.translate("Threads", "Not a valid NIfTI file"))

            # Porta l'immagine nello spazio canonico (RAS+)
            canonical_img = nib.as_closest_canonical(img)
            self.progress.emit(50)

            dims = canonical_img.header.get_data_shape()
            is_4d = len(dims) == 4
            affine = canonical_img.affine

            self.progress.emit(70)

            # Carica i dati come float32
            img_data = np.asanyarray(canonical_img.dataobj, dtype=np.float32)

            self.progress.emit(80)

            # Normalizza i dati
            img_data = self.normalize_data_matplotlib_style(img_data)

            self.progress.emit(100)

            # Emissione segnale di completamento
            self.finished.emit(img_data, dims, affine, is_4d, self.is_overlay)

        except Exception as e:
            self.error.emit(str(e))

    def normalize_data_matplotlib_style(self, data):
        """Normalize NIfTI data (3D or 4D) using robust percentile scaling like matplotlib."""

        if data.size == 0:
            return data

        def normalize_volume(volume):
            valid_data = volume[np.isfinite(volume)]
            if valid_data.size == 0:
                return np.zeros_like(volume, dtype=np.float32)

            vmin, vmax = np.percentile(valid_data, [0.5, 99.5])
            if vmax <= vmin:
                vmax = vmin + 1.0

            return np.clip((volume - vmin) / (vmax - vmin), 0, 1).astype(np.float32)

        # Se 4D → normalizza ogni volume separatamente
        if data.ndim == 4:
            normalized = np.empty_like(data, dtype=np.float32)
            for i in range(data.shape[3]):
                normalized[..., i] = normalize_volume(data[..., i])
        else:
            normalized = normalize_volume(data)

        return normalized
