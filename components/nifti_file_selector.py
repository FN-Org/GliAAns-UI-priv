from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QLineEdit, QComboBox,
    QCheckBox, QListWidget, QListWidgetItem, QPushButton, QDialogButtonBox,
    QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
import os
import logging

log = logging.getLogger(__name__)

class NiftiFileDialog(QDialog):
    def __init__(self, parent, workspace_path, allow_multiple=None, has_existing_func=None, label=None,forced_filters = None):
        super().__init__(parent)
        self.label = label
        self.setWindowTitle(f"Select NIfTI Files ({self.label})")
        self.resize(700, 650)

        self.workspace_path = workspace_path
        self.allow_multiple = allow_multiple
        self.has_existing_func = has_existing_func or (lambda *_: False)
        self.forced_filters = forced_filters or {}


        self.selected_files = []
        self.relative_to_absolute = {}
        self.files_with_flag = set()

        self._build_ui()
        self._populate_files()
        self._connect_signals()

    # === Public API ===
    @staticmethod
    def get_files(parent, workspace_path, allow_multiple=True, has_existing_func=None, label="mask",forced_filters=None):
        dialog = NiftiFileDialog(parent, workspace_path, allow_multiple, has_existing_func, label,forced_filters)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_files
        return None

    # === UI Construction ===
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # === Filters ===
        filter_group = QGroupBox("Filters")
        filter_layout = QGridLayout(filter_group)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search files (FLAIR, T1, T2, etc.)")
        self.search_bar.setClearButtonEnabled(True)
        filter_layout.addWidget(QLabel("Search:"), 0, 0)
        filter_layout.addWidget(self.search_bar, 0, 1, 1, 3)

        self.subject_combo = QComboBox()
        self.subject_combo.setEditable(True)
        self.subject_combo.lineEdit().setPlaceholderText("All subjects or type subject ID...")
        filter_layout.addWidget(QLabel("Subject:"), 1, 0)
        filter_layout.addWidget(self.subject_combo, 1, 1)

        self.session_combo = QComboBox()
        self.session_combo.setEditable(True)
        self.session_combo.lineEdit().setPlaceholderText("All sessions...")
        filter_layout.addWidget(QLabel("Session:"), 1, 2)
        filter_layout.addWidget(self.session_combo, 1, 3)

        self.modality_combo = QComboBox()
        self.modality_combo.setEditable(True)
        self.modality_combo.lineEdit().setPlaceholderText("All modalities...")
        filter_layout.addWidget(QLabel("Modality:"), 2, 0)
        filter_layout.addWidget(self.modality_combo, 2, 1)

        self.datatype_combo = QComboBox()
        self.datatype_combo.addItems(["All types", "anat", "func", "dwi", "fmap", "perf"])
        filter_layout.addWidget(QLabel("Data type:"), 2, 2)
        filter_layout.addWidget(self.datatype_combo, 2, 3)

        self.no_flag_checkbox = QCheckBox(f"Show only files without existing {self.label}s")
        self.with_flag_checkbox = QCheckBox(f"Show only files with existing {self.label}s")
        filter_layout.addWidget(self.no_flag_checkbox, 3, 0, 1, 2)
        filter_layout.addWidget(self.with_flag_checkbox, 3, 2, 1, 2)

        layout.addWidget(filter_group)

        # === Info label ===
        self.info_label = QLabel()
        layout.addWidget(self.info_label)

        # === File list ===
        self.file_list = QListWidget()
        self.file_list.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        self.file_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection if self.allow_multiple else QListWidget.SelectionMode.SingleSelection
        )
        self.file_list.setAlternatingRowColors(True)
        layout.addWidget(self.file_list)

        # === Buttons ===
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        reset_button = QPushButton("Reset Filters")
        select_all_button = QPushButton("Select All Visible")
        deselect_all_button = QPushButton("Deselect All")

        self.buttons.addButton(reset_button, QDialogButtonBox.ButtonRole.ResetRole)
        self.buttons.addButton(select_all_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.buttons.addButton(deselect_all_button, QDialogButtonBox.ButtonRole.ActionRole)

        layout.addWidget(self.buttons)

        # === Store buttons for handlers ===
        self._reset_button = reset_button
        self._select_all_button = select_all_button
        self._deselect_all_button = deselect_all_button

    # === Populate ===
    def _populate_files(self):
        self.all_nii_files = []
        subjects_set, sessions_set, modalities_set = set(), set(), set()

        for root, dirs, files in os.walk(self.workspace_path):
            dirs[:] = [d for d in dirs if d != "derivatives"]

            for f in files:
                if f.endswith((".nii", ".nii.gz")):
                    full_path = os.path.join(root, f)
                    relative_path = os.path.relpath(full_path, self.workspace_path)
                    self.all_nii_files.append(relative_path)
                    self.relative_to_absolute[relative_path] = full_path

                    path_parts = relative_path.split(os.sep)

                    # subject
                    for part in path_parts:
                        if part.startswith("sub-"):
                            subjects_set.add(part)
                            break

                    # session
                    for part in path_parts:
                        if part.startswith("ses-"):
                            sessions_set.add(part)
                            break

                    # modality
                    filename_noext = os.path.splitext(os.path.splitext(f)[0])[0]
                    modality = filename_noext.split("_")[-1] or "Unknown"
                    modalities_set.add(modality)

                    # existing flag (mask/skull strip)
                    if self.has_existing_func(full_path, self.workspace_path):
                        self.files_with_flag.add(relative_path)

        self.subject_combo.addItem("All subjects")
        self.subject_combo.addItems(sorted(subjects_set))

        self.session_combo.addItem("All sessions")
        self.session_combo.addItems(sorted(sessions_set))

        self.modality_combo.addItem("All modalities")
        self.modality_combo.addItems(sorted(modalities_set))

        self._update_info_label(len(self.all_nii_files))
        self._populate_file_list()

        if self.forced_filters:
            self._apply_forced_filters()


    def _populate_file_list(self):
        self.file_list.clear()
        for relative_path in sorted(self.all_nii_files):
            item = QListWidgetItem(relative_path)
            if relative_path in self.files_with_flag:
                item.setForeground(QBrush(QColor(255, 193, 7)))
                item.setToolTip(f"{self.relative_to_absolute[relative_path]}\n✓ Existing {self.label}")
            else:
                item.setToolTip(f"{self.relative_to_absolute[relative_path]}\n○ No {self.label}")
            self.file_list.addItem(item)

    # === Helpers ===
    def _update_info_label(self, visible_count):
        info_text = f"Showing {visible_count} of {len(self.all_nii_files)} files"
        if self.files_with_flag:
            info_text += f" ({len(self.files_with_flag)} with existing {self.label}s)"
        self.info_label.setText(info_text)
        self.info_label.setStyleSheet("color: gray; font-size: 10px;")

    def _apply_filters(self):
        search_text = self.search_bar.text().lower()
        selected_subject = self.subject_combo.currentText()
        selected_session = self.session_combo.currentText()
        selected_modality = self.modality_combo.currentText()
        selected_datatype = self.datatype_combo.currentText()

        show_only_no_flag = self.no_flag_checkbox.isChecked()
        show_only_with_flag = self.with_flag_checkbox.isChecked()

        visible_count = 0
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            relative_path = item.text()
            should_show = True

            if search_text and search_text not in relative_path.lower():
                should_show = False
            if selected_subject != "All subjects" and selected_subject not in relative_path:
                should_show = False
            if selected_session != "All sessions" and selected_session not in relative_path:
                should_show = False
            if selected_modality != "All modalities" and selected_modality not in relative_path:
                should_show = False
            if selected_datatype != "All types" and f"/{selected_datatype}/" not in relative_path and f"\\{selected_datatype}\\" not in relative_path:
                should_show = False

            has_flag = relative_path in self.files_with_flag
            if show_only_no_flag and has_flag:
                should_show = False
            if show_only_with_flag and not has_flag:
                should_show = False

            item.setHidden(not should_show)
            if should_show:
                visible_count += 1

        self._update_info_label(visible_count)

    # === Signals ===
    def _connect_signals(self):
        self.search_bar.textChanged.connect(self._apply_filters)
        self.subject_combo.currentTextChanged.connect(self._apply_filters)
        self.session_combo.currentTextChanged.connect(self._apply_filters)
        self.modality_combo.currentTextChanged.connect(self._apply_filters)
        self.datatype_combo.currentTextChanged.connect(self._apply_filters)
        self.no_flag_checkbox.toggled.connect(self._apply_filters)
        self.with_flag_checkbox.toggled.connect(self._apply_filters)

        def on_no_flag_toggled(checked):
            if checked:
                self.with_flag_checkbox.setChecked(False)
        def on_with_flag_toggled(checked):
            if checked:
                self.no_flag_checkbox.setChecked(False)
        self.no_flag_checkbox.toggled.connect(on_no_flag_toggled)
        self.with_flag_checkbox.toggled.connect(on_with_flag_toggled)

        self._reset_button.clicked.connect(self._reset_filters)
        self._select_all_button.clicked.connect(self._select_all_visible)
        self._deselect_all_button.clicked.connect(lambda: self.file_list.clearSelection())

        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)

    def _reset_filters(self):
        self.search_bar.clear()
        self.subject_combo.setCurrentIndex(0)
        self.session_combo.setCurrentIndex(0)
        self.modality_combo.setCurrentIndex(0)
        self.datatype_combo.setCurrentIndex(0)
        self.no_flag_checkbox.setChecked(False)
        self.with_flag_checkbox.setChecked(False)

    def _select_all_visible(self):
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if not item.isHidden():
                item.setSelected(True)

    def _accept(self):
        selected_items = [item for item in self.file_list.selectedItems() if not item.isHidden()]
        if not selected_items:
            QMessageBox.warning(self, "No selection", f"Please select at least one visible NIfTI file.")
            log.info("No selection")
            return

        selected_files = []
        warnings = []

        for item in selected_items:
            relative_path = item.text()
            abs_path = self.relative_to_absolute[relative_path]
            path_parts = abs_path.replace(self.workspace_path, '').strip(os.sep).split(os.sep)
            subject = next((p for p in path_parts if p.startswith('sub-')), None)
            session = next((p for p in path_parts if p.startswith('ses-')), None)
            filename = os.path.basename(abs_path)
            filename_noext = os.path.splitext(os.path.splitext(filename)[0])[0]
            modality = filename_noext.split("_")[-1] or "Unknown"
            datatype = next((p for p in path_parts if p in ["anat", "func", "dwi", "fmap", "perf"]), None)

            has_flag = relative_path in self.files_with_flag
            if has_flag:
                warnings.append((abs_path, subject))

            selected_files.append(abs_path)

        # Show warnings if needed
        if warnings:
            unique_subjects = sorted({s for _, s in warnings if s})
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle(f"Existing {self.label.title()} Detected")
            if len(unique_subjects) == 1:
                subject_display = unique_subjects[0] or "this patient"
                msg.setText(f"A {self.label} already exists for {subject_display}.")
            else:
                msg.setText(f"{self.label.title()}s already exist for {len(unique_subjects)} patients: {', '.join(unique_subjects)}")
            msg.setInformativeText(f"You can still proceed to create additional {self.label}s. Continue?")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if msg.exec() == QMessageBox.StandardButton.No:
                return

        self.selected_files = selected_files
        self.accept()

    def _apply_forced_filters(self):
        """Applica i filtri forzati definiti in self.forced_filters."""
        if "search" in self.forced_filters:
            self.search_bar.setText(self.forced_filters["search"])
            self.search_bar.setEnabled(False)

        if "subject" in self.forced_filters:
            self.subject_combo.setCurrentText(self.forced_filters["subject"])
            self.subject_combo.setEnabled(False)

        if "session" in self.forced_filters:
            self.session_combo.setCurrentText(self.forced_filters["session"])
            self.session_combo.setEnabled(False)

        if "modality" in self.forced_filters:
            self.modality_combo.setCurrentText(self.forced_filters["modality"])
            self.modality_combo.setEnabled(False)

        if "datatype" in self.forced_filters:
            self.datatype_combo.setCurrentText(self.forced_filters["datatype"])
            self.datatype_combo.setEnabled(False)

        if "no_flag" in self.forced_filters:
            self.no_flag_checkbox.setChecked(bool(self.forced_filters["no_flag"]))
            self.no_flag_checkbox.setEnabled(False)

        if "with_flag" in self.forced_filters:
            self.with_flag_checkbox.setChecked(bool(self.forced_filters["with_flag"]))
            self.with_flag_checkbox.setEnabled(False)

        # Riapplica i filtri alla lista
        self._apply_filters()



