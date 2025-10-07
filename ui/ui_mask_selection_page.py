
from PyQt6.QtWidgets import (QVBoxLayout, QLabel, QPushButton,)
from PyQt6.QtCore import Qt, QCoreApplication

import os

from components.file_selector_widget import FileSelectorWidget
from page import Page
from logger import get_logger

log = get_logger()


class MaskNiftiSelectionPage(Page):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.selected_file = None

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.title = QLabel("Select a NIfTI file for Automatic Drawing")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        self.file_selector_widget = FileSelectorWidget(parent=self,
                                                       context=self.context,
                                                       has_existing_function=self.has_existing_mask,
                                                       label="mask",
                                                       allow_multiple=False)
        self.layout.addWidget(self.file_selector_widget)

        # Aggiungi uno stretch solo alla fine se vuoi che tutto sia in alto
        self.layout.addStretch()

        # Bottone open NIfTI viewer
        self.viewer_button = QPushButton("Open NIfTI file")
        self.file_selector_widget.has_file.connect(self.viewer_button.setEnabled)
        self.viewer_button.setEnabled(False)
        self.viewer_button.clicked.connect(self.open_nifti_viewer)
        self.layout.addWidget(self.viewer_button)

        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

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
        manual_mask_dir = os.path.join(workspace_path, 'derivatives', 'manual_masks', subject_id, 'anat')
        deep_learnig_mask_dir = os.path.join(workspace_path, 'derivatives', 'deep_learning_masks', subject_id, 'anat')

        # Controlla se la directory esiste
        if not os.path.exists(manual_mask_dir) and not os.path.exists(deep_learnig_mask_dir):
            return False


        # Controlla se esistono file .nii.gz
        has_nii = False

        if os.path.exists(manual_mask_dir):
            for file in os.listdir(manual_mask_dir):
                if file.endswith('.nii.gz'):
                    has_nii = True
                    break
        if os.path.exists(deep_learnig_mask_dir):
            for file in os.listdir(deep_learnig_mask_dir):
                if file.endswith('.nii.gz'):
                    has_nii = True
                    break

        # Ritorna True solo se esistono entrambi i tipi di file
        return has_nii

    def is_ready_to_advance(self):
        return False

    def is_ready_to_go_back(self):
        return True

    def on_enter(self):
        pass

    def open_nifti_viewer(self):
        try:
            file = self.file_selector_widget.get_selected_files()[-1]
            self.context["open_nifti_viewer"](file)
        except Exception:
            log.exception("Error while opening Nifti viewer")

    def back(self):
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page

        return None

    def reset_page(self):
        """Resets the page to its initial state, clearing all selections"""
        # Clear selected file
        self.selected_file = None
        self.file_selector_widget.clear_selected_files()
        self.viewer_button.setEnabled(False)

    def _translate_ui(self):
        self.title.setText(QCoreApplication.translate("NiftiMaskSelectionPage", "Select a NIfTI file for Automatic Drawing"))
        self.viewer_button.setText(QCoreApplication.translate("NiftiMaskSelectionPage", "Open NIfTI file"))