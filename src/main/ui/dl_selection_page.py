from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGridLayout, QHBoxLayout,
    QMessageBox, QGroupBox, QListWidget, QDialog, QLineEdit, QDialogButtonBox, QListWidgetItem
)
from PyQt6.QtCore import Qt, QCoreApplication
import os

from components.file_selector_widget import FileSelectorWidget
from ui.dl_execution_page import DlExecutionPage
from page import Page
from logger import get_logger

log = get_logger()


class DlNiftiSelectionPage(Page):
    """
    GUI page that allows the user to select NIfTI files for Deep Learning-based segmentation.

    This page is part of a multi-step workflow:
    - Displays a title and a FileSelectorWidget to pick one or more NIfTI files.
    - Checks if a segmentation already exists for a given subject.
    - Saves selections in a shared context and navigates to the next page (DlExecutionPage).
    """

    def __init__(self, context=None, previous_page=None):
        """
        Initialize the patient selection page.

        :param context: Shared application context dictionary (used for data persistence between pages)
        :param previous_page: Reference to the previous Page object (for navigation)
        """
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None  # Will be created when advancing

        self._setup_ui()
        self._translate_ui()

        # Re-translate the UI dynamically if the language changes in the context
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def _setup_ui(self):
        """Create and organize all UI elements for this page."""
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        # Title label
        self.title = QLabel("Select NIfTI files for Deep Learning Segmentation")
        self.title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        # Widget for selecting NIfTI files
        # - `has_existing_function` allows pre-checking if a segmentation already exists
        self.file_selector_widget = FileSelectorWidget(
            parent=self,
            context=self.context,
            has_existing_function=self.has_existing_segmentation,
            label="seg",
            allow_multiple=True
        )
        self.layout.addWidget(self.file_selector_widget)

        # Pushes everything upward visually
        self.layout.addStretch()

        # Label for displaying temporary status or messages
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)

    def has_existing_segmentation(self, nifti_file_path, workspace_path):
        """
        Check if a deep learning segmentation already exists for the patient corresponding to this NIfTI file.

        :param nifti_file_path: Full path to the selected NIfTI file.
        :param workspace_path: Root path of the working directory.
        :return: True if a segmentation file is already present, otherwise False.
        """
        # Extract patient ID (subject ID) from the NIfTI file path
        path_parts = nifti_file_path.replace(workspace_path, '').strip(os.sep).split(os.sep)

        # Look for a directory segment starting with 'sub-' (BIDS convention)
        subject_id = None
        for part in path_parts:
            if part.startswith('sub-'):
                subject_id = part
                break

        # If no subject identifier found, no segmentation can be associated
        if not subject_id:
            return False

        # Expected directory where segmentations are stored
        seg_dir = os.path.join(workspace_path, 'derivatives', 'deep_learning_seg', subject_id, 'anat')

        # If the segmentation directory does not exist, return False
        if not os.path.exists(seg_dir):
            return False

        # Check for any segmentation file in the directory
        for file in os.listdir(seg_dir):
            if file.endswith('_seg.nii.gz') or file.endswith('_seg.nii'):
                return True

        return False

    def back(self):
        """
        Navigate back to the previous page in the workflow.

        :return: The previous Page instance, or None if there is none.
        """
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def next(self, context):
        """
        Save the selected files in the context and move to the next page (DlExecutionPage).

        :param context: The shared application context dictionary.
        :return: The next Page instance.
        """
        # Store selected files in the context
        if self.context is not None:
            self.context["selected_segmentation_files"] = self.file_selector_widget.get_selected_files()

        # Instantiate the next page only once
        if not self.next_page:
            self.next_page = DlExecutionPage(self.context, self)
            if "history" in self.context:
                self.context["history"].append(self.next_page)

        # Prepare the next page before displaying
        self.next_page.on_enter()
        return self.next_page

    def on_enter(self):
        """Called when the page is shown — resets transient UI elements."""
        self.status_label.setText("")

    def is_ready_to_advance(self):
        """
        Check if the user can proceed to the next page.

        :return: True if one or more files are selected.
        """
        return self.file_selector_widget.get_selected_files()

    def is_ready_to_go_back(self):
        """
        Check if the user can navigate backward.

        :return: Always True for this page.
        """
        return True

    def reset_page(self):
        """
        Reset the page to its initial state, clearing all selections and messages.
        """
        self.file_selector_widget._selected_files = []

        self.status_label.setText("")

        # Clear any saved data in the context
        if self.context:
            self.context["selected_segmentation_files"] = []

    def _translate_ui(self):
        """Apply translations to all text elements in the UI."""
        self.title.setText(QCoreApplication.translate(
            "DlSelectionPage",
            "Select NIfTI files for Deep Learning Segmentation"
        ))
