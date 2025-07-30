from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
    QHBoxLayout, QDialog, QLineEdit, QListView, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QStringListModel, QSortFilterProxyModel
from PyQt6.QtGui import QIcon
import os

from wizard_state import WizardPage


class NiftiSelectionPage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.selected_file = None

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.label = QLabel("Select a NIfTI file for Manual/Automatic Drawing")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        # Layout orizzontale per bottone + visualizzazione file selezionato
        selector_layout = QHBoxLayout()

        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.file_list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.file_list_widget.setMaximumHeight(60)
        selector_layout.addWidget(self.file_list_widget, stretch=1)

        self.file_button = QPushButton("Choose NIfTI File")
        self.file_button.clicked.connect(self.open_tree_dialog)
        selector_layout.addWidget(self.file_button)

        self.layout.addLayout(selector_layout)

    def on_enter(self, controller):
        self.controller = controller
        self.controller.next_page_index = 4
        self.controller.previous_page_index = 2
        self.selected_file = None
        self.file_list_widget.clear()
        self.context.controller.update_buttons_state()

    def open_tree_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select a NIfTI file from workspace")
        dialog.resize(600, 500)

        layout = QVBoxLayout(dialog)

        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search (e.g., T1, FLAIR, etc.)")
        layout.addWidget(QLabel("Search:"))
        layout.addWidget(search_bar)

        # Lista di tutti i NIfTI file nel workspace
        nii_files = []
        for root, dirs, files in os.walk(self.context.workspace_path):
            for f in files:
                if f.endswith((".nii", ".nii.gz")):
                    nii_files.append(os.path.join(root, f))

        model = QStringListModel(nii_files)
        proxy = QSortFilterProxyModel()
        proxy.setSourceModel(model)
        proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        view = QListView()
        view.setModel(proxy)
        view.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        layout.addWidget(view)

        search_bar.textChanged.connect(proxy.setFilterFixedString)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def accept():
            indexes = view.selectionModel().selectedIndexes()
            if not indexes:
                QMessageBox.warning(dialog, "No selection", "Please select a NIfTI file.")
                return
            selected_path = proxy.data(indexes[0])
            self.set_selected_file(selected_path)
            dialog.accept()

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)

        dialog.exec()

    def set_selected_file(self, file_path):
        self.selected_file = file_path
        self.file_list_widget.clear()
        item = QListWidgetItem(QIcon.fromTheme("document"), os.path.basename(file_path))
        item.setToolTip(file_path)
        self.file_list_widget.addItem(item)
        self.context.controller.update_buttons_state()

    def is_ready_to_advance(self):
        return self.selected_file is not None

    def is_ready_to_go_back(self):
        return True

    def on_exit(self, controller):
        if self.selected_file:
            self.context.selected_nifti_path = self.selected_file
