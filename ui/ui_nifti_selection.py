import re
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
    QHBoxLayout, QDialog, QLineEdit, QListView, QDialogButtonBox, QComboBox, QSpinBox, QGroupBox, QGridLayout
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

        self.title = QLabel("Select a NIfTI file for Manual/Automatic Drawing")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

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
        self.layout.addLayout(list_button_layout)

        # Bottone open NIfTI viewer
        self.viewer_button = QPushButton("Open NIfTI file")
        self.viewer_button.setEnabled(False)
        self.viewer_button.clicked.connect(self.open_nifti_viewer)
        self.layout.addWidget(self.viewer_button)

        # Aggiungi uno stretch solo alla fine se vuoi che tutto sia in alto
        self.layout.addStretch()

    def has_existing_mask(self, nifti_file_path, workspace_path):
        """
        Controlla se per il paziente di questo file NIfTI esiste già una mask.

        Args:
            nifti_file_path (str): Percorso completo al file NIfTI
            workspace_path (str): Percorso del workspace

        Returns:
            bool: True se esiste già una mask, False altrimenti
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
            # Se non riesco a identificare il subject ID, assumo che non ci sia mask
            return False

        # Costruisci il percorso dove dovrebbe essere la mask
        mask_dir = os.path.join(workspace_path, 'derivatives', 'manual_masks', subject_id, 'anat')

        # Controlla se la directory esiste
        if not os.path.exists(mask_dir):
            return False

        # Controlla se esistono file .nii.gz
        has_nii = False

        for file in os.listdir(mask_dir):
            if file.endswith('.nii.gz'):
                has_nii = True
                break

        # Ritorna True solo se esistono entrambi i tipi di file
        return has_nii

    def open_tree_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select a NIfTI file from workspace")
        dialog.resize(700, 600)  # Leggermente più grande per i nuovi controlli

        layout = QVBoxLayout(dialog)

        # === SEZIONE FILTRI MODERNA ===
        filter_group = QGroupBox("Filters")
        filter_layout = QGridLayout(filter_group)

        # Ricerca testuale (migliorata)
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search files (T1, FLAIR, dwi, func, etc.)")
        search_bar.setClearButtonEnabled(True)  # Pulsante X per cancellare
        filter_layout.addWidget(QLabel("Search:"), 0, 0)
        filter_layout.addWidget(search_bar, 0, 1, 1, 3)

        # Filtro per soggetto/paziente
        from PyQt6.QtWidgets import QComboBox
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

        # Checkbox per mostrare solo file senza mask
        from PyQt6.QtWidgets import QCheckBox
        no_mask_checkbox = QCheckBox("Show only files without existing masks")
        filter_layout.addWidget(no_mask_checkbox, 3, 0, 1, 2)

        # Checkbox per mostrare solo file con mask
        with_mask_checkbox = QCheckBox("Show only files with existing masks")
        filter_layout.addWidget(with_mask_checkbox, 3, 2, 1, 2)

        layout.addWidget(filter_group)

        # === RACCOLTA E PARSING DEI FILE ===
        all_nii_files = []
        relative_to_absolute = {}
        files_with_masks = set()
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

                    filename = os.path.basename(f)
                    json_path = full_path.replace(".nii.gz", ".json").replace(".nii", ".json")

                    # Estrai modality
                    modality = None
                    if os.path.exists(json_path):
                        try:
                            with open(json_path, 'r') as jf:
                                metadata = json.load(jf)
                                protocol_name = metadata.get("ProtocolName", "")
                                if protocol_name:
                                    # Pulizia: sostituisci caratteri strani con spazi e rimuovi spazi multipli
                                    modality = re.sub(r'[^A-Za-z0-9 ]+', ' ', protocol_name)
                                    modality = re.sub(r'\s+', '_', modality).strip()
                        except Exception as e:
                            print(f"Errore nella lettura del JSON {json_path}: {e}")

                    # Fallback se non c'è il json o non contiene ProtocolName
                    if not modality:
                        # Prende una parte del filename tra l’ultimo "_" e un blocco numerico finale
                        match = re.search(r'_([^_]+(?:_[^_]+)+)_(?:\d{6,})', filename)
                        if match:
                            modality = match.group(1)
                        else:
                            modality = "Unknown"

                    modalities_set.add(modality)

                    # Segna i file che hanno già una mask
                    if self.has_existing_mask(full_path, self.context["workspace_path"]):
                        files_with_masks.add(relative_path)

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
            if files_with_masks:
                info_text += f" ({len(files_with_masks)} total with existing masks)"
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
        file_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        file_list.setAlternatingRowColors(True)  # Righe alternate colorate

        # Aggiungi tutti i file con colori differenziati
        def populate_file_list():
            file_list.clear()
            for relative_path in sorted(all_nii_files):
                item = QListWidgetItem(relative_path)

                # Se il file ha già una mask, coloralo in arancione
                if relative_path in files_with_masks:
                    item.setForeground(QBrush(QColor(255, 140, 0)))  # Arancione più scuro
                    item.setToolTip(f"{relative_to_absolute[relative_path]}\n✓ This patient already has a mask")
                else:
                    item.setToolTip(f"{relative_to_absolute[relative_path]}\n○ No existing mask")

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

            show_only_no_mask = no_mask_checkbox.isChecked()
            show_only_with_mask = with_mask_checkbox.isChecked()

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

                # Filtro per presenza/assenza mask
                has_mask = relative_path in files_with_masks
                if show_only_no_mask and has_mask:
                    should_show = False
                if show_only_with_mask and not has_mask:
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
        no_mask_checkbox.toggled.connect(apply_filters)
        with_mask_checkbox.toggled.connect(apply_filters)

        # Evita che entrambi i checkbox siano selezionati insieme
        def on_no_mask_toggled(checked):
            if checked:
                with_mask_checkbox.setChecked(False)

        def on_with_mask_toggled(checked):
            if checked:
                no_mask_checkbox.setChecked(False)

        no_mask_checkbox.toggled.connect(on_no_mask_toggled)
        with_mask_checkbox.toggled.connect(on_with_mask_toggled)

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
            no_mask_checkbox.setChecked(False)
            with_mask_checkbox.setChecked(False)

        reset_button.clicked.connect(reset_filters)
        buttons.addButton(reset_button, QDialogButtonBox.ButtonRole.ResetRole)

        layout.addWidget(buttons)

        # === LOGICA ACCETTAZIONE ===
        def accept():
            current_item = file_list.currentItem()
            if not current_item or current_item.isHidden():
                QMessageBox.warning(dialog, "No selection", "Please select a visible NIfTI file.")
                return

            selected_relative_path = current_item.text()
            selected_absolute_path = relative_to_absolute[selected_relative_path]

            # Se il file selezionato ha già una mask, mostra il warning
            if selected_relative_path in files_with_masks:
                # Estrai l'ID del paziente per il messaggio
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

                # Mostra il warning
                msg = QMessageBox(dialog)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle("Existing Mask Detected")
                msg.setText(f"A mask already exists for {subject_display}.")
                msg.setInformativeText(
                    f"File: {os.path.basename(selected_absolute_path)}\n\n"
                    "You can still proceed to create additional masks for this patient.\n"
                    "Do you want to continue with this selection?"
                )
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                # Se l'utente sceglie No, non procedere
                if msg.exec() == QMessageBox.StandardButton.No:
                    return

            # Procedi con la selezione
            self.set_selected_file(selected_absolute_path)
            dialog.accept()

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)

        dialog.exec()

    def set_selected_file(self, file_path):
        """
        Imposta il file selezionato (il warning è ora gestito nel dialog di selezione).
        """
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
        """
        Aggiorna i file selezionati e mostra warning se esistono mask per i pazienti.
        """
        self.selected_file = None
        self.file_list_widget.clear()

        for path in files:
            if path.endswith(".nii") or path.endswith(".nii.gz"):
                # Controlla se esiste già una mask per questo paziente
                if self.has_existing_mask(path, self.context["workspace_path"]):
                    # Estrai l'ID del paziente per il messaggio
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

                    # Mostra il warning
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("Existing Mask Detected")
                    msg.setText(f"A mask already exists for {subject_display}.")
                    msg.setInformativeText(
                        f"File: {os.path.basename(path)}\n\n"
                        "You can still proceed to create additional masks for this patient.\n"
                        "Do you want to continue with this selection?"
                    )
                    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                    # Se l'utente sceglie No, salta questo file
                    if msg.exec() == QMessageBox.StandardButton.No:
                        continue

                # Procedi con la selezione
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

    def is_ready_to_advance(self):
        return False

    def is_ready_to_go_back(self):
        return True

    def on_enter(self):
        pass

    def open_nifti_viewer(self):
        if "nifti_viewer" in self.context and self.context["nifti_viewer"]:
            self.context["nifti_viewer"].open_file(self.selected_file)
            self.context["nifti_viewer"].show()
            pass
        else:
            self.context["nifti_viewer"] = NiftiViewer(self.context)
            self.context["nifti_viewer"].open_file(self.selected_file)
            self.context["nifti_viewer"].show()
            pass

    def back(self):
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page

        return None

    def reset_page(self):
        """Resets the page to its initial state, clearing all selections"""
        # Clear selected file
        self.selected_file = None
        self.file_list_widget.clear()

        # Reset buttons state
        self.clear_button.setEnabled(False)
        self.viewer_button.setEnabled(False)