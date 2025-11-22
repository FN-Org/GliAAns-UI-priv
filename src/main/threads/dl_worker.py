import os
import shutil
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal, QProcess, QObject, QCoreApplication

from logger import get_logger
from utils import get_bin_path, resource_path, get_dl_python_executable, get_script_path

log = get_logger()


class DlWorker(QObject):
    progressbar_update = pyqtSignal(int)  # Overall progress (0-100)
    file_update = pyqtSignal(str, str)  # (filename, status)
    log_update = pyqtSignal(str, str)  # Log messages
    finished = pyqtSignal(bool, str)  # (success, message)
    cancel_requested = pyqtSignal()

    def __init__(self, input_files, workspace_path, has_freesurfer):
        super().__init__()
        self.input_files = input_files
        self.workspace_path = workspace_path
        self.has_freesurfer = has_freesurfer

        self.output_dir = None

        self.total_files = None
        self.processed_files = None
        self.failed_files = None

        self.is_cancelled = False

        # Progress tracking
        self.total_phases = 6  # Total number of phases per file
        self.current_file_index = 0
        self.current_phase = 0

        self.current_input_file = None
        self.current_input_file_basename = None
        self.current_synthstrip_file = None
        self.atlas_file = get_script_path("deep_learning/atlas/T1.nii.gz")
        self.brats_file = get_script_path("deep_learning/atlas/BraTS-GLI-01-001.nii")
        self.synthstrip_model = get_script_path("deep_learning/synthstrip.1.pt")

        # All processes for all phases
        self.synthstrip_process = None
        self.coregistration_process = None
        self.reorientation_process = None
        self.dl_preprocess = None
        self.dl_process = None
        self.dl_postprocess = None

        try:
            self.nipreps_synthstrip_bin_path = get_bin_path("nipreps-synthstrip")
        except FileNotFoundError:
            log.error(str(FileNotFoundError))
            raise RuntimeError
        log.debug(f"nipreps synthstrip binary path: {self.nipreps_synthstrip_bin_path}")

        self.python_executable = get_dl_python_executable()

        self.cancel_requested.connect(self.cancel)

    def update_progress(self):
        """Calculates and updates the progress bar based on files and phases"""
        if self.total_files == 0:
            return

        # Calculate progress: (completed files * 6 + current file phases) / (total files * 6) * 100
        total_phases_completed = (self.current_file_index * self.total_phases) + self.current_phase
        total_phases_overall = self.total_files * self.total_phases

        progress = int((total_phases_completed / total_phases_overall) * 100)
        progress = min(progress, 100)  # Ensure it doesn't exceed 100

        self.progressbar_update.emit(progress)

        # Debug log (optional)
        self.log_update.emit(
            QCoreApplication.translate("DlWorker", "Progress: {0}% (File {1}/{2}, "
            "Phase {3}/{4})").format(progress, self.current_file_index + 1, self.total_files, self.current_phase, self.total_phases),
            'd'
        )

    def start(self):
        """Processes all NIfTI files with the Deep Learning pipeline"""

        self.total_files = len(self.input_files)
        log.debug(self.input_files)
        self.processed_files = 0
        self.failed_files = []

        # Initialize progress bar
        self.current_file_index = 0
        self.current_phase = 0
        self.update_progress()
        self.progressbar_update.emit(5)

        self.process_single_file()

    def process_single_file(self):
        """Process single file with the Deep Learning pipeline"""
        temp_dir = tempfile.mkdtemp(prefix=f"dl_processing_{self.current_file_index+1}_")
        # out_dir = os.path.join(self.workspace_path, "outputs")
        # os.makedirs(out_dir, exist_ok=True)
        self.output_dir = temp_dir

        self.current_input_file = self.input_files[self.current_file_index]
        self.current_input_file_basename = os.path.basename(self.current_input_file)

        self.log_update.emit(QCoreApplication.translate("DlWorker", "=== PROCESSING: {0} ===").format(self.current_input_file_basename), 'i')

        # PHASE 1: SynthStrip
        self.current_phase = 1
        self.run_synthstrip()

    def run_synthstrip(self):
        """Synthstrip on a single file"""
        phase = "Synthstrip"
        self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Phase 1/6: Synthstrip skull strip..."))
        self.log_update.emit(QCoreApplication.translate("DlWorker", "PHASE 1: Skull strip with Synthstrip"), 'i')

        self.log_update.emit(QCoreApplication.translate("DlWorker", "SynthStrip started: {0}").format(os.path.basename(self.current_input_file)), 'i')

        # Skull stripped file name
        base_name = self.current_input_file_basename.replace(".nii.gz", "").replace(".nii", "")
        self.current_synthstrip_file = os.path.join(self.output_dir, f"{base_name}_skull_stripped.nii.gz")

        self.synthstrip_process = QProcess()
        self.synthstrip_process.finished.connect(self.on_synthstrip_finished)
        self.synthstrip_process.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.synthstrip_process.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.synthstrip_process.readAllStandardOutput()))
        self.synthstrip_process.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.synthstrip_process.readAllStandardError()))

        if self.has_freesurfer:
            cmd = [
                "mri_synthstrip",
                "-i", self.current_input_file,
                "-o", self.current_synthstrip_file
            ]
        else:
            cmd = [
                self.nipreps_synthstrip_bin_path,
                "-i", self.current_input_file,
                "-o", self.current_synthstrip_file,
                "-g",
                "--model", self.synthstrip_model
            ]

        self.synthstrip_process.start(cmd[0], cmd[1:])

    def on_synthstrip_finished(self, exit_code, exit_status):
        if self.is_cancelled:
            return

        # This slot is called by the QProcess when it finishes
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("SynthStrip failed", f"Exit code: {exit_code}")
            if self.current_file_index + 1 < self.total_files:
                self.current_file_index += 1
                self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Segmentation failed for this file"))
                self.process_single_file()
            return

        self.log_update.emit(QCoreApplication.translate("DlWorker", "✓ Skull stripping completed"), 'i')
        self.update_progress()
        # PHASE 2: Coregistration
        self.current_phase = 2
        self.run_coregistration()  # Start the next phase

    def run_coregistration(self):
        """Performs coregistration with atlas"""
        phase = "Coregistration"

        self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Phase 2/6: Coregistration..."))
        self.log_update.emit(QCoreApplication.translate("DlWorker", "PHASE 2: Coregistration"), 'i')

        self.log_update.emit(QCoreApplication.translate("DlWorker", "Coregistration started: {0}").format(os.path.basename(self.current_input_file)), 'i')

        # Create directory for coregistration
        coreg_dir = os.path.join(self.output_dir, "coregistration")
        os.makedirs(coreg_dir, exist_ok=True)

        self.coregistration_process = QProcess()
        self.coregistration_process.finished.connect(self.on_coregistration_finished)
        self.coregistration_process.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.coregistration_process.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.coregistration_process.readAllStandardOutput()))
        self.coregistration_process.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.coregistration_process.readAllStandardError()))

        args = [
            get_script_path("deep_learning/coregistration.py"),
            "--mri", self.current_input_file,
            "--skull", self.current_synthstrip_file,
            "--atlas", self.atlas_file,
            "-o", coreg_dir
        ]

        self.coregistration_process.start(self.python_executable, args)

    def on_coregistration_finished(self, exit_code, exit_status):
        if self.is_cancelled:
            return

        # This slot is called by the QProcess when it finishes
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("Coregistration failed", f"Exit code: {exit_code}")
            if self.current_file_index + 1 < self.total_files:
                self.current_file_index += 1
                self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Segmentation failed for this file"))
                self.process_single_file()
            return

        self.log_update.emit(QCoreApplication.translate("DlWorker", "✓ Coregistration completed"), 'i')
        self.update_progress()
        # PHASE 3: Reorientation
        self.current_phase = 3
        self.run_reorientation()  # Start the next phase

    def run_reorientation(self):
        """Performs reorientation of the brain_in_atlas file using the BraTS affine matrix"""
        phase = "Reorientation"

        self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Phase 3/6: Reorientation..."))
        self.log_update.emit(QCoreApplication.translate("DlWorker", "PHASE 3: Reorientation"), 'i')

        self.log_update.emit(QCoreApplication.translate("DlWorker", "Reorientation started: {0}").format(os.path.basename(self.current_input_file)), 'i')

        coreg_dir = Path(os.path.join(self.output_dir, "coregistration"))
        brain_in_atlas_files = list(coreg_dir.glob("*.nii.gz")) + list(coreg_dir.glob("*.nii"))

        if not brain_in_atlas_files:
            self.log_update.emit(QCoreApplication.translate("DlWorker", "✗ No brain_in_atlas file found"), 'e')
            return False

        rsl_files = [f for f in brain_in_atlas_files if f.name.endswith("_rsl.nii") or f.name.endswith("_rsl.nii.gz")]

        if rsl_files:
            brain_in_atlas_file = str(rsl_files[0])
        else:
            # fallback
            brain_in_atlas_file = str(brain_in_atlas_files[0])

        self.reorientation_process = QProcess()
        self.reorientation_process.finished.connect(self.on_reorientation_finished)
        self.reorientation_process.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.reorientation_process.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.reorientation_process.readAllStandardOutput()))
        self.reorientation_process.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.reorientation_process.readAllStandardError()))

        args = [
            get_script_path("deep_learning/reorientation.py"),
            "--input", brain_in_atlas_file,
            "--output", self.output_dir + "/reoriented",
            "--brats", self.brats_file,
            "--basename", self.current_input_file_basename.replace(".nii.gz", "").replace(".nii", "")
        ]

        self.reorientation_process.start(self.python_executable, args)

    def on_reorientation_finished(self, exit_code, exit_status):
        if self.is_cancelled:
            return

        # This slot is called by the QProcess when it finishes
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("Reorientation failed", f"Exit code: {exit_code}")
            if self.current_file_index + 1 < self.total_files:
                self.current_file_index += 1
                self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Segmentation failed for this file"))
                self.process_single_file()
            return

        self.log_update.emit(QCoreApplication.translate("DlWorker", "✓ Reorientation completed"), 'i')
        self.update_progress()
        # PHASE 4: Preprocess
        self.current_phase = 4
        self.run_preprocess()  # Start the next phase

    def run_preprocess(self):
        """Runs PHASE 4: PREPARE and PREPROCESS"""
        phase = "Preprocessing"

        self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Phase 4/6: Preparing and preprocessing..."))
        self.log_update.emit(QCoreApplication.translate("DlWorker", "PHASE 4: Prepare and preprocess"), 'i')

        data_path = os.path.join(self.output_dir, "reoriented")
        results_path = os.path.join(self.output_dir, "preprocess")

        self.dl_preprocess = QProcess()
        self.dl_preprocess.finished.connect(self.on_preprocess_finished)
        self.dl_preprocess.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.dl_preprocess.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.dl_preprocess.readAllStandardOutput()))
        self.dl_preprocess.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.dl_preprocess.readAllStandardError()))

        args = [
            get_script_path("deep_learning/preprocess.py"),
            '--data', data_path,
            '--results', results_path,
            '--ohe'
        ]

        self.dl_preprocess.start(self.python_executable, args)

    def on_preprocess_finished(self, exit_code, exit_status):
        # This slot is called by the QProcess when it finishes
        if self.is_cancelled:
            return

        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("Preprocess failed", f"Exit code: {exit_code}")
            if self.current_file_index + 1 < self.total_files:
                self.current_file_index += 1
                self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Segmentation failed for this file"))
                self.process_single_file()
            return

        self.log_update.emit(QCoreApplication.translate("DlWorker", "✓ Preprocess completed"), 'i')
        self.update_progress()
        # PHASE 5: Deep learning execution
        self.current_phase = 5
        self.run_deep_learning()  # Start the next phase

    def run_deep_learning(self):
        """Runs PHASE 5: DEEP LEARNING"""
        phase = "Deep Learning execution"

        self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Phase 5/6: Deep Learning..."))
        self.log_update.emit(QCoreApplication.translate("DlWorker", "PHASE 5: Deep learning execution"), 'i')

        self.dl_process = QProcess()
        self.dl_process.finished.connect(self.on_dl_finished)
        self.dl_process.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.dl_process.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.dl_process.readAllStandardOutput()))
        self.dl_process.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.dl_process.readAllStandardError()))

        args = [
            get_script_path("deep_learning/deep_learning_runner.py"),
            '--depth', '6',
            '--filters', '64', '96', '128', '192', '256', '384', '512',
            '--min_fmap', '2',
            '--gpus', '1',
            '--amp',
            '--save_preds',
            '--exec_mode', 'predict',
            '--data', f'{self.output_dir}/preprocess/val_3d/test',
            '--ckpt_path', get_script_path('deep_learning/checkpoints/fold3/epoch=146-dice=88.05.ckpt'),
            '--tta',
            '--results', f'{self.output_dir}/dl_results'
        ]

        self.dl_process.start(self.python_executable, args)

    def on_dl_finished(self, exit_code, exit_status):
        if self.is_cancelled:
            return

        # This slot is called by the QProcess when it finishes
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("Deep learning execution failed", f"Exit code: {exit_code}")
            if self.current_file_index + 1 < self.total_files:
                self.current_file_index += 1
                self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Segmentation failed for this file"))
                self.process_single_file()
            return

        self.log_update.emit(QCoreApplication.translate("DlWorker", "✓ Deep learning execution completed"), 'i')
        self.update_progress()
        # PHASE 6: Postprocess
        self.current_phase = 6
        self.run_postprocess()  # Start the next phase

    def run_postprocess(self):
        phase = "Postprocessing"

        self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Phase 6/6: Postprocessing..."))
        self.log_update.emit(QCoreApplication.translate("DlWorker", "PHASE 6: Postprocess"), 'i')

        self.dl_postprocess = QProcess()
        self.dl_postprocess.finished.connect(self.on_postprocess_finished)
        self.dl_postprocess.errorOccurred.connect(lambda error, string=phase: self.on_error(string, error))
        self.dl_postprocess.readyReadStandardOutput.connect(lambda string=phase: self.on_stdout(string, self.dl_postprocess.readAllStandardOutput()))
        self.dl_postprocess.readyReadStandardError.connect(lambda string=phase: self.on_stderr(string, self.dl_postprocess.readAllStandardError()))

        args = [
            get_script_path("deep_learning/postprocess.py"),
            '-i', f'{self.output_dir}/dl_results/predictions_epoch=146-dice=88_05_task=train_fold=0_tta',
            '-o', f'{self.output_dir}/dl_postprocess',
            '--w', f'{self.workspace_path}',
            '--atlas', self.atlas_file,
            "--brats", self.brats_file,
            '--mri', f'{self.current_input_file}'
        ]

        self.dl_postprocess.start(self.python_executable, args)

    def on_postprocess_finished(self, exit_code, exit_status):
        if self.is_cancelled:
            return

        # This slot is called by the QProcess when it finishes
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self.log_update.emit("Postprocess failed", f"Exit code: {exit_code}")
            if self.current_file_index + 1 < self.total_files:
                self.current_file_index += 1
                self.file_update.emit(self.current_input_file_basename, QCoreApplication.translate("DlWorker", "Segmentation failed for this file"))
                self.process_single_file()
            return

        self.log_update.emit(QCoreApplication.translate("DlWorker", "✓ Postprocess completed"), 'i')
        self.file_update.emit(self.current_input_file_basename,
                              QCoreApplication.translate("DlWorker", "Segmentation completed"))
        self.update_progress()

        if self.current_file_index + 1 < self.total_files:
            self.current_file_index += 1
            self.process_single_file()
        else:
            self.finished.emit(True, QCoreApplication.translate("DlWorker", "Processing completed"))
        return

    def cancel(self):
        self.is_cancelled = True
        self.log_update.emit(QCoreApplication.translate("DlWorker", "Cancellation requested - stopping all processes..."), 'w')

        processes = {
            'SynthStrip': self.synthstrip_process,
            'Coregistration': self.coregistration_process,
            'Reorientation': self.reorientation_process,
            'Preprocess': self.dl_preprocess,
            'Deep Learning': self.dl_process,
            'Postprocess': self.dl_postprocess
        }

        for name, process in processes.items():
            if process is not None and process.state() != QProcess.ProcessState.NotRunning:
                self.log_update.emit(QCoreApplication.translate("DlWorker", "Stopping {name}...").format(name=name), 'w')

                # No need to disconnect signals manually!
                process.terminate()

                # only kill if it doesn't respond after a timeout
                if not process.waitForFinished(2000):
                    self.log_update.emit(QCoreApplication.translate("DlWorker", "Forcing {name} to quit...").format(name=name), 'e')
                    process.kill()
                    process.waitForFinished(1000)

        self.finished.emit(False, QCoreApplication.translate("DlWorker", "Processing cancelled by user"))

    def on_stdout(self, phase, data):
        """Correct handler for QProcess stdout"""
        try:
            # Correctly decode data from QByteArray
            text = data.data().decode("utf-8", errors='replace').strip()
            if text:
                # Split by lines and log each one
                for line in text.splitlines():
                    if line.strip():  # Avoid empty lines
                        self.log_update.emit(f"[{phase}] {line.strip()}", 'i')
        except Exception as e:
            self.log_update.emit(f"[{phase}] Error decoding stdout: {str(e)}", 'e')

    def on_stderr(self, phase, data):
        """Correct handler for QProcess stderr"""
        try:
            # Correctly decode data from QByteArray
            text = data.data().decode("utf-8", errors='replace').strip()
            if text:
                # Split by lines and log each one
                for line in text.splitlines():
                    if line.strip():  # Avoid empty lines
                        self.log_update.emit(f"[{phase}] {line.strip()}", 'e')
        except Exception as e:
            self.log_update.emit(f"[{phase}] Error decoding stderr: {str(e)}", 'e')

    def on_error(self, phase, error):
        """Handler for QProcess errors"""
        try:
            error_messages = {
                QProcess.ProcessError.FailedToStart: QCoreApplication.translate("DlWorker", "Failed to start process"),
                QProcess.ProcessError.Crashed: QCoreApplication.translate("DlWorker", "Process crashed"),
                QProcess.ProcessError.Timedout: QCoreApplication.translate("DlWorker", "Process timed out"),
                QProcess.ProcessError.WriteError: QCoreApplication.translate("DlWorker", "Write error"),
                QProcess.ProcessError.ReadError: QCoreApplication.translate("DlWorker", "Read error"),
                QProcess.ProcessError.UnknownError: QCoreApplication.translate("DlWorker", "Unknown error")
            }

            error_msg = error_messages.get(error, QCoreApplication.translate("DlWorker", "Unknown error code: {error}").format(error=error))
            self.log_update.emit(f"[{phase}] Process error: {error_msg}", 'e')

        except Exception as e:
            self.log_update.emit(f"[{phase}] Error in error handler: {str(e)}", 'e')