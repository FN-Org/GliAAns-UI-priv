import torch
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton, QMessageBox, QCheckBox,
    QHBoxLayout, QWidget, QDoubleSpinBox, QSpinBox, QGroupBox,
    QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QCoreApplication
import os
import subprocess

from components.file_selector_widget import FileSelectorWidget
from threads.skull_strip_thread import SkullStripThread
from page import Page
from logger import get_logger

log = get_logger()


class SkullStrippingPage(Page):
    """
    GUI page for performing skull stripping on NIfTI files.

    This class provides a user interface to select anatomical MRI images
    and perform skull stripping using either:
        - BET (Brain Extraction Tool) from FSL (if available)
        - HD-BET (deep learning-based alternative)

    It handles:
        * User input for tool parameters
        * Background processing using a worker thread
        * Progress and status updates

    Signals:
        processing (bool): emitted when processing starts or stops.
    """

    processing = pyqtSignal(bool)

    def __init__(self, context=None, previous_page=None):
        """
        Initialize the SkullStrippingPage.

        Args:
            context (dict, optional): Shared app context for state and communication.
            previous_page (Page, optional): Reference to previous navigation page.
        """
        super().__init__()
        self.canceled = False
        self.context = context
        self.previous_page = previous_page
        self.next_page = None
        self.worker = None  # Background thread reference
        self.has_cuda = torch.cuda.is_available()
        self.bet_tool = ""

        self._setup_ui()
        self._translate_ui()

        # Re-translate if app language changes
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def _setup_ui(self):
        """Create and configure all UI components."""
        self.processing.connect(self.set_processing_mode)
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        # Title
        self.title = QLabel("Select a NIfTI file for Skull Stripping")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        # Info label (link to BET or HD-BET)
        self.info_label = QLabel(
            'Using tool: <a href="https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/BET">BET from FSL toolkit</a>'
        )
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
        self.layout.addWidget(self.info_label)

        # File selector widget for NIfTI files
        self.file_selector_widget = FileSelectorWidget(
            parent=self,
            context=self.context,
            has_existing_function=self.has_existing_skull_strip,
            label="skull strip",
            allow_multiple=True,
            processing=self.processing,
            forced_filters={"datatype": "anat"}
        )
        self.layout.addWidget(self.file_selector_widget)

        # Check if BET command exists in system
        try:
            subprocess.run(['bet'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.has_bet = True
        except FileNotFoundError:
            self.has_bet = False

        # Setup parameters for BET (if installed)
        if self.has_bet:
            self._setup_bet_options()
        else:
            try:
                subprocess.run(['mri_synthstrip'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.has_synthstrip = True
            except FileNotFoundError:
                self.has_synthstrip = False

            if self.has_synthstrip:
                self.info_label.setText(
                    QCoreApplication.translate("SkullStrippingPage", 'Using tool: <a href="https://surfer.nmr.mgh.harvard.edu/docs/synthstrip/">SynthStrip</a> <br>')
                )
            else:
                self.info_label.setText(
                    QCoreApplication.translate("SkullStrippingPage",
                        'Using tool: <a href="https://github.com/MIC-DKFZ/HD-BET">hd-bet</a> <br>'
                        'To use BET from FSL toolkit, install it following the instructions at: '
                        '<a href="https://fsl.fmrib.ox.ac.uk/fsl/docs/#/install/index">FSL installation</a>')
                )
            self.info_label.setOpenExternalLinks(True)
            self.info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            self.info_label.setToolTip("Open link")

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)

        # Action buttons (Run / Cancel)
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 15, 0, 0)

        # --- RUN button (green) ---
        self.run_button = QPushButton("Run Skull Stripping")
        self.file_selector_widget.has_file.connect(self.run_button.setEnabled)
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.run_bet)
        self.run_button.setStyleSheet("""
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
        button_layout.addStretch()
        button_layout.addWidget(self.run_button)

        # --- CANCEL button (red) ---
        self.cancel_button = QPushButton("Stop Processing")
        self.cancel_button.setVisible(False)
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
                    QPushButton:hover { 
                        background-color: #c0392b; 
                    }
                    QPushButton:disabled {
                        background-color: #bdc3c7;
                        color: #7f8c8d;
                    }
                """)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()

        self.layout.addWidget(button_frame)

        # Stato
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)

    def _setup_bet_options(self):
        """Setup BET-specific parameter inputs and advanced options."""
        # Fractional intensity threshold (main parameter)
        self.f_box = QGroupBox()
        f_layout = QHBoxLayout()
        self.f_label = QLabel("Fractional intensity threshold, smaller values give larger brain outline estimates")
        f_layout.addWidget(self.f_label)

        self.f_spinbox = QDoubleSpinBox()
        self.f_spinbox.setRange(0.0, 1.0)
        self.f_spinbox.setSingleStep(0.05)
        self.f_spinbox.setValue(0.50)
        self.f_spinbox.setDecimals(2)
        self.f_spinbox.setMinimumWidth(60)
        self.f_spinbox.setMaximumWidth(80)
        f_layout.addWidget(self.f_spinbox)
        f_layout.addStretch()
        self.f_box.setLayout(f_layout)
        self.layout.addWidget(self.f_box)

        # Toggle for advanced options
        self.advanced_btn = QPushButton("Show Advanced Options")
        self.advanced_btn.setCheckable(True)
        self.advanced_btn.clicked.connect(self.toggle_advanced)
        self.layout.addWidget(self.advanced_btn)

        # Advanced parameters box
        self.is_checked = False
        self.advanced_box = QGroupBox()
        self.advanced_layout = QVBoxLayout()

        # Output options
        self.output_label = QLabel("Advanced options:")
        self.output_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        self.advanced_layout.addWidget(self.output_label)

        self.opt_brain_extracted = QCheckBox("Output brain-extracted image")
        self.opt_brain_extracted.setChecked(True)
        self.advanced_layout.addWidget(self.opt_brain_extracted)

        self.opt_m = QCheckBox("Output binary brain mask image")
        self.advanced_layout.addWidget(self.opt_m)

        self.opt_t = QCheckBox("Apply thresholding to brain and mask image")
        self.advanced_layout.addWidget(self.opt_t)

        self.opt_s = QCheckBox("Output exterior skull surface image")
        self.advanced_layout.addWidget(self.opt_s)

        self.opt_o = QCheckBox("Output brain surface overlaid onto original image")
        self.advanced_layout.addWidget(self.opt_o)

        # Threshold gradient
        self.threshold_layout = QHBoxLayout()
        self.threshold_label = QLabel("Threshold gradient; positive values give larger brain outline at bottom, smaller at top")
        self.threshold_layout.addWidget(self.threshold_label)
        self.g_spinbox = QDoubleSpinBox()
        self.g_spinbox.setRange(-1.0, 1.0)
        self.g_spinbox.setSingleStep(0.1)
        self.g_spinbox.setValue(0.0)
        self.g_spinbox.setDecimals(1)
        self.g_spinbox.setMinimumWidth(60)
        self.g_spinbox.setMaximumWidth(80)
        self.threshold_layout.addWidget(self.g_spinbox)
        self.threshold_layout.addStretch()
        self.advanced_layout.addLayout(self.threshold_layout)

        # Sphere coordinates
        coords_layout = QHBoxLayout()
        self.coords_label = QLabel("Coordinates (voxels) for centre of initial brain surface sphere")
        coords_layout.addWidget(self.coords_label)

        self.c_x_spinbox = QSpinBox()
        self.c_x_spinbox.setRange(0, 9999)
        coords_layout.addWidget(self.c_x_spinbox)
        coords_layout.addWidget(QLabel("Y"))

        self.c_y_spinbox = QSpinBox()
        self.c_y_spinbox.setRange(0, 9999)
        coords_layout.addWidget(self.c_y_spinbox)
        coords_layout.addWidget(QLabel("Z"))

        self.c_z_spinbox = QSpinBox()
        self.c_z_spinbox.setRange(0, 9999)
        coords_layout.addWidget(self.c_z_spinbox)
        coords_layout.addStretch()

        self.advanced_layout.addLayout(coords_layout)
        self.advanced_box.setLayout(self.advanced_layout)
        self.advanced_box.setVisible(False)
        self.layout.addWidget(self.advanced_box)

    def has_existing_skull_strip(self, nifti_file_path, workspace_path):
        """
        Check if a skull-stripped file already exists for the selected subject.

        Args:
            nifti_file_path (str): Full path to input NIfTI file.
            workspace_path (str): Base workspace directory path.

        Returns:
            bool: True if an existing skull strip is found, False otherwise.
        """
        path_parts = nifti_file_path.replace(workspace_path, '').strip(os.sep).split(os.sep)
        subject_id = next((p for p in path_parts if p.startswith('sub-')), None)
        if not subject_id:
            return False

        skull_strip_dir = os.path.join(workspace_path, 'derivatives', 'skullstrips', subject_id, 'anat')
        if not os.path.exists(skull_strip_dir):
            return False

        return any(f.endswith('.nii.gz') for f in os.listdir(skull_strip_dir))

    def toggle_advanced(self):
        """Toggle visibility of advanced BET parameters."""
        self.is_checked = self.advanced_btn.isChecked()
        self.advanced_box.setVisible(self.is_checked)
        self.advanced_btn.setText("Hide Advanced Options" if self.is_checked else "Show Advanced Options")

    def run_bet(self):
        """Start the skull stripping process in a background thread."""
        selected_files = self.file_selector_widget.get_selected_files()
        if not selected_files:
            QMessageBox.warning(self, "No files", "Please select at least one NIfTI file first.")
            return

        parameters = None
        if self.has_bet:
            parameters = {
                'f_val': self.f_spinbox.value(),
                'opt_brain_extracted': self.opt_brain_extracted.isChecked(),
                'opt_m': self.opt_m.isChecked(),
                'opt_t': self.opt_t.isChecked(),
                'opt_s': self.opt_s.isChecked(),
                'opt_o': self.opt_o.isChecked(),
                'g_val': self.g_spinbox.value(),
                'c_x': self.c_x_spinbox.value(),
                'c_y': self.c_y_spinbox.value(),
                'c_z': self.c_z_spinbox.value(),
            }

        if self.has_bet:
            self.bet_tool = "fsl-bet"
        elif self.has_synthstrip:
            self.bet_tool = "synthstrip"
        else:
            self.bet_tool = "hd-bet"

        # Create worker thread
        self.worker = SkullStripThread(selected_files, self.context["workspace_path"], parameters, self.has_cuda, self.bet_tool)

        # Connect worker signals
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.progress_value_updated.connect(self.on_progress_value_updated)
        self.worker.file_started.connect(self.on_file_started)
        self.worker.file_completed.connect(self.on_file_completed)
        self.worker.all_completed.connect(self.on_all_completed)
        self.worker.finished.connect(self.on_worker_finished)

        # Update UI
        self.processing.emit(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.worker.start()

    def cancel_processing(self):
        """Cancel the currently running process."""
        self.canceled = True
        if self.worker and self.worker.isRunning():

            self.worker.cancel()
            self.status_label.setText("Cancelling...")
            self.status_label.setStyleSheet("color: #FF9800; font-weight: bold;")

    def set_processing_mode(self, processing):
        """Enable or disable UI controls depending on processing state."""
        self.run_button.setVisible(not processing and bool(self.file_selector_widget.get_selected_files()))
        self.cancel_button.setVisible(processing)
        if hasattr(self, "f_spinbox"):
            self.f_spinbox.setEnabled(not processing)
        if hasattr(self, "advanced_btn"):
            self.advanced_btn.setEnabled(not processing)
        if hasattr(self, "advanced_box"):
            for widget in self.advanced_box.findChildren(QWidget):
                widget.setEnabled(not processing)
        self.cancel_button.setVisible(processing)


    def on_progress_updated(self, message):
        """Update progress text message."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #2196F3; font-weight: bold;")

    def on_progress_value_updated(self, value):
        """Update numeric progress bar value."""
        self.progress_bar.setValue(value)

    def on_file_started(self, filename):
        """Triggered when a new file starts processing."""
        pass

    def on_file_completed(self, filename, success, error_message):
        """Triggered when a file finishes processing."""
        if not success and error_message:
            log.error(f"Error processing {filename}: {error_message}")

    def on_all_completed(self, success_count, failed_files):
        """Triggered after all files are processed."""
        # Nascondi progress bar
        self.progress_bar.setVisible(False)

        # Aggiorna il messaggio di stato finale
        if success_count > 0:
            summary = QCoreApplication.translate("SkullStrippingPage",
                                                 "Skull Stripping completed successfully for {0} file(s)").format(
                success_count)
            if failed_files:
                failed_summary = QCoreApplication.translate("SkullStrippingPage",
                                                            "{count} file(s) failed: {files}").format(
                    count=len(failed_files),
                    files=', '.join([os.path.basename(f) for f in failed_files])
                )
                summary += f"\n{failed_summary}"
                self.status_label.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 12pt; padding: 5px;")
            else:
                self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12pt; padding: 5px;")
        else:
            failed_files_num = len(failed_files)
            if failed_files_num == 0:
                failed_files_num = ""
            summary = QCoreApplication.translate("SkullStrippingPage", "All {0} file(s) failed to process").format(
                failed_files_num)
            self.status_label.setStyleSheet("color: #FF0000; font-weight: bold; font-size: 12pt; padding: 5px;")

        self.status_label.setText(summary)


    def on_worker_finished(self):
            """Triggered when worker thread finishes execution."""
            self.processing.emit(False)
            if self.worker:
                self.worker.deleteLater()
                self.worker = None
            if self.context and "update_main_buttons" in self.context:
                self.context["update_main_buttons"]()

    def back(self):
        """Navigate back to the previous page if not processing."""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Processing in progress",
                                "Cannot go back while skull stripping is in progress. Please wait or cancel.")
            log.warning("Processing in progress")
            return None
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def on_enter(self):
        """Reset status label when page is entered."""
        self.status_label.setText("")

    def is_ready_to_advance(self):
        """Return False since this page doesn't advance automatically."""
        return False

    def is_ready_to_go_back(self):
        """Disable back navigation during processing."""
        return not (self.worker and self.worker.isRunning())

    def reset_page(self):
        """Reset the page state to its initial configuration."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()

        self.file_selector_widget.clear_selected_files()
        self.run_button.setEnabled(False)

        # Reset advanced options
        self.f_spinbox.setValue(0.50)
        self.advanced_btn.setChecked(False)
        self.advanced_box.setVisible(False)
        self.advanced_btn.setText("Show Advanced Options")

        self.opt_brain_extracted.setChecked(True)
        self.opt_m.setChecked(False)
        self.opt_t.setChecked(False)
        self.opt_s.setChecked(False)
        self.opt_o.setChecked(False)

        self.g_spinbox.setValue(0.0)
        self.c_x_spinbox.setValue(0)
        self.c_y_spinbox.setValue(0)
        self.c_z_spinbox.setValue(0)

        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.processing.emit(False)
        self.status_label.setText("")

    def _translate_ui(self):
        """Translate UI strings according to the active language."""
        self.title.setText(QCoreApplication.translate("SkullStrippingPage", "Select a NIfTI file for Skull Stripping"))
        if self.has_bet:
            self.f_label.setText(QCoreApplication.translate("SkullStrippingPage", "Fractional intensity threshold, smaller values give larger brain outline estimates"))
            self.advanced_btn.setText(QCoreApplication.translate("SkullStrippingPage", "Show Advanced Options"))
            self.output_label.setText(QCoreApplication.translate("SkullStrippingPage", "Advanced options:"))
            self.opt_brain_extracted.setText(QCoreApplication.translate("SkullStrippingPage", "Output brain-extracted image"))
            self.opt_m.setText(QCoreApplication.translate("SkullStrippingPage", "Output binary brain mask image"))
            self.opt_t.setText(QCoreApplication.translate("SkullStrippingPage", "Apply thresholding to brain and mask image"))
            self.opt_s.setText(QCoreApplication.translate("SkullStrippingPage", "Output exterior skull surface image"))
            self.opt_o.setText(QCoreApplication.translate("SkullStrippingPage", "Output brain surface overlaid onto original image"))
            self.threshold_label.setText(QCoreApplication.translate("SkullStrippingPage", "Threshold gradient; positive values give larger brain outline at bottom, smaller at top"))
            self.coords_label.setText(QCoreApplication.translate("SkullStrippingPage", "Coordinates (voxels) for centre of initial brain surface sphere"))
        else:
            self.info_label.setToolTip(QCoreApplication.translate("SkullStrippingPage", "Open link"))

        self.run_button.setText(QCoreApplication.translate("SkullStrippingPage", "Run Skull Stripping"))
        self.cancel_button.setText(QCoreApplication.translate("SkullStrippingPage", "Cancel"))
