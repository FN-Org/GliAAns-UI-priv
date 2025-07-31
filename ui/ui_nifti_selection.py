from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
    QHBoxLayout, QDialog, QLineEdit, QListView, QDialogButtonBox, QComboBox, QSpinBox, QGroupBox
)
from PyQt6.QtCore import Qt, QStringListModel, QSortFilterProxyModel
from PyQt6.QtGui import QIcon
import os

from ui.ui_nifti_viewer import NiftiViewer
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

        selector_layout = QVBoxLayout()

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
        selector_layout.addLayout(list_button_layout)

        # Bottone open NIfTI viewer
        self.viewer_button = QPushButton("Open NIfTI file")
        self.viewer_button.setEnabled(False)
        self.viewer_button.clicked.connect(self.open_nifti_viewer)
        selector_layout.addWidget(self.viewer_button)

        self.layout.addLayout(selector_layout)

        # Sezione VOI (inizialmente nascosta)
        self.voi_section = self.create_voi_section()
        self.voi_section.setVisible(False)
        self.layout.addWidget(self.voi_section)

        # Aggiungi uno stretch solo alla fine se vuoi che tutto sia in alto
        self.layout.addStretch()

    def open_nifti_viewer(self):
        self.voi_section.setVisible(not self.voi_section.isVisible())


    def create_voi_section(self):
        group_box = QGroupBox("Create ROI")
        layout = QVBoxLayout()

        # Reset origin
        reset_button = QPushButton("Reset origin")
        layout.addWidget(reset_button, alignment=Qt.AlignmentFlag.AlignLeft)

        # Difference from origin
        diff_layout = QHBoxLayout()
        diff_layout.addWidget(QLabel("Difference from origin"))
        self.diff_spinbox = QSpinBox()
        self.diff_spinbox.setRange(0, 999)
        self.diff_spinbox.setValue(16)
        diff_layout.addWidget(self.diff_spinbox)
        layout.addLayout(diff_layout)

        # Radius
        radius_layout = QHBoxLayout()
        radius_layout.addWidget(QLabel("Radius (mm)"))
        self.radius_spinbox = QSpinBox()
        self.radius_spinbox.setRange(0, 999)
        self.radius_spinbox.setValue(32)
        radius_layout.addWidget(self.radius_spinbox)
        layout.addLayout(radius_layout)

        # Combo box
        self.voi_mode_combo = QComboBox()
        self.voi_mode_combo.addItems([
            "Append to current VOI",
            "Delete from current VOI",
            "Constrain with current VOI"
        ])
        layout.addWidget(self.voi_mode_combo)

        # Cancel / Apply buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Apply)
        button_box.rejected.connect(self.cancel_voi)
        button_box.accepted.connect(self.apply_voi)
        layout.addWidget(button_box)

        group_box.setLayout(layout)
        return group_box

    def cancel_voi(self):
        self.voi_section.setVisible(False)

    def apply_voi(self):
        radius = self.radius_spinbox.value()
        diff = self.diff_spinbox.value()
        mode = self.voi_mode_combo.currentText()

        QMessageBox.information(
            self,
            "ROI Created",
            f"Radius: {radius} mm\nDiff: {diff}\nMode: {mode}"
        )

    def open_tree_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select a NIfTI file from workspace")
        dialog.resize(600, 500)

        layout = QVBoxLayout(dialog)

        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search (e.g., T1, FLAIR, etc.)")
        layout.addWidget(QLabel("Search:"))
        layout.addWidget(search_bar)

        nii_files = []
        for root, dirs, files in os.walk(self.context["workspace_path"]):
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
        self.selected_file = None
        self.file_list_widget.clear()

        for path in files:
            if path.endswith(".nii") or path.endswith(".nii.gz"):
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

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def is_ready_to_advance(self):
        return False

    def is_ready_to_go_back(self):
        return True

    def on_exit(self):
        pass

    def back(self):
        if self.previous_page:
            self.on_exit()
            return self.previous_page

        return None
