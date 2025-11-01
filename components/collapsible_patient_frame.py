import glob
import os

from PyQt6.QtCore import pyqtSignal, Qt, QSize, QPropertyAnimation, QEasingCurve, QCoreApplication
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QHBoxLayout,
    QLabel, QToolButton, QComboBox, QPushButton
)

# ------------------------------
# Custom QFrame subclass that emits a signal when clicked.
# Used to make headers clickable.
# ------------------------------
class ClickableFrame(QFrame):
    # Signal emitted when the frame is clicked
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()  # Emit custom signal when frame is clicked


# ------------------------------
# Main collapsible frame for displaying patient data.
# It shows the patient name, available files (one or multiple),
# and supports saving a configuration per patient.
# ------------------------------
class CollapsiblePatientFrame(QFrame):
    def __init__(self, context, patient_id, files, patterns, multiple_choice=False, save_callback=None):
        super().__init__()
        self.patient_id = patient_id
        self.workspace_path = context["workspace_path"]  # Root folder of workspace
        self.patterns = patterns  # File search patterns per category (e.g. {"pet4d": ["*/PET4D*.nii.gz"]})
        self.files = files  # Dictionary of selected files per category
        self.multiple_choice = multiple_choice  # Whether multiple files are allowed to be chosen
        self.is_expanded = False  # State of the collapsible section
        self.category_widgets = {}  # To store widgets (like combos) per category
        self.save_callback = save_callback  # Function to call when saving
        self.locked = not multiple_choice  # If single-choice mode, automatically locked

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("collapsiblePatientFrame")

        # Add a subtle drop shadow to the frame for depth
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 1)
        self.setGraphicsEffect(shadow)

        # Build visual layout and connect signals
        self._build_ui()
        self._apply_style()

        # Handle translation/localization
        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    # ------------------------------
    # Set visual style based on "locked" status.
    # Locked (white frame) = auto-selected
    # Unlocked (yellow frame) = requires manual selection.
    # ------------------------------
    def _apply_style(self):
        if self.locked:
            self.setStyleSheet("""
                QFrame#collapsiblePatientFrame {
                    background: white;
                    border: 1px solid #4CAF50;
                    border-radius: 10px;
                    padding: 10px;
                    margin: 2px;
                }
            """)
            self.toggle_button.setStyleSheet("""
                QToolButton {
                    font-size: 13px;
                    font-weight: bold;
                    color: #222;
                    border: none;
                    padding: 6px 8px 6px 4px;
                    text-align: right;
                    border-radius: 6px;
                }
                QToolButton:hover {
                    background-color: rgba(0, 0, 0, 0.05);
                }
                QToolButton:checked {
                    background-color: rgba(155, 155, 155, 0.15);
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#collapsiblePatientFrame {
                    border: 2px solid #FFC107;
                    border-radius: 10px;
                    background-color: #FFF8E1;
                    padding: 10px;
                    margin: 2px;
                }
            """)
            self.toggle_button.setStyleSheet("""
                QToolButton {
                    font-size: 13px;
                    font-weight: bold;
                    color: #222;
                    border: none;
                    padding: 6px 8px 6px 4px;
                    text-align: right;
                    border-radius: 6px;
                }
                QToolButton:hover {
                    background-color: rgba(0, 0, 0, 0.05);
                }
                QToolButton:checked {
                    background-color: rgba(255, 193, 7, 0.15);
                }
            """)

    # ------------------------------
    # Build the UI layout and main widgets.
    # Includes header, toggle button, collapsible content area.
    # ------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # --- HEADER SECTION ---
        frame_header = ClickableFrame(self)
        frame_header_layout = QHBoxLayout(frame_header)

        # Patient label
        self.subject_name = QLabel(self)
        self.subject_name.setText(QCoreApplication.translate("Components", "Patient: {0}").format(self.patient_id))
        self.subject_name.setStyleSheet("font-size: 13px; font-weight: bold;")
        frame_header_layout.addWidget(self.subject_name)

        # Expand/collapse button
        self.toggle_button = QToolButton(self)
        self.toggle_button.setText(QCoreApplication.translate("Components", "Patient: {patient}").format(patient=self.patient_id))
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setIconSize(QSize(14, 14))
        self.toggle_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Connect toggle behavior
        self.toggle_button.clicked.connect(self._toggle_expand)
        frame_header.clicked.connect(self._on_header_clicked)

        frame_header_layout.addWidget(self.toggle_button)
        layout.addWidget(frame_header)

        # --- COLLAPSIBLE CONTENT SECTION ---
        self.content_frame = QFrame()
        self.content_frame.setStyleSheet("QFrame { border-radius: 4px; padding: 4px; }")
        self.content_frame.setMaximumHeight(0)  # Start collapsed
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(8, 4, 8, 4)
        self.content_layout.setSpacing(6)

        self._populate_content()
        layout.addWidget(self.content_frame)

        # --- COLLAPSE/EXPAND ANIMATION ---
        self.animation = QPropertyAnimation(self.content_frame, b"maximumHeight")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    # ------------------------------
    # Populate the collapsible content area with file options.
    # If locked → static label. If editable → combo box.
    # ------------------------------
    def _populate_content(self):
        # Clear existing widgets
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # For each category (like CT, PET4D, etc.)
        for category, pat_list in self.patterns.items():
            category_container = QFrame()
            category_layout = QVBoxLayout(category_container)
            category_layout.setContentsMargins(6, 4, 6, 4)
            category_layout.setSpacing(4)

            category_label = QLabel(category.replace("_", " ").title())
            category_label.setStyleSheet("font-size: 13px; font-weight: bold;")

            # Search for files matching the patterns
            all_files = []
            for pat in pat_list:
                all_files.extend(glob.glob(pat))
            all_files_rel = [os.path.relpath(f, self.workspace_path) for f in all_files]

            # --- SINGLE FILE MODE (locked) ---
            if self.locked:
                self.chosen_file = self.files.get(category, "")
                self.file_label = QLabel(self.chosen_file if self.chosen_file else QCoreApplication.translate("Components", "No file found"))
                category_layout.addWidget(category_label)
                category_layout.addWidget(self.file_label)

                # If category is PET4D, also show JSON info
                if category == "pet4d":
                    self._add_pet4d_json_display(category_layout, self.chosen_file)

            # --- MULTIPLE CHOICE MODE ---
            else:
                combo = QComboBox()
                combo.setMinimumHeight(28)
                combo.addItems(all_files_rel)
                current_file = self.files.get(category)
                if current_file in all_files_rel:
                    combo.setCurrentIndex(all_files_rel.index(current_file))
                elif all_files_rel:
                    combo.setCurrentIndex(0)
                self.category_widgets[category] = combo
                category_layout.addWidget(category_label)
                category_layout.addWidget(combo)

                if category == "pet4d":
                    # Display associated JSON dynamically
                    self.pet4d_json_label = QLabel()
                    self.pet4d_json_label.setWordWrap(True)
                    category_layout.addWidget(self.pet4d_json_label)

                    combo.currentIndexChanged.connect(self._update_pet4d_json_display)
                    self._update_pet4d_json_display()

            self.content_layout.addWidget(category_container)

        # Add Save button if editable
        if not self.locked:
            save_container = QFrame()
            save_layout = QHBoxLayout(save_container)
            save_layout.setContentsMargins(6, 10, 6, 4)

            self.save_btn = QPushButton(QCoreApplication.translate("Components", "Save Patient Configuration"))
            self.save_btn.setMinimumHeight(32)
            self.save_btn.setStyleSheet("""
                QPushButton {
                    font-size: 12px;
                    font-weight: bold;
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 12px;
                    padding: 8px 16px;
                }
                QPushButton:hover { background-color: #45a049; }
            """)
            self.save_btn.clicked.connect(self._save_patient)

            save_layout.addStretch()
            save_layout.addWidget(self.save_btn)
            save_layout.addStretch()
            self.content_layout.addWidget(save_container)

    # ------------------------------
    # Helper: show JSON file associated with PET4D data (locked mode).
    # ------------------------------
    def _add_pet4d_json_display(self, parent_layout, pet4d_file_rel):
        if not pet4d_file_rel:
            label = QLabel(QCoreApplication.translate("Components", "<span style='color:red;'>No PET4D file selected</span>"))
            parent_layout.addWidget(label)
            return

        abs_pet4d_path = os.path.join(self.workspace_path, pet4d_file_rel)
        json_candidate = abs_pet4d_path.replace(".nii.gz", ".json").replace(".nii", ".json")

        if os.path.exists(json_candidate):
            rel_json = os.path.relpath(json_candidate, self.workspace_path)
            label = QLabel(QCoreApplication.translate("Components", "JSON related: <strong>{rel_json}</strong>").format(rel_json=rel_json))
            label.setStyleSheet("color: black; font-size: 12px;")
            self.files["pet4d_json"] = rel_json
        else:
            label = QLabel(QCoreApplication.translate("Components", "<span style='color:red;'>Error: associated JSON file not found</span>"))
            self.files["pet4d_json"] = ""

        label.setWordWrap(True)
        parent_layout.addWidget(label)

    # ------------------------------
    # Update JSON label dynamically when PET4D combo changes.
    # ------------------------------
    def _update_pet4d_json_display(self):
        if "pet4d" not in self.category_widgets:
            return

        combo = self.category_widgets["pet4d"]
        selected_file = combo.currentText()
        if not selected_file:
            self.pet4d_json_label.setText(QCoreApplication.translate("Components", "<span style='color:red;'>No PET4D file selected</span>"))
            return

        abs_pet4d_path = os.path.join(self.workspace_path, selected_file)
        json_candidate = abs_pet4d_path.replace(".nii.gz", ".json").replace(".nii", ".json")

        if os.path.exists(json_candidate):
            rel_json = os.path.relpath(json_candidate, self.workspace_path)
            self.pet4d_json_label.setText(QCoreApplication.translate("Components", "JSON related: <strong>{rel_json}</strong>").format(rel_json=rel_json))
            self.pet4d_json_label.setStyleSheet("color: black; font-size: 12px;")
            self.files["pet4d_json"] = rel_json
        else:
            self.pet4d_json_label.setText(QCoreApplication.translate("Components", "<span style='color:red;'>Error: associated JSON file not found</span>"))
            self.files["pet4d_json"] = ""

    # ------------------------------
    # Header click toggles expansion (alternative to pressing button).
    # ------------------------------
    def _on_header_clicked(self):
        new_state = not self.toggle_button.isChecked()
        self.toggle_button.setChecked(new_state)
        self._toggle_expand(new_state)

    # ------------------------------
    # Animate expand/collapse of the content frame.
    # ------------------------------
    def _toggle_expand(self, checked):
        self.is_expanded = checked
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.animation.setStartValue(self.content_frame.maximumHeight())
        self.animation.setEndValue(self.content_frame.sizeHint().height() if checked else 0)
        self.animation.start()

    # ------------------------------
    # Save current patient configuration (if editable).
    # ------------------------------
    def _save_patient(self):
        # Save current combo selections
        for category, combo in self.category_widgets.items():
            self.files[category] = combo.currentText()

        # Mark as reviewed
        self.files["need_revision"] = False

        # Call external save handler if provided
        if self.save_callback:
            self.save_callback(self.patient_id, self.files)

        # Lock and refresh UI
        self.locked = True
        self._apply_style()
        self._populate_content()

    # ------------------------------
    # Reapply translations dynamically.
    # ------------------------------
    def _translate_ui(self):
        self.toggle_button.setText(QCoreApplication.translate("Components", "Patient: {patient}").format(patient=self.patient_id))
        self.subject_name.setText(QCoreApplication.translate("Components", "Patient: {0}").format(self.patient_id))

        if self.locked and hasattr(self, "file_label"):
            self.file_label.setText(self.chosen_file if self.chosen_file else QCoreApplication.translate("Components", "No file found"))
        if not self.locked:
            self.save_btn.setText(QCoreApplication.translate("Components", "Save Patient Configuration"))

        self._populate_content()
