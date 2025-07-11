from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QCheckBox, QGroupBox, QFormLayout, QDialogButtonBox, QDialog, QTreeView, QHBoxLayout,
    QListView, QTextEdit
)
from PyQt6.QtCore import Qt, QSortFilterProxyModel, QStringListModel
import os
import subprocess

from wizard_controller import WizardPage

class SkullStrippingPage(WizardPage):
    def __init__(self, context=None):
        super().__init__()
        self.context = context
        self.selected_file = None

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.label = QLabel("Select a NIfTI file for Skull Stripping")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        # Layout orizzontale per bottone + campo percorso
        file_selector_layout = QHBoxLayout()

        self.file_path_display = QTextEdit()
        self.file_path_display.setReadOnly(True)
        self.file_path_display.setPlaceholderText("No file selected")
        self.file_path_display.setMaximumHeight(80)
        file_selector_layout.addWidget(self.file_path_display, stretch=1)

        self.file_button = QPushButton("Choose NIfTI File")
        self.file_button.clicked.connect(self.open_tree_dialog)
        file_selector_layout.addWidget(self.file_button)

        self.layout.addLayout(file_selector_layout)

        # Parametro principale
        self.f_input = QLineEdit()
        self.f_input.setPlaceholderText("Fractional intensity (-f), default 0.5")
        self.layout.addWidget(self.f_input)

        # Toggle opzioni avanzate
        self.advanced_btn = QPushButton("Show Advanced Options")
        self.advanced_btn.setCheckable(True)
        self.advanced_btn.clicked.connect(self.toggle_advanced)
        self.layout.addWidget(self.advanced_btn)

        # Opzioni avanzate nascoste in un QGroupBox
        self.advanced_box = QGroupBox("Advanced Options")
        self.advanced_layout = QFormLayout()

        # Opzioni a checkbox
        self.opt_o = QCheckBox("Generate brain surface outline (-o)")
        self.opt_m = QCheckBox("Generate binary brain mask (-m)")
        self.opt_s = QCheckBox("Generate approximate skull image (-s)")
        self.opt_n = QCheckBox("Don't output brain image (-n)")
        self.opt_t = QCheckBox("Apply thresholding (-t)")
        self.opt_e = QCheckBox("Generate surface mesh (.vtk) (-e)")
        self.opt_R = QCheckBox("Robust center estimation (-R)")
        self.opt_S = QCheckBox("Eye & optic nerve cleanup (-S)")
        self.opt_B = QCheckBox("Bias field & neck cleanup (-B)")
        self.opt_Z = QCheckBox("FOV padding in Z (-Z)")
        self.opt_F = QCheckBox("FMRI mode (-F)")
        self.opt_A = QCheckBox("Betsurf with skull/scalp surfaces (-A)")
        self.opt_v = QCheckBox("Verbose mode (-v)")

        # Opzioni con parametri
        self.g_input = QLineEdit()
        self.g_input.setPlaceholderText("Vertical gradient (-g), default 0")

        self.r_input = QLineEdit()
        self.r_input.setPlaceholderText("Head radius (-r) in mm")

        self.c_input = QLineEdit()
        self.c_input.setPlaceholderText("Centre of gravity (-c) x y z")

        self.A2_input = QLineEdit()
        self.A2_input.setPlaceholderText("T2 image path for -A2")

        # Aggiungi tutto
        for widget in [
            self.opt_o, self.opt_m, self.opt_s, self.opt_n,
            self.opt_t, self.opt_e, self.opt_R, self.opt_S,
            self.opt_B, self.opt_Z, self.opt_F, self.opt_A,
            self.opt_v,
            self.g_input, self.r_input, self.c_input, self.A2_input
        ]:
            self.advanced_layout.addRow(widget)

        self.advanced_box.setLayout(self.advanced_layout)
        self.advanced_box.setVisible(False)
        self.layout.addWidget(self.advanced_box)

        # Bottone RUN
        self.run_button = QPushButton("Run Skull Stripping (FSL BET)")
        self.run_button.clicked.connect(self.run_bet)
        self.layout.addWidget(self.run_button)

        # Stato
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)

    def open_tree_dialog(self):

        dialog = QDialog(self)
        dialog.setWindowTitle("Select a NIfTI file from workspace")
        dialog.resize(600, 500)

        layout = QVBoxLayout(dialog)

        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search (e.g., FLAIR)")
        layout.addWidget(QLabel("Search:"))
        layout.addWidget(search_bar)

        # 🔍 Scansione ricorsiva di tutti i file .nii / .nii.gz nel workspace
        nii_files = []
        for root, dirs, files in os.walk(self.context.workspace_path):
            for f in files:
                if f.endswith((".nii", ".nii.gz")):
                    full_path = os.path.join(root, f)
                    nii_files.append(full_path)

        # Modello semplice di stringhe
        model = QStringListModel(nii_files)

        # Filtro
        proxy = QSortFilterProxyModel()
        proxy.setSourceModel(model)
        proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        view = QListView()
        view.setModel(proxy)
        view.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        layout.addWidget(view)

        # Collegamento della search bar
        search_bar.textChanged.connect(proxy.setFilterFixedString)

        # Pulsanti
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def accept():
            indexes = view.selectionModel().selectedIndexes()
            if not indexes:
                QMessageBox.warning(dialog, "No selection", "Please select at least one NIfTI file.")
                return

            selected_files = [proxy.data(index) for index in indexes]
            self.set_selected_files(selected_files)
            dialog.accept()

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)

        dialog.exec()

    def set_selected_files(self, file_paths):
        self.selected_files = file_paths
        if len(file_paths) == 1:
            self.file_path_display.setPlainText(file_paths[0])
        else:
            self.file_path_display.setPlainText("\n".join(file_paths))
        self.file_button.setText("Choose NIfTI Files")
        self.context.controller.update_buttons_state()

    # def set_selected_file(self, file_path):
    #     self.selected_file = file_path
    #     self.file_path_display.setText(file_path)
    #     self.file_button.setText("Choose NIfTI File")
    #     self.context.controller.update_buttons_state()

    def toggle_advanced(self):
        is_checked = self.advanced_btn.isChecked()
        self.advanced_box.setVisible(is_checked)
        self.advanced_btn.setText("Hide Advanced Options" if is_checked else "Show Advanced Options")

    def run_bet(self):
        if not self.selected_files:
            QMessageBox.warning(self, "No files", "Please select at least one NIfTI file first.")
            return

        success_count = 0
        failed_files = []

        for nifti_file in self.selected_files:
            base, ext = os.path.splitext(nifti_file)
            if ext == ".gz":
                base = os.path.splitext(base)[0]
            output_file = base + "_brain.nii.gz"

            cmd = ["bet", nifti_file, output_file]

            f_val = self.f_input.text()
            if f_val:
                cmd += ["-f", f_val]

            if self.opt_o.isChecked(): cmd.append("-o")
            if self.opt_m.isChecked(): cmd.append("-m")
            if self.opt_s.isChecked(): cmd.append("-s")
            if self.opt_n.isChecked(): cmd.append("-n")
            if self.opt_t.isChecked(): cmd.append("-t")
            if self.opt_e.isChecked(): cmd.append("-e")
            if self.opt_R.isChecked(): cmd.append("-R")
            if self.opt_S.isChecked(): cmd.append("-S")
            if self.opt_B.isChecked(): cmd.append("-B")
            if self.opt_Z.isChecked(): cmd.append("-Z")
            if self.opt_F.isChecked(): cmd.append("-F")
            if self.opt_A.isChecked(): cmd.append("-A")
            if self.opt_v.isChecked(): cmd.append("-v")

            if self.g_input.text():
                cmd += ["-g", self.g_input.text()]
            if self.r_input.text():
                cmd += ["-r", self.r_input.text()]
            if self.c_input.text():
                coords = self.c_input.text().strip().split()
                if len(coords) == 3:
                    cmd += ["-c"] + coords
                else:
                    QMessageBox.warning(self, "Invalid center", f"Invalid center for {nifti_file}: use format x y z")
                    return
            if self.A2_input.text():
                cmd += ["-A2", self.A2_input.text()]

            try:
                subprocess.run(cmd, check=True)
                success_count += 1
            except subprocess.CalledProcessError:
                failed_files.append(nifti_file)

        summary = f"Skull Stripping completed: {success_count} succeeded"
        if failed_files:
            summary += f"\nFailed files:\n" + "\n".join(failed_files)

        self.status_label.setText(summary)

    def on_enter(self, controller):
        self.status_label.setText("")  # Reset

        self.controller = controller
        self.controller.update_buttons_state()
        controller.previous_page_index = 2

    def is_ready_to_advance(self):
        return False  # Ultima pagina

    def is_ready_to_go_back(self):
        return True