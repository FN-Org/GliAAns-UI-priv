import re
import json
from PyQt6.QtGui import QFileSystemModel, QIcon
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QCheckBox, QDialogButtonBox, QDialog, QHBoxLayout,
    QListWidget, QListWidgetItem, QWidget, QDoubleSpinBox, QSpinBox, QGridLayout, QGroupBox
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

        self.selected_files = None

        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.title = QLabel("Select a NIfTI file for Skull Stripping")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

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
        # self.f_input = QLineEdit()
        # self.f_input.setPlaceholderText("Fractional intensity (-f), default 0.5")
        # self.layout.addWidget(self.f_input)

        self.f_box = QGroupBox()

        f_layout = QHBoxLayout()
        f_label = QLabel(
            "Fractional intensity threshold, smaller values give larger brain outline estimates")
        f_layout.addWidget(f_label)

        self.f_spinbox = QDoubleSpinBox()
        self.f_spinbox.setRange(0.0, 1.0)
        self.f_spinbox.setSingleStep(0.05)
        self.f_spinbox.setValue(0.50)
        self.f_spinbox.setDecimals(2)
        self.f_spinbox.setMinimumWidth(60)
        self.f_spinbox.setMaximumWidth(80)
        f_layout.addWidget(self.f_spinbox)

        f_layout.addStretch()

        self.f_box.setLayout(f_layout)
        self.layout.addWidget(self.f_box)

        # Toggle opzioni avanzate
        self.advanced_btn = QPushButton("Show Advanced Options")
        self.advanced_btn.setCheckable(True)
        self.advanced_btn.clicked.connect(self.toggle_advanced)
        self.layout.addWidget(self.advanced_btn)

        # Opzioni avanzate nascoste in un QGroupBox
        self.advanced_box = QGroupBox()
        self.advanced_layout = QVBoxLayout()

        # Sezione 1: Output options (checkboxes)
        output_label = QLabel("Advanced options:")
        output_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        self.advanced_layout.addWidget(output_label)

        self.opt_brain_extracted = QCheckBox("Output brain-extracted image")
        self.opt_brain_extracted.setChecked(True)  # Checked by default come in FSL
        self.advanced_layout.addWidget(self.opt_brain_extracted)

        self.opt_m = QCheckBox("Output binary brain mask image")
        self.advanced_layout.addWidget(self.opt_m)

        self.opt_t = QCheckBox("Apply thresholding to brain and mask image")
        self.advanced_layout.addWidget(self.opt_t)

        self.opt_s = QCheckBox("Output exterior skull surface image")
        self.advanced_layout.addWidget(self.opt_s)

        self.opt_o = QCheckBox("Output brain surface overlaid onto original image")
        self.advanced_layout.addWidget(self.opt_o)

        # Sezione 2: Threshold gradient
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel(
            "Threshold gradient; positive values give larger brain outline at bottom, smaller at top")
        threshold_layout.addWidget(threshold_label)

        self.g_spinbox = QDoubleSpinBox()
        self.g_spinbox.setRange(-1.0, 1.0)
        self.g_spinbox.setSingleStep(0.1)
        self.g_spinbox.setValue(0.0)
        self.g_spinbox.setDecimals(1)
        self.g_spinbox.setMinimumWidth(60)
        self.g_spinbox.setMaximumWidth(80)
        threshold_layout.addWidget(self.g_spinbox)

        threshold_layout.addStretch()
        self.advanced_layout.addLayout(threshold_layout)

        # Sezione 3: Coordinates
        coords_layout = QHBoxLayout()
        coords_label = QLabel("Coordinates (voxels) for centre of initial brain surface sphere")
        coords_layout.addWidget(coords_label)

        # X coordinate
        self.c_x_spinbox = QSpinBox()
        self.c_x_spinbox.setRange(0, 9999)
        self.c_x_spinbox.setValue(0)
        self.c_x_spinbox.setMinimumWidth(50)
        self.c_x_spinbox.setMaximumWidth(70)
        coords_layout.addWidget(self.c_x_spinbox)

        coords_layout.addWidget(QLabel("Y"))

        # Y coordinate
        self.c_y_spinbox = QSpinBox()
        self.c_y_spinbox.setRange(0, 9999)
        self.c_y_spinbox.setValue(0)
        self.c_y_spinbox.setMinimumWidth(50)
        self.c_y_spinbox.setMaximumWidth(70)
        coords_layout.addWidget(self.c_y_spinbox)

        coords_layout.addWidget(QLabel("Z"))

        # Z coordinate
        self.c_z_spinbox = QSpinBox()
        self.c_z_spinbox.setRange(0, 9999)
        self.c_z_spinbox.setValue(0)
        self.c_z_spinbox.setMinimumWidth(50)
        self.c_z_spinbox.setMaximumWidth(70)
        coords_layout.addWidget(self.c_z_spinbox)

        coords_layout.addStretch()
        self.advanced_layout.addLayout(coords_layout)

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
        skull_strip_dir = os.path.join(workspace_path, 'derivatives', 'fsl_skullstrips', subject_id, 'anat')

        # Controlla se la directory esiste
        if not os.path.exists(skull_strip_dir):
            return False

        # Controlla se esistono file .nii.gz e .json nella directory
        has_nii = False

        for file in os.listdir(skull_strip_dir):
            if file.endswith('.nii.gz'):
                has_nii = True
                break

        # Ritorna True solo se esistono entrambi i tipi di file
        return has_nii

    def open_tree_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select NIfTI files for skull stripping")
        dialog.resize(700, 650)  # Aumentato per i nuovi controlli

        layout = QVBoxLayout(dialog)

        # === SEZIONE FILTRI MODERNA ===
        filter_group = QGroupBox("Filters")
        filter_layout = QGridLayout(filter_group)

        # Ricerca testuale (migliorata)
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search files (FLAIR, T1, T2, etc.)")
        search_bar.setClearButtonEnabled(True)  # Pulsante X per cancellare
        filter_layout.addWidget(QLabel("Search:"), 0, 0)
        filter_layout.addWidget(search_bar, 0, 1, 1, 3)

        # Filtro per soggetto/paziente
        from PyQt6.QtWidgets import QComboBox, QCheckBox, QPushButton
        subject_combo = QComboBox()
        subject_combo.setEditable(True)  # Permette digitazione custom
        subject_combo.lineEdit().setPlaceholderText("All subjects or type subject ID...")
        filter_layout.addWidget(QLabel("Subject:"), 1, 0)
        filter_layout.addWidget(subject_combo, 1, 1)

        # Filtro per sessione
        session_combo = QComboBox()
        session_combo.setEditable(True)
        session_combo.lineEdit().setPlaceholderText("All sessions...")
        filter_layout.addWidget(QLabel("Session:"), 1, 2)
        filter_layout.addWidget(session_combo, 1, 3)

        # Filtro per modalità (T1, T2, FLAIR, etc.)
        modality_combo = QComboBox()
        modality_combo.setEditable(True)
        modality_combo.lineEdit().setPlaceholderText("All modalities...")
        filter_layout.addWidget(QLabel("Modality:"), 2, 0)
        filter_layout.addWidget(modality_combo, 2, 1)

        # Filtro per tipo di file (anatomico, funzionale, etc.)
        datatype_combo = QComboBox()
        datatype_combo.addItems(["All types", "anat", "func", "dwi", "fmap", "perf"])
        filter_layout.addWidget(QLabel("Data type:"), 2, 2)
        filter_layout.addWidget(datatype_combo, 2, 3)

        # Checkbox per mostrare solo file senza skull strip
        no_strip_checkbox = QCheckBox("Show only files without existing skull strips")
        filter_layout.addWidget(no_strip_checkbox, 3, 0, 1, 2)

        # Checkbox per mostrare solo file con skull strip
        with_strip_checkbox = QCheckBox("Show only files with existing skull strips")
        filter_layout.addWidget(with_strip_checkbox, 3, 2, 1, 2)

        layout.addWidget(filter_group)

        # === RACCOLTA E PARSING DEI FILE ===
        all_nii_files = []
        relative_to_absolute = {}
        files_with_skull_strips = set()
        subjects_set = set()
        sessions_set = set()
        modalities_set = set()

        for root, dirs, files in os.walk(self.context["workspace_path"]):
            # Ignora la cartella 'derivatives' e tutte le sue sottocartelle
            dirs[:] = [d for d in dirs if d != "derivatives"]

            for f in files:
                if f.endswith((".nii", ".nii.gz")):
                    full_path = os.path.join(root, f)
                    relative_path = os.path.relpath(full_path, self.context["workspace_path"])
                    all_nii_files.append(relative_path)
                    relative_to_absolute[relative_path] = full_path

                    # Estrai informazioni BIDS dal percorso
                    path_parts = relative_path.split(os.sep)

                    # Estrai subject
                    for part in path_parts:
                        if part.startswith('sub-'):
                            subjects_set.add(part)
                            break

                    # Estrai session
                    for part in path_parts:
                        if part.startswith('ses-'):
                            sessions_set.add(part)
                            break

                    # Estrai modalità dal nome file
                    filename = os.path.basename(f)
                    json_path = full_path.replace(".nii.gz", ".json").replace(".nii", ".json")

                    modality = None
                    if os.path.exists(json_path):
                        try:
                            with open(json_path, 'r') as jf:
                                metadata = json.load(jf)
                                protocol_name = metadata.get("ProtocolName", "")
                                if protocol_name:
                                    modality = re.sub(r'[^A-Za-z0-9 ]+', ' ', protocol_name)
                                    modality = re.sub(r'\s+', '_', modality).strip()
                        except Exception:
                            pass

                    if not modality:
                        match = re.search(r'_([^_]+(?:_[^_]+)+)_(?:\d{6,})', filename)
                        modality = match.group(1) if match else "Unknown"

                    modalities_set.add(modality)

        # === POPOLA I DROPDOWN ===
        subject_combo.addItem("All subjects")
        subject_combo.addItems(sorted(subjects_set))

        session_combo.addItem("All sessions")
        session_combo.addItems(sorted(sessions_set))

        modality_combo.addItem("All modalities")
        modality_combo.addItems(sorted(modalities_set))

        # === INFO LABEL ===
        info_label = QLabel()

        def update_info_label(visible_count):
            info_text = f"Showing {visible_count} of {len(all_nii_files)} files"
            if files_with_skull_strips:
                info_text += f" ({len(files_with_skull_strips)} total with existing skull strips)"
            info_label.setText(info_text)
            info_label.setStyleSheet("color: gray; font-size: 10px;")

        update_info_label(len(all_nii_files))
        layout.addWidget(info_label)

        # === LISTA FILE ===
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QBrush, QColor

        file_list = QListWidget()
        file_list.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)  # Permette selezione multipla
        file_list.setAlternatingRowColors(True)  # Righe alternate colorate

        # Aggiungi tutti i file con colori differenziati
        def populate_file_list():
            file_list.clear()
            for relative_path in sorted(all_nii_files):
                item = QListWidgetItem(relative_path)

                # Se il file ha già uno skull strip, coloralo in giallo
                if relative_path in files_with_skull_strips:
                    item.setForeground(QBrush(QColor(255, 193, 7)))  # Giallo (Bootstrap warning color)
                    item.setToolTip(f"{relative_to_absolute[relative_path]}\n✓ This patient already has a skull strip")
                else:
                    item.setToolTip(f"{relative_to_absolute[relative_path]}\n○ No existing skull strip")

                file_list.addItem(item)

        populate_file_list()
        layout.addWidget(file_list)

        # === FUNZIONE DI FILTRO AVANZATA ===
        def apply_filters():
            search_text = search_bar.text().lower()
            selected_subject = subject_combo.currentText()
            selected_session = session_combo.currentText()
            selected_modality = modality_combo.currentText()
            selected_datatype = datatype_combo.currentText()

            show_only_no_strip = no_strip_checkbox.isChecked()
            show_only_with_strip = with_strip_checkbox.isChecked()

            visible_count = 0

            for i in range(file_list.count()):
                item = file_list.item(i)
                relative_path = item.text()
                should_show = True

                # Filtro ricerca testuale
                if search_text and search_text not in relative_path.lower():
                    should_show = False

                # Filtro soggetto
                if selected_subject != "All subjects" and selected_subject:
                    if selected_subject not in relative_path:
                        should_show = False

                # Filtro sessione
                if selected_session != "All sessions" and selected_session:
                    if selected_session not in relative_path:
                        should_show = False

                # Filtro modalità
                if selected_modality != "All modalities" and selected_modality:
                    if selected_modality not in relative_path:
                        should_show = False

                # Filtro tipo di dato
                if selected_datatype != "All types":
                    if f"/{selected_datatype}/" not in relative_path and f"\\{selected_datatype}\\" not in relative_path:
                        should_show = False

                # Filtro per presenza/assenza skull strip
                has_strip = relative_path in files_with_skull_strips
                if show_only_no_strip and has_strip:
                    should_show = False
                if show_only_with_strip and not has_strip:
                    should_show = False

                item.setHidden(not should_show)
                if should_show:
                    visible_count += 1

            update_info_label(visible_count)

        # === CONNESSIONI EVENTI ===
        search_bar.textChanged.connect(apply_filters)
        subject_combo.currentTextChanged.connect(apply_filters)
        session_combo.currentTextChanged.connect(apply_filters)
        modality_combo.currentTextChanged.connect(apply_filters)
        datatype_combo.currentTextChanged.connect(apply_filters)
        no_strip_checkbox.toggled.connect(apply_filters)
        with_strip_checkbox.toggled.connect(apply_filters)

        # Evita che entrambi i checkbox siano selezionati insieme
        def on_no_strip_toggled(checked):
            if checked:
                with_strip_checkbox.setChecked(False)

        def on_with_strip_toggled(checked):
            if checked:
                no_strip_checkbox.setChecked(False)

        no_strip_checkbox.toggled.connect(on_no_strip_toggled)
        with_strip_checkbox.toggled.connect(on_with_strip_toggled)

        # === PULSANTI ===
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        # Pulsante per resettare tutti i filtri
        reset_button = QPushButton("Reset Filters")

        def reset_filters():
            search_bar.clear()
            subject_combo.setCurrentIndex(0)
            session_combo.setCurrentIndex(0)
            modality_combo.setCurrentIndex(0)
            datatype_combo.setCurrentIndex(0)
            no_strip_checkbox.setChecked(False)
            with_strip_checkbox.setChecked(False)

        reset_button.clicked.connect(reset_filters)
        buttons.addButton(reset_button, QDialogButtonBox.ButtonRole.ResetRole)

        # Pulsante per selezionare tutti i file visibili
        select_all_button = QPushButton("Select All Visible")

        def select_all_visible():
            for i in range(file_list.count()):
                item = file_list.item(i)
                if not item.isHidden():
                    item.setSelected(True)

        select_all_button.clicked.connect(select_all_visible)
        buttons.addButton(select_all_button, QDialogButtonBox.ButtonRole.ActionRole)

        # Pulsante per deselezionare tutto
        deselect_all_button = QPushButton("Deselect All")

        def deselect_all():
            file_list.clearSelection()

        deselect_all_button.clicked.connect(deselect_all)
        buttons.addButton(deselect_all_button, QDialogButtonBox.ButtonRole.ActionRole)

        layout.addWidget(buttons)

        # === LOGICA ACCETTAZIONE ===
        def accept():
            selected_items = file_list.selectedItems()
            # Filtra solo gli elementi visibili (non nascosti)
            visible_selected_items = [item for item in selected_items if not item.isHidden()]

            if not visible_selected_items:
                QMessageBox.warning(dialog, "No selection", "Please select at least one visible NIfTI file.")
                return

            selected_files = []
            files_with_warnings = []

            # Processa ogni file selezionato
            for item in visible_selected_items:
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
        if not hasattr(self, 'selected_files') or not self.selected_files:
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
                output_dir = os.path.join(self.context["workspace_path"], 'derivatives', 'fsl_skullstrips', subject_id,
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
                f_val = self.f_spinbox.value()
                f_str = f"{f_val:.2f}"  # Formatta con 2 decimali
                f_formatted = f"f{f_str.replace('.', '')}"  # Rimuovi il punto per il nome file

                # Nome del file di output
                output_filename = f"{base_name}_{f_formatted}_brain.nii.gz"
                output_file = os.path.join(output_dir, output_filename)

                # Costruisci il comando BET
                cmd = ["bet", nifti_file, output_file]

                # Aggiungi il parametro fractional intensity
                if f_val:
                    cmd += ["-f", str(f_val)]

                # Aggiungi opzioni avanzate se selezionate
                if self.opt_m.isChecked():
                    cmd.append("-m")
                if self.opt_t.isChecked():
                    cmd.append("-t")
                if self.opt_s.isChecked():
                    cmd.append("-s")
                if self.opt_o.isChecked():
                    cmd.append("-o")

                # Aggiungi parametro gradient se impostato
                g_val = self.g_spinbox.value()
                if g_val != 0.0:
                    cmd += ["-g", str(g_val)]

                # Aggiungi coordinate del centro se impostate (diverse da 0,0,0)
                c_x = self.c_x_spinbox.value()
                c_y = self.c_y_spinbox.value()
                c_z = self.c_z_spinbox.value()
                if c_x != 0 or c_y != 0 or c_z != 0:
                    cmd += ["-c", str(c_x), str(c_y), str(c_z)]

                # Se non è selezionata l'opzione "Output brain-extracted image", aggiungi -n
                if not self.opt_brain_extracted.isChecked():
                    cmd.append("-n")

                # Esegui il comando
                self.status_label.setText(f"Running skull stripping on {os.path.basename(nifti_file)}...")
                self.status_label.setStyleSheet("color: #2196F3; font-weight: bold;")

                result = subprocess.run(cmd, check=True, capture_output=True, text=True)

                # Crea anche un file JSON con i metadati (opzionale ma utile per BIDS)
                json_file = output_file.replace('.nii.gz', '.json')
                import json
                metadata = {
                    "SkullStripped": True,
                    "Description": "Skull-stripped brain image",
                    "Sources": [os.path.basename(nifti_file)],
                    "SkullStrippingMethod": "FSL BET",
                    "SkullStrippingParameters": {
                        "fractional_intensity": f_val
                    }
                }

                # Aggiungi parametri utilizzati ai metadati
                if g_val != 0.0:
                    metadata["SkullStrippingParameters"]["vertical_gradient"] = g_val
                if c_x != 0 or c_y != 0 or c_z != 0:
                    metadata["SkullStrippingParameters"]["center_of_gravity"] = [c_x, c_y, c_z]

                # Aggiungi flags utilizzati
                flags_used = []
                if not self.opt_brain_extracted.isChecked():
                    flags_used.append("-n (no brain image output)")
                if self.opt_m.isChecked():
                    flags_used.append("-m (binary brain mask)")
                if self.opt_t.isChecked():
                    flags_used.append("-t (thresholding)")
                if self.opt_s.isChecked():
                    flags_used.append("-s (exterior skull surface)")
                if self.opt_o.isChecked():
                    flags_used.append("-o (brain surface overlay)")

                if flags_used:
                    metadata["SkullStrippingParameters"]["flags_used"] = flags_used

                with open(json_file, 'w') as f:
                    json.dump(metadata, f, indent=2)

                success_count += 1

            except subprocess.CalledProcessError as e:
                error_msg = f"BET command failed for {os.path.basename(nifti_file)}"
                if e.stderr:
                    error_msg += f": {e.stderr}"
                QMessageBox.warning(self, "BET Error", error_msg)
                failed_files.append(nifti_file)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error processing {nifti_file}: {str(e)}")
                failed_files.append(nifti_file)

        # Aggiorna il messaggio di stato
        if success_count > 0:
            summary = f"Skull Stripping completed successfully for {success_count} file(s)"
            if failed_files:
                summary += f"\n{len(failed_files)} file(s) failed: {', '.join([os.path.basename(f) for f in failed_files])}"
                self.status_label.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 12pt; padding: 5px;")
            else:
                self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12pt; padding: 5px;")
        else:
            summary = f"All {len(failed_files)} file(s) failed to process"
            self.status_label.setStyleSheet("color: #FF0000; font-weight: bold; font-size: 12pt; padding: 5px;")

        self.status_label.setText(summary)

        # Se ci sono stati successi, aggiorna la UI
        if success_count > 0:
            if self.context and "update_main_buttons" in self.context:
                self.context["update_main_buttons"]()

    def back(self):
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page

        return None

    def on_enter(self):
        self.status_label.setText("")

    def is_ready_to_advance(self):
        return False # You can't advance from here

    def is_ready_to_go_back(self):
        return True

    def reset_page(self):
        """Resets the page to its initial state, clearing all selections and parameters"""
        # Clear selected files
        self.selected_files = []
        self.file_list_widget.clear()

        # Reset buttons state
        self.clear_button.setEnabled(False)
        self.run_button.setEnabled(False)

        # Reset main parameter
        self.f_spinbox.setValue(0.50)

        # Reset advanced options
        self.advanced_btn.setChecked(False)
        self.advanced_box.setVisible(False)
        self.advanced_btn.setText("Show Advanced Options")

        # Reset advanced checkboxes
        self.opt_brain_extracted.setChecked(True)
        self.opt_m.setChecked(False)
        self.opt_t.setChecked(False)
        self.opt_s.setChecked(False)
        self.opt_o.setChecked(False)

        # Reset advanced parameters
        self.g_spinbox.setValue(0.0)
        self.c_x_spinbox.setValue(0)
        self.c_y_spinbox.setValue(0)
        self.c_z_spinbox.setValue(0)

        # Clear status message
        self.status_label.setText("")