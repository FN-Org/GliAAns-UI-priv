import os
import shutil
import subprocess
import json
import tempfile

from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QApplication, QFileDialog, QListView, QTreeView, QMessageBox

import pydicom

from ui.ui_patient_selection_frame import PatientSelectionPage
from wizard_state import WizardPage


class ImportFrame(WizardPage):

    def __init__(self, context=None):
        super().__init__()
        self.context = context
        self.next_page = None

        self.setAcceptDrops(True)
        self.setEnabled(True)
        self.setStyleSheet("border: 2px dashed gray;")

        frame_layout = QHBoxLayout(self)
        self.drop_label = QLabel("Import or select patients' data")
        self.drop_label.setFont(QFont("", 14))
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.drop_label)

        self.context = context
        self.workspace_path = context["workspace_path"]

        self._retranslate_ui()
        if context and hasattr(context, "language_changed"):
            context.language_changed.connect(self._retranslate_ui)

    def is_ready_to_advance(self):
        """Restituisce True se si può avanzare alla prossima pagina."""
        has_content = any(
            os.path.isdir(os.path.join(self.workspace_path, name)) or
            os.path.islink(os.path.join(self.workspace_path, name))
            for name in os.listdir(self.workspace_path)
            if not name.startswith(".")
        )

        if has_content:
            return True
        else:
            return False

    def is_ready_to_go_back(self):
        return False

    def next(self, context):
        if self.next_page:
            return self.next_page
        else:
            self.next_page = PatientSelectionPage(context, self)
            return self.next_page

    def back(self):
        return False

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            for url in urls:
                file_path = url.toLocalFile()
                if os.path.exists(file_path) and os.path.isdir(file_path):
                    self._handle_import(file_path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_folder_dialog()

    def open_folder_dialog(self):
        dialog = QFileDialog(self.context, "Select Folder")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.Option.ReadOnly, True)
        dialog.setDirectory(os.path.expanduser("~"))

        for view in dialog.findChildren((QListView, QTreeView)):
            view.setSelectionMode(view.SelectionMode.MultiSelection)

        if dialog.exec():
            folders = [os.path.abspath(path) for path in dialog.selectedFiles() if os.path.isdir(path)]
            unique_folders = [f for f in folders if not any(f != other and other.startswith(f + os.sep) for other in folders)]
            for folder in unique_folders:
                self._handle_import(folder)

    def _is_nifti_file(self, file_path):
        return file_path.endswith(".nii") or file_path.endswith(".nii.gz")

    def _is_dicom_file(self, file_path):
        try:
            dcm = pydicom.dcmread(file_path, stop_before_pixels=True)
            return True
        except Exception:
            return False

    def _convert_dicom_folder_to_nifti(self, dicom_folder, output_folder):
        if os.path.isdir(output_folder):
            for filename in os.listdir(output_folder):
                file_path = os.path.join(output_folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Errore durante la rimozione di {file_path}: {e}")
        else:
            os.makedirs(output_folder, exist_ok=True)

        try:
            command = [
                "dcm2niix",
                "-f", "%p_%s",  # Naming format
                "-p", "y",  # Preserve original acquisition order
                "-z", "y",  # Compress output as .nii.gz
                "-o", output_folder,  # Destination folder
                dicom_folder  # Source DICOM folder
            ]
            subprocess.run(command, check=True)
            print(f"Converted DICOM in {dicom_folder} to NIfTI using dcm2niix (optimized)")
        except subprocess.CalledProcessError as e:
            print(f"Conversion error: {e}")
        except Exception as e:
            print(f"Failed to convert DICOM: {e}")

    def _handle_import(self, folder_path):
        if not os.path.isdir(folder_path):
            return

        # Se è una cartella normale (singolo paziente o BIDS), continua come prima
        if self._is_bids_folder(folder_path):
            print(f"BIDS structure detected in: {folder_path}")

            new_sub_id = self._get_next_sub_id()  # es: "sub-03"
            dest = os.path.join(self.workspace_path, new_sub_id)
            shutil.copytree(folder_path, dest, dirs_exist_ok=True)

            print(f"BIDS folder copied as {new_sub_id}.")
            self.controller.update_buttons_state()
            return

        # Se contiene solo sottocartelle, assumiamo siano pazienti diversi → importa ognuna separatamente
        subfolders = [os.path.join(folder_path, d) for d in os.listdir(folder_path) if
                      os.path.isdir(os.path.join(folder_path, d))]
        if subfolders and not any(self._is_nifti_file(f) or self._is_dicom_file(os.path.join(folder_path, f)) for f in
                                  os.listdir(folder_path)):
            print(f"Multiple patient folders detected in: {folder_path}")
            for subfolder in subfolders:
                self._handle_import(subfolder)
            return

        nifti_files = []
        dicom_files = []

        base_folder_name = os.path.basename(os.path.normpath(folder_path))

        # Creiamo una cartella temporanea per la conversione
        temp_dir = tempfile.mkdtemp()
        temp_base_dir = os.path.join(temp_dir, base_folder_name)

        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)

                relative_path = os.path.relpath(root, folder_path)
                dest_dir = os.path.join(temp_base_dir, relative_path)
                os.makedirs(dest_dir, exist_ok=True)

                if self._is_nifti_file(file):
                    nifti_files.append((file_path, os.path.join(dest_dir, file)))

                elif self._is_dicom_file(file_path):
                    dicom_files.append(file_path)

                else:
                    shutil.copy2(file_path, os.path.join(dest_dir, file))
                    print(f"Imported other file: {os.path.join(relative_path, file)}")

        for src, dest in nifti_files:
            shutil.copy2(src, dest)
            print(f"Imported NIfTI file: {os.path.relpath(dest, temp_base_dir)}")

        if dicom_files:
            self._convert_dicom_folder_to_nifti(folder_path, temp_base_dir)

        # Ora la conversione è fatta su cartella temporanea, ma scrive nel workspace
        self._convert_to_bids_structure(temp_base_dir)

        # Dopo conversione, cancella cartella temporanea
        shutil.rmtree(temp_dir, ignore_errors=True)

        self.controller.update_buttons_state()
        print("Import completed.")

    def _is_bids_folder(self, folder_path):
        """
        Verifica se una cartella è una cartella BIDS valida per un singolo soggetto.
        Controlla che:
        - il nome della cartella inizi con 'sub-'
        - all'interno ci siano sottocartelle come 'anat', 'func', ecc.
        - queste contengano file NIfTI (e opzionalmente JSON)
        """
        base = os.path.basename(folder_path.rstrip(os.sep))

        # Deve chiamarsi sub-*
        if not base.startswith("sub-"):
            return False

        # Cerca sottocartelle BIDS standard con file utili
        for session_or_modality in os.listdir(folder_path):
            session_path = os.path.join(folder_path, session_or_modality)
            if os.path.isdir(session_path):
                for modality in os.listdir(session_path):
                    modality_path = os.path.join(session_path, modality)
                    if os.path.isdir(modality_path):
                        if any(f.endswith(".nii") or f.endswith(".nii.gz") for f in os.listdir(modality_path)):
                            return True
                # oppure è una cartella "anat", "func", ecc. direttamente sotto sub-01 (senza ses-*)
                if any(f.endswith(".nii") or f.endswith(".nii.gz") for f in os.listdir(session_path)):
                    return True

        return False

    def _convert_to_bids_structure(self, input_folder):
        """
        Converte un dataset contenente file NIfTI + JSON in struttura BIDS.
        Funziona anche se i file sono nella stessa cartella, senza sottocartelle per paziente.
        """
        all_json_files = []
        for root, _, files in os.walk(input_folder):
            for file in files:
                if file.endswith(".json"):
                    all_json_files.append(os.path.join(root, file))

        if not all_json_files:
            print("[BIDS] Nessun file JSON trovato. Conversione annullata.")
            return

        sub_id = self._get_next_sub_id()
        dest_sub_dir = os.path.join(self.workspace_path, sub_id)
        os.makedirs(dest_sub_dir, exist_ok=True)

        for json_path in all_json_files:
            nii_path = json_path.replace(".json", ".nii.gz")
            if not os.path.exists(nii_path):
                print(f"[BIDS] Skipping: no matching NIfTI for {json_path}")
                continue

            with open(json_path, "r") as f:
                metadata = json.load(f)

            modality = metadata.get("Modality", "").upper()
            original_base = os.path.basename(nii_path).replace(".nii.gz", "")
            new_base = f"{sub_id}_{original_base}"

            if modality == "MR":
                anat_dir = os.path.join(dest_sub_dir, "anat")
                os.makedirs(anat_dir, exist_ok=True)
                shutil.copy2(nii_path, os.path.join(anat_dir, f"{new_base}.nii.gz"))
                shutil.copy2(json_path, os.path.join(anat_dir, f"{new_base}.json"))

            elif modality == "PT":
                keys = ["FrameDuration", "FrameReferenceTime"]
                if all(
                        k in metadata and isinstance(metadata[k], (list, tuple)) and len(metadata[k]) > 1
                        for k in keys
                ):
                    ses_dir = os.path.join(dest_sub_dir, "ses-02")
                else:
                    ses_dir = os.path.join(dest_sub_dir, "ses-01")

                os.makedirs(ses_dir, exist_ok=True)
                shutil.copy2(nii_path, os.path.join(ses_dir, f"{new_base}.nii.gz"))
                shutil.copy2(json_path, os.path.join(ses_dir, f"{new_base}.json"))

        print(f"[BIDS] Importato {sub_id} in struttura BIDS.")

    def _get_next_sub_id(self):
        existing = [
            name for name in os.listdir(self.workspace_path)
            if os.path.isdir(os.path.join(self.workspace_path, name)) and name.startswith("sub-")
        ]
        numbers = sorted([
            int(name.split("-")[1]) for name in existing
            if name.split("-")[1].isdigit()
        ])
        next_number = numbers[-1] + 1 if numbers else 1
        return f"sub-{next_number:02d}"

    def _retranslate_ui(self):
        _ = QCoreApplication.translate
        self.drop_label.setText(_("MainWindow", "Import or select patients' data"))

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    frame = ImportFrame()
    frame.show()
    sys.exit(app.exec())