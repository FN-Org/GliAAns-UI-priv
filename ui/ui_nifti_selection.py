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
        selector_layout.addWidget(self.viewer_button)

        self.layout.addLayout(selector_layout)

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

        # Controlla se esistono file .nii.gz e .json nella directory
        has_nii = False
        has_json = False

        for file in os.listdir(mask_dir):
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
        search_bar.setPlaceholderText("Search (e.g., T1, FLAIR, etc.)")
        layout.addWidget(QLabel("Search:"))
        layout.addWidget(search_bar)

        # Lista di file e dizionario di mappatura
        all_nii_files = []
        relative_to_absolute = {}
        files_with_masks = set()

        for root, dirs, files in os.walk(self.context["workspace_path"]):
            # Ignora la cartella 'derivatives' e tutte le sue sottocartelle
            dirs[:] = [d for d in dirs if d != "derivatives"]

            for f in files:
                if f.endswith((".nii", ".nii.gz")):
                    full_path = os.path.join(root, f)
                    relative_path = os.path.relpath(full_path, self.context["workspace_path"])
                    all_nii_files.append(relative_path)
                    relative_to_absolute[relative_path] = full_path

                    # Segna i file che hanno già una mask
                    if self.has_existing_mask(full_path, self.context["workspace_path"]):
                        files_with_masks.add(relative_path)

        # Info label con legenda colori
        info_text = f"Showing {len(all_nii_files)} files"
        if files_with_masks:
            info_text += f" ({len(files_with_masks)} with existing masks shown in orange)"

        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)

        # Usa QListWidget invece di QListView per avere più controllo sui colori
        from PyQt6.QtWidgets import QListWidget
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QBrush, QColor

        file_list = QListWidget()
        file_list.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        file_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        # Aggiungi tutti i file con colori differenziati
        for relative_path in sorted(all_nii_files):
            item = QListWidgetItem(relative_path)

            # Se il file ha già una mask, coloralo in arancione
            if relative_path in files_with_masks:
                item.setForeground(QBrush(QColor(255, 193, 7)))  # Giallo (Bootstrap warning color)
                item.setToolTip(f"{relative_to_absolute[relative_path]}\nThis patient already has a mask")
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
            current_item = file_list.currentItem()
            if not current_item:
                QMessageBox.warning(dialog, "No selection", "Please select a NIfTI file.")
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
