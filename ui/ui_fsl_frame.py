from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QCheckBox, QGroupBox, QFormLayout, QDialogButtonBox, QDialog, QTreeView
)
from PyQt6.QtCore import Qt
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

        # Pulsante per aprire treeview
        self.file_button = QPushButton("Choose NIfTI File")
        self.file_button.clicked.connect(self.open_tree_dialog)
        self.layout.addWidget(self.file_button)

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
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)

        model = QFileSystemModel()
        model.setRootPath(self.context.workspace_path)
        model.setNameFilters(["*.nii", "*.nii.gz"])
        model.setNameFilterDisables(False)

        view = QTreeView()
        view.setModel(model)
        view.setRootIndex(model.index(self.context.workspace_path))
        view.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        view.setColumnWidth(0, 300)

        layout.addWidget(view)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def accept():
            index = view.currentIndex()
            if not index.isValid() or model.isDir(index):
                QMessageBox.warning(dialog, "Invalid selection", "Please select a valid NIfTI file.")
                return
            file_path = model.filePath(index)
            self.selected_file = file_path
            self.file_button.setText(f"Selected: {os.path.basename(file_path)}")
            self.context.controller.update_buttons_state()
            dialog.accept()

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)

        dialog.exec()

    def toggle_advanced(self):
        is_checked = self.advanced_btn.isChecked()
        self.advanced_box.setVisible(is_checked)
        self.advanced_btn.setText("Hide Advanced Options" if is_checked else "Show Advanced Options")

    def run_bet(self):
        if not self.selected_file:
            QMessageBox.warning(self, "No file", "Please select a NIfTI file first.")
            return

        base, ext = os.path.splitext(self.selected_file)
        if ext == ".gz":
            base = os.path.splitext(base)[0]

        output_file = base + "_brain.nii.gz"

        # Costruzione comando
        cmd = ["bet", self.selected_file, output_file]

        # Parametri principali
        f_val = self.f_input.text()
        if f_val:
            cmd += ["-f", f_val]

        # Opzioni avanzate
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
                QMessageBox.warning(self, "Invalid center", "Use format: x y z")
                return
        if self.A2_input.text():
            cmd += ["-A2", self.A2_input.text()]

        try:
            subprocess.run(cmd, check=True)
            self.status_label.setText(f"BET completed:\n{output_file}")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "BET failed", str(e))
            self.status_label.setText("BET failed.")

    def on_enter(self, controller):
        self.status_label.setText("")  # Reset

    def is_ready_to_advance(self):
        return False  # Ultima pagina

    def is_ready_to_go_back(self):
        return True