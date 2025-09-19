import os
import shutil
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal, QProcess

from logger import get_logger

log = get_logger()


class DlThread(QThread):
    progressbar_update = pyqtSignal(int)  # Progresso generale (0-100)
    file_update = pyqtSignal(str, str)  # (filename, status)
    log_update = pyqtSignal(str, str)  # Messaggi di log
    finished = pyqtSignal(bool, str)  # (success, message)
    cancel_requested = pyqtSignal()

    def __init__(self, input_files, workspace_path):
        super().__init__()
        self.input_files = input_files
        self.workspace_path = workspace_path

        self.output_dir = None

        self.total_files = None
        self.processed_files = None
        self.failed_files = None

        self.is_cancelled = False

        # Progress tracking
        self.total_phases = 6  # Numero totale di fasi per file
        self.current_file_index = 0
        self.current_phase = 0

        self.current_input_file = None
        self.current_input_file_basename = None
        self.current_synthstrip_file = None
        self.atlas_file = "pediatric_fdopa_pipeline/atlas/T1.nii.gz"

        # All processes for all phases
        self.synthstrip_process = None
        self.coregistration_process = None
        self.reorientation_process = None
        self.dl_preprocess = None
        self.dl_process = None
        self.dl_postprocess = None

        self.cancel_requested.connect(self.cancel)

    def update_progress(self):
        """Calcola e aggiorna la progress bar basata su file e fasi"""
        if self.total_files == 0:
            return

        # Calcola il progresso: (file completati * 6 + fasi del file corrente) / (totale file * 6) * 100
        total_phases_completed = (self.current_file_index * self.total_phases) + self.current_phase
        total_phases_overall = self.total_files * self.total_phases

        progress = int((total_phases_completed / total_phases_overall) * 100)
        progress = min(progress, 100)  # Assicurati che non superi 100

        self.progressbar_update.emit(progress)

        # Log di debug (opzionale)
        self.log_update.emit(
            f"Progress: {progress}% (File {self.current_file_index + 1}/{self.total_files}, "
            f"Phase {self.current_phase}/{self.total_phases})",
            'd'
        )

    def run(self):
        """Processa tutti i file NIfTI con la Deep Learning pipeline"""
        try:
            self.total_files = len(self.input_files)
            self.processed_files = 0
            self.failed_files = []

            # Inizializza progress bar
            self.current_file_index = 0
            self.current_phase = 0
            self.update_progress()
            self.progressbar_update.emit(5)

            for i, input_file in enumerate(self.input_files):
                if self.is_cancelled:
                    break

                self.current_file_index = i
                self.current_phase = 0

                # Crea directory temporanea per questo file
                temp_dir = None
                try:
                    temp_dir = tempfile.mkdtemp(prefix=f"dl_processing_{i}_")
                    out_dir = os.path.join(self.workspace_path, "outputs")
                    os.makedirs(out_dir, exist_ok=True)
                    self.output_dir = temp_dir

                    self.current_input_file = input_file
                    self.current_input_file_basename = os.path.basename(input_file)

                    success = self.process_single_file()

                    if success:
                        self.processed_files += 1
                        self.file_update.emit(
                            os.path.basename(input_file),
                            "✓ Completed"
                        )
                    else:
                        self.failed_files.append(os.path.basename(input_file))
                        self.file_update.emit(
                            os.path.basename(input_file),
                            "✗ Failed"
                        )

                except Exception as e:
                    self.failed_files.append(os.path.basename(input_file))
                    self.file_update.emit(
                        os.path.basename(input_file),
                        f"✗ Error: {str(e)}"
                    )
                    log.error(f"Error processing {input_file}: {e}")

                finally:
                    # Remove the temporary directory
                    if temp_dir and os.path.exists(temp_dir):
                        try:
                            shutil.rmtree(temp_dir)
                            self.log_update.emit(f"Removed temporary directory: {temp_dir}", 'i')
                        except Exception as e:
                            self.log_update.emit(f"Failed to remove temp dir {temp_dir}: {e}", 'w')

            # Progress bar al 100% alla fine
            self.progressbar_update.emit(100)

            # Final result
            if self.is_cancelled:
                self.finished.emit(False, "Processing cancelled by the user")
            elif self.failed_files:
                message = f"Processing completed with errors\n"
                message += f"Processed: {self.processed_files}/{self.total_files}\n"
                message += f"Failed: {', '.join(self.failed_files)}"
                self.finished.emit(True, message)
            else:
                message = f"Every {self.total_files} file processed successfully!"
                self.finished.emit(True, message)

        except Exception as e:
            log.error(f"General error in the worker: {e}")
            self.finished.emit(False, f"General error: {str(e)}")

    def process_single_file(self):
        """Process single file with the Deep Learning pipeline"""

        self.log_update.emit(f"=== PROCESSING: {self.current_input_file_basename} ===", 'i')

        # FASE 1: SynthStrip
        self.current_phase = 1
        ok = self.run_synthstrip()
        if not ok:
            return False
        self.update_progress()

        # FASE 2: Coregistration
        self.current_phase = 2
        ok = self.run_coregistration()
        if not ok or self.is_cancelled:
            return False
        self.update_progress()

        # FASE 3: Reorientation
        self.current_phase = 3
        ok = self.run_reorientation()
        if not ok or self.is_cancelled:
            return False
        self.update_progress()

        # FASE 4: Preprocess
        self.current_phase = 4
        ok = self.run_preprocess()
        if not ok or self.is_cancelled:
            return False
        self.update_progress()

        # FASE 5: Deep Learning
        self.current_phase = 5
        ok = self.run_deep_learning()
        if not ok or self.is_cancelled:
            return False
        self.update_progress()

        # FASE 6: Postprocess
        self.current_phase = 6
        ok = self.run_postprocess()
        if not ok or self.is_cancelled:
            return False
        self.update_progress()

        return True

    def run_synthstrip(self):
        """Synthstrip on a single file"""
        self.file_update.emit(self.current_input_file_basename, "Phase 1/6: Synthstrip skull strip...")
        self.log_update.emit("FASE 1: Skull strip with Synthstrip", 'i')

        self.log_update.emit(f"SynthStrip started: {os.path.basename(self.current_input_file)}", 'i')

        # Nome file skull stripped
        base_name = self.current_input_file_basename.replace(".nii.gz", "").replace(".nii", "")
        self.current_synthstrip_file = os.path.join(self.output_dir, f"{base_name}_skull_stripped.nii.gz")

        self.synthstrip_process = QProcess()

        cmd = [
            "nipreps-synthstrip",
            "-i", self.current_input_file,
            "-o", self.current_synthstrip_file,
            "-g",
            "--model", "synthstrip.infant.1.pt"
        ]

        self.synthstrip_process.start(cmd[0], cmd[1:])

        if not self.synthstrip_process.waitForStarted():
            self.log_update.emit("✗ Error: Synthstrip didn't start", 'e')
            return False

        if not self.synthstrip_process.waitForFinished(-1):  # -1 = senza timeout
            self.log_update.emit("✗ SynthStrip finished on timeout", 'e')
            return False

        if self.synthstrip_process.exitCode() != 0:
            self.log_update.emit(f"✗ SynthStrip failed (code: {self.synthstrip_process.exitCode()})", 'e')
            return False

        if not os.path.exists(self.current_synthstrip_file):
            self.log_update.emit("✗ Output skull stripped file non creato", 'e')
            return False

        self.log_update.emit("✓ Skull stripping completed", 'i')
        return True

    def run_coregistration(self):
        """Esegue coregistrazione con atlas"""

        self.file_update.emit(self.current_input_file_basename, "Phase 2/6: Coregistration...")
        self.log_update.emit("FASE 2: Coregistration", 'i')

        self.log_update.emit(f"Coregistration started: {os.path.basename(self.current_input_file)}", 'i')

        # Crea directory per coregistrazione
        coreg_dir = os.path.join(self.output_dir, "coregistration")
        os.makedirs(coreg_dir, exist_ok=True)

        self.coregistration_process = QProcess()

        python_executable = sys.executable
        args = [
            "deep_learning/coregistration.py",
            "--mri", self.current_input_file,
            "--skull", self.current_synthstrip_file,
            "--atlas", self.atlas_file,
            "-o", coreg_dir
        ]

        self.coregistration_process.start(python_executable, args)

        if not self.coregistration_process.waitForStarted():
            self.log_update.emit("✗ Error: Coregistration didn't start", 'e')
            return False

        if not self.coregistration_process.waitForFinished(-1):  # -1 = senza timeout
            self.log_update.emit("✗ Coregistration finished on timeout", 'e')
            return False

        if self.coregistration_process.exitCode() != 0:
            self.log_update.emit(f"✗ Coregistration failed (code: {self.coregistration_process.exitCode()})", 'e')
            return False

        self.log_update.emit("✓ Coregistration completed", 'i')
        return True

    def run_reorientation(self):
        """Esegue la riorientazione del file brain_in_atlas usando la matrice affine di BraTS"""

        self.file_update.emit(self.current_input_file_basename, "Phase 3/6: Reorientation...")
        self.log_update.emit("FASE 3: Reorientation", 'i')

        self.log_update.emit(f"Reorientation started: {os.path.basename(self.current_input_file)}", 'i')

        coreg_dir = Path(os.path.join(self.output_dir, "coregistration"))
        brain_in_atlas_files = list(coreg_dir.glob("*.nii.gz")) + list(coreg_dir.glob("*.nii"))

        if not brain_in_atlas_files:
            self.log_update.emit("✗ No brain_in_atlas file found", 'e')
            return False

        brain_in_atlas_file = str(brain_in_atlas_files[0])

        self.reorientation_process = QProcess()

        python_executable = sys.executable
        args = [
            "deep_learning/reorientation.py",
            "--input", brain_in_atlas_file,
            "--output", self.output_dir + "/reoriented",
            "--basename", self.current_input_file_basename.replace(".nii.gz", "").replace(".nii", "")
        ]

        self.reorientation_process.start(python_executable, args)

        if not self.reorientation_process.waitForStarted():
            self.log_update.emit("✗ Error: Reorientation didn't start", 'e')
            return False

        if not self.reorientation_process.waitForFinished(-1):  # -1 = senza timeout
            self.log_update.emit("✗ Reorientation finished on timeout", 'e')
            return False

        if self.reorientation_process.exitCode() != 0:
            self.log_update.emit(f"✗ Reorientation failed (code: {self.reorientation_process.exitCode()})", 'e')
            return False

        self.log_update.emit("✓ Reorientation completed", 'i')
        return True

    def run_preprocess(self):
        """Esegue FASE 4: PREPARE & FASE 5: PREPROCESS"""
        self.file_update.emit(self.current_input_file_basename, "Phase 4/6: Preparing and preprocessing...")
        self.log_update.emit("FASE 4: Prepare and preprocess", 'i')

        data_path = os.path.join(self.output_dir, "reoriented")
        results_path = os.path.join(self.output_dir, "preprocess")

        self.dl_preprocess = QProcess()

        python_executable = sys.executable  # Usa lo stesso interprete Python
        args = [
            "deep_learning/preprocess.py",
            '--data', data_path,
            '--results', results_path,
            '--ohe'
        ]

        self.dl_preprocess.start(python_executable, args)

        if not self.dl_preprocess.waitForStarted():
            self.log_update.emit("✗ Error: Deep learning preprocess didn't start", 'e')
            return False

        if not self.dl_preprocess.waitForFinished(-1):  # -1 = senza timeout
            self.log_update.emit("✗ Deep learning preprocess finished on timeout", 'e')
            return False

        if self.dl_preprocess.exitCode() != 0:
            self.log_update.emit(f"✗ Deep learning preprocess failed (code: {self.dl_preprocess.exitCode()})", 'e')
            return False

        self.log_update.emit("✓ Deep learning preprocess completed", 'i')
        return True

    def run_deep_learning(self):
        """Esegue FASE 5: DEEP LEARNING"""
        self.file_update.emit(self.current_input_file_basename, "Phase 5/6: Deep Learning...")
        self.log_update.emit("FASE 5: Deep learning execution", 'i')

        self.dl_process = QProcess()

        python_executable = sys.executable
        args = [
            "deep_learning/deep_learning_runner.py",
            '--depth', '6',
            '--filters', '64', '96', '128', '192', '256', '384', '512',
            '--min_fmap', '2',
            '--gpus', '1',
            '--amp',
            '--save_preds',
            '--exec_mode', 'predict',
            '--data', f'{self.output_dir}/preprocess/val_3d/test',
            '--ckpt_path', 'deep_learning/checkpoints/fold3/epoch=146-dice=88.05.ckpt',
            '--tta',
            '--results', f'{self.output_dir}/dl_results'
        ]

        self.dl_process.start(python_executable, args)

        if not self.dl_process.waitForStarted():
            self.log_update.emit("✗ Error: Deep learning execution didn't start", 'e')
            return False

        if not self.dl_process.waitForFinished(-1):  # -1 = senza timeout
            self.log_update.emit("✗ Deep learning execution finished on timeout", 'e')
            return False

        if self.dl_process.exitCode() != 0:
            self.log_update.emit(f"✗ Deep learning execution failed (code: {self.dl_process.exitCode()})", 'e')
            return False

        self.log_update.emit("✓ Deep learning execution completed", 'i')
        return True

    def run_postprocess(self):
        self.file_update.emit(self.current_input_file_basename, "Phase 6/6: Postprocessing...")
        self.log_update.emit("FASE 6: Postprocess", 'i')

        self.dl_postprocess = QProcess()

        python_executable = sys.executable
        args = [
            "deep_learning/postprocess.py",
            '-i', f'{self.output_dir}/dl_results/predictions_epoch=146-dice=88_05_task=train_fold=0_tta',
            '-o', f'{self.output_dir}/dl_postprocess',
            '--mri', f'{self.current_input_file}'
        ]

        self.dl_postprocess.start(python_executable, args)

        if not self.dl_postprocess.waitForStarted():
            self.log_update.emit("✗ Error: Postprocess didn't start", 'e')
            return False

        if not self.dl_postprocess.waitForFinished(-1):  # -1 = senza timeout
            self.log_update.emit("✗ Postprocess finished on timeout", 'e')
            return False

        if self.dl_postprocess.exitCode() != 0:
            self.log_update.emit(f"✗ Postprocess failed (code: {self.dl_postprocess.exitCode()})", 'e')
            return False

        self.log_update.emit("✓ Postprocess completed", 'i')
        return True

    def cancel(self):
        self.is_cancelled = True

        self.log_update.emit("Cancellation requested - stopping all processes...", 'w')

        # Dizionario con nome processo e oggetto
        processes = {
            'SynthStrip': self.synthstrip_process,
            'Coregistration': self.coregistration_process,
            'Reorientation': self.reorientation_process,
            'Preprocess': self.dl_preprocess,
            'Deep Learning': self.dl_process,
            'Postprocess': self.dl_postprocess
        }

        active_processes = []

        # Primo passo: identifica processi attivi
        for name, process in processes.items():
            if process is not None:
                state = process.state()
                if state in [QProcess.ProcessState.Running, QProcess.ProcessState.Starting]:
                    active_processes.append((name, process))
                    self.log_update.emit(f"Found active process: {name} (state: {state.name})", 'i')

        if not active_processes:
            self.log_update.emit("No active processes to cancel", 'i')
            return

        # Secondo passo: termina processi attivi
        for name, process in active_processes:
            try:
                self.log_update.emit(f"Stopping {name}...", 'w')

                # Step 1: Terminate (SIGTERM)
                process.terminate()
                if process.waitForFinished(3000):
                    self.log_update.emit(f"{name} terminated gracefully", 'i')
                    continue

                # Step 2: Kill (SIGKILL) se terminate non ha funzionato
                self.log_update.emit(f"Force killing {name}...", 'w')
                process.kill()
                if process.waitForFinished(2000):
                    self.log_update.emit(f"{name} killed successfully", 'i')
                else:
                    self.log_update.emit(f"Warning: {name} may still be running", 'w')

            except Exception as e:
                self.log_update.emit(f"Error stopping {name}: {str(e)}", 'e')

        self.log_update.emit("Cancellation procedure completed", 'i')

        # Opzionale: emetti il segnale finished per notificare la UI
        self.finished.emit(False, "Processing cancelled by user")