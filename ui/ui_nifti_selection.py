import re
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
    QHBoxLayout, QDialog, QLineEdit, QListView, QDialogButtonBox, QComboBox, QSpinBox, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, QStringListModel, QSortFilterProxyModel
from PyQt6.QtGui import QIcon
import os

from components.nifti_file_selector import NiftiFileDialog
from ui.ui_nifti_viewer import NiftiViewer
from wizard_state import WizardPage
from logger import get_logger

log = get_logger()


class NiftiSelectionPage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.selected_file = None

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.title = QLabel("Select a NIfTI file for Manual/Automatic Drawing")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        # Layout orizzontale per lista + bottoni
        list_button_layout = QHBoxLayout()

        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.file_list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.file_list_widget.setMaximumHeight(60)
        list_button_layout.addWidget(self.file_list_widget, stretch=1)

        # Contenitore per centrare verticalmente i bottoni
        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.addStretch()

        self.file_button = QPushButton("Choose NIfTI File")
        self.file_button.clicked.connect(self.open_tree_dialog)
        button_layout.addWidget(self.file_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_selected_file)
        button_layout.addWidget(self.clear_button, alignment=Qt.AlignmentFlag.AlignCenter)

        button_layout.addStretch()
        list_button_layout.addWidget(button_container)
        self.layout.addLayout(list_button_layout)

        # Bottone open NIfTI viewer
        self.viewer_button = QPushButton("Open NIfTI file")
        self.viewer_button.setEnabled(False)
        self.viewer_button.clicked.connect(self.open_nifti_viewer)
        self.layout.addWidget(self.viewer_button)

        # Aggiungi uno stretch solo alla fine se vuoi che tutto sia in alto
        self.layout.addStretch()

    def has_existing_mask(self, nifti_file_path, workspace_path):
        """
        Controlla se per il paziente di questo file NIfTI esiste già una mask.

        Args:
            nifti_file_path (str): Percorso completo al file NIfTI
            workspace_path (str): Percorso del workspace

        Returns:
            bool: True se esiste già una mask, False altrimenti
        """
        # Estrai l'ID del paziente dal percorso del file
        # Assumo una struttura tipo: .../sub-XX/anat/sub-XX_modality.nii.gz
        path_parts = nifti_file_path.replace(workspace_path, '').strip(os.sep).split(os.sep)

        # Cerca la parte che inizia con 'sub-'
        subject_id = None
        for part in path_parts:
            if part.startswith('sub-'):
                subject_id = part
                break

        if not subject_id:
            # Se non riesco a identificare il subject ID, assumo che non ci sia mask
            return False

        # Costruisci il percorso dove dovrebbe essere la mask
        mask_dir = os.path.join(workspace_path, 'derivatives', 'manual_masks', subject_id, 'anat')

        # Controlla se la directory esiste
        if not os.path.exists(mask_dir):
            return False

        # Controlla se esistono file .nii.gz
        has_nii = False

        for file in os.listdir(mask_dir):
            if file.endswith('.nii.gz'):
                has_nii = True
                break

        # Ritorna True solo se esistono entrambi i tipi di file
        return has_nii

    def open_tree_dialog(self):
        result = NiftiFileDialog.get_files(
            self,
            self.context["workspace_path"],
            allow_multiple=False,
            has_existing_func=self.has_existing_mask,
            label="mask"
        )
        if result:
            self.set_selected_file(result[0])


    def set_selected_file(self, file_path):
        """
        Imposta il file selezionato (il warning è ora gestito nel dialog di selezione).
        """
        self.selected_file = file_path
        self.file_list_widget.clear()
        item = QListWidgetItem(QIcon.fromTheme("document"), os.path.basename(file_path))
        item.setToolTip(file_path)
        self.file_list_widget.addItem(item)

        self.clear_button.setEnabled(True)
        self.viewer_button.setEnabled(True)

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def clear_selected_file(self):
        self.selected_file = None
        self.file_list_widget.clear()
        self.clear_button.setEnabled(False)
        self.viewer_button.setEnabled(False)

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def update_selected_files(self, files):
        """
        Aggiorna i file selezionati e mostra warning se esistono mask per i pazienti.
        """
        self.selected_file = None
        self.file_list_widget.clear()

        for path in files:
            if path.endswith(".nii") or path.endswith(".nii.gz"):
                # Controlla se esiste già una mask per questo paziente
                if self.has_existing_mask(path, self.context["workspace_path"]):
                    # Estrai l'ID del paziente per il messaggio
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

                    # Mostra il warning
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("Existing Mask Detected")
                    msg.setText(f"A mask already exists for {subject_display}.")
                    msg.setInformativeText(
                        f"File: {os.path.basename(path)}\n\n"
                        "You can still proceed to create additional masks for this patient.\n"
                        "Do you want to continue with this selection?"
                    )
                    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                    # Se l'utente sceglie No, salta questo file
                    if msg.exec() == QMessageBox.StandardButton.No:
                        continue

                # Procedi con la selezione
                item = QListWidgetItem(QIcon.fromTheme("document"), os.path.basename(path))
                item.setToolTip(path)
                self.file_list_widget.addItem(item)
                self.selected_file = path
                self.clear_button.setEnabled(True)
                self.viewer_button.setEnabled(True)
                break  # Visualize just the first choice

        if not self.selected_file:
            self.clear_button.setEnabled(False)
            self.viewer_button.setEnabled(False)

    def is_ready_to_advance(self):
        return False

    def is_ready_to_go_back(self):
        return True

    def on_enter(self):
        pass

    def open_nifti_viewer(self):
        if "nifti_viewer" in self.context and self.context["nifti_viewer"]:
            self.context["nifti_viewer"].open_file(self.selected_file)
            self.context["nifti_viewer"].show()
            pass
        else:
            self.context["nifti_viewer"] = NiftiViewer(self.context)
            self.context["nifti_viewer"].open_file(self.selected_file)
            self.context["nifti_viewer"].show()
            pass

    def back(self):
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page

        return None

    def reset_page(self):
        """Resets the page to its initial state, clearing all selections"""
        # Clear selected file
        self.selected_file = None
        self.file_list_widget.clear()

        # Reset buttons state
        self.clear_button.setEnabled(False)
        self.viewer_button.setEnabled(False)