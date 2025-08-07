import os
import shutil
import subprocess
import json
import tempfile

from PyQt6.QtCore import Qt, QCoreApplication, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QApplication, QFileDialog, QListView, QTreeView, QMessageBox, \
    QProgressDialog

import pydicom

from ui.ui_patient_selection_frame import PatientSelectionPage
from wizard_state import WizardPage


class ImportThread(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, context, folders_path, workspace_path):
        super().__init__()
        self.context = context
        self.folders_path = folders_path
        self.workspace_path = workspace_path
        self.current_progress = 0

    def run(self):
        try:
            self.current_progress = 10
            self.progress.emit(self.current_progress)

            if len(self.folders_path) == 1:
                folder_path = self.folders_path[0]  # CORREZIONE: prendi il primo elemento della lista
                if not os.path.isdir(folder_path):  # CORREZIONE: usa folder_path invece di self.folders_path
                    raise Exception("Invalid folders path")

                # Se è una cartella normale (singolo paziente o BIDS), continua come prima
                if self._is_bids_folder(folder_path):
                    print(f"BIDS structure detected in: {folder_path}")

                    self.current_progress = 50
                    self.progress.emit(self.current_progress)

                    new_sub_id = self._get_next_sub_id()  # es: "sub-03"
                    dest = os.path.join(self.workspace_path, new_sub_id)
                    shutil.copytree(folder_path, dest, dirs_exist_ok=True)

                    self.current_progress = 100
                    self.progress.emit(self.current_progress)

                    print(f"BIDS folder copied as {new_sub_id}.")
                    self.finished.emit()
                    return

                # Se contiene solo sottocartelle, assumiamo siano pazienti diversi → importa ognuna separatamente
                subfolders = [os.path.join(folder_path, d) for d in os.listdir(folder_path) if
                              os.path.isdir(os.path.join(folder_path, d))]
                if subfolders and not any(
                        self._is_nifti_file(f) or self._is_dicom_file(os.path.join(folder_path, f)) for f in
                        os.listdir(folder_path)):
                    print(f"Multiple patient folders detected in: {folder_path}")

                    folders_num = len(subfolders)
                    progress_for_folder = 90 / folders_num
                    self.current_progress = 10

                    for subfolder in subfolders:
                        self._handle_import(subfolder)
                        self.current_progress += progress_for_folder
                        self.progress.emit(self.current_progress)

                    self.progress.emit(100)
                    self.finished.emit()
                    return

                nifti_files = []
                dicom_files = []

                base_folder_name = os.path.basename(os.path.normpath(folder_path))  # CORREZIONE: usa folder_path

                # Creiamo una cartella temporanea per la conversione
                temp_dir = tempfile.mkdtemp()
                temp_base_dir = os.path.join(temp_dir, base_folder_name)

                for root, _, files in os.walk(folder_path):  # CORREZIONE: usa folder_path
                    for file in files:
                        file_path = os.path.join(root, file)

                        relative_path = os.path.relpath(root, folder_path)  # CORREZIONE: usa folder_path
                        dest_dir = os.path.join(temp_base_dir, relative_path)
                        os.makedirs(dest_dir, exist_ok=True)

                        if self._is_nifti_file(file):
                            nifti_files.append((file_path, os.path.join(dest_dir, file)))

                        elif self._is_dicom_file(file_path):
                            dicom_files.append(file_path)

                        else:
                            shutil.copy2(file_path, os.path.join(dest_dir, file))
                            print(f"Imported other file: {os.path.join(relative_path, file)}")

                self.current_progress = 20
                self.progress.emit(self.current_progress)

                nifti_num = len(nifti_files)
                if nifti_num > 0:  # CORREZIONE: evita divisione per zero
                    progress_per_nifti = int(40 / nifti_num)
                    for src, dest in nifti_files:
                        shutil.copy2(src, dest)
                        self.current_progress += progress_per_nifti
                        self.progress.emit(self.current_progress)
                        print(f"Imported NIfTI file: {os.path.relpath(dest, temp_base_dir)}")

                self.current_progress = 60
                self.progress.emit(self.current_progress)

                if dicom_files:
                    self._convert_dicom_folder_to_nifti(folder_path, temp_base_dir)  # CORREZIONE: usa folder_path

                self.current_progress += 10
                self.progress.emit(self.current_progress)
                # Ora la conversione è fatta su cartella temporanea, ma scrive nel workspace
                self._convert_to_bids_structure(temp_base_dir)

                # Dopo conversione, cancella cartella temporanea
                shutil.rmtree(temp_dir, ignore_errors=True)
            elif len(self.folders_path) == 0:
                raise Exception("Invalid folders path")
            elif len(self.folders_path) > 1:
                progress_for_folder = int(90 / len(self.folders_path))
                for path in self.folders_path:
                    self._handle_import(path)
                    self.current_progress += progress_for_folder
                    self.progress.emit(self.current_progress)
            else:
                raise Exception("Invalid folders path")

            self.current_progress = 100
            self.progress.emit(self.current_progress)
            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))

    def _handle_import(self, folder_path):
        if not os.path.isdir(folder_path):
            return

        print(f"Processing folder: {folder_path}")

        # Se è una cartella BIDS, copiala direttamente
        if self._is_bids_folder(folder_path):
            print(f"BIDS structure detected in: {folder_path}")
            new_sub_id = self._get_next_sub_id()
            dest = os.path.join(self.workspace_path, new_sub_id)
            shutil.copytree(folder_path, dest, dirs_exist_ok=True)
            print(f"BIDS folder copied as {new_sub_id}.")
            if self.context and "update_main_buttons" in self.context:
                self.context["update_main_buttons"]()
            return

        # Prima verifica: ci sono file DICOM o NIfTI direttamente nella cartella?
        has_direct_medical_files = False
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                if self._is_nifti_file(file) or self._is_dicom_file(file_path):
                    has_direct_medical_files = True
                    break

        # Se ha file medici diretti, processala come singolo paziente
        if has_direct_medical_files:
            print(f"Direct medical files found, processing as single patient: {folder_path}")
            self._process_single_patient_folder(folder_path)
            return

        # Ottieni le sottocartelle
        subfolders = [os.path.join(folder_path, d) for d in os.listdir(folder_path) if
                      os.path.isdir(os.path.join(folder_path, d))]

        if not subfolders:
            print(f"No subfolders found in: {folder_path}")
            return

        # Verifica se le sottocartelle sono serie DICOM dello stesso paziente
        if self._are_dicom_series_of_same_patient(subfolders):
            print(f"DICOM series of same patient detected: {folder_path}")
            self._process_single_patient_folder(folder_path)
            return

        # Verifica se sono pazienti diversi basandosi sui nomi delle cartelle
        if self._subfolders_look_like_different_patients(subfolders):
            print(f"Multiple patients detected by folder names: {folder_path}")
            for subfolder in subfolders:
                self._handle_import(subfolder)
            return

        # Default: tratta come singolo paziente
        print(f"Default: treating as single patient: {folder_path}")
        self._process_single_patient_folder(folder_path)

    def _are_dicom_series_of_same_patient(self, subfolders):
        """
        Verifica se le sottocartelle sono serie DICOM dello stesso paziente.
        """
        print(f"Checking if {len(subfolders)} subfolders are DICOM series of same patient...")

        patient_ids = set()
        dicom_folders_count = 0

        for subfolder in subfolders:
            print(f"  Checking subfolder: {os.path.basename(subfolder)}")

            # Controlla se la sottocartella contiene DICOM
            has_dicom_in_subfolder = False
            first_dicom_file = None

            for root, _, files in os.walk(subfolder):
                for file in files:
                    file_path = os.path.join(root, file)
                    if self._is_dicom_file(file_path):
                        has_dicom_in_subfolder = True
                        first_dicom_file = file_path
                        break
                if has_dicom_in_subfolder:
                    break

            if has_dicom_in_subfolder:
                dicom_folders_count += 1
                print(f"    Found DICOM files in: {os.path.basename(subfolder)}")

                # Prova a leggere il Patient ID
                try:
                    dcm = pydicom.dcmread(first_dicom_file, stop_before_pixels=True)
                    patient_id = getattr(dcm, 'PatientID', None)
                    patient_name = getattr(dcm, 'PatientName', None)

                    print(f"    Patient ID: {patient_id}, Patient Name: {patient_name}")

                    if patient_id:
                        patient_ids.add(patient_id)
                    elif patient_name:
                        patient_ids.add(str(patient_name))

                except Exception as e:
                    print(f"    Could not read DICOM metadata: {e}")
            else:
                print(f"    No DICOM files found in: {os.path.basename(subfolder)}")

        print(f"Found {dicom_folders_count} folders with DICOM, {len(patient_ids)} unique patient IDs: {patient_ids}")

        # È un singolo paziente se:
        # 1. Almeno una cartella ha DICOM
        # 2. Al massimo un Patient ID unico (o nessuno se non riusciamo a leggere i metadati)
        is_same_patient = dicom_folders_count > 0 and len(patient_ids) <= 1
        print(f"  Result: is_same_patient = {is_same_patient}")

        return is_same_patient

    def _subfolders_look_like_different_patients(self, subfolders):
        """
        Verifica se i nomi delle sottocartelle suggeriscono che siano pazienti diversi.
        """
        patient_like_prefixes = ['sub-', 'patient', 'subj', 'p_', 'subject']

        for subfolder in subfolders:
            folder_name = os.path.basename(subfolder).lower()
            if any(folder_name.startswith(prefix) for prefix in patient_like_prefixes):
                print(f"Folder name '{folder_name}' suggests different patients")
                return True

        return False

    def _process_single_patient_folder(self, folder_path):
        """
        Processa una cartella di un singolo paziente (può avere multiple serie DICOM).
        """
        print(f"Processing single patient folder: {folder_path}")

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

        # Copia i file NIfTI
        for src, dest in nifti_files:
            shutil.copy2(src, dest)
            print(f"Imported NIfTI file: {os.path.relpath(dest, temp_base_dir)}")

        # Converti i DICOM se presenti
        if dicom_files:
            print(f"Converting {len(dicom_files)} DICOM files to NIfTI...")
            self._convert_dicom_folder_to_nifti(folder_path, temp_base_dir)

        # Converti in struttura BIDS
        print(f"Converting to BIDS structure...")
        self._convert_to_bids_structure(temp_base_dir)

        # Pulisci la cartella temporanea
        shutil.rmtree(temp_dir, ignore_errors=True)

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()
        print("Import completed for single patient.")

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
        self.current_progress += 10
        self.progress.emit(self.current_progress)
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
            self.current_progress += 10
            self.progress.emit(self.current_progress)
            print(f"Converted DICOM in {dicom_folder} to NIfTI using dcm2niix (optimized)")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Conversion error: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to convert DICOM: {e}") from e

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
        I file vengono rinominati come: sub-XX_<ProtocolName>.nii.gz
        """
        import re
        from collections import defaultdict

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

        used_names = defaultdict(int)  # Per tracciare nomi usati ed evitare duplicati

        for json_path in all_json_files:
            nii_path = json_path.replace(".json", ".nii.gz")
            if not os.path.exists(nii_path):
                print(f"[BIDS] Skipping: no matching NIfTI for {json_path}")
                continue

            with open(json_path, "r") as f:
                metadata = json.load(f)

            modality = metadata.get("Modality", "").upper()
            series_desc = metadata.get("ProtocolName", "unknown")

            # Pulisce la ProtocolName: rimuove caratteri non validi
            series_desc_clean = re.sub(r'[^\w\-]+', '_', series_desc.strip())

            # Crea nome base e gestisce duplicati
            base_name = f"{sub_id}_{series_desc_clean}"
            used_names[base_name] += 1
            if used_names[base_name] > 1:
                base_name = f"{base_name}_{used_names[base_name] - 1}"

            # Determina la cartella di destinazione
            if modality == "MR":
                target_dir = os.path.join(dest_sub_dir, "anat")
            elif modality == "PT":
                keys = ["FrameDuration", "FrameReferenceTime"]
                if all(
                        k in metadata and isinstance(metadata[k], (list, tuple)) and len(metadata[k]) > 1
                        for k in keys
                ):
                    target_dir = os.path.join(dest_sub_dir, "ses-02")
                else:
                    target_dir = os.path.join(dest_sub_dir, "ses-01")
            else:
                target_dir = os.path.join(dest_sub_dir, "unknown")

            os.makedirs(target_dir, exist_ok=True)

            # Copia i file con il nuovo nome
            shutil.copy2(nii_path, os.path.join(target_dir, f"{base_name}.nii.gz"))
            shutil.copy2(json_path, os.path.join(target_dir, f"{base_name}.json"))

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

class ImportFrame(WizardPage):

    def __init__(self, context=None):
        super().__init__()
        self.context = context
        self.next_page = None
        self.workspace_path = context["workspace_path"]

        self.setAcceptDrops(True)
        self.setEnabled(True)
        self.setStyleSheet("border: 2px dashed gray;")

        frame_layout = QHBoxLayout(self)
        self.drop_label = QLabel("Import or select patients' data")
        self.drop_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.drop_label.setFont(QFont("", 14))
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.drop_label)

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
        """Restituisce True se si può tornare indietro alla pagina precedente."""
        return False

    def next(self, context):
        if self.next_page:
            self.next_page.on_enter()
            return self.next_page
        else:
            self.next_page = PatientSelectionPage(context, self)
            self.context["history"].append(self.next_page)
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
                    self._handle_import([file_path])

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_folder_dialog()

    def open_folder_dialog(self):
        dialog = QFileDialog(self.context["main_window"], "Select Folder")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.Option.ReadOnly, True)
        dialog.setDirectory(os.path.expanduser("~"))

        for view in dialog.findChildren((QListView, QTreeView)):
            view.setSelectionMode(view.SelectionMode.MultiSelection)

        if dialog.exec():
            folders = [os.path.abspath(path) for path in dialog.selectedFiles() if os.path.isdir(path)]
            unique_folders = [f for f in folders if not any(f != other and other.startswith(f + os.sep) for other in folders)]
            self._handle_import(unique_folders)

    def _handle_import(self, folders_path):

        self.progress_dialog = QProgressDialog("Loading NIfTI file...","Cancel",
                                               0, 100, self.context["main_window"])
        self.progress_dialog.setWindowModality(Qt.WindowModality.NonModal)
        self.progress_dialog.setMinimumDuration(0)

        # Start importing thread
        self.load_thread = ImportThread(self.context, folders_path, self.workspace_path)
        self.load_thread.finished.connect(self.on_file_loaded)
        self.load_thread.error.connect(self.on_load_error)
        self.load_thread.progress.connect(self.progress_dialog.setValue)
        self.load_thread.start()

    def on_load_error(self, error):
        """Handle file loading errors"""
        self.progress_dialog.close()
        QMessageBox.critical(self, "Error Importing Files", "Failed to import files"+ f":\n{error}")

    def on_file_loaded(self):
        self.progress_dialog.close()
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()
        print("Import completed.")

    def _retranslate_ui(self):
        _ = QCoreApplication.translate
        self.drop_label.setText(_("MainWindow", "Import or select patients' data"))