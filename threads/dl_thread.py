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

        self.total_files = len(self.input_files)
        self.processed_files = 0
        self.failed_files = []

        # Inizializza progress bar
        self.current_file_index = 0
        self.current_phase = 0
        self.update_progress()
        self.progressbar_update.emit(5)

        self.process_single_file()

    def process_single_file(self):
        """Process single file with the Deep Learning pipeline"""
        temp_dir = tempfile.mkdtemp(prefix=f"dl_processing_{self.current_file_index+1}_")
        out_dir = os.path.join(self.workspace_path, "outputs")
        os.makedirs(out_dir, exist_ok=True)
        self.output_dir = temp_dir

        self.current_input_file = self.input_files[self.current_file_index]
        self.current_input_file_basename = os.path.basename(self.current_input_file)

        self.log_update.emit(f"=== PROCESSING: {self.current_input_file_basename} ===", 'i')

        # FASE 1: SynthStrip
        self.current_phase = 1
        self.run_synthstrip()

    def run_synthstrip(self):
        """Synthstrip on a single file"""
        phase = "Synthstrip"
        self.file_update.emit(self.current_input_file_basename, "Phase 1/6: Synthstrip skull strip...")
        self.log_update.emit("FASE 1: Skull strip with Synthstrip", 'i')

        self.log_update.emit(f"SynthStrip started: {os.path.basename(self.current_input_file)}", 'i')

        # Nome file skull stripped
        base_name = self.current_input_file_basename.replace(".nii.gz", "").replace(".nii", "")
        self.current_synthstrip_file = os.path.join(self.output_dir, f"{base_name}_skull_stripped.nii.gz")

        self.synthstrip_process = QProcess()
        self.synthstrip_process.finished.connect(self.on_synthstrip_finished)
        self.synthstrip_process.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.synthstrip_process.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.synthstrip_process.readAllStandardOutput()))
        self.synthstrip_process.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.synthstrip_process.readAllStandardError()))

        cmd = [
            "nipreps-synthstrip",
            "-i", self.current_input_file,
            "-o", self.current_synthstrip_file,
            "-g",
            "--model", "synthstrip.infant.1.pt"
        ]

        self.synthstrip_process.start(cmd[0], cmd[1:])

    def on_synthstrip_finished(self, exit_code, exit_status):
        # This slot is called by the QProcess when it finishes
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("SynthStrip failed", f"Exit code: {exit_code}")
            if self.current_file_index < self.total_files:
                self.current_file_index += 1
                self.file_update(self.current_input_file_basename, "Segmentation failed for this file")
                self.process_single_file()
            return

        self.log_update.emit("✓ Skull stripping completed", 'i')
        self.update_progress()
        # FASE 2: Coregistration
        self.current_phase = 2
        self.run_coregistration()  # Start the next phase

    def run_coregistration(self):
        """Esegue coregistrazione con atlas"""
        phase = "Coregistration"

        self.file_update.emit(self.current_input_file_basename, "Phase 2/6: Coregistration...")
        self.log_update.emit("FASE 2: Coregistration", 'i')

        self.log_update.emit(f"Coregistration started: {os.path.basename(self.current_input_file)}", 'i')

        # Crea directory per coregistrazione
        coreg_dir = os.path.join(self.output_dir, "coregistration")
        os.makedirs(coreg_dir, exist_ok=True)

        self.coregistration_process = QProcess()
        self.coregistration_process.finished.connect(self.on_coregistration_finished)
        self.coregistration_process.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.coregistration_process.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.coregistration_process.readAllStandardOutput()))
        self.coregistration_process.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.coregistration_process.readAllStandardError()))

        python_executable = sys.executable
        args = [
            "deep_learning/coregistration.py",
            "--mri", self.current_input_file,
            "--skull", self.current_synthstrip_file,
            "--atlas", self.atlas_file,
            "-o", coreg_dir
        ]

        self.coregistration_process.start(python_executable, args)

    def on_coregistration_finished(self, exit_code, exit_status):
        # This slot is called by the QProcess when it finishes
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("Coregistration failed", f"Exit code: {exit_code}")
            if self.current_file_index < self.total_files:
                self.current_file_index += 1
                self.file_update(self.current_input_file_basename, "Segmentation failed for this file")
                self.process_single_file()
            return

        self.log_update.emit("✓ Coregistration completed", 'i')
        self.update_progress()
        # FASE 3: Reorientation
        self.current_phase = 3
        self.run_reorientation()  # Start the next phase

    def run_reorientation(self):
        """Esegue la riorientazione del file brain_in_atlas usando la matrice affine di BraTS"""
        phase = "Reorientation"

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
        self.reorientation_process.finished.connect(self.on_reorientation_finished)
        self.reorientation_process.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.reorientation_process.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.reorientation_process.readAllStandardOutput()))
        self.reorientation_process.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.reorientation_process.readAllStandardError()))

        python_executable = sys.executable
        args = [
            "deep_learning/reorientation.py",
            "--input", brain_in_atlas_file,
            "--output", self.output_dir + "/reoriented",
            "--basename", self.current_input_file_basename.replace(".nii.gz", "").replace(".nii", "")
        ]

        self.reorientation_process.start(python_executable, args)

    def on_reorientation_finished(self, exit_code, exit_status):
        # This slot is called by the QProcess when it finishes
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("Reorientation failed", f"Exit code: {exit_code}")
            if self.current_file_index < self.total_files:
                self.current_file_index += 1
                self.file_update(self.current_input_file_basename, "Segmentation failed for this file")
                self.process_single_file()
            return

        self.log_update.emit("✓ Reorientation completed", 'i')
        self.update_progress()
        # FASE 4: Preprocess
        self.current_phase = 4
        self.run_reorientation()  # Start the next phase

    def run_preprocess(self):
        """Esegue FASE 4: PREPARE & FASE 5: PREPROCESS"""
        phase = "Preprocessing"

        self.file_update.emit(self.current_input_file_basename, "Phase 4/6: Preparing and preprocessing...")
        self.log_update.emit("FASE 4: Prepare and preprocess", 'i')

        data_path = os.path.join(self.output_dir, "reoriented")
        results_path = os.path.join(self.output_dir, "preprocess")

        self.dl_preprocess = QProcess()
        self.dl_preprocess.finished.connect(self.on_preprocess_finished)
        self.dl_preprocess.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.dl_preprocess.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.dl_preprocess.readAllStandardOutput()))
        self.dl_preprocess.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.dl_preprocess.readAllStandardError()))

        python_executable = sys.executable  # Usa lo stesso interprete Python
        args = [
            "deep_learning/preprocess.py",
            '--data', data_path,
            '--results', results_path,
            '--ohe'
        ]

        self.dl_preprocess.start(python_executable, args)

    def on_preprocess_finished(self, exit_code, exit_status):
        # This slot is called by the QProcess when it finishes
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("Preprocess failed", f"Exit code: {exit_code}")
            if self.current_file_index < self.total_files:
                self.current_file_index += 1
                self.file_update(self.current_input_file_basename, "Segmentation failed for this file")
                self.process_single_file()
            return

        self.log_update.emit("✓ Preprocess completed", 'i')
        self.update_progress()
        # FASE 5: Deep learning execution
        self.current_phase = 5
        self.run_deep_learning()  # Start the next phase

    def run_deep_learning(self):
        """Esegue FASE 5: DEEP LEARNING"""
        phase = "Deep Learning execution"

        self.file_update.emit(self.current_input_file_basename, "Phase 5/6: Deep Learning...")
        self.log_update.emit("FASE 5: Deep learning execution", 'i')

        self.dl_process = QProcess()
        self.dl_process.finished.connect(self.on_dl_finished)
        self.dl_process.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.dl_process.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.dl_process.readAllStandardOutput()))
        self.dl_process.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.dl_process.readAllStandardError()))

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

    def on_dl_finished(self, exit_code, exit_status):
        # This slot is called by the QProcess when it finishes
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("Deep learning execution failed", f"Exit code: {exit_code}")
            if self.current_file_index < self.total_files:
                self.current_file_index += 1
                self.file_update(self.current_input_file_basename, "Segmentation failed for this file")
                self.process_single_file()
            return

        self.log_update.emit("✓ Deep learning execution completed", 'i')
        self.update_progress()
        # FASE 6: Postprocess
        self.current_phase = 6
        self.run_postprocess()  # Start the next phase

    def run_postprocess(self):
        phase = "Postprocessing"

        self.file_update.emit(self.current_input_file_basename, "Phase 6/6: Postprocessing...")
        self.log_update.emit("FASE 6: Postprocess", 'i')

        self.dl_postprocess = QProcess()
        self.dl_postprocess.finished.connect(self.on_postprocess_finished)
        self.dl_postprocess.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.dl_postprocess.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.dl_postprocess.readAllStandardOutput()))
        self.dl_postprocess.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.dl_postprocess.readAllStandardError()))

        python_executable = sys.executable
        args = [
            "deep_learning/postprocess.py",
            '-i', f'{self.output_dir}/dl_results/predictions_epoch=146-dice=88_05_task=train_fold=0_tta',
            '-o', f'{self.output_dir}/dl_postprocess',
            '--mri', f'{self.current_input_file}'
        ]

        self.dl_postprocess.start(python_executable, args)

    def on_postprocess_finished(self, exit_code, exit_status):
        # This slot is called by the QProcess when it finishes
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("Postprocess failed", f"Exit code: {exit_code}")
            if self.current_file_index < self.total_files:
                self.current_file_index += 1
                self.file_update(self.current_input_file_basename, "Segmentation failed for this file")
                self.process_single_file()
            return

        self.log_update.emit("✓ Postprocess completed", 'i')
        self.update_progress()

        if self.current_file_index < self.total_files:
            self.current_file_index += 1
            self.process_single_file()
        else:
            self.finished.emit(False, "Processing completed")
        return

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

    def on_error(self, phase: str, error):
        """
        Handler per errori di avvio/exec di un QProcess.
        """
        try:
            self.log_update.emit(f"[{phase}] Process error: {error}", 'e')
        except Exception as e:
            self.log_update.emit(f"[{phase}] Error in on_error handler: {str(e)}", 'e')

    def on_stdout(self, phase: str, data):
        """
        Handler per lo stdout di un QProcess.
        """
        try:
            text = bytes(data).decode("utf-8").strip()
            if text:
                for line in text.splitlines():
                    self.log_update.emit(f"[{phase}] {line}", 'i')
        except Exception as e:
            self.log_update.emit(f"[{phase}] Error decoding stdout: {str(e)}", 'e')

    def on_stderr(self, phase: str, data):
        """
        Handler per lo stderr di un QProcess.
        """
        try:
            text = bytes(data).decode("utf-8").strip()
            if text:
                for line in text.splitlines():
                    self.log_update.emit(f"[{phase}] {line}", 'e')
        except Exception as e:
            self.log_update.emit(f"[{phase}] Error decoding stderr: {str(e)}", 'e')