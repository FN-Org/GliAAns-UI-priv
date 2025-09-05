import platform
import re
import json


from PyQt6.QtGui import QFileSystemModel, QIcon
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QCheckBox, QDialogButtonBox, QDialog, QHBoxLayout,
    QListWidget, QListWidgetItem, QWidget, QDoubleSpinBox, QSpinBox, QGridLayout, QGroupBox,
    QProgressBar
)
from PyQt6.QtCore import Qt, QSortFilterProxyModel, QStringListModel, QThread, pyqtSignal
import os
import subprocess

from components.nifti_file_selector import NiftiFileDialog
from threads.skull_stripping_thread import SkullStripThread
from wizard_state import WizardPage
from logger import get_logger

log = get_logger()

class SkullStrippingPage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.selected_files = None
        self.worker = None  # Per tenere traccia del worker thread

        self.system_info = self.get_system_info()

        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.title = QLabel("Select a NIfTI file for Skull Stripping")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        file_selector_layout = QHBoxLayout()

        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.file_list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.file_list_widget.setMaximumHeight(100)
        file_selector_layout.addWidget(self.file_list_widget, stretch=1)

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)

        button_layout.addStretch()

        self.file_button = QPushButton("Choose NIfTI File(s)")
        self.file_button.clicked.connect(self.open_tree_dialog)
        button_layout.addWidget(self.file_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_selected_files)
        button_layout.addWidget(self.clear_button, alignment=Qt.AlignmentFlag.AlignCenter)

        button_layout.addStretch()

        file_selector_layout.addWidget(button_container)

        self.layout.addLayout(file_selector_layout)
        if self.system_info["os"] != "Windows":
            # Parametro principale
            self.f_box = QGroupBox()

            f_layout = QHBoxLayout()
            f_label = QLabel(
                "Fractional intensity threshold, smaller values give larger brain outline estimates")
            f_layout.addWidget(f_label)

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
            self.advanced_box = QGroupBox()
            self.advanced_layout = QVBoxLayout()

            # Sezione 1: Output options (checkboxes)
            output_label = QLabel("Advanced options:")
            output_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
            self.advanced_layout.addWidget(output_label)

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
            threshold_layout = QHBoxLayout()
            threshold_label = QLabel(
                "Threshold gradient; positive values give larger brain outline at bottom, smaller at top")
            threshold_layout.addWidget(threshold_label)

            self.g_spinbox = QDoubleSpinBox()
            self.g_spinbox.setRange(-1.0, 1.0)
            self.g_spinbox.setSingleStep(0.1)
            self.g_spinbox.setValue(0.0)
            self.g_spinbox.setDecimals(1)
            self.g_spinbox.setMinimumWidth(60)
            self.g_spinbox.setMaximumWidth(80)
            threshold_layout.addWidget(self.g_spinbox)

            threshold_layout.addStretch()
            self.advanced_layout.addLayout(threshold_layout)

            # Sezione 3: Coordinates
            coords_layout = QHBoxLayout()
            coords_label = QLabel("Coordinates (voxels) for centre of initial brain surface sphere")
            coords_layout.addWidget(coords_label)

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

        # Progress bar (inizialmente nascosta)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)

        # Container per i bottoni Run e Cancel
        button_container = QHBoxLayout()

        # Bottone RUN
        self.run_button = QPushButton("Run Skull Stripping")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.run_bet)
        button_container.addWidget(self.run_button)

        # Bottone CANCEL (inizialmente nascosto)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_processing)
        button_container.addWidget(self.cancel_button)

        self.layout.addLayout(button_container)

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

    def open_tree_dialog(self):
        results = NiftiFileDialog.get_files(
            self,
            self.context["workspace_path"],
            allow_multiple=True,
            has_existing_func=self.has_existing_skull_strip,
            label="skull strip"
        )
        if results:
            self.set_selected_files(results)

    def set_selected_files(self, file_paths):
        self.selected_files = file_paths
        self.file_list_widget.clear()

        for path in file_paths:
            item = QListWidgetItem(QIcon.fromTheme("document"), os.path.basename(path))
            item.setToolTip(path)
            self.file_list_widget.addItem(item)

        self.clear_button.setEnabled(bool(file_paths))
        self.run_button.setEnabled(bool(file_paths))
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def clear_selected_files(self):
        self.selected_files = []
        self.file_list_widget.clear()
        self.clear_button.setEnabled(False)
        self.run_button.setEnabled(False)

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def toggle_advanced(self):
        is_checked = self.advanced_btn.isChecked()
        self.advanced_box.setVisible(is_checked)
        self.advanced_btn.setText("Hide Advanced Options" if is_checked else "Show Advanced Options")

    def run_bet(self):
        """Avvia il processing in background usando QThread"""
        if not hasattr(self, 'selected_files') or not self.selected_files:
            QMessageBox.warning(self, "No files", "Please select at least one NIfTI file first.")
            return
        parameters = None
        if self.system_info["os"] != "Windows":
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
        self.worker = SkullStripThread(self.selected_files, self.context["workspace_path"], parameters,self.system_info)

        # Connetti i segnali
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.progress_value_updated.connect(self.on_progress_value_updated)
        self.worker.file_started.connect(self.on_file_started)
        self.worker.file_completed.connect(self.on_file_completed)
        self.worker.all_completed.connect(self.on_all_completed)
        self.worker.finished.connect(self.on_worker_finished)

        # Aggiorna l'interfaccia per lo stato "processing"
        self.set_processing_mode(True)

        # Configura e mostra la progress bar
        self.progress_bar.setRange(0, 100)  # Cambiato per percentuale
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        # Avvia il worker
        self.worker.start()

    def cancel_processing(self):
        """Cancella il processing in corso"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText("Cancelling...")
            self.status_label.setStyleSheet("color: #FF9800; font-weight: bold;")

    def set_processing_mode(self, processing):
        """Abilita/disabilita controlli durante il processing"""
        # Disabilita/abilita controlli
        self.file_button.setEnabled(not processing)
        self.clear_button.setEnabled(not processing and bool(self.selected_files))
        self.run_button.setEnabled(not processing and bool(self.selected_files))

        if hasattr(self,"f_spinbox"):
            self.f_spinbox.setEnabled(not processing)
        if hasattr(self,"advanced_btn"):
            self.advanced_btn.setEnabled(not processing)

        if hasattr(self,"advanced_box"):
            # Disabilita tutti i controlli avanzati
            for widget in self.advanced_box.findChildren(QWidget):
                widget.setEnabled(not processing)

        # Mostra/nascondi pulsante cancel
        self.cancel_button.setVisible(processing)

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
            summary = f"Skull Stripping completed successfully for {success_count} file(s)"
            if failed_files:
                summary += f"\n{len(failed_files)} file(s) failed: {', '.join([os.path.basename(f) for f in failed_files])}"
                self.status_label.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 12pt; padding: 5px;")
            else:
                self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12pt; padding: 5px;")
        else:
            summary = f"All {len(failed_files)} file(s) failed to process"
            self.status_label.setStyleSheet("color: #FF0000; font-weight: bold; font-size: 12pt; padding: 5px;")

        self.status_label.setText(summary)

        # Se ci sono stati successi, aggiorna la UI
        if success_count > 0:
            if self.context and "update_main_buttons" in self.context:
                self.context["update_main_buttons"]()

    def on_worker_finished(self):
        """Gestisce la fine del worker thread"""
        # Riabilita l'interfaccia
        self.set_processing_mode(False)

        # Pulisci il worker
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def update_selected_files(self, files):
        """
        Aggiorna i file selezionati e mostra warning se esistono skull strip per i pazienti.
        """
        selected_files = []
        files_with_warnings = []

        # Controlla tutti i file NIfTI nella lista
        for path in files:
            if path.endswith(".nii") or path.endswith(".nii.gz"):
                # Controlla se esiste già uno skull strip per questo paziente
                if self.has_existing_skull_strip(path, self.context["workspace_path"]):
                    files_with_warnings.append(path)

                selected_files.append(path)

        # Se ci sono file con warning, mostra il messaggio
        if files_with_warnings:
            if len(files_with_warnings) == 1:
                path = files_with_warnings[0]
                path_parts = path.replace(self.context["workspace_path"], '').strip(os.sep).split(os.sep)
                subject_id = None
                for part in path_parts:
                    if part.startswith('sub-'):
                        subject_id = part
                        break

                if subject_id:
                    subject_display = subject_id
                else:
                    subject_display = "this patient"

                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle("Existing Skull Strip Detected")
                msg.setText(f"A skull strip already exists for {subject_display}.")
                msg.setInformativeText(
                    f"File: {os.path.basename(path)}\n\n"
                    "You can still proceed to create additional skull strips for this patient.\n"
                    "Do you want to continue with this selection?"
                )
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                if msg.exec() == QMessageBox.StandardButton.No:
                    self.selected_files = []
                    self.file_list_widget.clear()
                    self.clear_button.setEnabled(False)
                    self.run_button.setEnabled(False)
                    if self.context and "update_main_buttons" in self.context:
                        self.context["update_main_buttons"]()
                    return
            else:
                subjects_with_strips = set()
                for path in files_with_warnings:
                    path_parts = path.replace(self.context["workspace_path"], '').strip(os.sep).split(os.sep)
                    for part in path_parts:
                        if part.startswith('sub-'):
                            subjects_with_strips.add(part)
                            break

                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle("Existing Skull Strips Detected")
                msg.setText(f"Skull strips already exist for {len(subjects_with_strips)} patients:")

                subject_list = ", ".join(sorted(subjects_with_strips))
                msg.setInformativeText(
                    f"Patients: {subject_list}\n\n"
                    "You can still proceed to create additional skull strips for these patients.\n"
                    "Do you want to continue with this selection?"
                )
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                if msg.exec() == QMessageBox.StandardButton.No:
                    self.selected_files = []
                    self.file_list_widget.clear()
                    self.clear_button.setEnabled(False)
                    self.run_button.setEnabled(False)
                    if self.context and "update_main_buttons" in self.context:
                        self.context["update_main_buttons"]()
                    return

        # Procedi con la selezione normale
        self.selected_files = selected_files
        self.file_list_widget.clear()

        for path in selected_files:
            item = QListWidgetItem(QIcon.fromTheme("document"), os.path.basename(path))
            item.setToolTip(path)
            self.file_list_widget.addItem(item)

        self.clear_button.setEnabled(bool(selected_files))
        self.run_button.setEnabled(bool(selected_files))

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def back(self):
        # Non permettere di tornare indietro durante il processing
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Processing in progress",
                                "Cannot go back while skull stripping is in progress. Please wait or cancel the operation.")
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
        self.selected_files = []
        self.file_list_widget.clear()

        # Reset buttons state
        self.clear_button.setEnabled(False)
        self.run_button.setEnabled(False)

        # Reset main parameter
        self.f_spinbox.setValue(0.50)

        # Reset advanced options
        self.advanced_btn.setChecked(False)
        self.advanced_box.setVisible(False)
        self.advanced_btn.setText("Show Advanced Options")

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
        self.set_processing_mode(False)

        # Clear status message
        self.status_label.setText("")

    def get_system_info(self):
        """
        Raccoglie info sul sistema operativo e GPU disponibili.
        Usa solo librerie standard di Python + quelle che già hai.

        Returns
        -------
        dict
            Informazioni su sistema e GPU.
        """
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "gpus": []
        }

        os_name = info["os"]

        try:
            if os_name == "Windows":
                result = subprocess.check_output(
                    ["wmic", "path", "win32_VideoController", "get", "name"],
                    shell=True
                ).decode(errors="ignore").strip().split("\n")[1:]
                gpus = [gpu.strip() for gpu in result if gpu.strip()]
                info["gpus"] = [{"name": gpu} for gpu in gpus]

            elif os_name == "Linux":
                result = subprocess.check_output("lspci | grep -i vga", shell=True).decode(errors="ignore")
                gpus = [line.strip() for line in result.splitlines() if line.strip()]
                info["gpus"] = [{"name": gpu} for gpu in gpus]

            elif os_name == "Darwin":  # macOS
                result = subprocess.check_output(
                    ["system_profiler", "SPDisplaysDataType"],
                    stderr=subprocess.DEVNULL
                ).decode(errors="ignore")
                gpus = [line.strip().split(":")[-1].strip()
                        for line in result.splitlines() if "Chipset Model" in line]
                info["gpus"] = [{"name": gpu} for gpu in gpus]

        except Exception:
            log.info("Failed to get system info")
            info["gpus"] = []


        return info