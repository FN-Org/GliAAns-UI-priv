import os
import json
import re
import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QHBoxLayout, QScrollArea, QGridLayout,
    QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QProcess, QCoreApplication

from components.circular_progress_bar import CircularProgress
from components.folder_card import FolderCard
from utils import get_bin_path
from page import Page
from logger import get_logger

log = get_logger()


class PipelineExecutionPage(Page):
    """
    GUI page that manages the **execution of a processing pipeline**.

    This class runs an external pipeline process, tracks its progress,
    captures log output in real time, and provides user controls
    (e.g., stop execution, monitor folders, show progress).

    It extends :class:`Page` and is typically part of a multi-page
    PyQt-based GUI workflow.
    """

    # ─────────────────────────────────────────────
    # INITIALIZATION
    # ─────────────────────────────────────────────
    def __init__(self, context=None, previous_page=None):
        """
        Initialize the pipeline execution page.

        Args:
            context (dict): Application context (e.g., workspace path, signals).
            previous_page (Page): Reference to the previous page in the workflow.
        """
        super().__init__()
        self.context = context
        self.workspace_path = context["workspace_path"]
        self.previous_page = previous_page
        self.next_page = None

        # Pipeline state
        self.pipeline_process = None
        self.pipeline_completed = False
        self.pipeline_error = None

        # Load the most recent pipeline configuration file
        self.config_path = self._find_latest_config()

        # Extract pipeline ID and output directory
        config_filename = os.path.basename(self.config_path)
        try:
            config_id = config_filename.split('_')[0]
            self.pipeline_output_dir = os.path.join(
                self.workspace_path, "pipeline", f"{config_id}_output"
            )
            os.makedirs(self.pipeline_output_dir, exist_ok=True)
        except (IndexError, ValueError):
            log.debug("Failed to create pipeline_output_dir")
            self.pipeline_output_dir = os.path.join(self.workspace_path, "pipeline")

        # Resolve path to pipeline executable
        try:
            self.pipeline_bin_path = get_bin_path("pipeline_runner")
        except FileNotFoundError:
            log.error("Pipeline runner binary not found")
            raise RuntimeError("Pipeline runner executable missing.")

        log.debug(f"Pipeline binary path: {self.pipeline_bin_path}")

        self.folder_cards = {}

        # Build UI
        self._setup_ui()
        self._translate_ui()

        # Connect translation handler if needed
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    # ─────────────────────────────────────────────
    # CONFIGURATION FILE HANDLING
    # ─────────────────────────────────────────────
    def _find_latest_config(self):
        """Find the config file with the highest numeric ID in the pipeline directory."""
        import glob
        pipeline_dir = os.path.join(self.workspace_path, "pipeline")

        if not os.path.exists(pipeline_dir):
            return os.path.join(pipeline_dir, "pipeline_config.json")

        config_pattern = os.path.join(pipeline_dir, "*_config.json")
        config_files = glob.glob(config_pattern)

        if not config_files:
            return os.path.join(pipeline_dir, "pipeline_config.json")

        max_id = 0
        latest_config = None

        # Parse filenames to detect the latest config ID
        for config_file in config_files:
            filename = os.path.basename(config_file)
            try:
                config_id = int(filename.split('_')[0])
                if config_id > max_id:
                    max_id = config_id
                    latest_config = config_file
            except (ValueError, IndexError):
                continue

        return latest_config or os.path.join(pipeline_dir, "pipeline_config.json")

    # ─────────────────────────────────────────────
    # UI SETUP
    # ─────────────────────────────────────────────
    def _setup_ui(self):
        """Constructs the page layout and visual elements."""
        main_layout = QVBoxLayout(self)

        # Header
        self.header = QLabel("Pipeline Execution")
        self.header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.header)

        # Subheader: current operation label
        self.current_operation = QLabel(
            QCoreApplication.translate("PipelineExecutionPage", "Preparing to start...")
        )
        self.current_operation.setStyleSheet("""
            font-size: 13px;
            color: #7f8c8d;
            margin-top: 8px;
        """)
        self.current_operation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.current_operation)

        # Content grid (progress bar + folders + logs)
        content_layout = QGridLayout()
        main_layout.addLayout(content_layout, stretch=1)

        # Left: progress indicator
        left_layout = QVBoxLayout()
        self.progress_bar = CircularProgress()
        left_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        content_layout.addLayout(left_layout, 0, 0)

        # Right: folder cards (output directories)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        content_layout.addWidget(scroll_area, 0, 1)

        # Grid layout proportions
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 2)
        content_layout.setRowStretch(0, 1)
        content_layout.setRowStretch(1, 0)
        content_layout.setRowStretch(2, 1)

        # Log section
        self.log_label = QLabel("Execution Log:")
        self.log_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            margin-top: 15px;
            margin-bottom: 5px;
        """)
        content_layout.addWidget(self.log_label, 1, 0, 1, 2)

        # Log text box
        self.log_text = QTextEdit()
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                border: 2px solid #34495e;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        content_layout.addWidget(self.log_text, 2, 0, 1, 2)

        # Stop button
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 15, 0, 0)

        self.stop_button = QPushButton("Stop Pipeline")
        self.stop_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #e74c3c;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                min-width: 140px;
            }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        button_layout.addStretch()
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()

        main_layout.addWidget(button_frame)

    def _setup_folder_cards(self):
        # Load folder cards dynamically from configuration
        self.watch_dirs = self.get_sub_list(self.config_path)
        self.watch_dirs = [os.path.join(self.pipeline_output_dir, d) for d in self.watch_dirs]
        self.dir_completed = 0
        for d in self.watch_dirs:
            card = FolderCard(self.context, d)
            card.open_folder_requested.connect(self.context["tree_view"]._open_in_explorer)
            self.scroll_layout.addWidget(card)
            self.folder_cards[d] = card

    # ─────────────────────────────────────────────
    # PIPELINE PROCESS HANDLING
    # ─────────────────────────────────────────────
    def _start_pipeline(self):
        """Start the external pipeline process and monitor its output."""
        if self.pipeline_process:
            return  # Already running

        self.pipeline_process = QProcess()
        self.pipeline_process.finished.connect(self._on_process_finished)
        self.pipeline_process.errorOccurred.connect(self._on_process_error)
        self.pipeline_process.readyReadStandardOutput.connect(self._on_stdout_ready)
        self.pipeline_process.readyReadStandardError.connect(self._on_stderr_ready)

        self.progress_bar.setValue(0)
        self.stop_button.setEnabled(True)
        self._log_message(QCoreApplication.translate("PipelineExecutionPage", "Starting pipeline execution..."))

        cmd = [
            self.pipeline_bin_path,
            "--config", self.config_path,
            "--work-dir", self.workspace_path,
            "--out-dir", self.pipeline_output_dir
        ]
        log.debug(f"{self.pipeline_bin_path} --config {self.config_path} --work-dir {self.workspace_path} --out-dir {self.pipeline_output_dir}")

        self.pipeline_process.start(cmd[0], cmd[1:])

        if not self.pipeline_process.waitForStarted(3000):
            self._log_message(
                QCoreApplication.translate("PipelineExecutionPage", "ERROR: Failed to start pipeline process"))
            self._on_pipeline_error(
                QCoreApplication.translate("PipelineExecutionPage", "Failed to start pipeline process"))

    # ─────────────────────────────────────────────
    # PROCESS SIGNAL HANDLERS
    # ─────────────────────────────────────────────
    def _on_process_finished(self, exit_code, exit_status):
        """Called when the process terminates."""
        if exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            self._on_pipeline_finished()
        else:
            self._on_pipeline_error(
                QCoreApplication.translate(
                    "PipelineExecutionPage",
                    "Process exited with code {exit_code}"
                ).format(exit_code=exit_code)
            )

    def _on_process_error(self, error):
        """Called when an error occurs in the process."""
        error_messages = {
            QProcess.ProcessError.FailedToStart: QCoreApplication.translate("PipelineExecutionPage",
                                                                            "Failed to start process"),
            QProcess.ProcessError.Crashed: QCoreApplication.translate("PipelineExecutionPage", "Process crashed"),
            QProcess.ProcessError.Timedout: QCoreApplication.translate("PipelineExecutionPage", "Process timed out"),
            QProcess.ProcessError.WriteError: QCoreApplication.translate("PipelineExecutionPage", "Write error"),
            QProcess.ProcessError.ReadError: QCoreApplication.translate("PipelineExecutionPage", "Read error"),
            QProcess.ProcessError.UnknownError: QCoreApplication.translate("PipelineExecutionPage", "Unknown error")
        }
        error_msg = error_messages.get(
            error,
            QCoreApplication.translate("PipelineExecutionPage",
                                      "Process error: {error}").format(error=error)
        )
        self._on_pipeline_error(error_msg)

    # ─────────────────────────────────────────────
    # STDOUT / STDERR MONITORING
    # ─────────────────────────────────────────────
    def _on_stdout_ready(self):
        """Called when data is available on stdout."""
        if self.pipeline_process:
            data = self.pipeline_process.readAllStandardOutput()
            output = data.data().decode('utf-8').strip()

            for line in output.split('\n'):
                if line.strip():
                    self._process_pipeline_output(line.strip())

    def _on_stderr_ready(self):
        """Called when data is available on stderr."""
        if self.pipeline_process:
            data = self.pipeline_process.readAllStandardError()
            error_output = data.data().decode('utf-8').strip()

            for line in error_output.split('\n'):
                if line.strip():
                    self._log_message(f"STDERR: {line.strip()}")
    # ─────────────────────────────────────────────
    # OUTPUT INTERPRETATION
    # ─────────────────────────────────────────────
    def _process_pipeline_output(self, line):
        """Process the pipeline output logs"""
        if line.startswith("LOG: "):
            message = line[5:]
            self._log_message(message)
            self._update_current_operation(message)
        elif line.startswith("ERROR: "):
            error_msg = line[7:]
            self._log_message(
                QCoreApplication.translate("PipelineExecutionPage", "ERROR: {error}").format(error=error_msg))
        elif line.startswith("PROGRESS: "):
            progress_info = line[10:]
            self._update_progress(progress_info)
        elif line.startswith("PATIENT: "):
            patient_info = line[9:]
            self._log_message(
                QCoreApplication.translate("PipelineExecutionPage", "Pipeline finished for patient: {message}").format(message=patient_info))
            self._update_progress(patient_info)
        elif line.startswith("FINISHED: "):
            message = line[10:]
            self._log_message(QCoreApplication.translate("PipelineExecutionPage", "FINISHED for: {message}").format(message=message))
        else:
            self._log_message(line)

    # ─────────────────────────────────────────────
    # STATE MANAGEMENT
    # ─────────────────────────────────────────────
    def _on_pipeline_finished(self):
        """Called when the pipeline finishes successfully."""
        self.pipeline_completed = True
        self.current_operation.setText(QCoreApplication.translate("PipelineExecutionPage", "All patients processed successfully."))
        self.progress_bar.setValue(100)
        self.stop_button.setEnabled(False)
        self._log_message(
            QCoreApplication.translate("PipelineExecutionPage", "Pipeline execution completed successfully!"))
        self._log_message(
            QCoreApplication.translate("PipelineExecutionPage", "Results saved in: {pipeline_output_dir}").format(
                pipeline_output_dir=self.pipeline_output_dir))
        self.pipeline_process = None
        for card in self.folder_cards.values():
            card.set_finished_state()
        self.context["update_main_buttons"]()

    def _on_pipeline_error(self, error_message):
        """Called when the pipeline terminates due to an error."""
        self.pipeline_error = error_message
        self.current_operation.setText(
            QCoreApplication.translate("PipelineExecutionPage", "An error occurred during execution."))
        self.current_operation.setStyleSheet("""
                    color: #c0392b;
                    font-weight: bold;
                """)
        self.progress_bar.setColor("#c0392b")
        self.stop_button.setEnabled(False)
        self._log_message(QCoreApplication.translate("PipelineExecutionPage", "ERROR: {error_message}").format(error_message=error_message))
        self.pipeline_process = None
        self.context["update_main_buttons"]()

    # ─────────────────────────────────────────────
    # PROGRESS AND UI UPDATES
    # ─────────────────────────────────────────────
    def _update_progress(self, progress_info):
        """
        Update the circular progress bar based on progress information.

        Expected format from pipeline: `"PROGRESS: X/Y"`

        Args:
            progress_info (str): Progress data string (e.g., `"3/10"`).
        """
        try:
            if '/' in progress_info:
                current, total = map(int, progress_info.split('/'))
                percentage = int((current / total) * 100)
                self.progress_bar.setValue(percentage)

                self.check_new_files()  # Update folder views
            elif "sub" in progress_info:
                match = re.search(r"(sub-[a-zA-Z0-9_]+)", progress_info)
                if match:
                    sub_id = match.group(1)
                    log.debug(f"Detected progress completion for: {sub_id}")

                    for folder_path, card in self.folder_cards.items():
                        folder_name = os.path.basename(folder_path)
                        if sub_id in folder_name:
                            log.debug(f"Setting finished state for card: {folder_name}")
                            card.set_finished_state()
                            break
                    else:
                        log.warning(f"No matching FolderCard found for {sub_id}")
                else:
                    log.warning(f"Could not extract sub-id from progress info: {progress_info}")

        except ValueError:
                log.warning("Failed to parse progress info")

    def _update_current_operation(self, message):
        """
        Update the current operation label based on pipeline output message.

        Args:
            message (str): Message received from the pipeline log.
        """
        if "Starting pipeline" in message:
            self.current_operation.setText(
                QCoreApplication.translate("PipelineExecutionPage", "Initializing pipeline...")
            )
        elif "Processing patient" in message or "sub-" in message:
            patient_id = self._extract_patient_id_from_log(message)
            if patient_id:
                self.current_operation.setText(
                    QCoreApplication.translate(
                        "PipelineExecutionPage",
                        "Processing patient: {patient_id}"
                    ).format(patient_id=patient_id)
                )
            else:
                self.current_operation.setText(
                    QCoreApplication.translate("PipelineExecutionPage", "Processing patient data...")
                )
        elif "analysis" in message.lower():
            self.current_operation.setText(
                QCoreApplication.translate("PipelineExecutionPage", "Performing statistical analysis...")
            )
        elif "saving" in message.lower() or "csv" in message.lower():
            self.current_operation.setText(
                QCoreApplication.translate("PipelineExecutionPage", "Saving results...")
            )

    def _extract_patient_id_from_log(self, message):
        """
        Extract a patient ID (e.g., 'sub-001') from a log message.

        Args:
            message (str): Log message.

        Returns:
            str | None: The patient ID if extracted, otherwise None.
        """
        import re
        match = re.search(r'sub-(\w+)', message)
        return f"sub-{match.group(1)}" if match else None

    # ─────────────────────────────────────────────
    # LOGGING AND FILE MONITORING
    # ─────────────────────────────────────────────
    def _log_message(self, message):
        """
        Append a message to the on-screen log with a timestamp.

        Args:
            message (str): The message text to append.
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)

        # Auto-scroll to the newest entry
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def check_new_files(self):
        """Check each FolderCard for newly created files."""
        for card in self.folder_cards.values():
            card.check_new_files()

    # ─────────────────────────────────────────────
    # USER INTERACTION: STOP / NAVIGATION
    # ─────────────────────────────────────────────
    def _on_stop_clicked(self):
        """
        Handle a user click on the "Stop Pipeline" button.

        Attempts graceful termination, followed by forced termination if necessary.
        """
        if self.pipeline_process and self.pipeline_process.state() == QProcess.ProcessState.Running:
            self._log_message(QCoreApplication.translate("PipelineExecutionPage", "Stopping pipeline..."))

            # Attempt graceful termination first
            self.pipeline_process.terminate()

            # Force termination if not stopped within 5 seconds
            if not self.pipeline_process.waitForFinished(5000):
                self.pipeline_process.kill()
                self.pipeline_process.waitForFinished(3000)

            self._log_message(QCoreApplication.translate("PipelineExecutionPage", "Pipeline stopped by user."))

            self.current_operation.setText(
                QCoreApplication.translate("PipelineExecutionPage", "Execution was interrupted by user."))

            self.progress_bar.setValue(0)
            self.stop_button.setEnabled(False)

            self.pipeline_process = None
            self.context["update_main_buttons"]()

    def _return_to_import(self):
        """
        Return to the import page if no pipeline is running.

        Prevents navigation while the pipeline is still active.
        """
        if self.pipeline_process and self.pipeline_process.state() == QProcess.ProcessState.Running:
            return  # Navigation disabled while pipeline is running

        if self.context and "return_to_import" in self.context:
            self.context["return_to_import"]()

    # ─────────────────────────────────────────────
    # PAGE NAVIGATION (from Page base class)
    # ─────────────────────────────────────────────
    def on_enter(self):
        """
        Called automatically when this page becomes visible.

        Starts the pipeline automatically after the UI is fully rendered.
        """
        # Load the most recent pipeline configuration file
        self.config_path = self._find_latest_config()

        # Extract pipeline ID and output directory
        config_filename = os.path.basename(self.config_path)
        try:
            config_id = config_filename.split('_')[0]
            self.pipeline_output_dir = os.path.join(
                self.workspace_path, "pipeline", f"{config_id}_output"
            )
            os.makedirs(self.pipeline_output_dir, exist_ok=True)
        except (IndexError, ValueError):
            log.debug("Failed to create pipeline_output_dir")
            self.pipeline_output_dir = os.path.join(self.workspace_path, "pipeline")

        # Resolve path to pipeline executable
        try:
            self.pipeline_bin_path = get_bin_path("pipeline_runner")
        except FileNotFoundError:
            log.error("Pipeline runner binary not found")
            raise RuntimeError("Pipeline runner executable missing.")

        if not self.pipeline_completed and self.pipeline_process is None:
            QTimer.singleShot(500, self._start_pipeline)

        self._setup_folder_cards()

    def back(self):
        """
        Navigate back to the previous page, resetting this page first.

        Returns:
            Page | None: The previous page, if available.
        """
        self.reset_page()
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def next(self, context):
        """
        Called when the user presses "Next".

        Displays a confirmation dialog asking whether to return to the import page.

        Args:
            context (dict): Application context.

        Returns:
            Page | None: The next page to navigate to.
        """
        msg_box = QMessageBox()
        msg_box.setWindowTitle(QCoreApplication.translate("PipelineExecutionPage", "Confirm"))
        msg_box.setText(QCoreApplication.translate("PipelineExecutionPage", "You want to return to the import page?"))
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

        result = msg_box.exec()

        if result == QMessageBox.StandardButton.Ok:
            self.reset_page()
            self._return_to_import()
            return self.context["return_to_import"]()
        return None

    def is_ready_to_go_back(self):
        """Allow going back only when the pipeline has finished or encountered an error."""
        return self.pipeline_completed or self.pipeline_error is not None

    def is_ready_to_advance(self):
        """Allow advancing only when the pipeline has finished or encountered an error."""
        return self.pipeline_completed or self.pipeline_error is not None

    # ─────────────────────────────────────────────
    # JSON UTILITIES
    # ─────────────────────────────────────────────
    def get_sub_list(self, json_path: str) -> list:
        """
        Read a pipeline configuration JSON file and return the list of subjects.

        Args:
            json_path (str): Path to the JSON configuration file.

        Returns:
            list[str]: A list of keys that begin with `"sub-"`.
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return [key for key in data.keys() if key.startswith("sub-")]

    # ─────────────────────────────────────────────
    # STATE RESET / CLEANUP
    # ─────────────────────────────────────────────
    def reset_page(self):
        """
        Reset the page state to its initial condition.

        Clears logs, progress, and error flags.
        """
        if hasattr(self, "scroll_layout"):
            while self.scroll_layout.count():
                item = self.scroll_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
        self.folder_cards = {}

        self.progress_bar.setValue(0)
        self.progress_bar.setColor("#3498DB")
        self.stop_button.setEnabled(False)
        self.current_operation.setText("Preparing to start...")
        self.current_operation.setStyleSheet("""
            font-size: 13px;
            color: #7f8c8d;
            margin-top: 8px;
        """)
        self.log_text.clear()
        self.pipeline_process = None
        self.pipeline_error = None
        self.pipeline_completed = False

    def __del__(self):
        """Ensure that any running pipeline process is terminated when this object is destroyed."""
        if self.pipeline_process and self.pipeline_process.state() == QProcess.ProcessState.Running:
            self.pipeline_process.kill()
            self.pipeline_process.waitForFinished(1000)

    def _translate_ui(self):
        """Update all translatable UI text (used for multilingual support)."""
        self.header.setText(QCoreApplication.translate("PipelineExecutionPage", "Pipeline Execution"))
        self.stop_button.setText(QCoreApplication.translate("PipelineExecutionPage", "Stop Pipeline"))
        self.log_text.setText(QCoreApplication.translate("PipelineExecutionPage", "Execution Log:"))
        self.log_label.setText(QCoreApplication.translate("PipelineExecutionPage", "Execution Log:"))
