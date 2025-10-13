from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QLineEdit, QComboBox,
    QCheckBox, QListWidget, QListWidgetItem, QPushButton, QDialogButtonBox,
    QMessageBox
)
from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QBrush, QColor
import os
from logger import get_logger

log = get_logger()

class NiftiFileDialog(QDialog):
    def __init__(self, context, allow_multiple=None, has_existing_func=None, label=None, forced_filters=None):
        super().__init__()
        self.label = label
        self.setWindowTitle(QCoreApplication.translate("Components", "Select NIfTI Files ({0})").format(self.label))
        self.resize(700, 650)

        self.workspace_path = context["workspace_path"]
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
    def get_files(context, allow_multiple=True, has_existing_func=None, label="mask",forced_filters=None):
        dialog = NiftiFileDialog(context, allow_multiple, has_existing_func, label,forced_filters)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_files
        return None

    # === UI Construction ===
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # === Filters ===
        filter_group = QGroupBox(QCoreApplication.translate("Components", "Filters"))
        filter_layout = QGridLayout(filter_group)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(QCoreApplication.translate("Components", "Search files (FLAIR, T1, T2, etc.)"))
        self.search_bar.setClearButtonEnabled(True)
        filter_layout.addWidget(QLabel(QCoreApplication.translate("Components", "Search:")), 0, 0)
        filter_layout.addWidget(self.search_bar, 0, 1, 1, 3)

        self.subject_combo = QComboBox()
        self.subject_combo.addItem(QCoreApplication.translate("Components", "All subjects"))
        self.subject_combo.model().item(0)
        filter_layout.addWidget(QLabel(QCoreApplication.translate("Components", "Subject:")), 1, 0)
        filter_layout.addWidget(self.subject_combo, 1, 1)

        self.session_combo = QComboBox()
        self.session_combo.addItem(QCoreApplication.translate("Components", "All sessions"))
        self.session_combo.model().item(0)
        filter_layout.addWidget(QLabel(QCoreApplication.translate("Components", "Session:")), 1, 2)
        filter_layout.addWidget(self.session_combo, 1, 3)

        self.modality_combo = QComboBox()
        self.modality_combo.addItem(QCoreApplication.translate("Components", "All modalities"))
        self.modality_combo.model().item(0)
        filter_layout.addWidget(QLabel(QCoreApplication.translate("Components", "Modality:")), 2, 0)
        filter_layout.addWidget(self.modality_combo, 2, 1)

        self.datatype_combo = QComboBox()
        self.datatype_combo.addItem(QCoreApplication.translate("Components", "All types"))
        self.datatype_combo.model().item(0)
        filter_layout.addWidget(QLabel(QCoreApplication.translate("Components", "Data type:")), 2, 2)
        filter_layout.addWidget(self.datatype_combo, 2, 3)

        self.no_flag_checkbox = QCheckBox(QCoreApplication.translate("Components", "Show only files without existing {0}s").format(self.label))
        self.with_flag_checkbox = QCheckBox(QCoreApplication.translate("Components", "Show only files with existing {0}s").format(self.label))
        if self.label is None:
            self.no_flag_checkbox.setVisible(False)
            self.with_flag_checkbox.setVisible(False)
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

        reset_button = QPushButton(QCoreApplication.translate("Components", "Reset Filters"))
        select_all_button = QPushButton(QCoreApplication.translate("Components", "Select All Visible"))
        deselect_all_button = QPushButton(QCoreApplication.translate("Components", "Deselect All"))

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
        subjects_set, sessions_set, modalities_set, datatypes_set = set(), set(), set(), set()

        for root, dirs, files in os.walk(self.workspace_path):
            # dirs[:] = [d for d in dirs if d != "derivatives"]

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
                    modality = filename_noext.split("_")[-1] or QCoreApplication.translate("Components", "Unknown")
                    modalities_set.add(modality)

                    # existing flag (mask/skull strip)
                    if self.has_existing_func(full_path, self.workspace_path):
                        self.files_with_flag.add(relative_path)

        # --- Cerca data type directories ---
        for subject_dir in sorted(Path(self.workspace_path).glob("sub-*")):
            if subject_dir.is_dir():
                # Caso: sub-*/anat, sub-*/func, ecc.
                for child in subject_dir.iterdir():
                    if child.is_dir() and not child.name.startswith("ses-"):
                        datatypes_set.add(child.name)

                # Caso: sub-*/ses-*/anat, sub-*/ses-*/func, ecc.
                for ses_dir in subject_dir.glob("ses-*"):
                    if ses_dir.is_dir():
                        for child in ses_dir.iterdir():
                            if child.is_dir():
                                datatypes_set.add(child.name)

        self.subject_combo.addItems(sorted(subjects_set))
        self.session_combo.addItems(sorted(sessions_set))
        self.modality_combo.addItems(sorted(modalities_set))
        self.datatype_combo.addItems(sorted(datatypes_set))

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
                item.setToolTip(QCoreApplication.translate("Components", "{0}\n✓ Existing {1}").format(self.relative_to_absolute[relative_path], self.label))
            else:
                item.setToolTip(QCoreApplication.translate("Components", "{0}\n○ No {1}").format(self.relative_to_absolute[relative_path], self.label))
            self.file_list.addItem(item)

    # === Helpers ===
    def _update_info_label(self, visible_count):
        info_text = QCoreApplication.translate("Components", "Showing {0} of {1} files").format(visible_count, len(self.all_nii_files))
        if self.files_with_flag:
            info_text += QCoreApplication.translate("Components", " ({0} with existing {1}s)").format(len(self.files_with_flag), self.label)
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
            if selected_subject != QCoreApplication.translate("Components", "All subjects") and selected_subject not in relative_path:
                should_show = False
            if selected_session != QCoreApplication.translate("Components", "All sessions") and selected_session not in relative_path:
                should_show = False
            if selected_modality != QCoreApplication.translate("Components", "All modalities") and selected_modality not in relative_path:
                should_show = False
            if selected_datatype != QCoreApplication.translate("Components", "All types") and f"/{selected_datatype}/" not in relative_path and f"\\{selected_datatype}\\" not in relative_path:
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
            QMessageBox.warning(
                self,
                QCoreApplication.translate("Components", "No selection"),
                QCoreApplication.translate("Components", "Please select at least one visible NIfTI file."))
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
            modality = filename_noext.split("_")[-1] or QCoreApplication.translate("Components", "Unknown")
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
            msg.setWindowTitle(QCoreApplication.translate("Components", "Existing {0} Detected").format(self.label.title()))
            if len(unique_subjects) == 1:
                subject_display = unique_subjects[0] or QCoreApplication.translate("Components", "this patient")
                msg.setText(QCoreApplication.translate("Components", "A {0} already exists for {1}.").format(self.label, subject_display))
            else:
                msg.setText(QCoreApplication.translate("Components", "{0}s already exist for {1} patients: {2}").format(self.label.title(), len(unique_subjects), ', '.join(unique_subjects)))
            msg.setInformativeText(QCoreApplication.translate("Components", "You can still proceed to create additional {0}s. Continue?").format(self.label))
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

        def safe_set_combo_value(combo, key):
            if key in self.forced_filters:
                value = self.forced_filters[key]
                index = combo.findText(value)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.addItem(value)
                    combo.setCurrentIndex(combo.count() - 1)
                combo.setEnabled(False)

        safe_set_combo_value(self.subject_combo, "subject")
        safe_set_combo_value(self.session_combo, "session")
        safe_set_combo_value(self.modality_combo, "modality")
        safe_set_combo_value(self.datatype_combo, "datatype")

        if "no_flag" in self.forced_filters:
            self.no_flag_checkbox.setChecked(bool(self.forced_filters["no_flag"]))
            self.no_flag_checkbox.setEnabled(False)

        if "with_flag" in self.forced_filters:
            self.with_flag_checkbox.setChecked(bool(self.forced_filters["with_flag"]))
            self.with_flag_checkbox.setEnabled(False)

        # Riapplica i filtri
        self._apply_filters()



