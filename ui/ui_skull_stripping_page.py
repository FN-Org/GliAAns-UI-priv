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
from threads.skull_stripping_thread import SkullStripThread
from page import Page
from logger import get_logger

log = get_logger()

class SkullStrippingPage(Page):

    processing = pyqtSignal(bool)
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.canceled = False
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.worker = None  # Per tenere traccia del worker thread

        self.has_cuda = torch.cuda.is_available()

        self._setup_ui()

        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def _setup_ui(self):
        self.processing.connect(self.set_processing_mode)

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.title = QLabel("Select a NIfTI file for Skull Stripping")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

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

        self.file_selector_widget = FileSelectorWidget(parent=self,
                                                       context=self.context,
                                                       has_existing_function=self.has_existing_skull_strip,
                                                       label="skull strip",
                                                       allow_multiple=True,
                                                       processing=self.processing,
                                                       forced_filters={"datatype": "anat"})

        self.layout.addWidget(self.file_selector_widget)

        try:
            # eseguo il comando, senza output a video
            result = subprocess.run(
                ['bet'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # ritorna True se exit code = 0 (successo), False altrimenti
            self.has_bet = True
        except FileNotFoundError:
            # se il comando non esiste proprio
            self.has_bet = False

        if self.has_bet:
            # Parametro principale
            self.f_box = QGroupBox()

            f_layout = QHBoxLayout()
            self.f_label = QLabel(
                "Fractional intensity threshold, smaller values give larger brain outline estimates")
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

            # Toggle opzioni avanzate
            self.advanced_btn = QPushButton("Show Advanced Options")
            self.advanced_btn.setCheckable(True)
            self.advanced_btn.clicked.connect(self.toggle_advanced)
            self.layout.addWidget(self.advanced_btn)

            # Opzioni avanzate nascoste in un QGroupBox
            self.is_checked = False
            self.advanced_box = QGroupBox()
            self.advanced_layout = QVBoxLayout()

            # Sezione 1: Output options (checkboxes)
            self.output_label = QLabel("Advanced options:")
            self.output_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
            self.advanced_layout.addWidget(self.output_label)

            self.opt_brain_extracted = QCheckBox("Output brain-extracted image")
            self.opt_brain_extracted.setChecked(True)  # Checked by default come in FSL
            self.advanced_layout.addWidget(self.opt_brain_extracted)

            self.opt_m = QCheckBox("Output binary brain mask image")
            self.advanced_layout.addWidget(self.opt_m)

            self.opt_t = QCheckBox("Apply thresholding to brain and mask image")
            self.advanced_layout.addWidget(self.opt_t)

            self.opt_s = QCheckBox("Output exterior skull surface image")
            self.advanced_layout.addWidget(self.opt_s)

            self.opt_o = QCheckBox("Output brain surface overlaid onto original image")
            self.advanced_layout.addWidget(self.opt_o)

            # Sezione 2: Threshold gradient
            self.threshold_layout = QHBoxLayout()
            self.threshold_label = QLabel(
                "Threshold gradient; positive values give larger brain outline at bottom, smaller at top")
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

            # Sezione 3: Coordinates
            coords_layout = QHBoxLayout()
            self.coords_label = QLabel("Coordinates (voxels) for centre of initial brain surface sphere")
            coords_layout.addWidget(self.coords_label)

            # X coordinate
            self.c_x_spinbox = QSpinBox()
            self.c_x_spinbox.setRange(0, 9999)
            self.c_x_spinbox.setValue(0)
            self.c_x_spinbox.setMinimumWidth(50)
            self.c_x_spinbox.setMaximumWidth(70)
            coords_layout.addWidget(self.c_x_spinbox)

            coords_layout.addWidget(QLabel("Y"))

            # Y coordinate
            self.c_y_spinbox = QSpinBox()
            self.c_y_spinbox.setRange(0, 9999)
            self.c_y_spinbox.setValue(0)
            self.c_y_spinbox.setMinimumWidth(50)
            self.c_y_spinbox.setMaximumWidth(70)
            coords_layout.addWidget(self.c_y_spinbox)

            coords_layout.addWidget(QLabel("Z"))

            # Z coordinate
            self.c_z_spinbox = QSpinBox()
            self.c_z_spinbox.setRange(0, 9999)
            self.c_z_spinbox.setValue(0)
            self.c_z_spinbox.setMinimumWidth(50)
            self.c_z_spinbox.setMaximumWidth(70)
            coords_layout.addWidget(self.c_z_spinbox)

            coords_layout.addStretch()
            self.advanced_layout.addLayout(coords_layout)

            self.advanced_box.setLayout(self.advanced_layout)
            self.advanced_box.setVisible(False)
            self.layout.addWidget(self.advanced_box)
        else:
            self.info_label.setText(
                'Using tool: <a href="https://github.com/MIC-DKFZ/HD-BET">hd-bet</a> <br>'
                'To use BET from FSL toolkit, you have to be on linux and follow the instructions at: <a href="https://fsl.fmrib.ox.ac.uk/fsl/docs/#/install/index">FSL installation</a>'
            )
            self.info_label.setOpenExternalLinks(True)  # abilita apertura link nel browser
            self.info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            self.info_label.setToolTip("Open link")

        # Progress bar (inizialmente nascosta)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)

        # ===============================
        # Bottoni di esecuzione / annullamento
        # ===============================

        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 15, 0, 0)

        # --- RUN button (verde) ---
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

        # --- CANCEL button (rosso) ---
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

    def has_existing_skull_strip(self, nifti_file_path, workspace_path):
        """
        Controlla se per il paziente di questo file NIfTI esiste già uno skull strip.
        """
        # Estrai l'ID del paziente dal percorso del file
        path_parts = nifti_file_path.replace(workspace_path, '').strip(os.sep).split(os.sep)

        # Cerca la parte che inizia con 'sub-'
        subject_id = None
        for part in path_parts:
            if part.startswith('sub-'):
                subject_id = part
                break

        if not subject_id:
            return False

        # Costruisci il percorso dove dovrebbe essere lo skull strip
        skull_strip_dir = os.path.join(workspace_path, 'derivatives', 'skullstrips', subject_id, 'anat')

        # Controlla se la directory esiste
        if not os.path.exists(skull_strip_dir):
            return False

        # Controlla se esistono file .nii.gz nella directory
        for file in os.listdir(skull_strip_dir):
            if file.endswith('.nii.gz'):
                return True

        return False

    def toggle_advanced(self):
        self.is_checked = self.advanced_btn.isChecked()
        self.advanced_box.setVisible(self.is_checked)
        self.advanced_btn.setText("Hide Advanced Options" if self.is_checked else "Show Advanced Options")

    def run_bet(self):
        """Avvia il processing in background usando QThread"""
        selected_files = self.file_selector_widget.get_selected_files()
        if not selected_files:
            QMessageBox.warning(self, QCoreApplication.translate("SkullStrippingPage", "No files"), QCoreApplication.translate("SkullStrippingPage", "Please select at least one NIfTI file first."))
            return
        parameters = None
        if self.has_bet:
            # Prepara i parametri per il worker
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


        # Crea e configura il worker thread
        self.worker = SkullStripThread(selected_files, self.context["workspace_path"], parameters,self.has_cuda,self.has_bet)

        # Connetti i segnali
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.progress_value_updated.connect(self.on_progress_value_updated)
        self.worker.file_started.connect(self.on_file_started)
        self.worker.file_completed.connect(self.on_file_completed)
        self.worker.all_completed.connect(self.on_all_completed)
        self.worker.finished.connect(self.on_worker_finished)

        # Aggiorna l'interfaccia per lo stato "processing"
        self.processing.emit(True)

        # Configura e mostra la progress bar
        self.progress_bar.setRange(0, 100)  # Cambiato per percentuale
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        # Avvia il worker
        self.worker.start()

    def cancel_processing(self):
        """Cancella il processing in corso"""
        self.canceled = True
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText(QCoreApplication.translate("SkullStrippingPage", "Cancelling..."))
            self.status_label.setStyleSheet("color: #FF9800; font-weight: bold;")

    def set_processing_mode(self, processing):
        """Gestisce lo stato dell'interfaccia durante il processing"""

        # Mostra/nascondi pulsanti coerentemente
        self.run_button.setVisible(not processing)
        self.cancel_button.setVisible(processing)

        # Abilita/disabilita run_button solo quando non stiamo processando
        if not processing:
            has_files = bool(self.file_selector_widget.get_selected_files())
            self.run_button.setEnabled(has_files)

        # Disabilita/abilita controlli parametri
        if hasattr(self, "f_spinbox"):
            self.f_spinbox.setEnabled(not processing)
        if hasattr(self, "advanced_btn"):
            self.advanced_btn.setEnabled(not processing)
        if hasattr(self, "advanced_box"):
            for widget in self.advanced_box.findChildren(QWidget):
                widget.setEnabled(not processing)

    def on_progress_updated(self, message):
        """Aggiorna il messaggio di progresso"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #2196F3; font-weight: bold;")

    def on_progress_value_updated(self, value):
        """Aggiorna il valore numerico della progress bar"""
        self.progress_bar.setValue(value)

    def on_file_started(self, filename):
        """Gestisce l'inizio del processing di un file"""
        # Potresti aggiungere ulteriori feedback qui se necessario
        pass

    def on_file_completed(self, filename, success, error_message):
        """Gestisce il completamento di un singolo file"""
        if not success and error_message:
            # Potresti voler loggare gli errori o mostrarli in una lista
            log.error(f"Error processing {filename}: {error_message}")

    def on_all_completed(self, success_count, failed_files):
        """Gestisce il completamento di tutti i file"""
        # Nascondi progress bar
        self.progress_bar.setVisible(False)

        # Aggiorna il messaggio di stato finale
        if success_count > 0:
            summary = QCoreApplication.translate("SkullStrippingPage", "Skull Stripping completed successfully for {0} file(s)").format(success_count)
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
            summary = QCoreApplication.translate("SkullStrippingPage", "All {0} file(s) failed to process").format(failed_files_num)
            self.status_label.setStyleSheet("color: #FF0000; font-weight: bold; font-size: 12pt; padding: 5px;")

        self.status_label.setText(summary)

    def on_worker_finished(self):
        """Gestisce la fine del worker thread"""
        # Riabilita l'interfaccia
        self.processing.emit(False)

        # Pulisci il worker
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

        # Se ci sono stati successi, aggiorna la UI
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def back(self):
        # Non permettere di tornare indietro durante il processing
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(
                self,
                QCoreApplication.translate("SkullStrippingPage", "Processing in progress"),
                QCoreApplication.translate("SkullStrippingPage", "Cannot go back while skull stripping is in progress. Please wait or cancel the operation."))
            log.warning("Processing in progress")
            return None

        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page

        return None

    def on_enter(self):
        self.status_label.setText("")

    def is_ready_to_advance(self):
        return False

    def is_ready_to_go_back(self):
        # Non permettere di tornare indietro durante il processing
        return not (self.worker and self.worker.isRunning())

    def reset_page(self):
        """Resets the page to its initial state, clearing all selections and parameters"""
        # Cancella il processing se in corso
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()  # Aspetta che il thread finisca

        # Clear selected files
        self.file_selector_widget.clear_selected_files()

        self.run_button.setEnabled(False)

        # Reset main parameter
        self.f_spinbox.setValue(0.50)

        # Reset advanced options
        self.advanced_btn.setChecked(False)
        self.advanced_box.setVisible(False)
        self.advanced_btn.setText(QCoreApplication.translate("SkullStrippingPage", "Show Advanced Options"))

        # Reset advanced checkboxes
        self.opt_brain_extracted.setChecked(True)
        self.opt_m.setChecked(False)
        self.opt_t.setChecked(False)
        self.opt_s.setChecked(False)
        self.opt_o.setChecked(False)

        # Reset advanced parameters
        self.g_spinbox.setValue(0.0)
        self.c_x_spinbox.setValue(0)
        self.c_y_spinbox.setValue(0)
        self.c_z_spinbox.setValue(0)

        # Hide progress bar and cancel button
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)

        # Reset UI state
        self.processing.emit(False)

        # Clear status message
        self.status_label.setText("")

    def _translate_ui(self):
        self.title.setText(QCoreApplication.translate("SkullStrippingPage", "Select a NIfTI file for Skull Stripping"))


        if self.has_bet:
            self.f_label.setText(QCoreApplication.translate("SkullStrippingPage",
                                                            "Fractional intensity threshold, smaller values give larger brain outline estimates"))
            self.advanced_btn.setText(QCoreApplication.translate("SkullStrippingPage", "Show Advanced Options"))
            self.output_label.setText(QCoreApplication.translate("SkullStrippingPage", "Advanced options:"))
            self.opt_brain_extracted.setText(
                QCoreApplication.translate("SkullStrippingPage", "Output brain-extracted image"))
            self.opt_m.setText(QCoreApplication.translate("SkullStrippingFrame", "Output binary brain mask image"))
            self.opt_t.setText(
                QCoreApplication.translate("SkullStrippingFrame", "Apply thresholding to brain and mask image"))
            self.opt_s.setText(QCoreApplication.translate("SkullStrippingFrame", "Output exterior skull surface image"))
            self.opt_o.setText(
                QCoreApplication.translate("SkullStrippingFrame", "Output brain surface overlaid onto original image"))
            self.threshold_label.setText(QCoreApplication.translate("SkullStrippingFrame",
                                                                    "Threshold gradient; positive values give larger brain outline at bottom, smaller at top"))
            self.coords_label.setText(QCoreApplication.translate("SkullStrippingFrame",
                                                                 "Coordinates (voxels) for centre of initial brain surface sphere"))
            self.info_label.setText(QCoreApplication.translate("SkullStrippingFrame", "Using tool: <a href='https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/BET'>BET from FSL toolkit</a>"))
            self.advanced_btn.setText(QCoreApplication.translate("SkullStrippingFrame",
                                                                 "Hide Advanced Options") if self.is_checked else QCoreApplication.translate(
                "SkullStrippingFrame", "Show Advanced Options"))
        else:
            self.info_label.setText(QCoreApplication.translate("SkullStrippingFrame", "Using tool: <a href='https://github.com/MIC-DKFZ/HD-BET'>hd-bet</a> <br>"
                "To use BET from FSL toolkit, you have to be on linux and follow the instructions at: <a href='https://fsl.fmrib.ox.ac.uk/fsl/docs/#/install/index'>FSL installation</a>"
            ))
        self.info_label.setToolTip(QCoreApplication.translate("SkullStrippingFrame", "Open link"))

        self.run_button.setText(QCoreApplication.translate("SkullStrippingFrame", "Run Skull Stripping"))
        self.cancel_button.setText(QCoreApplication.translate("SkullStrippingFrame", "Cancel"))
