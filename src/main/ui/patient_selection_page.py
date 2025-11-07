import shutil
import sys
import os

from PyQt6 import QtGui
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea, QFrame,
    QGridLayout, QHBoxLayout, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QCoreApplication

from ui.tool_selection_page import ToolSelectionPage
from utils import resource_path
from page import Page
from logger import get_logger

log = get_logger()


class PatientSelectionPage(Page):
    """
    Page for selecting patients to analyze.

    Displays all patient directories found in the workspace and allows
    selecting/deselecting them individually or in bulk. Supports dynamic layout
    resizing, deletion of unselected patients, and navigation to the next step.

    Attributes
    ----------
    context : dict
        Application-wide shared state (paths, callbacks, etc.).
    previous_page : Page | None
        The page to return to when navigating backward.
    next_page : Page | None
        The next page to navigate to.
    workspace_path : str
        Base folder containing patient data.
    patient_buttons : dict[str, QPushButton]
        Mapping of patient IDs to their toggle buttons.
    selected_patients : set[str]
        IDs of currently selected patients.
    column_count : int
        Number of columns in the patient grid.
    """

    def __init__(self, context=None, previous_page=None):
        """
        Initialize the patient selection page UI and logic.

        Parameters
        ----------
        context : dict, optional
            Shared context containing app settings and UI references.
        previous_page : Page, optional
            Reference to the previous page for navigation.
        """
        super().__init__()

        self.context = context
        self.previous_page = previous_page
        self.next_page = None
        self.workspace_path = context["workspace_path"]

        self.patient_buttons = {}
        self.selected_patients = set()

        # ----- Layout setup -----
        self.layout = QVBoxLayout(self)
        self.title = QLabel("Select Patients to Analyze")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.layout.addWidget(self.title)

        # ----- Top button controls -----
        top_buttons_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.deselect_all_btn = QPushButton("Deselect All")

        # Button styling
        btn_style = """
            QPushButton {
                background-color: #e0e0e0;
                padding: 10px 20px;
                border-radius: 10px;
                border: 1px solid #bdc3c7;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """
        self.select_all_btn.setStyleSheet(btn_style)
        self.deselect_all_btn.setStyleSheet(btn_style)

        # Button actions
        self.select_all_btn.clicked.connect(self._select_all_patients)
        self.deselect_all_btn.clicked.connect(self._deselect_all_patients)

        top_buttons_layout.addStretch()
        top_buttons_layout.addWidget(self.select_all_btn)
        top_buttons_layout.addWidget(self.deselect_all_btn)
        self.layout.addLayout(top_buttons_layout)

        # ----- Scroll area for patient cards -----
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                font-size: 13px;
                border: 1px solid #CCCCCC;
                border-radius: 10px;
                padding: 5px;
            }
        """)

        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area)

        self.column_count = 2  # Default column layout
        self._load_patients()

        # ----- Translation / Localization -----
        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    # -------------------------------------------------------
    # Dynamic Layout & Resizing
    # -------------------------------------------------------

    def _update_column_count(self):
        """Adjust grid column count dynamically based on window width."""
        available_width = self.scroll_area.viewport().width() - 40
        min_card_width = 250
        new_column_count = max(1, available_width // min_card_width)

        if new_column_count != self.column_count:
            self.column_count = new_column_count
            self._reload_patient_grid()

    def resizeEvent(self, event):
        """Update layout columns when the window is resized."""
        super().resizeEvent(event)
        self._update_column_count()

    def _reload_patient_grid(self):
        """Reload patient cards keeping previous selection state."""
        selected = self.selected_patients.copy()
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        self._load_patients()
        self.selected_patients = selected

    # -------------------------------------------------------
    # Navigation
    # -------------------------------------------------------

    def on_enter(self):
        """Called when the page becomes active."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._load_patients()

    def is_ready_to_advance(self):
        """Return True if at least one patient is selected."""
        return bool(self.selected_patients)

    def is_ready_to_go_back(self):
        """This page can always go back to the previous one."""
        return True

    def next(self, context):
        """
        Proceed to the next page, deleting unselected patient directories.

        Returns
        -------
        Page | None
            The next page to show, or None if the user cancels.
        """
        to_delete = [
            p for p in self._find_patient_dirs()
            if os.path.basename(p) not in self.selected_patients and os.path.basename(p) != "derivatives"
        ]
        unselected_ids = [os.path.basename(p) for p in to_delete]

        # Confirm deletion of unselected patients
        if to_delete:
            reply = QMessageBox.question(
                self,
                QCoreApplication.translate("PatientSelectionPage", "Confirm Cleanup"),
                QCoreApplication.translate(
                    "PatientSelectionPage",
                    "{0} unselected patient(s) will be removed from the workspace. Continue?"
                ).format(len(to_delete)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                return None

            # Delete directories
            for patient_path in to_delete:
                try:
                    shutil.rmtree(patient_path)
                    patient_id = os.path.basename(patient_path)
                    self.selected_patients.discard(patient_id)
                    log.info(f"Deleted patient directory: {patient_path}")
                except Exception as e:
                    log.error(f"Failed to delete {patient_path}: {e}")

            # Remove from 'derivatives'
            derivatives_root = os.path.join(self.workspace_path, "derivatives")
            if os.path.exists(derivatives_root):
                for root, dirs, _ in os.walk(derivatives_root, topdown=False):
                    for dir_name in dirs:
                        if dir_name in unselected_ids:
                            full_path = os.path.join(root, dir_name)
                            try:
                                shutil.rmtree(full_path)
                                log.info(f"Deleted from derivatives: {full_path}")
                            except Exception as e:
                                log.error(f"Failed to delete from derivatives: {full_path}: {e}")

        # Create next page if needed
        if not self.next_page:
            self.next_page = ToolSelectionPage(context, self)
            self.context["history"].append(self.next_page)

        self.next_page.on_enter()
        return self.next_page

    def back(self):
        """Return to the previous page, if any."""
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    # -------------------------------------------------------
    # Patient Loading & Selection
    # -------------------------------------------------------

    def _load_patients(self):
        """Load patient directories into the grid view."""
        patient_dirs = self._find_patient_dirs()
        patient_dirs.sort()
        self.patient_buttons.clear()

        for i, patient_path in enumerate(patient_dirs):
            patient_id = os.path.basename(patient_path)

            # Card container
            patient_frame = QFrame()
            patient_frame.setObjectName("patientCard")
            patient_frame.setStyleSheet("""
                QFrame#patientCard {
                    border: 1px solid #CCCCCC;
                    border-radius: 10px;
                    background-color: #FFFFFF;
                    padding: 6px;
                }
            """)
            patient_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            patient_frame.setMaximumHeight(140)

            # Layout for each patient card
            patient_layout = QHBoxLayout(patient_frame)
            patient_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            profile = QFrame()
            profile_layout = QVBoxLayout(profile)

            # Patient icon
            image = QLabel()
            pixmap = QtGui.QPixmap(resource_path("resources/user.png")).scaled(
                30, 30,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            image.setPixmap(pixmap)
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Label and selection button
            label = QLabel(f"{patient_id}")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            button = QPushButton(QCoreApplication.translate("PatientSelectionFrame", "Select"))
            button.setCheckable(True)
            button.setStyleSheet("""
                QPushButton {
                    border-radius: 12px;
                    padding: 8px 16px;
                    background-color: #DADADA;
                }
                QPushButton:checked {
                    background-color: #4CAF50;
                    color: white;
                }
            """)

            # Restore selection state
            is_selected = patient_id in self.selected_patients
            button.setChecked(is_selected)
            button.setText(
                QCoreApplication.translate("PatientSelectionFrame", "Selected")
                if is_selected else
                QCoreApplication.translate("PatientSelectionFrame", "Select")
            )
            button.clicked.connect(lambda checked, pid=patient_id, btn=button:
                                   self._toggle_patient(pid, checked, btn))

            self.patient_buttons[patient_id] = button

            # Assemble card
            profile_layout.addWidget(image)
            profile_layout.addWidget(label)
            patient_layout.addWidget(profile)
            patient_layout.addStretch()
            patient_layout.addWidget(button)

            self.grid_layout.addWidget(patient_frame, i // self.column_count, i % self.column_count)

    def _select_all_patients(self):
        """Mark all patients as selected."""
        for patient_id, button in self.patient_buttons.items():
            if not button.isChecked():
                button.setChecked(True)
                button.setText(QCoreApplication.translate("PatientSelectionFrame", "Selected"))
                self.selected_patients.add(patient_id)
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def _deselect_all_patients(self):
        """Unselect all patients."""
        for patient_id, button in self.patient_buttons.items():
            if button.isChecked():
                button.setChecked(False)
                button.setText(QCoreApplication.translate("PatientSelectionFrame", "Select"))
                self.selected_patients.discard(patient_id)
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def _find_patient_dirs(self):
        """Recursively find all patient directories (sub-*) in the workspace."""
        patient_dirs = []
        for root, dirs, _ in os.walk(self.workspace_path):
            # Skip derivatives and pipeline folders
            for skip in ("derivatives", "pipeline"):
                if skip in dirs:
                    dirs.remove(skip)

            # Collect patient directories
            for dir_name in dirs:
                if dir_name.startswith("sub-"):
                    patient_dirs.append(os.path.join(root, dir_name))

            # Prevent recursion into patient subdirectories
            dirs[:] = [d for d in dirs if not d.startswith("sub-")]

        return patient_dirs

    def _toggle_patient(self, patient_id, is_selected, button):
        """Toggle selection for a single patient."""
        if is_selected:
            self.selected_patients.add(patient_id)
            button.setText(QCoreApplication.translate("PatientSelectionFrame", "Selected"))
        else:
            self.selected_patients.discard(patient_id)
            button.setText(QCoreApplication.translate("PatientSelectionFrame", "Select"))

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def get_selected_patients(self):
        """Return a list of selected patient IDs."""
        return list(self.selected_patients)

    def reset_page(self):
        """Reset the UI, clearing selections and reloading patients."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        self.selected_patients.clear()
        self.patient_buttons.clear()
        self._load_patients()

    # -------------------------------------------------------
    # Translation
    # -------------------------------------------------------

    def _translate_ui(self):
        """Apply localized text to all UI elements."""
        self.title.setText(QCoreApplication.translate("PatientSelectionFrame", "Select Patients to Analyze"))
        self.select_all_btn.setText(QCoreApplication.translate("PatientSelectionFrame", "Select All"))
        self.deselect_all_btn.setText(QCoreApplication.translate("PatientSelectionFrame", "Deselect All"))
        self._load_patients()
