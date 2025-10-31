import os
import re

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QWidget, QLabel, QRadioButton,
    QButtonGroup, QFrame, QGroupBox, QComboBox, QDialogButtonBox
)


class FileRoleDialog(QDialog):
    """
    A multistep dialog for assigning a file's logical role within a workspace.

    Structure:
      1. Main or Derivatives
      2. Subject selection (e.g., sub-001)
      3. Role selection (e.g., anat, ses-01, ses-02)

    Dynamically adapts based on the provided arguments:
        - `main`, `subj`, and `role` can be pre-filled to skip steps.
    """

    def __init__(self, workspace_path=None, subj=None, role=None, main=None, parent=None):
        super().__init__(parent)

        # Store initial state and references
        self.subj = subj
        self.role = role
        self.main = main
        self.workspace_path = workspace_path

        # Dialog setup
        self.setWindowTitle(QCoreApplication.translate("Components", "File role"))
        layout = QVBoxLayout(self)

        # ----------------------------------------------------------------------
        # LEVEL 1 — MAIN / DERIVATIVES SELECTION
        # ----------------------------------------------------------------------
        if main is None and subj is None:
            # Widget container for level 1
            self.level1_widget = QWidget()
            level1_layout = QVBoxLayout(self.level1_widget)

            # Label for level 1
            self.pos_label = QLabel(QCoreApplication.translate("Components", "Position:"))
            level1_layout.addWidget(self.pos_label)

            # Two radio options: main or derivatives
            self.opt_main = QRadioButton(QCoreApplication.translate("Components", "main subject files"))
            self.opt_derivatives = QRadioButton("derivatives")
            level1_layout.addWidget(self.opt_main)
            level1_layout.addWidget(self.opt_derivatives)

            # Group radio buttons to make them mutually exclusive
            self.button_first_group = QButtonGroup(self)
            self.button_first_group.addButton(self.opt_main)
            self.button_first_group.addButton(self.opt_derivatives)

            layout.addWidget(self.level1_widget)

            # When toggled, show/hide derivative options
            self.button_first_group.buttonToggled.connect(self.first_level_toggled)

            # --- Additional frame for choosing derivative type (hidden by default)
            self.derivative_extra_frame = QFrame()
            derivative_extra_layout = QVBoxLayout(self.derivative_extra_frame)
            self.derivative_extra_label = QLabel(QCoreApplication.translate("Components", "What derivative:"))
            derivative_extra_layout.addWidget(self.derivative_extra_label)

            # Create sub-options for derivatives
            self.derivative_extra_button_group = QButtonGroup(self)
            self.skull_strip_btn = QRadioButton("skullstrips")
            derivative_extra_layout.addWidget(self.skull_strip_btn)
            self.derivative_extra_button_group.addButton(self.skull_strip_btn)

            self.manual_mask_btn = QRadioButton("manual_masks")
            derivative_extra_layout.addWidget(self.manual_mask_btn)
            self.derivative_extra_button_group.addButton(self.manual_mask_btn)

            self.deep_learning_mask = QRadioButton("deep_learning_seg")
            derivative_extra_layout.addWidget(self.deep_learning_mask)
            self.derivative_extra_button_group.addButton(self.deep_learning_mask)

            # Initially hidden (only shown when “derivatives” is selected)
            self.derivative_extra_frame.hide()
            layout.addWidget(self.derivative_extra_frame)

        elif main == "derivatives":
            # When `main` is pre-set to “derivatives”, show only derivative subtype
            self.derivative_extra_frame = QFrame(self)
            derivative_extra_layout = QVBoxLayout(self.derivative_extra_frame)
            self.derivative_extra_label = QLabel(QCoreApplication.translate("Components", "What derivative:"))
            derivative_extra_layout.addWidget(self.derivative_extra_label)

            self.derivative_extra_button_group = QButtonGroup(self)
            self.skull_strip_btn = QRadioButton("skullstrips")
            derivative_extra_layout.addWidget(self.skull_strip_btn)
            self.derivative_extra_button_group.addButton(self.skull_strip_btn)

            self.manual_mask_btn = QRadioButton("manual_masks")
            derivative_extra_layout.addWidget(self.manual_mask_btn)
            self.derivative_extra_button_group.addButton(self.manual_mask_btn)

            self.deep_learning_mask = QRadioButton("deep_learning_seg")
            derivative_extra_layout.addWidget(self.deep_learning_mask)
            self.derivative_extra_button_group.addButton(self.deep_learning_mask)

            layout.addWidget(self.derivative_extra_frame)
            self.button_first_group = None  # no top-level main/derivatives group in this case

        else:
            # If `main` is not relevant, skip both
            self.button_first_group = None
            self.derivative_extra_button_group = None

        # ----------------------------------------------------------------------
        # LEVEL 2 — SUBJECT SELECTION
        # ----------------------------------------------------------------------
        if subj is None:
            # Group box for subject selection
            self.level2_widget = QGroupBox(QCoreApplication.translate("Components", "Subject"))
            level2_layout = QVBoxLayout(self.level2_widget)

            # Gather all available subjects (folders starting with "sub-")
            subjects = [os.path.basename(p) for p in self._find_patient_dirs()]

            # Use a dropdown instead of multiple radio buttons
            self.subj_combo = QComboBox()
            self.subj_combo.addItems(subjects)
            level2_layout.addWidget(self.subj_combo)

            # Placeholder for backward compatibility
            self.subj_buttons = []
            self.button_second_group = None

            layout.addWidget(self.level2_widget)
        else:
            self.button_second_group = None

        # ----------------------------------------------------------------------
        # LEVEL 3 — ROLE / SESSION SELECTION
        # ----------------------------------------------------------------------
        if role is None:
            self.level3_widget = QWidget()
            level3_layout = QVBoxLayout(self.level3_widget)
            self.role_label = QLabel(QCoreApplication.translate("Components", "Role:"))
            level3_layout.addWidget(self.role_label)

            # Possible role choices
            self.button_third_group = QButtonGroup(self)
            self.anat_button = QRadioButton("anat")
            self.button_third_group.addButton(self.anat_button)
            level3_layout.addWidget(self.anat_button)

            self.ses_1_button = QRadioButton("ses-01")
            self.button_third_group.addButton(self.ses_1_button)
            level3_layout.addWidget(self.ses_1_button)

            self.ses_2_button = QRadioButton("ses-02")
            self.button_third_group.addButton(self.ses_2_button)
            level3_layout.addWidget(self.ses_2_button)

            layout.addWidget(self.level3_widget)
        else:
            self.button_third_group = None

        # ----------------------------------------------------------------------
        # DIALOG BUTTONS (OK / CANCEL)
        # ----------------------------------------------------------------------
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Keep reference to OK button so we can enable/disable it
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)  # initially disabled

        # ----------------------------------------------------------------------
        # SIGNAL CONNECTIONS FOR VALIDATION
        # ----------------------------------------------------------------------
        if self.button_first_group:
            self.button_first_group.buttonToggled.connect(self.update_ok_button)

        if self.derivative_extra_button_group:
            self.derivative_extra_button_group.buttonToggled.connect(self.update_ok_button)

        if hasattr(self, "subj_combo"):
            self.subj_combo.currentIndexChanged.connect(self.update_ok_button)

        if self.button_third_group:
            self.button_third_group.buttonToggled.connect(self.update_ok_button)

    # ======================================================================
    # SUPPORT METHODS
    # ======================================================================

    def filter_subjects(self, text):
        """Live filter for subjects (used if implemented with QListWidget)."""
        if hasattr(self, "subj_list"):
            for i in range(self.subj_list.count()):
                item = self.subj_list.item(i)
                item.setHidden(text.lower() not in item.text().lower())

    def get_selections(self):
        """Return all selected values from each level as a dictionary."""
        selections = {}

        # --- Level 1: Main / Derivatives ---
        if self.button_first_group:
            btn = self.button_first_group.checkedButton()
            selections["main"] = btn.text() if btn else None

        if self.derivative_extra_button_group:
            btn = self.derivative_extra_button_group.checkedButton()
            selections["derivative"] = btn.text() if btn else None

        # --- Level 2: Subject ---
        if self.button_second_group:
            btn = self.button_second_group.checkedButton()
            selections["subj"] = btn.text() if btn else None
        elif hasattr(self, "subj_combo"):
            selections["subj"] = self.subj_combo.currentText()

        # --- Level 3: Role ---
        if self.button_third_group:
            btn = self.button_third_group.checkedButton()
            selections["role"] = btn.text() if btn else None

        return selections

    def get_relative_path(self):
        """
        Build a relative path string (BIDS-like) from user selections.
        Example:
            derivatives/manual_masks/sub-001/ses-01/pet
        """
        parts = []
        selections = self.get_selections()

        main = selections.get("main")
        subj = selections.get("subj")
        role = selections.get("role")
        derivative = selections.get("derivative")

        # Handle derivatives hierarchy
        if main == "derivatives":
            parts.append("derivatives")
            if derivative:
                parts.append(derivative)

        # Add subject
        if subj:
            parts.append(subj)

        # Add role (special handling for session)
        if role:
            if re.match(r"^ses-\d+$", role):
                parts.append(role)
                parts.append("pet")  # convention for PET session directories
            else:
                parts.append(role)

        return os.path.join(*parts) if parts else None

    def _find_patient_dirs(self):
        """Return list of patient directories (sub-xxx), excluding 'derivatives'."""
        patient_dirs = []

        for root, dirs, files in os.walk(self.workspace_path):
            # Exclude derivatives from search
            if "derivatives" in dirs:
                dirs.remove("derivatives")

            # Collect dirs starting with 'sub-'
            for dir_name in dirs:
                if dir_name.startswith("sub-"):
                    full_path = os.path.join(root, dir_name)
                    patient_dirs.append(full_path)

        return patient_dirs

    # ----------------------------------------------------------------------
    # UI DYNAMICS
    # ----------------------------------------------------------------------
    def first_level_toggled(self, button, checked):
        """Show/hide derivative subtype section depending on selection."""
        if not checked:
            return
        if button == self.opt_main:
            self.derivative_extra_frame.hide()
            self.adjustSize()
        if button == self.opt_derivatives:
            self.derivative_extra_frame.show()
            self.adjustSize()

    def update_ok_button(self):
        """Enable OK only when all required selections are made."""
        selections = self.get_selections()
        enable = True

        # Require main selection
        if not selections.get("main"):
            enable = False

        # Require derivative type if derivatives is selected
        if selections.get("main") == "derivatives" and not selections.get("derivative"):
            enable = False

        # Require subject selection
        if not selections.get("subj"):
            enable = False

        # Require role selection
        if not selections.get("role"):
            enable = False

        # Update OK button state
        self.ok_button.setEnabled(enable)
