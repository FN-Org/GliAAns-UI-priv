
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QGridLayout, QHBoxLayout, \
    QMessageBox, QGroupBox, QListWidget, QDialog, QLineEdit, QDialogButtonBox, QListWidgetItem
from PyQt6.QtCore import Qt, QCoreApplication
import os

from components.file_selector_widget import FileSelectorWidget
from ui.ui_dl_execution_page import DlExecutionPage
from page import Page
from logger import get_logger

log = get_logger()


class DlNiftiSelectionPage(Page):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self._setup_ui()

        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.title = QLabel("Select NIfTI files for Deep Learning Segmentation")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        self.file_selector_widget = FileSelectorWidget(parent=self,
                                                       context=self.context,
                                                       has_existing_function=self.has_existing_segmentation,
                                                       label="seg",
                                                       allow_multiple=True)
        self.layout.addWidget(self.file_selector_widget)

        # Aggiungi uno stretch solo alla fine se vuoi che tutto sia in alto
        self.layout.addStretch()

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)

    def has_existing_segmentation(self, nifti_file_path, workspace_path):
        """
        Check if segmentation already exists for the patient of this NIfTI file.
        """
        # Extract patient ID from file path
        path_parts = nifti_file_path.replace(workspace_path, '').strip(os.sep).split(os.sep)

        # Find the part that starts with 'sub-'
        subject_id = None
        for part in path_parts:
            if part.startswith('sub-'):
                subject_id = part
                break

        if not subject_id:
            return False

        # Build the path where segmentation should be
        seg_dir = os.path.join(workspace_path, 'derivatives', 'deep_learning_seg', subject_id, 'anat')

        # Check if directory exists
        if not os.path.exists(seg_dir):
            return False

        # Check if *_seg.nii.gz files exist in the directory
        for file in os.listdir(seg_dir):
            if file.endswith('_seg.nii.gz') or file.endswith('_seg.nii'):
                return True

        return False

    def back(self):
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def next(self, context):
        """
        Salva i file selezionati nel contesto e avanza alla pagina successiva.
        """
        # Mettiamo i file selezionati nel contesto
        if self.context is not None:
            self.context["selected_segmentation_files"] = self.file_selector_widget.get_selected_files()

        # Se la pagina successiva non è ancora stata creata, la instanziamo
        if not self.next_page:
            self.next_page = DlExecutionPage(self.context, self)
            if "history" in self.context:
                self.context["history"].append(self.next_page)

        # Prepariamo la prossima pagina
        self.next_page.on_enter()
        return self.next_page

    def on_enter(self):
        self.status_label.setText("")

    def is_ready_to_advance(self):
        return bool(self.file_selector_widget.get_selected_files())

    def is_ready_to_go_back(self):
        return True

    def reset_page(self):
        """Resets the page to its initial state, clearing all selections"""
        self.file_selector_widget._selected_files = []

        # Clear status message
        self.status_label.setText("")

        # Clear from context
        if self.context:
            self.context["selected_segmentation_files"] = []

    def _translate_ui(self):
        self.title.setText(QCoreApplication.translate("DlSelectionPage", "Select NIfTI files for Deep Learning Segmentation"))

