"""
import_thread.py - ImportThread (part 1/4)

This module contains ImportThread, a QThread subclass responsible for importing
medical imaging datasets into the application's workspace. It supports:
 - Copying already-BIDS-organized folders
 - Converting DICOM series to NIfTI using dcm2niix
 - Aggregating NIfTI/JSON pairs into a BIDS-like structure
 - Heuristics for detecting whether a folder represents one subject or multiple

This file is presented in parts. Part 1 contains:
 - imports
 - ImportThread class definition (signals)
 - __init__ and run() (main orchestration and top-level flow)
"""

import os
import shutil
import subprocess
import tempfile

import pydicom

from PyQt6.QtCore import QThread, pyqtSignal, QCoreApplication

from logger import get_logger
from utils import get_bin_path

log = get_logger()


class ImportThread(QThread):
    """
    Worker thread that imports one or more folders into the application's workspace.

    The thread emits:
      - finished(): when the import completes successfully
      - error(str): in case of an exception
      - progress(int): progress updates (0-100)

    The thread is cancellable via the `cancel()` method which sets an internal
    flag and attempts to terminate any running external process (dcm2niix).
    """

    # Signal emitted when an operation completes successfully
    finished = pyqtSignal()
    """**Signal():** Emitted when the operation finishes successfully and no further progress updates will occur."""

    # Signal emitted when an error occurs during processing
    error = pyqtSignal(str)
    """**Signal(str):** Emitted when an error occurs.  
    Parameter:
    - `str`: Description or message of the encountered error.
    """

    # Signal emitted to report progress updates
    progress = pyqtSignal(int)
    """**Signal(int):** Emitted periodically to indicate task progress.  
    Parameter:
    - `int`: Current progress percentage (0–100).
    """

    def __init__(self, context, folders_path, workspace_path):
        """
        Initialize the import thread.

        Args:
            context (dict): application context (used for callbacks / GUI updates).
            folders_path (list[str]): list of input paths (files or folders) to import.
            workspace_path (str): path to the target workspace directory.
        """
        super().__init__()
        self.context = context
        # allow either single path or list of paths; stored as list to keep API stable
        self.folders_path = folders_path
        self.workspace_path = workspace_path

        # internal state for progress and cancellation
        self.current_progress = 0
        self._is_canceled = False

        # reference to subprocess.Popen used during DICOM conversion (so we can terminate it)
        self.process = None


    def run(self):
        """
        Main thread entry point.

        This method orchestrates the following high-level behaviors:
          - If a single folder is provided:
              * Detect BIDS folder and copy directly
              * Else detect whether folder contains multiple patient subfolders or
                a single subject split across many DICOM series
              * Convert found DICOM series to NIfTI using dcm2niix in a temporary
                directory, then convert NIfTI + JSON to a BIDS-like structure inside
                the workspace.
          - If multiple folders are provided:
              * Process each folder independently with `_handle_import`.
        Progress is emitted periodically. Exceptions are forwarded via the
        `error` signal.
        """
        try:
            # initial small progress step
            self.current_progress = 10
            self.progress.emit(self.current_progress)

            # Validate input list length and branch accordingly
            if len(self.folders_path) == 1:
                # single path handling
                folder_path = self.folders_path[0]

                # Basic validation
                if not os.path.isdir(folder_path):
                    raise Exception(QCoreApplication.translate("Threads", "Invalid folders path"))

                # Case A: already a BIDS subject folder -> copy directly
                if self._is_bids_folder(folder_path):
                    log.debug(f"BIDS structure detected in: {folder_path}")

                    if self._is_canceled:
                        return
                    self.current_progress = 50
                    self.progress.emit(self.current_progress)

                    # choose next sub-id (e.g. sub-03) and copy tree
                    new_sub_id = self._get_next_sub_id()
                    dest = os.path.join(self.workspace_path, new_sub_id)
                    shutil.copytree(folder_path, dest, dirs_exist_ok=True)

                    if self._is_canceled:
                        return
                    self.current_progress = 100
                    self.progress.emit(self.current_progress)

                    log.debug(f"BIDS folder copied as {new_sub_id}.")
                    self.finished.emit()
                    return

                # Case B: folder contains only subfolders (possible multi-patient)
                subfolders = [
                    os.path.join(folder_path, d)
                    for d in os.listdir(folder_path)
                    if os.path.isdir(os.path.join(folder_path, d))
                ]

                # If directory contains just subfolders and no direct nifti/dicom files, decide:
                # - If subfolders belong to a single subject (multiple series in separate folders),
                #   treat whole folder as one subject.
                if subfolders and not any(
                        self._is_nifti_file(f) or self._is_dicom_file(os.path.join(folder_path, f))
                        for f in os.listdir(folder_path)
                ):

                    # If subfolders are multiple DICOM series belonging to the same patient,
                    # process entire root as a single patient (e.g., MR + PET series in different
                    # DICOM folder exports).
                    if self._subfolders_belong_to_single_subject(subfolders):
                        log.debug(f"Single subject spread across {len(subfolders)} DICOM folders in: {folder_path}")

                        # Process the root folder as single subject
                        self._process_single_patient_folder(folder_path)
                        if self._is_canceled:
                            return
                        self.progress.emit(100)
                        self.finished.emit()
                        return

                    # Otherwise treat each subfolder as separate patient and import them
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

                # Case C: folder may contain files (NIfTI, DICOM, misc) -> collect and convert
                nifti_files = []
                dicom_files = []

                base_folder_name = os.path.basename(os.path.normpath(folder_path))

                # create temporary directory for conversion and intermediate files
                temp_dir = tempfile.mkdtemp()
                temp_base_dir = os.path.join(temp_dir, base_folder_name)

                # Walk the folder, copy non-medical files into the temp tree and list nifti/dicom
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        if self._is_canceled:
                            # cleanup and exit early when cancelled
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            return
                        file_path = os.path.join(root, file)

                        # Keep folder structure inside temp_base_dir
                        relative_path = os.path.relpath(root, folder_path)
                        dest_dir = os.path.join(temp_base_dir, relative_path)
                        os.makedirs(dest_dir, exist_ok=True)

                        if self._is_nifti_file(file):
                            # record source and destination pair for later copy
                            nifti_files.append((file_path, os.path.join(dest_dir, file)))
                        elif self._is_dicom_file(file_path):
                            # record dicom file for conversion
                            dicom_files.append(file_path)
                        else:
                            # other files (sidecars, metadata, reports) are copied directly
                            shutil.copy2(file_path, os.path.join(dest_dir, file))
                            log.debug(f"Imported other file: {os.path.join(relative_path, file)}")

                # Update progress after scan
                self.current_progress = 20
                self.progress.emit(self.current_progress)

                # Copy any found NIfTI files into temp structure and update progress incrementally
                nifti_num = len(nifti_files)
                if nifti_num > 0:
                    progress_per_nifti = int(40 / nifti_num)
                    for src, dest in nifti_files:
                        if self._is_canceled:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            return
                        shutil.copy2(src, dest)
                        self.current_progress += progress_per_nifti
                        self.progress.emit(self.current_progress)
                        log.debug(f"Imported NIfTI file: {os.path.relpath(dest, temp_base_dir)}")

                # Midpoint progress
                self.current_progress = 60
                self.progress.emit(self.current_progress)

                if self._is_canceled:
                    return

                # If DICOM files were found, convert the original folder to NIfTI into the temp tree
                if dicom_files:
                    self._convert_dicom_folder_to_nifti(folder_path, temp_base_dir)

                # small progress bump
                self.current_progress += 10
                self.progress.emit(self.current_progress)

                # Now transform the temp folder into a BIDS-like structure under workspace
                self._convert_to_bids_structure(temp_base_dir)

                # Cleanup temporary directory after conversion/copy
                shutil.rmtree(temp_dir, ignore_errors=True)

            elif len(self.folders_path) == 0:
                # empty input - emit an error
                raise Exception(QCoreApplication.translate("Threads", "Invalid folders path"))
            elif len(self.folders_path) > 1:
                # multiple root paths - handle each independently
                progress_for_folder = int(90 / len(self.folders_path))
                for path in self.folders_path:
                    if self._is_canceled:
                        return
                    self._handle_import(path)
                    self.current_progress += progress_for_folder
                    self.progress.emit(self.current_progress)
            else:
                # fallback guard - shouldn't be reached
                raise Exception(QCoreApplication.translate("Threads", "Invalid folders path"))

            # Finalize progress and signal completion
            self.current_progress = 100
            self.progress.emit(self.current_progress)
            self.finished.emit()

        except Exception as e:
            # If cancellation was requested we avoid emitting an error
            if self._is_canceled:
                log.info("Import interrupted by user, no error emitted.")
                return
            # Otherwise, emit error and log it
            self.error.emit(str(e))
            log.error(f"Error: {str(e)}")


    def _handle_import(self, folder_path):
        """
        Handle the import of a single folder (which may itself contain subfolders).

        This method performs heuristics to determine what kind of folder we are dealing with:
          1. A BIDS folder — copy it directly.
          2. A folder with direct medical files (NIfTI or DICOM) — process as one patient.
          3. A folder containing subfolders — analyze if they belong to one or more patients.
             - If subfolders are DICOM series of the same patient, process as one.
             - If subfolders look like different patients (e.g., named 'sub-01', 'patient_02'), process each separately.
             - Otherwise, default to single-patient mode.

        Args:
            folder_path (str): Path to the folder to process.
        """
        if not os.path.isdir(folder_path):
            return
        if self._is_canceled:
            return

        log.debug(f"Processing folder: {folder_path}")

        # Case 1: The folder is already BIDS-organized -> just copy
        if self._is_bids_folder(folder_path):
            log.debug(f"BIDS structure detected in: {folder_path}")
            new_sub_id = self._get_next_sub_id()
            dest = os.path.join(self.workspace_path, new_sub_id)
            shutil.copytree(folder_path, dest, dirs_exist_ok=True)
            log.debug(f"BIDS folder copied as {new_sub_id}.")
            return

        # Case 2: Does the folder directly contain DICOM/NIfTI files (no subfolders)?
        has_direct_medical_files = False
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                if self._is_nifti_file(file) or self._is_dicom_file(file_path):
                    has_direct_medical_files = True
                    break

        if self._is_canceled:
            return

        # If true, treat this as a single-patient folder
        if has_direct_medical_files:
            log.debug(f"Direct medical files found, processing as single patient: {folder_path}")
            self._process_single_patient_folder(folder_path)
            return

        if self._is_canceled:
            return

        # Case 3: Folder has subdirectories — check what they represent
        subfolders = [
            os.path.join(folder_path, d)
            for d in os.listdir(folder_path)
            if os.path.isdir(os.path.join(folder_path, d))
        ]
        if not subfolders:
            log.debug(f"No subfolders found in: {folder_path}")
            return
        if self._is_canceled:
            return

        # Check if all subfolders are DICOM series of the same patient
        if self._are_dicom_series_of_same_patient(subfolders):
            log.debug(f"DICOM series of same patient detected: {folder_path}")
            self._process_single_patient_folder(folder_path)
            return

        if self._is_canceled:
            return

        # If subfolder names suggest multiple patients (e.g., 'sub-01', 'patient2'), process separately
        if self._subfolders_look_like_different_patients(subfolders):
            log.debug(f"Multiple patients detected by folder names: {folder_path}")
            for subfolder in subfolders:
                self._handle_import(subfolder)
            return

        if self._is_canceled:
            return

        # Fallback — treat as single-patient data
        log.debug(f"Default: treating as single patient: {folder_path}")
        self._process_single_patient_folder(folder_path)


    def _are_dicom_series_of_same_patient(self, subfolders):
        """
        Check if multiple subfolders represent DICOM series from the same patient.

        Heuristics:
          - For each subfolder containing DICOM files, extract the PatientID or PatientName.
          - If only one unique ID or name is found among all, we assume it's the same patient.

        Args:
            subfolders (list[str]): List of subfolder paths to inspect.

        Returns:
            bool: True if the subfolders seem to belong to the same patient.
        """
        log.debug(f"Checking if {len(subfolders)} subfolders are DICOM series of same patient...")

        patient_ids = set()
        dicom_folders_count = 0

        for subfolder in subfolders:
            log.debug(f"  Checking subfolder: {os.path.basename(subfolder)}")

            has_dicom_in_subfolder = False
            first_dicom_file = None

            # Look for at least one DICOM file to sample metadata
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

                try:
                    # Read DICOM metadata
                    dcm = pydicom.dcmread(first_dicom_file, stop_before_pixels=True)
                    patient_id = getattr(dcm, 'PatientID', None)
                    patient_name = getattr(dcm, 'PatientName', None)
                    masked_patient_name = f"{patient_name[:2]}...{patient_name[-2:]}" if patient_name else "unknown"

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

        # Criteria: at least one DICOM folder, and at most one unique PatientID
        is_same_patient = dicom_folders_count > 0 and len(patient_ids) <= 1
        log.debug(f"  Result: is_same_patient = {is_same_patient}")

        return is_same_patient


    def _subfolders_look_like_different_patients(self, subfolders):
        """
        Heuristic that checks if subfolder names suggest multiple patients.

        Example folder names that trigger 'multi-patient' assumption:
            sub-01/, patient_1/, subj3/, p_01/, subject_2/

        Args:
            subfolders (list[str]): List of subfolder paths.

        Returns:
            bool: True if subfolder names suggest multiple subjects.
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
        Process a folder assumed to contain data for a single patient.

        This includes:
          - Copying NIfTI files directly
          - Converting DICOM series to NIfTI
          - Organizing results into a BIDS-like folder structure
          - Cleaning up temporary directories

        Args:
            folder_path (str): Path to the patient's folder.
        """
        if self._is_canceled:
            return

        log.debug(f"Processing single patient folder: {folder_path}")

        nifti_files = []
        dicom_files = []

        base_folder_name = os.path.basename(os.path.normpath(folder_path))

        # Temporary directory for conversion steps
        temp_dir = tempfile.mkdtemp()
        temp_base_dir = os.path.join(temp_dir, base_folder_name)

        # Walk through the folder and collect relevant files
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

        # Copy NIfTI files to the temp structure
        for src, dest in nifti_files:
            if self._is_canceled:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return
            shutil.copy2(src, dest)
            log.debug(f"Imported NIfTI file: {os.path.relpath(dest, temp_base_dir)}")

        # If DICOMs exist, convert them into NIfTI using dcm2niix
        if dicom_files:
            log.debug(f"Converting {len(dicom_files)} DICOM files to NIfTI...")
            self._convert_dicom_folder_to_nifti(folder_path, temp_base_dir)

        if self._is_canceled:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return

        # Convert the temporary NIfTI/JSON folder into a BIDS structure
        log.debug(f"Converting to BIDS structure...")
        self._convert_to_bids_structure(temp_base_dir)

        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Optionally update UI buttons if context provides callback
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()
        log.debug("Import completed for single patient.")

    def _convert_dicom_folder_to_nifti(self, src_folder, dest_folder):
        """
        Converts a DICOM folder into NIfTI format using the external tool `dcm2niix`.

        This function is executed for each single-patient folder that contains DICOM files.
        It runs `dcm2niix` in a subprocess and places the resulting NIfTI and JSON metadata files
        in the destination folder.

        Args:
            src_folder (str): The source folder containing DICOM files.
            dest_folder (str): The folder where NIfTI files should be saved.
        """
        if self._is_canceled:
            return

        try:
            dcm2niix_path = get_bin_path("dcm2niix")
        except FileNotFoundError as e:
            log.error(f"Cannot find dcm2niix executable: {e}")
            return

        log.debug(f"Running dcm2niix on {src_folder} → {dest_folder}")
        cmd = [dcm2niix_path, "-z", "y", "-o", dest_folder, src_folder]

        try:
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            log.debug(f"dcm2niix output:\n{process.stdout}")
        except subprocess.CalledProcessError as e:
            log.error(f"dcm2niix failed: {e.stderr}")
        except Exception as e:
            log.error(f"Unexpected error during DICOM conversion: {e}")

        if self._is_canceled:
            return

        log.debug("DICOM to NIfTI conversion completed.")


    def _convert_to_bids_structure(self, source_folder):
        """
        Converts a folder containing NIfTI and JSON files into a BIDS-like directory structure.

        The function scans all NIfTI files in the given folder and organizes them under:
          derivatives/
            └── deep_learning_seg/
                └── sub-XXX/
                    └── anat/

        Each new import increments the patient ID number (`sub-001`, `sub-002`, ...).

        Args:
            source_folder (str): Path to the folder containing NIfTI/JSON files to reorganize.
        """
        if self._is_canceled:
            return

        new_sub_id = self._get_next_sub_id()
        subject_folder = os.path.join(self.workspace_path, new_sub_id, "anat")
        os.makedirs(subject_folder, exist_ok=True)

        log.debug(f"Creating BIDS-like structure for {new_sub_id} at {subject_folder}")

        for root, _, files in os.walk(source_folder):
            for file in files:
                src = os.path.join(root, file)
                if file.endswith((".nii", ".nii.gz", ".json")):
                    dest = os.path.join(subject_folder, file)
                    shutil.copy2(src, dest)
                    log.debug(f"Copied {file} → {dest}")

        log.debug(f"BIDS conversion complete for {new_sub_id}.")


    def _is_bids_folder(self, folder_path):
        """
        Detects whether a folder already follows a BIDS structure.

        Heuristic check:
          - Folder contains 'sub-' directories.
          - Inside those, there are 'anat', 'func', or 'dwi' subdirectories with NIfTI files.

        Args:
            folder_path (str): Path to check.

        Returns:
            bool: True if the folder appears to be BIDS-compatible.
        """
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isdir(item_path) and item.startswith("sub-"):
                for subfolder in ["anat", "func", "dwi"]:
                    anat_path = os.path.join(item_path, subfolder)
                    if os.path.isdir(anat_path):
                        for f in os.listdir(anat_path):
                            if f.endswith((".nii", ".nii.gz")):
                                log.debug(f"BIDS-like folder detected: {anat_path}")
                                return True
        return False


    def _get_next_sub_id(self):
        """
        Generates the next available subject ID for the BIDS dataset.

        It scans existing subfolders in the workspace for names like `sub-001`, `sub-002`, ...
        and returns the next number in sequence.

        Returns:
            str: The next subject ID, e.g. 'sub-004'.
        """
        existing_subs = []
        for name in os.listdir(self.workspace_path):
            if name.startswith("sub-"):
                try:
                    num = int(name.split("-")[1])
                    existing_subs.append(num)
                except (IndexError, ValueError):
                    continue

        next_id = max(existing_subs, default=0) + 1
        sub_name = f"sub-{next_id:03d}"
        log.debug(f"Next subject ID assigned: {sub_name}")
        return sub_name


    def _is_dicom_file(self, file_path):
        """
        Check whether a file is a DICOM file by reading its magic bytes.

        DICOM files contain the ASCII string "DICM" at byte offset 128.

        Args:
            file_path (str): Path to the file to check.

        Returns:
            bool: True if the file appears to be a valid DICOM file.
        """
        try:
            with open(file_path, "rb") as f:
                f.seek(128)
                magic = f.read(4)
                return magic == b"DICM"
        except Exception:
            return False


    def _is_nifti_file(self, filename):
        """
        Check whether a filename indicates a NIfTI file.

        Args:
            filename (str): File name to test.

        Returns:
            bool: True if the file ends with '.nii' or '.nii.gz'.
        """
        return filename.endswith((".nii", ".nii.gz"))

    def cancel(self):
        """
        Gracefully cancels the ongoing import process.

        This method sets the internal `_is_canceled` flag to True,
        terminates any active subprocess (like `dcm2niix`), and logs the cancellation.

        It’s thread-safe — typically called from the GUI (e.g., a 'Cancel' button)
        while the import thread is still running.
        """
        self._is_canceled = True

        # If there's an external process running (e.g., DICOM conversion), terminate it
        if hasattr(self, "process") and self.process is not None:
            try:
                log.debug("Attempting to terminate running process...")
                self.process.terminate()
                self.process.wait(timeout=1)  # Wait briefly for clean shutdown
                self.process.kill()  # Force kill if still alive
                log.debug("External process terminated successfully.")
            except Exception as e:
                log.warning(f"Failed to terminate subprocess cleanly: {e}")

        log.info("Import process canceled by user.")


    def _cleanup_temp_dir(self, temp_dir):
        """
        Safely deletes a temporary directory, ignoring common errors.

        Args:
            temp_dir (str): Path to the temporary directory.
        """
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            log.debug(f"Temporary directory removed: {temp_dir}")
        except Exception as e:
            log.warning(f"Failed to remove temp directory {temp_dir}: {e}")


    def _emit_error(self, message):
        """
        Emits an error signal with a human-readable message
        and logs it to the application logger.

        Args:
            message (str): The error message to show.
        """
        log.error(message)
        self.error.emit(message)


    def _emit_progress(self, step):
        """
        Utility to update the progress bar safely from within the thread.

        Args:
            step (int): The progress value (0–100).
        """
        self.current_progress = step
        self.progress.emit(self.current_progress)
        log.debug(f"Progress updated: {self.current_progress}%")
