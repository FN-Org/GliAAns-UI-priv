
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QGridLayout, QHBoxLayout, \
    QMessageBox, QGroupBox, QListWidget, QDialog, QLineEdit, QDialogButtonBox, QListWidgetItem
from PyQt6.QtCore import Qt, QCoreApplication
import os

from ui.ui_dl_execution_page import DlExecutionPage
from page import Page
from logger import get_logger

log = get_logger()


class DlPatientSelectionPage(Page):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.selected_files = []

        self._setup_ui()

        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.title = QLabel("Select NIfTI files for Deep Learning Segmentation")
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

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)

    def has_existing_segmentation(self, nifti_file_path, workspace_path):
        """
        Check if segmentation already exists for the patient of this NIfTI file.
        """
        # Extract patient ID from file path
        path_parts = nifti_file_path.replace(workspace_path, '').strip(os.sep).split(os.sep)

        # Find the part that starts with 'sub-'
        subject_id = None
        for part in path_parts:
            if part.startswith('sub-'):
                subject_id = part
                break

        if not subject_id:
            return False

        # Build the path where segmentation should be
        seg_dir = os.path.join(workspace_path, 'derivatives', 'deep_learning_seg', subject_id, 'anat')

        # Check if directory exists
        if not os.path.exists(seg_dir):
            return False

        # Check if *_seg.nii.gz files exist in the directory
        for file in os.listdir(seg_dir):
            if file.endswith('_seg.nii.gz') or file.endswith('_seg.nii'):
                return True

        return False

    def open_tree_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select NIfTI files for deep learning segmentation")
        dialog.resize(700, 650)

        layout = QVBoxLayout(dialog)

        # === MODERN FILTERS SECTION ===
        filter_group = QGroupBox("Filters")
        filter_layout = QGridLayout(filter_group)

        # Text search (improved)
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search files (FLAIR, T1, T2, etc.)")
        search_bar.setClearButtonEnabled(True)  # X button to clear
        filter_layout.addWidget(QLabel("Search:"), 0, 0)
        filter_layout.addWidget(search_bar, 0, 1, 1, 3)

        # Subject/patient filter
        from PyQt6.QtWidgets import QComboBox, QCheckBox, QPushButton
        subject_combo = QComboBox()
        subject_combo.setEditable(True)  # Allows custom typing
        subject_combo.lineEdit().setPlaceholderText("All subjects or type subject ID...")
        filter_layout.addWidget(QLabel("Subject:"), 1, 0)
        filter_layout.addWidget(subject_combo, 1, 1)

        # Session filter
        session_combo = QComboBox()
        session_combo.setEditable(True)
        session_combo.lineEdit().setPlaceholderText("All sessions...")
        filter_layout.addWidget(QLabel("Session:"), 1, 2)
        filter_layout.addWidget(session_combo, 1, 3)

        # Modality filter (T1, T2, FLAIR, etc.)
        modality_combo = QComboBox()
        modality_combo.setEditable(True)
        modality_combo.lineEdit().setPlaceholderText("All modalities...")
        filter_layout.addWidget(QLabel("Modality:"), 2, 0)
        filter_layout.addWidget(modality_combo, 2, 1)

        # Data type filter (anatomical, functional, etc.)
        datatype_combo = QComboBox()
        datatype_combo.addItems(["All types", "anat", "func", "dwi", "fmap", "perf"])
        filter_layout.addWidget(QLabel("Data type:"), 2, 2)
        filter_layout.addWidget(datatype_combo, 2, 3)

        # Checkbox to show only files without segmentation
        no_seg_checkbox = QCheckBox("Show only files without existing segmentations")
        filter_layout.addWidget(no_seg_checkbox, 3, 0, 1, 2)

        # Checkbox to show only files with segmentation
        with_seg_checkbox = QCheckBox("Show only files with existing segmentations")
        filter_layout.addWidget(with_seg_checkbox, 3, 2, 1, 2)

        layout.addWidget(filter_group)

        # === FILE COLLECTION AND PARSING ===
        all_nii_files = []
        relative_to_absolute = {}
        files_with_segmentations = set()
        subjects_set = set()
        sessions_set = set()
        modalities_set = set()

        for root, dirs, files in os.walk(self.context["workspace_path"]):
            # Ignore 'derivatives' folder and all its subfolders
            dirs[:] = [d for d in dirs if d != "derivatives"]

            for f in files:
                if f.endswith((".nii", ".nii.gz")):
                    full_path = os.path.join(root, f)
                    relative_path = os.path.relpath(full_path, self.context["workspace_path"])
                    all_nii_files.append(relative_path)
                    relative_to_absolute[relative_path] = full_path

                    # Extract BIDS info from path
                    path_parts = relative_path.split(os.sep)

                    # Extract subject
                    for part in path_parts:
                        if part.startswith('sub-'):
                            subjects_set.add(part)
                            break

                    # Extract session
                    for part in path_parts:
                        if part.startswith('ses-'):
                            sessions_set.add(part)
                            break

                    # Extract modality
                    filename = os.path.basename(f)
                    filename_noext = os.path.splitext(os.path.splitext(filename)[0])[0]  # removes .nii.gz or .nii
                    parts = filename_noext.split("_")
                    # Modality is usually the last part of the name
                    possible_modality = parts[-1]
                    modality = possible_modality if possible_modality else "Unknown"

                    modalities_set.add(modality)

                    # Mark files that already have segmentation
                    if self.has_existing_segmentation(full_path, self.context["workspace_path"]):
                        files_with_segmentations.add(relative_path)

        # === POPULATE DROPDOWNS ===
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
            if files_with_segmentations:
                info_text += f" ({len(files_with_segmentations)} total with existing segmentations)"
            info_label.setText(info_text)
            info_label.setStyleSheet("color: gray; font-size: 10px;")

        update_info_label(len(all_nii_files))
        layout.addWidget(info_label)

        # === FILE LIST ===
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QBrush, QColor

        file_list = QListWidget()
        file_list.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)  # Allows multiple selection
        file_list.setAlternatingRowColors(True)  # Alternating row colors

        # Add all files with differentiated colors
        def populate_file_list():
            file_list.clear()
            for relative_path in sorted(all_nii_files):
                item = QListWidgetItem(relative_path)

                # If file already has segmentation, color it yellow
                if relative_path in files_with_segmentations:
                    item.setForeground(QBrush(QColor(255, 193, 7)))  # Yellow (Bootstrap warning color)
                    item.setToolTip(f"{relative_to_absolute[relative_path]}\n✓ This patient already has a segmentation")
                else:
                    item.setToolTip(f"{relative_to_absolute[relative_path]}\n○ No existing segmentation")

                file_list.addItem(item)

        populate_file_list()
        layout.addWidget(file_list)

        # === ADVANCED FILTER FUNCTION ===
        def apply_filters():
            search_text = search_bar.text().lower()
            selected_subject = subject_combo.currentText()
            selected_session = session_combo.currentText()
            selected_modality = modality_combo.currentText()
            selected_datatype = datatype_combo.currentText()

            show_only_no_seg = no_seg_checkbox.isChecked()
            show_only_with_seg = with_seg_checkbox.isChecked()

            visible_count = 0

            for i in range(file_list.count()):
                item = file_list.item(i)
                relative_path = item.text()
                should_show = True

                # Text search filter
                if search_text and search_text not in relative_path.lower():
                    should_show = False

                # Subject filter
                if selected_subject != "All subjects" and selected_subject:
                    if selected_subject not in relative_path:
                        should_show = False

                # Session filter
                if selected_session != "All sessions" and selected_session:
                    if selected_session not in relative_path:
                        should_show = False

                # Modality filter
                if selected_modality != "All modalities" and selected_modality:
                    if selected_modality not in relative_path:
                        should_show = False

                # Data type filter
                if selected_datatype != "All types":
                    if f"/{selected_datatype}/" not in relative_path and f"\\{selected_datatype}\\" not in relative_path:
                        should_show = False

                # Filter for presence/absence of segmentation
                has_seg = relative_path in files_with_segmentations
                if show_only_no_seg and has_seg:
                    should_show = False
                if show_only_with_seg and not has_seg:
                    should_show = False

                item.setHidden(not should_show)
                if should_show:
                    visible_count += 1

            update_info_label(visible_count)

        # === EVENT CONNECTIONS ===
        search_bar.textChanged.connect(apply_filters)
        subject_combo.currentTextChanged.connect(apply_filters)
        session_combo.currentTextChanged.connect(apply_filters)
        modality_combo.currentTextChanged.connect(apply_filters)
        datatype_combo.currentTextChanged.connect(apply_filters)
        no_seg_checkbox.toggled.connect(apply_filters)
        with_seg_checkbox.toggled.connect(apply_filters)

        # Prevent both checkboxes from being selected together
        def on_no_seg_toggled(checked):
            if checked:
                with_seg_checkbox.setChecked(False)

        def on_with_seg_toggled(checked):
            if checked:
                no_seg_checkbox.setChecked(False)

        no_seg_checkbox.toggled.connect(on_no_seg_toggled)
        with_seg_checkbox.toggled.connect(on_with_seg_toggled)

        # === BUTTONS ===
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        # Reset filters button
        reset_button = QPushButton("Reset Filters")

        def reset_filters():
            search_bar.clear()
            subject_combo.setCurrentIndex(0)
            session_combo.setCurrentIndex(0)
            modality_combo.setCurrentIndex(0)
            datatype_combo.setCurrentIndex(0)
            no_seg_checkbox.setChecked(False)
            with_seg_checkbox.setChecked(False)

        reset_button.clicked.connect(reset_filters)
        buttons.addButton(reset_button, QDialogButtonBox.ButtonRole.ResetRole)

        # Select all visible files button
        select_all_button = QPushButton("Select All Visible")

        def select_all_visible():
            for i in range(file_list.count()):
                item = file_list.item(i)
                if not item.isHidden():
                    item.setSelected(True)

        select_all_button.clicked.connect(select_all_visible)
        buttons.addButton(select_all_button, QDialogButtonBox.ButtonRole.ActionRole)

        # Deselect all button
        deselect_all_button = QPushButton("Deselect All")

        def deselect_all():
            file_list.clearSelection()

        deselect_all_button.clicked.connect(deselect_all)
        buttons.addButton(deselect_all_button, QDialogButtonBox.ButtonRole.ActionRole)

        layout.addWidget(buttons)

        # === ACCEPTANCE LOGIC ===
        def accept():
            selected_items = file_list.selectedItems()
            # Filter only visible (not hidden) items
            visible_selected_items = [item for item in selected_items if not item.isHidden()]

            if not visible_selected_items:
                QMessageBox.warning(dialog, "No selection", "Please select at least one visible NIfTI file.")
                log.info("No selection")
                return

            selected_files = []
            files_with_warnings = []

            # Process each selected file
            for item in visible_selected_items:
                selected_relative_path = item.text()
                selected_absolute_path = relative_to_absolute[selected_relative_path]

                # If selected file already has segmentation, add to warnings list
                if selected_relative_path in files_with_segmentations:
                    files_with_warnings.append((selected_absolute_path, selected_relative_path))

                selected_files.append(selected_absolute_path)

            # If there are files with warnings, show message
            if files_with_warnings:
                if len(files_with_warnings) == 1:
                    # Single file with warning
                    selected_absolute_path, selected_relative_path = files_with_warnings[0]

                    # Extract patient ID
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
                    msg.setWindowTitle("Existing Segmentation Detected")
                    msg.setText(f"A deep learning segmentation already exists for {subject_display}.")
                    msg.setInformativeText(
                        f"File: {os.path.basename(selected_absolute_path)}\n\n"
                        "You can still proceed to create additional segmentations for this patient.\n"
                        "Do you want to continue with this selection?"
                    )
                    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                    if msg.exec() == QMessageBox.StandardButton.No:
                        return
                else:
                    # Multiple files with warnings
                    subjects_with_segs = set()
                    for selected_absolute_path, _ in files_with_warnings:
                        path_parts = selected_absolute_path.replace(self.context["workspace_path"], '').strip(
                            os.sep).split(os.sep)
                        for part in path_parts:
                            if part.startswith('sub-'):
                                subjects_with_segs.add(part)
                                break

                    msg = QMessageBox(dialog)
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("Existing Segmentations Detected")
                    msg.setText(f"Deep learning segmentations already exist for {len(subjects_with_segs)} patients:")

                    subject_list = ", ".join(sorted(subjects_with_segs))
                    msg.setInformativeText(
                        f"Patients: {subject_list}\n\n"
                        "You can still proceed to create additional segmentations for these patients.\n"
                        "Do you want to continue with this selection?"
                    )
                    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                    if msg.exec() == QMessageBox.StandardButton.No:
                        return

            # Proceed with selection
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

        # Update context with selected files for next page
        if self.context:
            self.context["selected_segmentation_files"] = file_paths
            if "update_main_buttons" in self.context:
                self.context["update_main_buttons"]()

    def clear_selected_files(self):
        self.selected_files = []
        self.file_list_widget.clear()
        self.clear_button.setEnabled(False)

        # Clear from context
        if self.context:
            self.context["selected_segmentation_files"] = []
            if "update_main_buttons" in self.context:
                self.context["update_main_buttons"]()

    def update_selected_files(self, files):
        """
        Update selected files and show warnings if segmentations exist for patients.
        """
        selected_files = []
        files_with_warnings = []

        # Check all NIfTI files in the list
        for path in files:
            if path.endswith(".nii") or path.endswith(".nii.gz"):
                # Check if segmentation already exists for this patient
                if self.has_existing_segmentation(path, self.context["workspace_path"]):
                    files_with_warnings.append(path)

                selected_files.append(path)

        # If there are files with warnings, show message
        if files_with_warnings:
            if len(files_with_warnings) == 1:
                path = files_with_warnings[0]
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
                msg.setWindowTitle("Existing Segmentation Detected")
                msg.setText(f"A deep learning segmentation already exists for {subject_display}.")
                msg.setInformativeText(
                    f"File: {os.path.basename(path)}\n\n"
                    "You can still proceed to create additional segmentations for this patient.\n"
                    "Do you want to continue with this selection?"
                )
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                if msg.exec() == QMessageBox.StandardButton.No:
                    self.selected_files = []
                    self.file_list_widget.clear()
                    self.clear_button.setEnabled(False)
                    if self.context:
                        self.context["selected_segmentation_files"] = []
                        if "update_main_buttons" in self.context:
                            self.context["update_main_buttons"]()
                    return
            else:
                subjects_with_segs = set()
                for path in files_with_warnings:
                    path_parts = path.replace(self.context["workspace_path"], '').strip(os.sep).split(os.sep)
                    for part in path_parts:
                        if part.startswith('sub-'):
                            subjects_with_segs.add(part)
                            break

                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle("Existing Segmentations Detected")
                msg.setText(f"Deep learning segmentations already exist for {len(subjects_with_segs)} patients:")

                subject_list = ", ".join(sorted(subjects_with_segs))
                msg.setInformativeText(
                    f"Patients: {subject_list}\n\n"
                    "You can still proceed to create additional segmentations for these patients.\n"
                    "Do you want to continue with this selection?"
                )
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setDefaultButton(QMessageBox.StandardButton.Yes)

                if msg.exec() == QMessageBox.StandardButton.No:
                    self.selected_files = []
                    self.file_list_widget.clear()
                    self.clear_button.setEnabled(False)
                    if self.context:
                        self.context["selected_segmentation_files"] = []
                        if "update_main_buttons" in self.context:
                            self.context["update_main_buttons"]()
                    return

        # Proceed with normal selection
        self.selected_files = selected_files
        self.file_list_widget.clear()

        for path in selected_files:
            item = QListWidgetItem(QIcon.fromTheme("document"), os.path.basename(path))
            item.setToolTip(path)
            self.file_list_widget.addItem(item)

        self.clear_button.setEnabled(bool(selected_files))

        # Update context
        if self.context:
            self.context["selected_segmentation_files"] = selected_files
            if "update_main_buttons" in self.context:
                self.context["update_main_buttons"]()

    def back(self):
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def next(self, context):
        """
        Salva i file selezionati nel contesto e avanza alla pagina successiva.
        """
        # Mettiamo i file selezionati nel contesto
        if self.context is not None:
            self.context["selected_segmentation_files"] = self.selected_files

        # Se la pagina successiva non è ancora stata creata, la instanziamo
        if not self.next_page:
            self.next_page = DlExecutionPage(self.context, self)
            if "history" in self.context:
                self.context["history"].append(self.next_page)

        # Prepariamo la prossima pagina
        self.next_page.on_enter()
        return self.next_page

    def on_enter(self):
        self.status_label.setText("")

    def is_ready_to_advance(self):
        return len(self.selected_files) > 0

    def is_ready_to_go_back(self):
        return True

    def reset_page(self):
        """Resets the page to its initial state, clearing all selections"""
        # Clear selected files
        self.selected_files = []
        self.file_list_widget.clear()

        # Reset buttons state
        self.clear_button.setEnabled(False)

        # Clear status message
        self.status_label.setText("")

        # Clear from context
        if self.context:
            self.context["selected_segmentation_files"] = []

    def _translate_ui(self):
        self.title.setText(QCoreApplication.translate("DlSelectionPage", "Select NIfTI files for Deep Learning Segmentation"))
        self.file_button.setText(QCoreApplication.translate("DlSelectionPage", "Choose NIfTI File(s)"))
        self.clear_button.setText(QCoreApplication.translate("DlSelectionPage", "Clear Selection"))

