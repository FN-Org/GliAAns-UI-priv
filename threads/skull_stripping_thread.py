import json
import os
import subprocess

from PyQt6.QtCore import pyqtSignal, QThread


class SkullStripThread(QThread):
    """Worker thread per eseguire i comandi BET in background"""

    # Segnali per comunicare con l'interfaccia principale
    progress_updated = pyqtSignal(str)  # Messaggio di progresso
    progress_value_updated = pyqtSignal(int)  # Valore numerico per progress bar
    file_started = pyqtSignal(str)  # filename quando inizia il processing
    file_completed = pyqtSignal(str, bool, str)  # filename, success, error_message
    all_completed = pyqtSignal(int, list)  # success_count, failed_files

    def __init__(self, files, workspace_path, parameters,system_info):
        super().__init__()
        self.files = files
        self.workspace_path = workspace_path
        self.parameters = parameters
        self.is_cancelled = False
        self.system_info = system_info

    def cancel(self):
        """Cancella l'operazione"""
        self.is_cancelled = True

    def run(self):
        """Esegue il processing dei file in background"""
        success_count = 0
        failed_files = []

        for i, nifti_file in enumerate(self.files):
            if self.is_cancelled:
                break

            try:
                # Emetti segnale di inizio file
                filename = os.path.basename(nifti_file)
                self.file_started.emit(filename)
                self.progress_updated.emit(f"Processing {filename} ({i + 1}/{len(self.files)})...")

                # Aggiorna progress bar all'inizio del file
                progress_base = int((i / len(self.files)) * 100)
                self.progress_value_updated.emit(progress_base)

                # Estrai l'ID del paziente dal percorso del file
                self.progress_updated.emit(f"Extracting subject ID for {filename}...")
                path_parts = nifti_file.replace(self.workspace_path, '').strip(os.sep).split(os.sep)
                subject_id = None
                for part in path_parts:
                    if part.startswith('sub-'):
                        subject_id = part
                        break

                if not subject_id:
                    error_msg = f"Could not extract subject ID from: {nifti_file}"
                    self.file_completed.emit(filename, False, error_msg)
                    failed_files.append(nifti_file)
                    continue

                # Crea la directory di output
                self.progress_updated.emit(f"Creating output directory for {filename}...")
                self.progress_value_updated.emit(progress_base + 10)

                output_dir = os.path.join(self.workspace_path, 'derivatives', 'skullstrips', subject_id, 'anat')
                os.makedirs(output_dir, exist_ok=True)

                # Prepara i parametri di output
                self.progress_updated.emit(f"Preparing parameters for {filename}...")
                self.progress_value_updated.emit(progress_base + 20)

                # Estrai il nome base del file (senza estensione)
                if filename.endswith('.nii.gz'):
                    base_name = filename[:-7]  # Rimuovi .nii.gz
                elif filename.endswith('.nii'):
                    base_name = filename[:-4]  # Rimuovi .nii
                else:
                    base_name = filename

                if self.system_info["os"] != "Windows":
                    # Estrai il parametro f per il naming
                    f_val = self.parameters['f_val']
                    f_str = f"{f_val:.2f}"  # Formatta con 2 decimali
                    f_formatted = f"f{f_str.replace('.', '')}"  # Rimuovi il punto per il nome file

                    # Nome del file di output
                    output_filename = f"{base_name}_{f_formatted}_brain.nii.gz"
                    output_file = os.path.join(output_dir, output_filename)

                    # Costruisci il comando BET
                    self.progress_updated.emit(f"Building BET command for {filename}...")
                    self.progress_value_updated.emit(progress_base + 30)

                    cmd = ["bet", nifti_file, output_file]

                    # Aggiungi il parametro fractional intensity
                    if f_val:
                        cmd += ["-f", str(f_val)]

                    # Aggiungi opzioni avanzate se selezionate
                    if self.parameters.get('opt_m', False):
                        cmd.append("-m")
                    if self.parameters.get('opt_t', False):
                        cmd.append("-t")
                    if self.parameters.get('opt_s', False):
                        cmd.append("-s")
                    if self.parameters.get('opt_o', False):
                        cmd.append("-o")

                    # Aggiungi parametro gradient se impostato
                    g_val = self.parameters.get('g_val', 0.0)
                    if g_val != 0.0:
                        cmd += ["-g", str(g_val)]

                    # Aggiungi coordinate del centro se impostate (diverse da 0,0,0)
                    c_x = self.parameters.get('c_x', 0)
                    c_y = self.parameters.get('c_y', 0)
                    c_z = self.parameters.get('c_z', 0)
                    if c_x != 0 or c_y != 0 or c_z != 0:
                        cmd += ["-c", str(c_x), str(c_y), str(c_z)]

                    # Se non è selezionata l'opzione "Output brain-extracted image", aggiungi -n
                    if not self.parameters.get('opt_brain_extracted', True):
                        cmd.append("-n")

                    # Esegui il comando
                    self.progress_updated.emit(f"Running FSL BET on {filename}... This may take a while.")
                    self.progress_value_updated.emit(progress_base + 40)

                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)

                    # Crea metadati
                    self.progress_updated.emit(f"Creating metadata for {filename}...")
                    self.progress_value_updated.emit(progress_base + 80)

                    # Crea anche un file JSON con i metadati (opzionale ma utile per BIDS)
                    json_file = output_file.replace('.nii.gz', '.json')
                    metadata = {
                        "SkullStripped": True,
                        "Description": "Skull-stripped brain image",
                        "Sources": [filename],
                        "SkullStrippingMethod": "FSL BET",
                        "SkullStrippingParameters": {
                            "fractional_intensity": f_val
                        }
                    }

                    # Aggiungi parametri utilizzati ai metadati
                    if g_val != 0.0:
                        metadata["SkullStrippingParameters"]["vertical_gradient"] = g_val
                    if c_x != 0 or c_y != 0 or c_z != 0:
                        metadata["SkullStrippingParameters"]["center_of_gravity"] = [c_x, c_y, c_z]

                    # Aggiungi flags utilizzati
                    flags_used = []
                    if not self.parameters.get('opt_brain_extracted', True):
                        flags_used.append("-n (no brain image output)")
                    if self.parameters.get('opt_m', False):
                        flags_used.append("-m (binary brain mask)")
                    if self.parameters.get('opt_t', False):
                        flags_used.append("-t (thresholding)")
                    if self.parameters.get('opt_s', False):
                        flags_used.append("-s (exterior skull surface)")
                    if self.parameters.get('opt_o', False):
                        flags_used.append("-o (brain surface overlay)")

                    if flags_used:
                        metadata["SkullStrippingParameters"]["flags_used"] = flags_used
                else:
                    # Nome del file di output
                    output_filename = f"{base_name}_hd-bet_brain.nii.gz"
                    output_file = os.path.join(output_dir, output_filename)

                    # Costruisci il comando HD-BET
                    self.progress_updated.emit(f"Building HD-BET command for {filename}...")
                    self.progress_value_updated.emit(progress_base + 30)

                    cmd = ["hd-bet","-i",nifti_file,"-o",output_file]

                    has_nvidia = any("NVIDIA" in gpu["name"].upper() for gpu in self.system_info["gpus"])

                    if not has_nvidia:
                        cmd += ["-device","cpu"]
                        cmd += ["--disable_tta"]



                    # Esegui il comando
                    self.progress_updated.emit(f"Running HD-BET on {filename}... This may take a while.")
                    self.progress_value_updated.emit(progress_base + 40)

                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)

                    # Crea metadati
                    self.progress_updated.emit(f"Creating metadata for {filename}...")
                    self.progress_value_updated.emit(progress_base + 80)

                    # Crea anche un file JSON con i metadati (opzionale ma utile per BIDS)
                    json_file = output_file.replace('.nii.gz', '.json')
                    metadata = {
                        "SkullStripped": True,
                        "Description": "Skull-stripped brain image",
                        "Sources": [filename],
                        "SkullStrippingMethod": "HD-BET",
                    }

                with open(json_file, 'w') as f:
                    json.dump(metadata, f, indent=2)

                # Completamento file
                self.progress_value_updated.emit(progress_base + 100)
                success_count += 1
                self.file_completed.emit(filename, True, "")

            except subprocess.CalledProcessError as e:
                if self.system_info["os"] == "Windows":
                    error_msg = f"HD-BET command failed"

                    for fname in ["dataset.json", "plans.json", "predict_from_raw_data_args.json"]:
                        fpath = os.path.join(output_dir, fname)
                        try:
                            os.remove(fpath)
                        except FileNotFoundError:
                            pass

                else:
                    error_msg = f"BET command failed"

                if e.stderr:
                    error_msg += f": {e.stderr}"
                self.file_completed.emit(filename, False, error_msg)
                failed_files.append(nifti_file)
            except Exception as e:
                error_msg = f"Error processing file: {str(e)}"
                self.file_completed.emit(filename, False, error_msg)
                failed_files.append(nifti_file)

        # Emetti segnale di completamento
        if not self.is_cancelled:
            self.progress_value_updated.emit(100)
            self.all_completed.emit(success_count, failed_files)