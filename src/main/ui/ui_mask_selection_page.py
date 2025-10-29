from PyQt6.QtWidgets import (QVBoxLayout, QLabel, QPushButton)
from PyQt6.QtCore import Qt, QCoreApplication
import os

from components.file_selector_widget import FileSelectorWidget
from page import Page
from logger import get_logger

log = get_logger()


class MaskNiftiSelectionPage(Page):
    """
    A page that allows the user to select a NIfTI file for automatic drawing (mask creation).

    This page provides an interface for selecting a NIfTI file and checking
    if a corresponding mask already exists in the workspace directory.
    """

    def __init__(self, context=None, previous_page=None):
        """
        Initialize the NiftiMaskSelectionPage.

        Args:
            context (dict, optional): Shared context object used for communication
                between pages and the main controller.
            previous_page (Page, optional): The previous page in the navigation flow.
        """
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None
        self.selected_file = None

        # Set up the main layout
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        # Title label
        self.title = QLabel("Select a NIfTI file for Automatic Drawing")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        # File selection widget
        self.file_selector_widget = FileSelectorWidget(
            parent=self,
            context=self.context,
            has_existing_function=self.has_existing_mask,
            label="mask",
            allow_multiple=False
        )
        self.layout.addWidget(self.file_selector_widget)

        # Push everything to the top
        self.layout.addStretch()

        # Button to open the NIfTI viewer
        self.viewer_button = QPushButton("Open NIfTI file")
        self.file_selector_widget.has_file.connect(self.viewer_button.setEnabled)
        self.viewer_button.setEnabled(False)
        self.viewer_button.clicked.connect(self.open_nifti_viewer)
        self.layout.addWidget(self.viewer_button)

        # Translation setup for UI text
        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def has_existing_mask(self, nifti_file_path, workspace_path):
        """
        Check if a manual or deep learning mask already exists for the selected NIfTI file.

        Args:
            nifti_file_path (str): Full path to the NIfTI file.
            workspace_path (str): Root workspace directory.

        Returns:
            bool: True if a mask file exists, False otherwise.
        """
        # Extract the subject ID (assuming a path structure like .../sub-XX/anat/sub-XX_modality.nii.gz)
        path_parts = nifti_file_path.replace(workspace_path, '').strip(os.sep).split(os.sep)

        subject_id = None
        for part in path_parts:
            if part.startswith('sub-'):
                subject_id = part
                break

        # If no subject ID is found, assume no mask exists
        if not subject_id:
            return False

        # Build expected paths for manual and deep learning masks
        manual_mask_dir = os.path.join(workspace_path, 'derivatives', 'manual_masks', subject_id, 'anat')
        deep_learning_mask_dir = os.path.join(workspace_path, 'derivatives', 'deep_learning_masks', subject_id, 'anat')

        # If neither directory exists, no mask can exist
        if not os.path.exists(manual_mask_dir) and not os.path.exists(deep_learning_mask_dir):
            return False

        # Check for existing NIfTI mask files (.nii.gz)
        has_nii = False

        if os.path.exists(manual_mask_dir):
            for file in os.listdir(manual_mask_dir):
                if file.endswith('.nii.gz'):
                    has_nii = True
                    break

        if os.path.exists(deep_learning_mask_dir):
            for file in os.listdir(deep_learning_mask_dir):
                if file.endswith('.nii.gz'):
                    has_nii = True
                    break

        return has_nii

    def is_ready_to_advance(self):
        """Return False because this page does not support advancing to the next page."""
        return False

    def is_ready_to_go_back(self):
        """Always allow navigating back to the previous page."""
        return True

    def on_enter(self):
        """Hook called when entering the page (currently does nothing)."""
        pass

    def open_nifti_viewer(self):
        """
        Open the selected NIfTI file in the external viewer defined in the context.

        This method retrieves the selected file and invokes the
        'open_nifti_viewer' function stored in the shared context.
        """
        try:
            file = self.file_selector_widget.get_selected_files()[-1]
            self.context["open_nifti_viewer"](file)
        except Exception:
            log.exception("Error while opening NIfTI viewer")

    def back(self):
        """
        Navigate back to the previous page in the workflow.

        Returns:
            Page | None: The previous page if available, otherwise None.
        """
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def reset_page(self):
        """
        Reset the page to its initial state.

        Clears all file selections and disables the viewer button.
        """
        self.selected_file = None
        self.file_selector_widget.clear_selected_files()
        self.viewer_button.setEnabled(False)

    def _translate_ui(self):
        """
        Update all user-facing text for language changes.

        This method uses Qt’s translation system to localize labels and buttons.
        """
        self.title.setText(QCoreApplication.translate(
            "NiftiMaskSelectionPage", "Select a NIfTI file for Automatic Drawing"
        ))
        self.viewer_button.setText(QCoreApplication.translate(
            "NiftiMaskSelectionPage", "Open NIfTI file"
        ))
