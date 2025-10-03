import json
import os
import re
import shutil
import subprocess
import tempfile
import pydicom

from PyQt6.QtCore import QThread, pyqtSignal, QCoreApplication

from logger import get_logger

log = get_logger()



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
        self._is_canceled = False
        self.process = None

    def run(self):
        try:
            self.current_progress = 10
            self.progress.emit(self.current_progress)

            if len(self.folders_path) == 1:
                folder_path = self.folders_path[0]  # CORREZIONE: prendi il primo elemento della lista
                if not os.path.isdir(folder_path):  # CORREZIONE: usa folder_path invece di self.folders_path
                    raise Exception(QCoreApplication.translate("Threads", "Invalid folders path"))

                # Se è una cartella normale (singolo paziente o BIDS), continua come prima
                if self._is_bids_folder(folder_path):
                    log.debug(f"BIDS structure detected in: {folder_path}")

                    if self._is_canceled:
                        return
                    self.current_progress = 50
                    self.progress.emit(self.current_progress)

                    new_sub_id = self._get_next_sub_id()  # es: "sub-03"
                    dest = os.path.join(self.workspace_path, new_sub_id)
                    shutil.copytree(folder_path, dest, dirs_exist_ok=True)
                    if self._is_canceled:
                        return
                    self.current_progress = 100
                    self.progress.emit(self.current_progress)

                    log.debug(f"BIDS folder copied as {new_sub_id}.")
                    self.finished.emit()
                    return

                # Se contiene solo sottocartelle, assumiamo siano pazienti diversi → importa ognuna separatamente
                subfolders = [os.path.join(folder_path, d) for d in os.listdir(folder_path) if
                              os.path.isdir(os.path.join(folder_path, d))]
                if subfolders and not any(
                        self._is_nifti_file(f) or self._is_dicom_file(os.path.join(folder_path, f)) for f in
                        os.listdir(folder_path)):

                    # NEW: prima di assumere "più pazienti", verifica se le sottocartelle appartengono allo stesso soggetto
                    if self._subfolders_belong_to_single_subject(subfolders):
                        log.debug(f"Single subject spread across {len(subfolders)} DICOM folders in: {folder_path}")

                        # Processa l'intera root come UN solo paziente (PET+MR ecc.)
                        self._process_single_patient_folder(folder_path)
                        if self._is_canceled:
                            return
                        self.progress.emit(100)
                        self.finished.emit()
                        return

                    # Altrimenti rimani con la logica “multi-paziente”
                    log.debug(f"Multiple patient folders detected in: {folder_path}")
                    folders_num = len(subfolders)
                    progress_for_folder = 90 / folders_num
                    self.current_progress = 10

                    for subfolder in subfolders:
                        if self._is_canceled:
                            return
                        self._handle_import(subfolder)
                        if self._is_canceled:
                            return
                        self.current_progress += progress_for_folder
                        self.progress.emit(self.current_progress)

                    if self._is_canceled:
                        return
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
                        if self._is_canceled:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            return
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
                            log.debug(f"Imported other file: {os.path.join(relative_path, file)}")

                self.current_progress = 20
                self.progress.emit(self.current_progress)

                nifti_num = len(nifti_files)
                if nifti_num > 0:  # CORREZIONE: evita divisione per zero
                    progress_per_nifti = int(40 / nifti_num)
                    for src, dest in nifti_files:
                        if self._is_canceled:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            return
                        shutil.copy2(src, dest)
                        self.current_progress += progress_per_nifti
                        self.progress.emit(self.current_progress)
                        log.debug(f"Imported NIfTI file: {os.path.relpath(dest, temp_base_dir)}")

                self.current_progress = 60
                self.progress.emit(self.current_progress)

                if self._is_canceled:
                    return

                if dicom_files:
                    self._convert_dicom_folder_to_nifti(folder_path, temp_base_dir)  # CORREZIONE: usa folder_path

                self.current_progress += 10
                self.progress.emit(self.current_progress)
                # Ora la conversione è fatta su cartella temporanea, ma scrive nel workspace
                self._convert_to_bids_structure(temp_base_dir)

                # Dopo conversione, cancella cartella temporanea
                shutil.rmtree(temp_dir, ignore_errors=True)
            elif len(self.folders_path) == 0:
                raise Exception(QCoreApplication.translate("Threads", "Invalid folders path"))
            elif len(self.folders_path) > 1:
                progress_for_folder = int(90 / len(self.folders_path))
                for path in self.folders_path:
                    if self._is_canceled:
                        return
                    self._handle_import(path)
                    self.current_progress += progress_for_folder
                    self.progress.emit(self.current_progress)
            else:
                raise Exception(QCoreApplication.translate("Threads", "Invalid folders path"))

            self.current_progress = 100
            self.progress.emit(self.current_progress)
            self.finished.emit()

        except Exception as e:
            if self._is_canceled:
                log.info("Import interrupted by user, no error emitted.")
                return
            self.error.emit(str(e))
            log.error(f"Error: {str(e)}")

    def _handle_import(self, folder_path):
        if not os.path.isdir(folder_path):
            return
        if self._is_canceled:
            return
        log.debug(f"Processing folder: {folder_path}")

        # Se è una cartella BIDS, copiala direttamente
        if self._is_bids_folder(folder_path):
            log.debug(f"BIDS structure detected in: {folder_path}")
            new_sub_id = self._get_next_sub_id()
            dest = os.path.join(self.workspace_path, new_sub_id)
            shutil.copytree(folder_path, dest, dirs_exist_ok=True)
            log.debug(f"BIDS folder copied as {new_sub_id}.")
            return

        # Prima verifica: ci sono file DICOM o NIfTI direttamente nella cartella?
        has_direct_medical_files = False
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                if self._is_nifti_file(file) or self._is_dicom_file(file_path):
                    has_direct_medical_files = True
                    break
        if self._is_canceled:
            return
            # Se ha file medici diretti, processala come singolo paziente
        if has_direct_medical_files:
            log.debug(f"Direct medical files found, processing as single patient: {folder_path}")
            self._process_single_patient_folder(folder_path)
            return
        if self._is_canceled:
            return
            # Ottieni le sottocartelle
        subfolders = [os.path.join(folder_path, d) for d in os.listdir(folder_path) if
                      os.path.isdir(os.path.join(folder_path, d))]
        if not subfolders:
            log.debug(f"No subfolders found in: {folder_path}")
            return
        if self._is_canceled:
            return
            # Verifica se le sottocartelle sono serie DICOM dello stesso paziente
        if self._are_dicom_series_of_same_patient(subfolders):
            log.debug(f"DICOM series of same patient detected: {folder_path}")
            self._process_single_patient_folder(folder_path)
            return
        if self._is_canceled:
            return
            # Verifica se sono pazienti diversi basandosi sui nomi delle cartelle
        if self._subfolders_look_like_different_patients(subfolders):
            log.debug(f"Multiple patients detected by folder names: {folder_path}")
            for subfolder in subfolders:
                self._handle_import(subfolder)
            return
        if self._is_canceled:
            return
            # Default: tratta come singolo paziente
        log.debug(f"Default: treating as single patient: {folder_path}")
        self._process_single_patient_folder(folder_path)

    def _are_dicom_series_of_same_patient(self, subfolders):
        """
        Verifica se le sottocartelle sono serie DICOM dello stesso paziente.
        """
        log.debug(f"Checking if {len(subfolders)} subfolders are DICOM series of same patient...")

        patient_ids = set()
        dicom_folders_count = 0

        for subfolder in subfolders:
            log.debug(f"  Checking subfolder: {os.path.basename(subfolder)}")

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
            if self._is_canceled:
                return
            if has_dicom_in_subfolder:
                dicom_folders_count += 1
                log.debug(f"    Found DICOM files in: {os.path.basename(subfolder)}")

                # Prova a leggere il Patient ID
                try:
                    dcm = pydicom.dcmread(first_dicom_file, stop_before_pixels=True)
                    patient_id = getattr(dcm, 'PatientID', None)
                    patient_name = getattr(dcm, 'PatientName', None)
                    masked_patient_name = f"{patient_name[:2]}...{patient_name[-2:]}"

                    log.debug(f"    Patient ID: {patient_id}, Patient Name: {masked_patient_name}")

                    if patient_id:
                        patient_ids.add(patient_id)
                    elif patient_name:
                        patient_ids.add(str(patient_name))

                except Exception as e:
                    log.debug(f"    Could not read DICOM metadata: {e}")
            else:
                log.debug(f"    No DICOM files found in: {os.path.basename(subfolder)}")

        log.debug(f"Found {dicom_folders_count} folders with DICOM, {len(patient_ids)} unique patient IDs: {patient_ids}")

        # È un singolo paziente se:
        # 1. Almeno una cartella ha DICOM
        # 2. Al massimo un Patient ID unico (o nessuno se non riusciamo a leggere i metadati)
        is_same_patient = dicom_folders_count > 0 and len(patient_ids) <= 1
        log.debug(f"  Result: is_same_patient = {is_same_patient}")

        return is_same_patient

    def _subfolders_look_like_different_patients(self, subfolders):
        """
        Verifica se i nomi delle sottocartelle suggeriscono che siano pazienti diversi.
        """
        patient_like_prefixes = ['sub-', 'patient', 'subj', 'p_', 'subject']

        for subfolder in subfolders:
            folder_name = os.path.basename(subfolder).lower()
            if any(folder_name.startswith(prefix) for prefix in patient_like_prefixes):
                log.debug(f"Folder name '{folder_name}' suggests different patients")
                return True

        return False

    def _process_single_patient_folder(self, folder_path):
        """
        Processa una cartella di un singolo paziente (può avere multiple serie DICOM).
        """
        if self._is_canceled:
            return
        log.debug(f"Processing single patient folder: {folder_path}")

        nifti_files = []
        dicom_files = []

        base_folder_name = os.path.basename(os.path.normpath(folder_path))

        # Creiamo una cartella temporanea per la conversione
        temp_dir = tempfile.mkdtemp()
        temp_base_dir = os.path.join(temp_dir, base_folder_name)

        for root, _, files in os.walk(folder_path):
            if self._is_canceled:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return
            for file in files:

                if self._is_canceled:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return

                file_path = os.path.join(root, file)

                relative_path = os.path.relpath(root, folder_path)
                dest_dir = os.path.join(temp_base_dir, relative_path)
                os.makedirs(dest_dir, exist_ok=True)

                if self._is_nifti_file(file):
                    nifti_files.append((file_path, os.path.join(dest_dir, file)))
                elif self._is_dicom_file(file_path):
                    dicom_files.append(file_path)
                else:
                    if self._is_canceled:
                        return
                    shutil.copy2(file_path, os.path.join(dest_dir, file))
                    log.debug(f"Imported other file: {os.path.join(relative_path, file)}")

        if self._is_canceled:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return
        # Copia i file NIfTI
        for src, dest in nifti_files:
            if self._is_canceled:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return
            shutil.copy2(src, dest)
            log.debug(f"Imported NIfTI file: {os.path.relpath(dest, temp_base_dir)}")

        # Converti i DICOM se presenti
        if dicom_files:
            log.debug(f"Converting {len(dicom_files)} DICOM files to NIfTI...")
            self._convert_dicom_folder_to_nifti(folder_path, temp_base_dir)

        if self._is_canceled:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return
        # Converti in struttura BIDS
        log.debug(f"Converting to BIDS structure...")
        self._convert_to_bids_structure(temp_base_dir)

        # Pulisci la cartella temporanea
        shutil.rmtree(temp_dir, ignore_errors=True)

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()
        log.debug("Import completed for single patient.")

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
                if self._is_canceled:
                    return
                file_path = os.path.join(output_folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    log.debug(f"Errore durante la rimozione di {file_path}: {e}")
        else:
            os.makedirs(output_folder, exist_ok=True)

        if self._is_canceled:
            shutil.rmtree(output_folder, ignore_errors=True)
            return
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

            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = self.process.communicate()
            if self.process.returncode != 0:
                raise RuntimeError(f"dcm2niix failed: {stderr.decode()}")

            self.current_progress += 10
            self.progress.emit(self.current_progress)
            log.debug(f"Converted DICOM in {dicom_folder} to NIfTI using dcm2niix (optimized)")
        except subprocess.CalledProcessError as e:
            log.error(f"Conversion error: {e}")
            raise RuntimeError(QCoreApplication.translate("Threads", "Conversion error: {0}").format(e)) from e
        except Exception as e:
            if self._is_canceled:
                log.info("Import canceled")
                raise Exception(QCoreApplication.translate("Threads", "Import canceled"))
            else:
                log.info(f"Import failed: {e}")
                raise RuntimeError(QCoreApplication.translate("Threads", "Failed to convert DICOM: {0}").format(e)) from e


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
        if self._is_canceled:
            return
        all_json_files = []
        for root, _, files in os.walk(input_folder):
            for file in files:
                if file.endswith(".json"):
                    all_json_files.append(os.path.join(root, file))

        if not all_json_files:
            log.debug("[BIDS] Nessun file JSON trovato. Conversione annullata.")
            return

        sub_id = self._get_next_sub_id()
        dest_sub_dir = os.path.join(self.workspace_path, sub_id)
        os.makedirs(dest_sub_dir, exist_ok=True)

        pet_run_counter = 1
        mr_run_counter = {}

        for json_path in all_json_files:
            nii_path = json_path.replace(".json", ".nii.gz")
            if not os.path.exists(nii_path):
                log.debug(f"[BIDS] Skipping: no matching NIfTI for {json_path}")
                continue

            with open(json_path, "r") as f:
                metadata = json.load(f)

            modality = metadata.get("Modality", "").upper()

            if modality == "MR":
                series_desc = metadata.get("ProtocolName", "").lower()

                # Identifica il tipo (suffix BIDS)
                if "flair" in series_desc:
                    suffix = "flair"
                elif "t1" in series_desc:
                    suffix = "T1w"
                elif "t2" in series_desc:
                    suffix = "T2w"
                else:
                    suffix = "T1w"  # fallback

                # Contatore run per stesso tipo
                mr_run_counter.setdefault(suffix, 1)
                run_label = f"run-{mr_run_counter[suffix]}"
                mr_run_counter[suffix] += 1

                # Directory anat
                anat_dir = os.path.join(dest_sub_dir, "anat")
                os.makedirs(anat_dir, exist_ok=True)

                new_base = f"{sub_id}_{run_label}_{suffix}"

                # Copia file
                shutil.copy2(nii_path, os.path.join(anat_dir, f"{new_base}.nii.gz"))
                shutil.copy2(json_path, os.path.join(anat_dir, f"{new_base}.json"))

            elif modality == "PT":
                # --- Ricava il tracciante ---
                raw_trc = metadata.get("Radiopharmaceutical", "unknown")
                # estrai la prima parola alfabetica come tracciante
                trc = re.sub(r'[^a-zA-Z]', '', raw_trc.split()[0]).lower()
                trc_label = f"trc-{trc}" if trc else "trc-unknown"

                # --- Ricava il task ---
                raw_task = metadata.get("SeriesDescription", "unknown")
                task_clean = re.sub(r'[^a-zA-Z0-9]', '', raw_task.lower())
                task_label = f"task-{task_clean}" if task_clean else "task-unknown"

                # --- Determina se statico o dinamico ---
                frame_durations = metadata.get("FrameDuration", [])
                frame_times = metadata.get("FrameReferenceTime", [])
                if (isinstance(frame_durations, (list, tuple)) and len(frame_durations) > 1) or \
                        (isinstance(frame_times, (list, tuple)) and len(frame_times) > 1):
                    acq_label = "rec-acdync"
                    ses_label = "ses-02"
                else:
                    acq_label = "rec-acstat"
                    ses_label = "ses-01"

                pet_dir = os.path.join(dest_sub_dir, ses_label, "pet")
                os.makedirs(pet_dir, exist_ok=True)

                run_label = f"run-{pet_run_counter}"

                # Add:
                # trc_label for the tracer
                # acq_label for the acquisition type (dynamic or static)
                new_base = f"{sub_id}_{task_label}_{run_label}_pet"

                shutil.copy2(nii_path, os.path.join(pet_dir, f"{new_base}.nii.gz"))
                shutil.copy2(json_path, os.path.join(pet_dir, f"{new_base}.json"))

                pet_run_counter += 1

        log.debug(f"[BIDS] Imported {sub_id} in BIDS structure.")

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

    def _subfolders_belong_to_single_subject(self, subfolders):
        """
        Heuristics: le sottocartelle appartengono allo stesso soggetto se:
        - c'è al massimo 1 PatientID non vuoto E al massimo 1 PatientName non vuoto, oppure
        - coincidono (<=1) Name + BirthDate + Sex, oppure
        - pattern tipico MR+PT (modalità {'MR','PT'}) con BirthDate/Sex coerenti e
          niente chiari segnali di più soggetti.
        """
        import re

        ids = set()
        names = set()
        births = set()
        sexes = set()
        modalities = set()

        found_any_dicom = False

        for sub in subfolders:
            first_dcm = None
            for root, _, files in os.walk(sub):
                for file in files:
                    fp = os.path.join(root, file)
                    if self._is_dicom_file(fp):
                        first_dcm = fp
                        break
                if first_dcm:
                    break

            if not first_dcm:
                continue

            found_any_dicom = True
            try:
                dcm = pydicom.dcmread(first_dcm, stop_before_pixels=True, force=True)
            except Exception:
                continue

            pid = (str(getattr(dcm, 'PatientID', '') or '')).strip().lower()
            pname = (str(getattr(dcm, 'PatientName', '') or '')).strip().lower()
            pname = re.sub(r'\\s+', '', pname)  # normalizza spazi
            bdate = (str(getattr(dcm, 'PatientBirthDate', '') or '')).strip()
            sex = (str(getattr(dcm, 'PatientSex', '') or '')).strip().upper()
            mod = (str(getattr(dcm, 'Modality', '') or '')).strip().upper()

            if pid:
                ids.add(pid)
            if pname:
                names.add(pname)
            if bdate:
                births.add(bdate)
            if sex:
                sexes.add(sex)
            if mod:
                modalities.add(mod)

        if not found_any_dicom:
            return False

        # Casi “forti” di singolo soggetto
        if len(ids) <= 1 and len(names) <= 1:
            return True
        if len(names) <= 1 and len(births) <= 1 and len(sexes) <= 1:
            return True

        # Heuristica comune: MR+PT per lo stesso paziente ma sistemi diversi → ID discordanti
        if modalities.issuperset({'MR', 'PT'}) and len(births) <= 1 and len(sexes) <= 1:
            # Niente anagrafiche in conflitto → un solo soggetto
            return True

        return False

    def cancel(self):
        self._is_canceled = True
        if hasattr(self, 'process') and self.process is not None:
            self.process.terminate()
            self.process.wait(1)
            self.process.kill()
        log.info("Import Canceled.")