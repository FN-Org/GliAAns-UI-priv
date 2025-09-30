import os
import json
from PyQt6.QtCore import pyqtSignal, QThread, QProcess
from logger import get_logger
from utils import setup_fsl_env

log = get_logger()


class SkullStripThread(QThread):
    """Worker thread per eseguire i comandi BET o HD-BET in background usando QProcess"""

    progress_updated = pyqtSignal(str)
    progress_value_updated = pyqtSignal(int)
    file_started = pyqtSignal(str)
    file_completed = pyqtSignal(str, bool, str)
    all_completed = pyqtSignal(int, list)

    def __init__(self, files, workspace_path, parameters, has_cuda,has_bet):
        super().__init__()
        self.files = files
        self.workspace_path = workspace_path
        self.parameters = parameters
        self.has_cuda = has_cuda
        self.is_cancelled = False
        self.success_count = 0
        self.failed_files = []
        self.has_bet = has_bet

    def cancel(self):
        """Cancella l'operazione"""
        self.is_cancelled = True
        if hasattr(self, "process") and self.process is not None:
            try:
                self.process.terminate()
                self.process.kill()
            except Exception as e:
                log.error(f"Errore nel cancellare il processo: {e}")

    def run(self):
        base_progress = 10
        progress_per_file = int(90/len(self.files))
        for i, nifti_file in enumerate(self.files):
            if self.is_cancelled:
                break

            filename = os.path.basename(nifti_file)
            self.file_started.emit(filename)
            base_progress = int(base_progress + i * progress_per_file)
            self.progress_value_updated.emit(base_progress)
            self.progress_updated.emit(f"Processing {filename} ({i+1}/{len(self.files)})")

            try:
                nifti_file = os.path.normpath(nifti_file)
                self.workspace_path = os.path.normpath(self.workspace_path)

                # Estrai subject ID
                path_parts = nifti_file.replace(self.workspace_path, '').strip(os.sep).split(os.sep)
                subject_id = next((p for p in path_parts if p.startswith("sub-")), None)
                if not subject_id:
                    self.file_completed.emit(filename, False, "Cannot extract subject ID")
                    self.failed_files.append(nifti_file)
                    continue

                # Directory output
                output_dir = os.path.join(self.workspace_path, 'derivatives', 'skullstrips', subject_id, 'anat')
                os.makedirs(output_dir, exist_ok=True)

                base_name = filename.replace('.nii.gz','').replace('.nii','')

                # Costruzione comando
                if self.has_bet:
                    os.environ["FSLDIR"] = setup_fsl_env()
                    f_val = self.parameters.get('f_val', 0.5)
                    f_str = f"f{str(f_val).replace('.', '')}"
                    output_file = os.path.join(output_dir, f"{base_name}_{f_str}_brain.nii.gz")
                    cmd = ["bet", nifti_file, output_file, "-f", str(f_val)]
                    for opt in ['opt_m','opt_t','opt_s','opt_o']:
                        if self.parameters.get(opt, False):
                            cmd.append(f"-{opt[-1]}")
                    for coord in ['c_x','c_y','c_z']:
                        val = self.parameters.get(coord,0)
                        if val != 0:
                            cmd += ["-c", str(val)]
                    if not self.parameters.get('opt_brain_extracted', True):
                        cmd.append("-n")
                    method = "FSL BET"
                else:
                    output_file = os.path.join(output_dir, f"{base_name}_hd-bet_brain.nii.gz")
                    cmd = ["hd-bet", "-i", nifti_file, "-o", output_file]
                    if not self.has_cuda:
                        cmd += ["-device", "cpu", "--disable_tta"]
                    method = "HD-BET"

                # Esecuzione con QProcess
                self.process = QProcess()
                self.process.start(cmd[0], cmd[1:])

                self.process.waitForFinished(-1)

                if self.is_cancelled:
                    break

                ret_code = self.process.exitCode()
                stderr = bytes(self.process.readAllStandardError()).decode()
                stdout = bytes(self.process.readAllStandardOutput()).decode()

                if ret_code != 0:
                    self.file_completed.emit(filename, False, stderr or "Error executing command")
                    self.failed_files.append(nifti_file)
                    continue

                # Salva metadati JSON
                json_file = output_file.replace(".nii.gz", ".json")
                metadata = {
                    "SkullStripped": True,
                    "Description": "Skull-stripped brain image",
                    "Sources": [filename],
                    "SkullStrippingMethod": method
                }
                with open(json_file, 'w') as f:
                    json.dump(metadata, f, indent=2)

                self.success_count += 1
                self.file_completed.emit(filename, True, "")

            except Exception as e:
                self.file_completed.emit(filename, False, str(e))
                self.failed_files.append(nifti_file)


        self.all_completed.emit(self.success_count, self.failed_files)
