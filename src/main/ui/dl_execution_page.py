import os
import subprocess

import torch
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QScrollArea, QFrame, QGridLayout, QHBoxLayout,
                             QMessageBox, QGroupBox, QListWidget, QProgressBar,
                             QListWidgetItem, QTextEdit, QSplitter, QFileDialog,
                             QCheckBox)
from PyQt6.QtCore import Qt, QThread, QCoreApplication

from components.circular_progress_bar import CircularProgress
from threads.dl_worker import DlWorker
from page import Page
from logger import get_logger

log = get_logger()


class DlExecutionPage(Page):
    """Page for SynthStrip + Coregistration of selected NIfTI files."""

    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.worker = None  # Worker thread instance
        self.current_file = None  # Currently processing file (if needed)
        self.context = context  # Shared application context (settings, file lists)
        self.previous_page = previous_page  # Reference to the previous page for navigation
        self.next_page = None  # Reference to the next page

        # State flags
        self.processing = False  # Flag to indicate if processing is active
        self.processing_completed = False  # Flag to indicate if processing has finished

        self._setup_ui()  # Initialize the user interface elements

        self._translate_ui()  # Apply initial translations
        if context and "language_changed" in context:
            # Connect to the global language change signal if it exists
            context["language_changed"].connect(self._translate_ui)

    def _setup_ui(self):
        """Sets up the user interface layout and widgets."""
        main_layout = QVBoxLayout(self)

        # --- Header ---
        self.header = QLabel("Deep Learning Segmentation")
        self.header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.header)

        # --- Info Label (Tool detection) ---
        self.info_label = QLabel("")
        self.info_label.setOpenExternalLinks(True)
        self.info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)

        self.info_label.setStyleSheet("""
                            font-size: 11px;
                            color: #666;
                            font-style: italic;
                            margin-bottom: 6px;
                        """)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        main_layout.addWidget(self.info_label)

        try:
            # Run the command with --help to check if it exists and works
            subprocess.run(
                ['mri_synthstrip', '--help'],
                stdout=subprocess.DEVNULL,  # Discard standard output
                stderr=subprocess.DEVNULL  # Discard standard error
            )
            self.has_freesurfer = True
            self.info_label.setText(
                "Using tool: <a href='https://surfer.nmr.mgh.harvard.edu/docs/synthstrip/'>SynthStrip from Free Surfer</a>")
        except (FileNotFoundError, subprocess.CalledProcessError):
            # Handle case where FreeSurfer version is not found
            self.has_freesurfer = False
            self.info_label.setText(
                'Using tool: <a href="https://github.com/nipreps/synthstrip">SynthStrip (nipreps)</a><br>'
                'To use SynthStrip from FreeSurfer, follow the instructions at: '
                '<a href="https://surfer.nmr.mgh.harvard.edu/docs/synthstrip/">SynthStrip official documentation</a>'
            )

        self.info_label.setOpenExternalLinks(True)  # Enable opening links in browser
        self.info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.info_label.setToolTip("Open link")

        # --- Current Operation Status ---
        self.current_operation = QLabel("Ready to start")
        self.current_operation.setStyleSheet("""
            font-size: 13px;
            color: #7f8c8d;
            margin-top: 8px;
        """)
        self.current_operation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.current_operation)

        # --- Content area (Grid) ---
        content_layout = QGridLayout()
        main_layout.addLayout(content_layout, stretch=1)

        # --- Left Column (Row 0, Col 0): Progress Display ---
        left_layout = QVBoxLayout()
        self.progress_bar = CircularProgress()  # Custom circular progress widget
        left_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        content_layout.addLayout(left_layout, 0, 0)

        # --- Right Column (Row 0, Col 1): File List ---
        self.files_group = QGroupBox("Files to process")
        files_layout = QVBoxLayout(self.files_group)

        self.files_list = QListWidget()
        self.files_list.setMaximumHeight(150)
        files_layout.addWidget(self.files_list)

        # Add the file list (QListWidget) directly to the grid
        content_layout.addWidget(self.files_list, 0, 1)

        # --- Grid Layout Stretch ---
        # Columns: 1/3 for progress bar, 2/3 for scroll area
        content_layout.setColumnStretch(0, 1)  # Left column (progress bar)
        content_layout.setColumnStretch(1, 2)  # Right column (folder list)

        # --- Bottom Row (Rows 1 & 2): Log Display ---
        self.log_label = QLabel("Execution Log:")
        self.log_label.setStyleSheet("""
                    font-size: 16px;
                    font-weight: bold;
                    color: #2c3e50;
                    margin-top: 15px;
                    margin-bottom: 5px;
                """)
        # Add log label, spanning both columns (Row 1, Col 0, 1 row span, 2 col span)
        content_layout.addWidget(self.log_label, 1, 0, 1, 2)

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
        # Add log text area, spanning both columns (Row 2, Col 0, 1 row span, 2 col span)
        content_layout.addWidget(self.log_text, 2, 0, 1, 2)

        # === Control Buttons ===

        # --- Button Layout (Start/Stop) ---
        button_frame = QFrame()  # Frame to hold the centered buttons
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 15, 0, 0)

        self.start_button = QPushButton("Start deep learning")
        button_layout.addStretch()  # Center the buttons
        self.start_button.clicked.connect(self.start_processing)
        self.start_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #27ae60;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                min-width: 140px;
            }
            QPushButton:hover { 
                background-color: #229954; 
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        button_layout.addWidget(self.start_button)

        self.cancel_button = QPushButton("Stop processing")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #e74c3c;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                min-width: 140px;
            }
            QPushButton:hover { 
                background-color: #c0392b; 
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        self.cancel_button.clicked.connect(self.cancel_processing)
        self.cancel_button.setVisible(False)  # Initially hidden

        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()  # Center the buttons

        main_layout.addWidget(button_frame)

    def on_enter(self):
        """Called when this page becomes active."""
        self.reset_processing_state()  # Ensure UI is in a clean, default state

        # Populate the file list if available from context
        if self.context and "selected_segmentation_files" in self.context:
            self.files_list.clear()
            for file_path in self.context["selected_segmentation_files"]:
                filename = os.path.basename(file_path)
                # Add item with "Waiting..." status
                self.files_list.addItem(
                    QCoreApplication.translate("DlExecutionPage", "📄 {filename} - Waiting...").format(
                        filename=filename))

    def start_processing(self):
        """Starts the deep learning processing workflow."""
        if not self.context or "selected_segmentation_files" not in self.context:
            QMessageBox.warning(self, QCoreApplication.translate("DlExecutionPage", "Error"),
                                QCoreApplication.translate("DlExecutionPage", "No files selected for processing."))
            return

        selected_files = self.context["selected_segmentation_files"]
        if not selected_files:
            QMessageBox.warning(self, QCoreApplication.translate("DlExecutionPage", "Error"),
                                QCoreApplication.translate("DlExecutionPage", "No files selected for processing."))
            return

        # --- Setup Worker Thread ---
        self.worker = DlWorker(
            input_files=selected_files,
            workspace_path=self.context["workspace_path"],
            has_freesurfer=self.has_freesurfer
        )

        # --- Connect Worker Signals ---
        self.worker.progressbar_update.connect(self.update_progress)
        self.worker.file_update.connect(self.update_file_status)
        self.worker.log_update.connect(self.add_log_message)
        self.worker.finished.connect(self.processing_finished)
        # self.worker.finished.connect(self.worker.deleteLater) # Option to auto-delete worker

        # --- Update UI for Processing State ---
        self.processing = True
        self.start_button.setVisible(False)
        self.cancel_button.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.current_operation.setText(QCoreApplication.translate("DlExecutionPage", "Processing..."))
        self.log_text.clear()

        # --- Start Worker ---
        self.worker.start()  # Start the QThread

        self.add_log_message(
            QCoreApplication.translate("DlExecutionPage", "Deep learning processing started for {0} file").format(
                len(selected_files)), 'i')
        log.info(f"Deep learning processing started for {len(selected_files)} file")

    def update_progress(self, value):
        """Updates the circular progress bar value."""
        self.progress_bar.setValue(value)

    def add_log_message(self, message, type):
        """Appends a message to the UI log text area."""
        timestamp = QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_text.append(f"[{timestamp}] {message}")

        # Log to external file based on message type
        if type == 'e':
            log.error(f"[{timestamp}] {message}")
        elif type == 'i':
            log.info(f"[{timestamp}] {message}")
        elif type == 'w':
            log.warning(f"[{timestamp}] {message}")
        else:
            log.debug(f"[{timestamp}] {message}")

        # Auto-scroll to the bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_file_status(self, filename, status):
        """Updates the status of a specific file in the QListWidget."""
        for i in range(self.files_list.count()):
            item = self.files_list.item(i)
            if filename in item.text():  # Find the matching item
                item.setText(f"📄 {filename} - {status}")
                break  # Stop searching once found

    def cancel_processing(self):
        """Requests the worker thread to cancel processing."""
        if self.worker:
            self.worker.cancel_requested.emit()  # Emit the signal to request cancellation
            # self.worker.cancel() # If you have a hard cancel method
            self.add_log_message(QCoreApplication.translate("DlExecutionPage", "Cancellation requested..."), 'i')

    def processing_finished(self, success, message):
        """Slot called when the worker thread finishes."""
        self.processing = False
        self.processing_completed = True

        # --- Update UI to Reflect Finished State ---
        self.start_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.progress_bar.setVisible(False)

        if success:
            self.current_operation.setText(QCoreApplication.translate("DlExecutionPage", "✓ Processing completed!"))
            self.current_operation.setStyleSheet("color: green; font-weight: bold;")
            self.start_button.setText(QCoreApplication.translate("DlExecutionPage", "Reprocess"))
        else:
            self.current_operation.setText("✗ Processing failed!")
            self.current_operation.setStyleSheet("color: #c0392b; font-weight: bold;")

        self.add_log_message(QCoreApplication.translate("DlExecutionPage", "Final: {message}").format(message=message),
                             'i')

        # --- Update Context with Results ---
        if success and "workspace_path" in self.context:
            # If successful, store the output directory in the context
            output_dir = os.path.join(self.context["workspace_path"], "outputs")
            self.context["processing_output_dir"] = output_dir

        # Notify main window to update its buttons (e.g., 'Next')
        if "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

        # --- Show Final Message Box ---
        if success:
            QMessageBox.information(self, QCoreApplication.translate("DlExecutionPage", "Completed"), message)
        else:
            QMessageBox.critical(self, QCoreApplication.translate("DlExecutionPage", "Error"), message)

    def reset_processing_state(self):
        """Resets the page to its initial state."""
        self.processing = False
        self.processing_completed = False
        self.start_button.setText(QCoreApplication.translate("DlExecutionPage", "Start deep learning"))
        self.start_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.progress_bar.setVisible(False)
        self.current_operation.setStyleSheet("")  # Reset color
        self.current_operation.setText(QCoreApplication.translate("DlExecutionPage", "Ready to start"))

        if self.worker:
            self.worker = None  # Clear worker reference

    def back(self):
        """Handles the 'Back' navigation request."""
        if self.processing:
            # Ask user for confirmation to stop
            reply = QMessageBox.question(
                self,
                QCoreApplication.translate("DlExecutionPage", "Processing in progress"),
                QCoreApplication.translate("DlExecutionPage",
                                           "Processing is in progress. Do you really want to go back?\nProcessing will be interrupted."),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return None  # Abort navigation

            # --- Stop Processing ---
            if self.worker:
                self.worker.cancel_requested.emit()
                # self.worker.cancel()

        if self.previous_page:
            self.previous_page.on_enter()  # Call on_enter of the previous page
            return self.previous_page
        return None  # No previous page

    def next(self, context):
        """Handles the 'Next' navigation request."""
        return None  # This page is a terminal step

    def is_ready_to_advance(self):
        """Checks if the page is in a state to advance."""
        return False  # Cannot advance from this page

    def is_ready_to_go_back(self):
        """Checks if the page is in a state to go back."""
        return True  # Can always go back (with a warning if processing)

    def _translate_ui(self):
        """Updates all user-visible strings for translation."""
        self.header.setText(QCoreApplication.translate("DlExecutionPage", "Deep Learning Segmentation"))

        # Only reset 'Ready to start' if not processing or completed
        if not self.processing and not self.processing_completed:
            self.current_operation.setText(QCoreApplication.translate("DlExecutionPage", "Ready to start"))

        self.files_group.setTitle(QCoreApplication.translate("DlExecutionPage", "Files to process"))
        self.log_label.setText(QCoreApplication.translate("DlExecutionPage", "Execution Log:"))

        if not self.processing_completed:
            self.start_button.setText(QCoreApplication.translate("DlExecutionPage", "Start deep learning"))
        else:
            self.start_button.setText(QCoreApplication.translate("DlExecutionPage", "Reprocess"))

        self.cancel_button.setText(QCoreApplication.translate("DlExecutionPage", "Stop processing"))

        # Repopulate the file list with translated "Waiting..." string
        if self.context and "selected_segmentation_files" in self.context and not self.processing:
            self.files_list.clear()
            for file_path in self.context["selected_segmentation_files"]:
                filename = os.path.basename(file_path)
                self.files_list.addItem(
                    QCoreApplication.translate("DlExecutionPage", "📄 {filename} - Waiting...").format(
                        filename=filename))