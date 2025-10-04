import os

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QPushButton, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QCoreApplication

from components.nifti_file_selector import NiftiFileDialog


class FileSelectorWidget(QWidget):
    has_file = pyqtSignal(bool)
    def __init__(self, context, has_existing_function, label, allow_multiple, processing=None, forced_filters=None, parent=None):
        super().__init__(parent)

        self.context = context
        self.context["selected_files_signal"].connect(self.set_selected_files)
        self.label = label
        self.allow_multiple = allow_multiple
        self.has_existing_function = has_existing_function
        if processing:
            processing.connect(self.set_processing_mode)
        self.forced_filters = forced_filters

        self.selected_files = None
        # Layout principale
        file_selector_layout = QHBoxLayout(self)
        self.setLayout(file_selector_layout)

        # Lista file
        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.file_list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.file_list_widget.setMaximumHeight(100)
        file_selector_layout.addWidget(self.file_list_widget, stretch=1)

        # Contenitore bottoni
        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)

        button_layout.addStretch()

        # Bottone scelta file
        self.file_button = QPushButton("Choose NIfTI File(s)")
        self.file_button.clicked.connect(self.open_tree_dialog)
        button_layout.addWidget(self.file_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # Bottone per pulire selezione
        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_selected_files)
        button_layout.addWidget(self.clear_button, alignment=Qt.AlignmentFlag.AlignCenter)

        button_layout.addStretch()

        file_selector_layout.addWidget(button_container)

        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def open_tree_dialog(self):
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
                self.set_selected_files([results[0]])

    def clear_selected_files(self):
        self.selected_files = []
        self.file_list_widget.clear()
        self.clear_button.setEnabled(False)
        self.has_file.emit(False)

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def set_selected_files(self, file_paths):
        if self.allow_multiple:
            file_paths = [file for file in file_paths if os.path.exists(file) and not os.path.isdir(file) and (file.endswith('.nii.gz') or file.endswith('.nii'))]
        else: file_paths = [file_paths[-1]]
        self.selected_files = file_paths
        self.file_list_widget.clear()

        for path in file_paths:
            item = QListWidgetItem(QIcon.fromTheme("document"), os.path.basename(path))
            item.setToolTip(path)
            self.file_list_widget.addItem(item)

        self.clear_button.setEnabled(bool(file_paths))
        self.has_file.emit(bool(file_paths))
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def get_selected_files(self):
        return self.selected_files

    def set_processing_mode(self,processing):
        self.file_button.setEnabled(not processing)
        self.clear_button.setEnabled(not processing and bool(self.selected_files))

    def _translate_ui(self):
        self.file_button.setText(QCoreApplication.translate("Components", "Choose NIfTI File(s)"))
        self.clear_button.setText(QCoreApplication.translate("Components", "Clear Selection"))