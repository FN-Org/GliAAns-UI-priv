from PyQt6.QtGui import QFileSystemModel, QIcon
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QCheckBox, QGroupBox, QFormLayout, QDialogButtonBox, QDialog, QTreeView, QHBoxLayout,
    QListView, QTextEdit, QListWidget, QListWidgetItem, QWidget
)
from PyQt6.QtCore import Qt, QSortFilterProxyModel, QStringListModel
import os
import subprocess

from wizard_state import WizardPage


class SkullStrippingPage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.selected_file = None

        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.label = QLabel("Select a NIfTI file for Skull Stripping")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        file_selector_layout = QHBoxLayout()

        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.file_list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.file_list_widget.setMaximumHeight(100)
        file_selector_layout.addWidget(self.file_list_widget, stretch=1)

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)

        button_layout.addStretch()

        self.file_button = QPushButton("Choose NIfTI File(s)")
        self.file_button.clicked.connect(self.open_tree_dialog)
        button_layout.addWidget(self.file_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_selected_files)
        button_layout.addWidget(self.clear_button, alignment=Qt.AlignmentFlag.AlignCenter)

        button_layout.addStretch()

        file_selector_layout.addWidget(button_container)

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
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.run_bet)
        self.layout.addWidget(self.run_button)

        # Stato
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)

    def has_existing_skull_strip(self, nifti_file_path, workspace_path):
        """
        Controlla se per il paziente di questo file NIfTI esiste già uno skull strip.

        Args:
            nifti_file_path (str): Percorso completo al file NIfTI
            workspace_path (str): Percorso del workspace

        Returns:
            bool: True se esiste già uno skull strip, False altrimenti
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
            # Se non riesco a identificare il subject ID, assumo che non ci sia skull strip
            return False

        # Costruisci il percorso dove dovrebbe essere lo skull strip
        skull_strip_dir = os.path.join(workspace_path, 'derivatives', 'fsl_skullstrip', subject_id, 'anat')

        # Controlla se la directory esiste
        if not os.path.exists(skull_strip_dir):
            return False

        # Controlla se esistono file .nii.gz e .json nella directory
        has_nii = False
        has_json = False

        for file in os.listdir(skull_strip_dir):
            if file.endswith('.nii.gz'):
                has_nii = True
            elif file.endswith('.json'):
                has_json = True

        # Ritorna True solo se esistono entrambi i tipi di file
        return has_nii and has_json

    def open_tree_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select a NIfTI file from workspace")
        dialog.resize(600, 500)

        layout = QVBoxLayout(dialog)

        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search (e.g., FLAIR)")
        layout.addWidget(QLabel("Search:"))
        layout.addWidget(search_bar)

        # Lista di file e dizionario di mappatura
        all_nii_files = []
        relative_to_absolute = {}
        files_with_skull_strips = set()

        for root, dirs, files in os.walk(self.context["workspace_path"]):
            # Ignora la cartella 'derivatives' e tutte le sue sottocartelle
            dirs[:] = [d for d in dirs if d != "derivatives"]

            for f in files:
                if f.endswith((".nii", ".nii.gz")):
                    full_path = os.path.join(root, f)
                    relative_path = os.path.relpath(full_path, self.context["workspace_path"])
                    all_nii_files.append(relative_path)
                    relative_to_absolute[relative_path] = full_path

                    # Segna i file che hanno già uno skull strip
                    if self.has_existing_skull_strip(full_path, self.context["workspace_path"]):
                        files_with_skull_strips.add(relative_path)

        # Info label con legenda colori
        info_text = f"Showing {len(all_nii_files)} files"
        if files_with_skull_strips:
            info_text += f" ({len(files_with_skull_strips)} with existing skull strips shown in yellow)"

        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)

        # Usa QListWidget per avere controllo sui colori
        from PyQt6.QtWidgets import QListWidget
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QBrush, QColor

        file_list = QListWidget()
        file_list.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)  # Permette selezione multipla

        # Aggiungi tutti i file con colori differenziati
        for relative_path in sorted(all_nii_files):
            item = QListWidgetItem(relative_path)

            # Se il file ha già uno skull strip, coloralo in giallo
            if relative_path in files_with_skull_strips:
                item.setForeground(QBrush(QColor(255, 193, 7)))  # Giallo (Bootstrap warning color)
                item.setToolTip(f"{relative_to_absolute[relative_path]}\nThis patient already has a skull strip")
            else:
                item.setToolTip(relative_to_absolute[relative_path])

            file_list.addItem(item)

        layout.addWidget(file_list)

        # Aggiungi filtro di ricerca
        def filter_items():
            search_text = search_bar.text().lower()
            for i in range(file_list.count()):
                item = file_list.item(i)
                item.setHidden(search_text not in item.text().lower())

        search_bar.textChanged.connect(filter_items)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def accept():
            selected_items = file_list.selectedItems()
            if not selected_items:
                QMessageBox.warning(dialog, "No selection", "Please select at least one NIfTI file.")
                return

            selected_files = []
            files_with_warnings = []

            # Processa ogni file selezionato
            for item in selected_items:
                selected_relative_path = item.text()
                selected_absolute_path = relative_to_absolute[selected_relative_path]

                # Se il file selezionato ha già uno skull strip, aggiungilo alla lista dei warning
                if selected_relative_path in files_with_skull_strips:
                    files_with_warnings.append((selected_absolute_path, selected_relative_path))

                selected_files.append(selected_absolute_path)

            # Se ci sono file con warning, mostra il messaggio
            if files_with_warnings:
                if len(files_with_warnings) == 1:
                    # Un solo file con warning
                    selected_absolute_path, selected_relative_path = files_with_warnings[0]

                    # Estrai l'ID del paziente
                    path_parts = selected_absolute_path.replace(self.context["workspace_path"], '').strip(os.sep).split(
                        os.sep)
                    subject_id = None
                    for part in path_parts:
                        if part.startswith('sub-'):
                            subject_id = part
                            break

                    if subject_id:
                        subject_display = subject_id
                    else:
                        subject_display = "this patient"

                    msg = QMessageBox(dialog)
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("Existing Skull Strip Detected")
                    msg.setText(f"A skull strip already exists for {subject_display}.")
                    msg.setInformativeText(
                        f"File: {os.path.basename(selected_absolute_path)}\n\n"
                        "You can still proceed to create additional skull strips for this patient.\n"
                        "Do you want to continue with this selection?"
                    )
                    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                    if msg.exec() == QMessageBox.StandardButton.No:
                        return
                else:
                    # Multipli file con warning
                    subjects_with_strips = set()
                    for selected_absolute_path, _ in files_with_warnings:
                        path_parts = selected_absolute_path.replace(self.context["workspace_path"], '').strip(
                            os.sep).split(os.sep)
                        for part in path_parts:
                            if part.startswith('sub-'):
                                subjects_with_strips.add(part)
                                break

                    msg = QMessageBox(dialog)
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("Existing Skull Strips Detected")
                    msg.setText(f"Skull strips already exist for {len(subjects_with_strips)} patients:")

                    subject_list = ", ".join(sorted(subjects_with_strips))
                    msg.setInformativeText(
                        f"Patients: {subject_list}\n\n"
                        "You can still proceed to create additional skull strips for these patients.\n"
                        "Do you want to continue with this selection?"
                    )
                    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                    if msg.exec() == QMessageBox.StandardButton.No:
                        return

            # Procedi con la selezione
            self.set_selected_files(selected_files)
            dialog.accept()

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)

        dialog.exec()

    def set_selected_files(self, file_paths):
        self.selected_files = file_paths
        self.file_list_widget.clear()

        for path in file_paths:
            item = QListWidgetItem(QIcon.fromTheme("document"), os.path.basename(path))
            item.setToolTip(path)
            self.file_list_widget.addItem(item)

        self.clear_button.setEnabled(bool(file_paths))
        self.run_button.setEnabled(bool(file_paths))
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def clear_selected_files(self):
        self.selected_files = []
        self.file_list_widget.clear()
        self.clear_button.setEnabled(False)
        self.run_button.setEnabled(False)

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def toggle_advanced(self):
        is_checked = self.advanced_btn.isChecked()
        self.advanced_box.setVisible(is_checked)
        self.advanced_btn.setText("Hide Advanced Options" if is_checked else "Show Advanced Options")

    def update_selected_files(self, files):
        """
        Aggiorna i file selezionati e mostra warning se esistono skull strip per i pazienti.
        """
        selected_files = []
        files_with_warnings = []

        # Controlla tutti i file NIfTI nella lista
        for path in files:
            if path.endswith(".nii") or path.endswith(".nii.gz"):
                # Controlla se esiste già uno skull strip per questo paziente
                if self.has_existing_skull_strip(path, self.context["workspace_path"]):
                    files_with_warnings.append(path)

                selected_files.append(path)

        # Se ci sono file con warning, mostra il messaggio
        if files_with_warnings:
            if len(files_with_warnings) == 1:
                # Un solo file con warning
                path = files_with_warnings[0]

                # Estrai l'ID del paziente
                path_parts = path.replace(self.context["workspace_path"], '').strip(os.sep).split(os.sep)
                subject_id = None
                for part in path_parts:
                    if part.startswith('sub-'):
                        subject_id = part
                        break

                if subject_id:
                    subject_display = subject_id
                else:
                    subject_display = "this patient"

                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle("Existing Skull Strip Detected")
                msg.setText(f"A skull strip already exists for {subject_display}.")
                msg.setInformativeText(
                    f"File: {os.path.basename(path)}\n\n"
                    "You can still proceed to create additional skull strips for this patient.\n"
                    "Do you want to continue with this selection?"
                )
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                if msg.exec() == QMessageBox.StandardButton.No:
                    # Non selezionare nessun file
                    self.selected_files = []
                    self.file_list_widget.clear()
                    self.clear_button.setEnabled(False)
                    self.run_button.setEnabled(False)
                    if self.context and "update_main_buttons" in self.context:
                        self.context["update_main_buttons"]()
                    return
            else:
                # Multipli file con warning
                subjects_with_strips = set()
                for path in files_with_warnings:
                    path_parts = path.replace(self.context["workspace_path"], '').strip(os.sep).split(os.sep)
                    for part in path_parts:
                        if part.startswith('sub-'):
                            subjects_with_strips.add(part)
                            break

                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle("Existing Skull Strips Detected")
                msg.setText(f"Skull strips already exist for {len(subjects_with_strips)} patients:")

                subject_list = ", ".join(sorted(subjects_with_strips))
                msg.setInformativeText(
                    f"Patients: {subject_list}\n\n"
                    "You can still proceed to create additional skull strips for these patients.\n"
                    "Do you want to continue with this selection?"
                )
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                if msg.exec() == QMessageBox.StandardButton.No:
                    # Non selezionare nessun file
                    self.selected_files = []
                    self.file_list_widget.clear()
                    self.clear_button.setEnabled(False)
                    self.run_button.setEnabled(False)
                    if self.context and "update_main_buttons" in self.context:
                        self.context["update_main_buttons"]()
                    return

        # Procedi con la selezione normale
        self.selected_files = selected_files
        self.file_list_widget.clear()

        for path in selected_files:
            item = QListWidgetItem(QIcon.fromTheme("document"), os.path.basename(path))
            item.setToolTip(path)
            self.file_list_widget.addItem(item)

        self.clear_button.setEnabled(bool(selected_files))
        self.run_button.setEnabled(bool(selected_files))

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def run_bet(self):
        if not self.selected_files:
            QMessageBox.warning(self, "No files", "Please select at least one NIfTI file first.")
            return

        success_count = 0
        failed_files = []

        for nifti_file in self.selected_files:
            try:
                # Estrai l'ID del paziente dal percorso del file
                path_parts = nifti_file.replace(self.context["workspace_path"], '').strip(os.sep).split(os.sep)
                subject_id = None
                for part in path_parts:
                    if part.startswith('sub-'):
                        subject_id = part
                        break

                if not subject_id:
                    QMessageBox.warning(self, "Subject ID Error", f"Could not extract subject ID from: {nifti_file}")
                    failed_files.append(nifti_file)
                    continue

                # Crea la directory di output
                output_dir = os.path.join(self.context["workspace_path"], 'derivatives', 'fsl_skullstrip', subject_id,
                                          'anat')
                os.makedirs(output_dir, exist_ok=True)

                # Estrai il nome base del file (senza estensione)
                filename = os.path.basename(nifti_file)
                if filename.endswith('.nii.gz'):
                    base_name = filename[:-7]  # Rimuovi .nii.gz
                elif filename.endswith('.nii'):
                    base_name = filename[:-4]  # Rimuovi .nii
                else:
                    base_name = filename

                # Estrai il parametro f per il naming
                f_val = self.f_input.text().strip()
                if not f_val:
                    f_val = "0.5"  # default

                # Rimuovi il punto e zeri iniziali
                f_formatted = f"f{f_val.replace('.', '').zfill(2)}"

                # Fallback se non riusciamo a parsare il nome
                output_filename = f"{base_name}_desc-skullstripped_{f_formatted}.nii.gz"

                output_file = os.path.join(output_dir, output_filename)

                # Costruisci il comando BET
                cmd = ["bet", nifti_file, output_file]

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
                        QMessageBox.warning(self, "Invalid center",
                                            f"Invalid center for {nifti_file}: use format x y z")
                        failed_files.append(nifti_file)
                        continue
                if self.A2_input.text():
                    cmd += ["-A2", self.A2_input.text()]

                # Esegui il comando
                subprocess.run(cmd, check=True)

                # Crea anche un file JSON con i metadati (opzionale ma utile per BIDS)
                json_file = output_file.replace('.nii.gz', '.json')
                import json
                metadata = {
                    "Description": "Skull-stripped brain image",
                    "Sources": [os.path.basename(nifti_file)],
                    "SkullStrippingMethod": "FSL BET",
                    "SkullStrippingVersion": "FSL BET",
                    "SkullStrippingParameters": {
                        "fractional_intensity": float(f_val) if f_val else 0.5
                    }
                }

                # Aggiungi parametri utilizzati ai metadati
                if self.g_input.text():
                    metadata["SkullStrippingParameters"]["vertical_gradient"] = float(self.g_input.text())
                if self.r_input.text():
                    metadata["SkullStrippingParameters"]["head_radius"] = float(self.r_input.text())
                if self.c_input.text():
                    coords = self.c_input.text().strip().split()
                    if len(coords) == 3:
                        metadata["SkullStrippingParameters"]["center_of_gravity"] = [float(c) for c in coords]

                # Aggiungi flags utilizzati
                flags_used = []
                if self.opt_o.isChecked(): flags_used.append("-o (brain surface outline)")
                if self.opt_m.isChecked(): flags_used.append("-m (binary brain mask)")
                if self.opt_s.isChecked(): flags_used.append("-s (skull image)")
                if self.opt_n.isChecked(): flags_used.append("-n (no brain image)")
                if self.opt_t.isChecked(): flags_used.append("-t (thresholding)")
                if self.opt_e.isChecked(): flags_used.append("-e (surface mesh)")
                if self.opt_R.isChecked(): flags_used.append("-R (robust center estimation)")
                if self.opt_S.isChecked(): flags_used.append("-S (eye & optic nerve cleanup)")
                if self.opt_B.isChecked(): flags_used.append("-B (bias field & neck cleanup)")
                if self.opt_Z.isChecked(): flags_used.append("-Z (FOV padding in Z)")
                if self.opt_F.isChecked(): flags_used.append("-F (FMRI mode)")
                if self.opt_A.isChecked(): flags_used.append("-A (betsurf with skull/scalp surfaces)")
                if self.opt_v.isChecked(): flags_used.append("-v (verbose mode)")

                if flags_used:
                    metadata["SkullStrippingParameters"]["flags_used"] = flags_used

                with open(json_file, 'w') as f:
                    json.dump(metadata, f, indent=2)

                success_count += 1

            except subprocess.CalledProcessError as e:
                failed_files.append(nifti_file)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error processing {nifti_file}: {str(e)}")
                failed_files.append(nifti_file)

        # Aggiorna il messaggio di stato
        summary = f"Skull Stripping completed: {success_count} succeeded"

        if failed_files:
            self.status_label.setStyleSheet("""
                            color: #FF0000;
                            font-weight: bold;
                            font-size: 12pt;
                            padding: 5px;
                        """)
            summary += f"\nFailed files ({len(failed_files)}):\n" + "\n".join(
                [os.path.basename(f) for f in failed_files])
        else:
            self.status_label.setStyleSheet("""
                color: #4CAF50;
                font-weight: bold;
                font-size: 12pt;
                padding: 5px;
            """)

        self.status_label.setText(summary)

        # Se ci sono stati successi, aggiorna la UI
        if success_count > 0:
            if self.context and "update_main_buttons" in self.context:
                self.context["update_main_buttons"]()

    def back(self):
        if self.previous_page:
            self.on_exit()
            return self.previous_page

        return None

    def is_ready_to_advance(self):
        return False # You can't advance from here

    def is_ready_to_go_back(self):
        return True