import os
import json
import shutil
import tempfile

from PyQt6.QtCore import pyqtSignal, QThread, QProcess, QCoreApplication
from logger import get_logger
from utils import setup_fsl_env, get_bin_path

log = get_logger()


class SkullStripThread(QThread):
    """
    Background worker thread for performing skull-stripping operations on NIfTI files.

    This thread executes either **FSL BET** or **HD-BET** commands in the background using
    a `QProcess`, preventing the GUI from freezing during long-running neuroimaging operations.

    It supports batch processing of multiple files, progress reporting, cancellation, and
    automatic generation of BIDS-like JSON sidecar metadata.

    ---
    **Signals**
    - `progress_updated (str)`: Emits a human-readable progress message.
    - `progress_value_updated (int)`: Emits a numeric progress percentage.
    - `file_started (str)`: Emitted when processing of a specific file begins.
    - `file_completed (str, bool, str)`: Emitted when a file finishes (filename, success flag, message).
    - `all_completed (int, list)`: Emitted after all files are processed (success count, list of failed files).

    ---

    **Parameters**
    - `files (list[str])`: List of NIfTI file paths to process.
    - `workspace_path (str)`: Root directory of the workspace, containing derivatives.
    - `parameters (dict)`: Dictionary of BET/HD-BET options (e.g., `f_val`, `opt_m`, `opt_t`).
    - `has_cuda (bool)`: Whether CUDA GPU acceleration is available (for HD-BET).
    - `has_bet (bool)`: Whether to use FSL BET instead of HD-BET.
    """

    # Signal emitted when a progress message is updated.
    progress_updated = pyqtSignal(str)
    """**Signal(str):** Emitted when the progress message text changes."""

    # Signal emitted when the progress bar value changes.
    progress_value_updated = pyqtSignal(int)
    """**Signal(int):** Emitted when the progress value is updated."""

    # Signal emitted when processing of an individual file starts.
    file_started = pyqtSignal(str)
    """**Signal(str):** Emitted when processing of a file begins. The parameter is the file path or name."""

    # Signal emitted when processing of an individual file completes.
    file_completed = pyqtSignal(str, bool, str)
    """**Signal(str, bool, str):** Emitted when a file has finished processing.
    The parameters are: file path/name, success status (True if completed successfully), and an optional message or error description.
    """

    # Signal emitted when all files have completed processing.
    all_completed = pyqtSignal(int, list)
    """**Signal(int, list):** Emitted when all files are processed.
    The parameters are: the total number of processed files and a list of results or statuses.
    """

    def __init__(self, files, workspace_path, parameters, has_cuda, bet_tool):
        super().__init__()
        self.files = files
        self.workspace_path = workspace_path
        self.parameters = parameters
        self.has_cuda = has_cuda

        self.bet_tool = bet_tool if bet_tool in ["fsl-bet","synthstrip","hd-bet"] else None
        self.is_cancelled = False
        self.success_count = 0
        self.failed_files = []

    def cancel(self):
        """
        Cancels the ongoing operation.

        If a subprocess (`QProcess`) is currently running, it is terminated and killed.
        This allows for safe interruption of long-running skull-stripping commands.
        """
        self.is_cancelled = True

        if hasattr(self, "process") and self.process is not None:
            try:
                self.process.terminate()
                self.process.kill()
            except Exception as e:
                log.error(f"Error while cancelling process: {e}")

    def run(self):
        """
        Executes the skull-stripping process for all input files.

        For each file:
        1. Emits a `file_started` signal.
        2. Determines subject ID from the file path.
        3. Chooses between **BET** or **HD-BET** and builds the command.
        4. Runs the command asynchronously using `QProcess`.
        5. Writes the stripped output and corresponding JSON metadata.
        6. Emits `file_completed` for each processed file.

        At the end, emits `all_completed` with a summary of successful and failed files.
        """

        if not self.files:
            log.warning("Nessun file da processare (lista vuota).")
            self.progress_value_updated.emit(100)
            self.progress_updated.emit(
                QCoreApplication.translate("Threads", "No files to process.")
            )
            self.all_completed.emit(0, [])
            return

        base_progress = 10
        progress_per_file = int(90 / len(self.files))

        for i, nifti_file in enumerate(self.files):
            if self.is_cancelled:
                break

            filename = os.path.basename(nifti_file)
            self.file_started.emit(filename)

            base_progress = int(base_progress + i * progress_per_file)
            self.progress_value_updated.emit(base_progress)
            self.progress_updated.emit(
                QCoreApplication.translate(
                    "Threads",
                    "Processing {0} ({1}/{2})"
                ).format(filename, i + 1, len(self.files))
            )

            try:
                nifti_file = os.path.normpath(nifti_file)
                self.workspace_path = os.path.normpath(self.workspace_path)

                # Extract subject ID from BIDS-like file path
                path_parts = nifti_file.replace(self.workspace_path, '').strip(os.sep).split(os.sep)
                subject_id = next((p for p in path_parts if p.startswith("sub-")), None)
                if not subject_id:
                    self.file_completed.emit(
                        filename,
                        False,
                        QCoreApplication.translate("Threads", "Cannot extract subject ID")
                    )
                    self.failed_files.append(nifti_file)
                    continue

                # Define output directory for this subject
                output_dir = os.path.join(
                    self.workspace_path,
                    'derivatives',
                    'skullstrips',
                    subject_id,
                    'anat'
                )
                os.makedirs(output_dir, exist_ok=True)

                base_name = filename.replace('.nii.gz', '').replace('.nii', '')

                # Create an isolated temporary working directory
                temp_dir = tempfile.mkdtemp(prefix="skullstrip_")

                # Build the appropriate command (BET or HD-BET)
                if self.bet_tool == "fsl-bet":
                    # Configure FSL environment variables
                    os.environ["FSLDIR"], os.environ["FSLOUTPUTTYPE"] = setup_fsl_env()
                    f_val = self.parameters.get('f_val', 0.5)
                    f_str = f"f{str(f_val).replace('.', '')}"

                    temp_output = os.path.join(temp_dir, f"{base_name}_{f_str}_brain.nii.gz")
                    final_output = os.path.join(output_dir, f"{base_name}_{f_str}_brain.nii.gz")

                    cmd = ["bet", nifti_file, temp_output, "-f", str(f_val)]

                    # Optional BET parameters
                    for opt in ['opt_m', 'opt_t', 'opt_s', 'opt_o']:
                        if self.parameters.get(opt, False):
                            cmd.append(f"-{opt[-1]}")

                    # Optional center coordinates
                    for coord in ['c_x', 'c_y', 'c_z']:
                        val = self.parameters.get(coord, 0)
                        if val != 0:
                            cmd += ["-c", str(val)]

                    # Exclude brain extraction mask if requested
                    if not self.parameters.get('opt_brain_extracted', True):
                        cmd.append("-n")

                    method = "FSL BET"

                else:
                    temp_output = os.path.join(temp_dir, f"{base_name}_{self.bet_tool}_brain.nii.gz")
                    final_output = os.path.join(output_dir, f"{base_name}_{self.bet_tool}_brain.nii.gz")
                    if self.bet_tool == "synthstrip":

                        cmd = [get_bin_path("mri_synthstrip"), "-i", nifti_file, "-o", temp_output]

                        method = "SynthStrip"

                    elif self.bet_tool == "hd-bet":

                        cmd = [get_bin_path("hd-bet"), "-i", nifti_file, "-o", temp_output]

                        # Disable CUDA if unavailable
                        if not self.has_cuda:
                            cmd += ["-device", "cpu", "--disable_tta"]

                        method = "HD-BET"

                    else:
                        log.error("Bet tool not recognized.")
                        return

                # Run skull-stripping command
                self.process = QProcess()
                self.process.start(cmd[0], cmd[1:])

                # Wait for process completion, checking for cancellation
                while not self.process.waitForFinished(-1):
                    if self.is_cancelled:
                        self.process.kill()
                        self.process.waitForFinished()
                        break

                # Handle cancellation mid-run
                if self.is_cancelled:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    break

                # Retrieve exit information and logs
                ret_code = self.process.exitCode()
                stderr = bytes(self.process.readAllStandardError()).decode()
                stdout = bytes(self.process.readAllStandardOutput()).decode()

                # Handle process errors
                if ret_code != 0:
                    self.file_completed.emit(
                        filename,
                        False,
                        stderr or QCoreApplication.translate("Threads", "Error executing command")
                    )
                    self.failed_files.append(nifti_file)
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    continue

                # Move temporary output to final destination
                shutil.move(temp_output, final_output)
                shutil.rmtree(temp_dir, ignore_errors=True)

                # Create BIDS-like JSON metadata
                json_file = final_output.replace(".nii.gz", ".json")
                metadata = {
                    "SkullStripped": True,
                    "Description": "Skull-stripped brain image",
                    "Sources": [filename],
                    "SkullStrippingMethod": method
                }

                with open(json_file, 'w') as f:
                    json.dump(metadata, f, indent=2)

                # Success count and signal
                self.success_count += 1
                self.file_completed.emit(filename, True, "")

            except Exception as e:
                # Catch all exceptions per file
                self.file_completed.emit(filename, False, str(e))
                self.failed_files.append(nifti_file)
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

        # Emit final summary signal
        self.all_completed.emit(self.success_count, self.failed_files)
