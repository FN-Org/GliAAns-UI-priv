import os

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QPushButton, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QCoreApplication

from components.nifti_file_dialog import NiftiFileDialog


class FileSelectorWidget(QWidget):
    """
    Widget for selecting and displaying one or multiple NIfTI files.
    Provides a graphical list of selected files and buttons for choosing or clearing them.
    """

    # Signal emitted when the widget has at least one file selected (True/False)
    has_file = pyqtSignal(bool)

    def __init__(self, context, has_existing_function, label, allow_multiple,
                 processing=None, forced_filters=None, parent=None):
        """
        Initialize the FileSelectorWidget.

        Args:
            context (dict): Shared context containing signals and shared UI functions.
            has_existing_function (callable): Function to check if a file already exists.
            label (str): Label describing the purpose of the file selection.
            allow_multiple (bool): Whether multiple file selection is allowed.
            processing (pyqtSignal, optional): Signal controlling whether buttons are active.
            forced_filters (list[str], optional): File type filters.
            parent (QWidget, optional): Parent widget.
        """
        super().__init__(parent)

        self.context = context
        # Connects external signal for when files are selected from a shared dialog
        if self.context and "selected_files_signal" in self.context:
            self.context["selected_files_signal"].connect(self.set_selected_files)

        self.label = label
        self.allow_multiple = allow_multiple
        self.has_existing_function = has_existing_function
        if processing:
            processing.connect(self.set_processing_mode)
        self.forced_filters = forced_filters

        self.selected_files = None

        # --- Main Layout ---
        file_selector_layout = QHBoxLayout(self)
        self.setLayout(file_selector_layout)

        # --- File list display ---
        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.file_list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.file_list_widget.setMaximumHeight(100)
        file_selector_layout.addWidget(self.file_list_widget, stretch=1)

        # --- Button container (Choose / Clear) ---
        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.addStretch()

        # "Choose file(s)" button — opens NIfTI selection dialog
        self.file_button = QPushButton("Choose NIfTI File(s)")
        self.file_button.clicked.connect(self.open_tree_dialog)
        button_layout.addWidget(self.file_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # "Clear selection" button — removes all selected files
        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_selected_files)
        button_layout.addWidget(self.clear_button, alignment=Qt.AlignmentFlag.AlignCenter)

        button_layout.addStretch()
        file_selector_layout.addWidget(button_container)

        # --- Translation support ---
        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    # -------------------------------------------------------------------------
    # Dialog and file selection
    # -------------------------------------------------------------------------
    def open_tree_dialog(self):
        """
        Opens the NIfTI file selection dialog (tree-based).
        Updates the file list upon user confirmation.
        """
        results = NiftiFileDialog.get_files(
            context=self.context,
            allow_multiple=self.allow_multiple,
            has_existing_func=self.has_existing_function,
            label=self.label,
            forced_filters=self.forced_filters
        )

        if results:
            if self.allow_multiple:
                self.set_selected_files(results)
            else:
                # If single selection only, use the last selected file
                self.set_selected_files([results[0]])

    def clear_selected_files(self):
        """
        Clears all selected files and updates UI state.
        """
        self.selected_files = []
        self.file_list_widget.clear()
        self.clear_button.setEnabled(False)
        self.has_file.emit(False)

        # Notify the main UI to update its state
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def set_selected_files(self, file_paths):
        """
        Updates the internal file list and UI after user selection.

        Args:
            file_paths (list[str]): List of selected file paths.
        """
        if self.allow_multiple:
            # Keep only valid NIfTI files (exclude folders and invalid extensions)
            file_paths = [
                file for file in file_paths
                if os.path.exists(file)
                and not os.path.isdir(file)
                and (file.endswith('.nii.gz') or file.endswith('.nii'))
            ]
        else:
            # If only one file is allowed, keep the last one
            file_paths = [file_paths[-1]]

        self.selected_files = file_paths
        self.file_list_widget.clear()

        # Populate the list widget with file names
        for path in file_paths:
            item = QListWidgetItem(QIcon.fromTheme("document"), os.path.basename(path))
            item.setToolTip(path)
            self.file_list_widget.addItem(item)

        # Enable/disable buttons based on selection
        self.clear_button.setEnabled(bool(file_paths))
        self.has_file.emit(bool(file_paths))

        # Notify main UI of state change
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    # -------------------------------------------------------------------------
    # Accessors and state management
    # -------------------------------------------------------------------------
    def get_selected_files(self):
        """Return the list of selected file paths."""
        return self.selected_files

    def set_processing_mode(self, processing):
        """
        Enable/disable user interaction when the app is processing data.

        Args:
            processing (bool): True to disable file selection during processing.
        """
        self.file_button.setEnabled(not processing)
        self.clear_button.setEnabled(not processing and bool(self.selected_files))
        if processing:
            self.context["selected_files_signal"].disconnect()
        else:
            self.context["selected_files_signal"].connect(self.set_selected_files)

    # -------------------------------------------------------------------------
    # Translation
    # -------------------------------------------------------------------------
    def _translate_ui(self):
        """Apply dynamic UI translations (for multi-language support)."""
        if self.allow_multiple:
            self.file_button.setText(QCoreApplication.translate("Components", "Choose NIfTI File(s)"))
        else:
            self.file_button.setText(QCoreApplication.translate("Components", "Choose NIfTI File"))
        self.clear_button.setText(QCoreApplication.translate("Components", "Clear Selection"))
