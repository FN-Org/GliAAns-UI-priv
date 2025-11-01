import os
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
    """
    Page handling the Deep Learning segmentation process.

    This class manages the interface for running and monitoring deep learning–based
    segmentation tasks, including progress updates, logging, and user controls.
    """

    def __init__(self, context=None, previous_page=None):
        """
        Initialize the execution page.

        **Args:**
        - `context` (*dict*, optional): Shared application context with state information.
        - `previous_page` (*Page*, optional): Reference to the previous page for navigation.
        """

        super().__init__()
        self.worker = None
        self.current_file = None
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.processing = False
        self.processing_completed = False

        self._setup_ui()
        self._translate_ui()

        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def _setup_ui(self):
        """Builds and arranges the UI elements for the execution page."""
        main_layout = QVBoxLayout(self)

        # Header section
        self.header = QLabel("Deep Learning Segmentation")
        self.header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.header)

        # Current operation label
        self.current_operation = QLabel("Ready to start")
        self.current_operation.setStyleSheet("""
            font-size: 13px;
            color: #7f8c8d;
            margin-top: 8px;
        """)
        self.current_operation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.current_operation)

        # Main content layout
        content_layout = QGridLayout()
        main_layout.addLayout(content_layout, stretch=1)

        # Circular progress indicator
        left_layout = QVBoxLayout()
        self.progress_bar = CircularProgress()
        left_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        content_layout.addLayout(left_layout, 0, 0)

        # List of selected files
        self.files_group = QGroupBox("Files to process")
        files_layout = QVBoxLayout(self.files_group)

        self.files_list = QListWidget()
        self.files_list.setMaximumHeight(150)
        files_layout.addWidget(self.files_list)
        content_layout.addWidget(self.files_list, 0, 1)

        # Progress bar
        left_layout = QVBoxLayout()
        self.progress_bar = CircularProgress()
        left_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        content_layout.addLayout(left_layout, 0, 0)

        # Set column proportions
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 2)

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

        # Control buttons
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 15, 0, 0)

        # Start button
        self.start_button = QPushButton("Start deep learning")
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
            QPushButton:hover { background-color: #229954; }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)

        # Cancel button
        self.cancel_button = QPushButton("Stop processing")
        self.cancel_button.clicked.connect(self.cancel_processing)
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
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        self.cancel_button.clicked.connect(self.cancel_processing)

        self.start_button.setVisible(True)
        self.cancel_button.setVisible(False)

        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()

        main_layout.addWidget(button_frame)

    def on_enter(self):
        """Called when entering this page. Resets UI and populates file list."""
        self.reset_processing_state()

        if self.context and "selected_segmentation_files" in self.context:
            self.files_list.clear()
            for file_path in self.context["selected_segmentation_files"]:
                filename = os.path.basename(file_path)
                self.files_list.addItem(QCoreApplication.translate(
                    "DlExecutionPage", "📄 {filename} - Waiting...").format(filename=filename))

    def start_processing(self):
        """Starts the deep learning segmentation process."""
        if not self.context or "selected_segmentation_files" not in self.context:
            QMessageBox.warning(self, QCoreApplication.translate("DlExecutionPage", "Error"),
                                QCoreApplication.translate("DlExecutionPage", "No files selected for processing."))
            return

        selected_files = self.context["selected_segmentation_files"]
        if not selected_files:
            QMessageBox.warning(self, QCoreApplication.translate("DlExecutionPage", "Error"),
                                QCoreApplication.translate("DlExecutionPage", "No files selected for processing."))
            return

        # Initialize background worker
        self.worker = DlWorker(
            input_files=selected_files,
            workspace_path=self.context["workspace_path"]
        )

        # Connect worker signals to handlers
        self.worker.progressbar_update.connect(self.update_progress)
        self.worker.file_update.connect(self.update_file_status)
        self.worker.log_update.connect(self.add_log_message)
        self.worker.finished.connect(self.processing_finished)

        # Update UI
        self.processing = True
        self.start_button.setVisible(False)
        self.cancel_button.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.current_operation.setText("Processing...")
        self.log_text.clear()

        # Start the worker
        self.worker.start()

        self.add_log_message(
            QCoreApplication.translate("DlExecutionPage", "Deep learning processing started for {0} file").format(
                len(selected_files)), 'i')
        log.info(f"Deep learning processing started for {len(selected_files)} file")

    def update_progress(self, value):
        """Update the circular progress bar with the given value."""
        self.progress_bar.setValue(value)

    def add_log_message(self, message, type):
        """Append a new message to the on-screen log and to the application log."""
        timestamp = QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_text.append(f"[{timestamp}] {message}")

        if type == 'e':
            log.error(f"[{timestamp}] {message}")
        elif type == 'i':
            log.info(f"[{timestamp}] {message}")
        elif type == 'w':
            log.warning(f"[{timestamp}] {message}")
        else:
            log.debug(f"[{timestamp}] {message}")

        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_file_status(self, filename, status):
        """Update the status label of a given file in the file list."""
        for i in range(self.files_list.count()):
            item = self.files_list.item(i)
            if filename in item.text():
                item.setText(f"📄 {filename} - {status}")
                break

    def cancel_processing(self):
        """Request cancellation of the ongoing processing."""
        if self.worker:
            self.worker.cancel_requested.emit()
            self.add_log_message(QCoreApplication.translate("DlExecutionPage", "Cancellation requested..."), 'i')


    def processing_finished(self, success, message):
        """Handle the completion of the processing."""
        self.processing = False
        self.processing_completed = True

        self.start_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.progress_bar.setVisible(False)

        if success:
            self.current_operation.setText(QCoreApplication.translate("DlExecutionPage", "✓ Processing completed!"))
            self.current_operation.setStyleSheet("color: green; font-weight: bold;")
            self.start_button.setText("Reprocess")
        else:
            self.current_operation.setText("Processing failed.")
            self.current_operation.setStyleSheet("color: #c0392b; font-weight: bold;")

        self.add_log_message(QCoreApplication.translate("DlExecutionPage", "Final: {message}").format(message=message),
                             'i')

        if success and "workspace_path" in self.context:
            output_dir = os.path.join(self.context["workspace_path"], "outputs")
            self.context["processing_output_dir"] = output_dir

        if "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

        if success:
            QMessageBox.information(self, QCoreApplication.translate("DlExecutionPage", "Completed"), message)
        else:
            QMessageBox.critical(self, QCoreApplication.translate("DlExecutionPage", "Error"), message)

    def reset_processing_state(self):
        """Reset the state of the UI and internal variables before or after processing."""
        self.processing = False
        self.processing_completed = False
        self.start_button.setText(QCoreApplication.translate("DlExecutionPage", "Start deep learning"))
        self.start_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.progress_bar.setVisible(False)
        self.current_operation.setStyleSheet("")

        if self.worker:
            self.worker = None

    def back(self):
        """Navigate back to the previous page, with confirmation if processing is active."""
        if self.processing:
            reply = QMessageBox.question(
                self,
                QCoreApplication.translate("DlExecutionPage", "Processing in progress"),
                QCoreApplication.translate("DlExecutionPage",
                                           "Processing is in progress. Do you really want to go back?\nProcessing will be interrupted."),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return None

            if self.worker:
                self.worker.cancel_requested.emit()

        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def next(self, context):
        """Return the next page (not used in this step)."""
        return None

    def is_ready_to_advance(self):
        """Return whether advancing to the next page is allowed."""
        return False

    def is_ready_to_go_back(self):
        """Return whether navigation to the previous page is allowed."""
        return True

    def _translate_ui(self):
        """Apply translation to all text elements on the page."""
        self.header.setText(QCoreApplication.translate("DlExecutionPage", "Deep Learning Segmentation"))
        self.current_operation.setText(QCoreApplication.translate("DlExecutionPage", "Ready to start"))
        self.files_group.setTitle(QCoreApplication.translate("DlExecutionPage", "Files to process"))
        self.log_label.setText(QCoreApplication.translate("DlExecutionPage", "Execution Log:"))
        self.start_button.setText(QCoreApplication.translate("DlExecutionPage", "Start deep learning"))
        self.cancel_button.setText(QCoreApplication.translate("DlExecutionPage", "Stop processing"))

        if self.context and "selected_segmentation_files" in self.context:
            self.files_list.clear()
            for file_path in self.context["selected_segmentation_files"]:
                filename = os.path.basename(file_path)
                self.files_list.addItem(QCoreApplication.translate(
                    "DlExecutionPage", "📄 {filename} - Waiting...").format(filename=filename))
