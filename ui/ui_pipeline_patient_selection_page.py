import json
import os
import glob

from PyQt6 import QtGui
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QGridLayout,
    QHBoxLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QCoreApplication

from ui.ui_pipeline_review_page import PipelineReviewPage
from utils import resource_path
from page import Page
from logger import get_logger

log = get_logger()


class PipelinePatientSelectionPage(Page):
    """
    Page that allows the user to select patients eligible for pipeline analysis.

    This class provides:
    - Automatic detection of patient folders within a workspace.
    - Validation of pipeline prerequisites (FLAIR, skull stripping, segmentation).
    - Interactive UI to select or deselect patients.
    - Generation of a JSON configuration file for the pipeline.
    """

    def __init__(self, context=None, previous_page=None):
        """
        Initialize the patient selection page.

        Args:
            context (dict): Shared context between pages.
            previous_page (Page): Reference to the previous page.
        """
        super().__init__()

        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.workspace_path = context["workspace_path"]

        # Maps patient_id -> QPushButton for selection toggling
        self.patient_buttons = {}
        # Set of currently selected patient IDs
        self.selected_patients = set()
        # Maps patient_id -> eligibility info
        self.patient_status = {}

        # Build UI layout and components
        self._setup_ui()

        # Setup translations (for multilingual UI)
        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    # ─────────────────────────────────────────────
    # UI CONSTRUCTION
    # ─────────────────────────────────────────────
    def _setup_ui(self):
        """Construct the overall page layout and initialize UI elements."""
        self.layout = QVBoxLayout(self)

        # --- Title section ---
        self.title = QLabel("Select Patients for Pipeline Analysis")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.layout.addWidget(self.title)

        # --- Top control buttons ---
        top_buttons_layout = QHBoxLayout()

        self.select_eligible_btn = QPushButton("Select All Eligible")
        self.deselect_all_btn = QPushButton("Deselect All")
        self.refresh_btn = QPushButton("Refresh Status")

        self.buttons = [self.select_eligible_btn, self.deselect_all_btn, self.refresh_btn]

        # Unified button style
        btn_style = """
            QPushButton {
                background-color: #e0e0e0;
                padding: 10px 20px;
                border-radius: 10px;
                border: 1px solid #bdc3c7;
                font-weight: bold;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #888888;
            }
        """
        for btn in self.buttons:
            btn.setStyleSheet(btn_style)

        # Connect button actions
        self.select_eligible_btn.clicked.connect(self._select_all_eligible_patients)
        self.deselect_all_btn.clicked.connect(self._deselect_all_patients)
        self.refresh_btn.clicked.connect(self._refresh_patient_status)

        # Add buttons to layout
        top_buttons_layout.addStretch()
        top_buttons_layout.addWidget(self.select_eligible_btn)
        top_buttons_layout.addWidget(self.deselect_all_btn)
        top_buttons_layout.addWidget(self.refresh_btn)
        self.layout.addLayout(top_buttons_layout)

        # --- Scroll area for patient cards ---
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

        # --- Summary header (Total / Eligible / Not Eligible) ---
        self.summary_widget = self._create_summary_widget()
        self.layout.addWidget(self.summary_widget)
        self.layout.addWidget(self.scroll_area)

        self.column_count = 2
        self._load_patients()

    def _create_summary_widget(self):
        """Create the summary section showing patient counts."""
        summary_frame = QFrame()
        summary_frame.setObjectName("summaryCard")
        summary_frame.setStyleSheet("""
            QFrame#summaryCard {
                border: 1px solid #e0e0e0;
                border-radius: 12px;
                background-color: #ffffff;
                padding: 0.1em;
            }
        """)

        main_layout = QVBoxLayout(summary_frame)

        # Section title
        self.title_summary = QLabel(QCoreApplication.translate("PipelinePatientSelectionPage", "Pipeline Requirements Summary"))
        self.title_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_summary.setStyleSheet("font-size: 16px; font-weight: bold; color: #000000; margin-bottom: 10px;")
        main_layout.addWidget(self.title_summary)

        # Pills showing numeric stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)

        self.total_label = self._create_stat_pill(resource_path("resources/icon_total.png"),
                                                  QCoreApplication.translate("PipelinePatientSelectionPage", "Total Patients"), "0")
        self.eligible_label = self._create_stat_pill(resource_path("resources/icon_check.png"),
                                                     QCoreApplication.translate("PipelinePatientSelectionPage", "Eligible"), "0",
                                                     color="#27ae60")
        self.not_eligible_label = self._create_stat_pill(resource_path("resources/icon_cross.png"),
                                                         QCoreApplication.translate("PipelinePatientSelectionPage", "Not Eligible"), "0",
                                                         color="#c0392b")

        for pill in [self.total_label, self.eligible_label, self.not_eligible_label]:
            pill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            stats_layout.addWidget(pill)

        main_layout.addLayout(stats_layout)
        return summary_frame

    def _create_stat_pill(self, icon_path, label_text, value_text, color="#000000"):
        """
        Create a small 'pill' UI component showing a metric and value.

        Args:
            icon_path (str): Path to the icon (unused in current version).
            label_text (str): Label of the metric (e.g., "Total Patients").
            value_text (str): Numerical value to display.
            color (str): Text color for the value.

        Returns:
            QFrame: The styled widget displaying the metric.
        """
        pill = QFrame()
        pill.setObjectName("summaryCard")
        pill.setStyleSheet("""
            QFrame#summaryCard {
                border: 1px solid #CCCCCC;
                border-radius: 10px;
                background-color: #f9f9f9;
            }
        """)

        layout = QVBoxLayout(pill)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 13px; font-weight: bold;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value = QLabel(value_text)
        value.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(label)
        layout.addWidget(value)

        pill.label = label
        pill.value_label = value
        pill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        pill.setMinimumHeight(50)
        pill.setMaximumHeight(120)
        return pill

    # ─────────────────────────────────────────────
    # PATIENT LOADING AND VALIDATION
    # ─────────────────────────────────────────────
    def _load_patients(self):
        """
        Scan the workspace directory and create patient cards for all detected patients.

        This function:
        - Searches for folders named `sub-*` under `workspace_path`.
        - Checks each patient's eligibility for pipeline processing.
        - Displays a grid of patient selection cards.
        - Updates summary counts (Total, Eligible, Not Eligible).
        """
        # Clear previous grid contents
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        self.patient_buttons.clear()
        self.patient_status.clear()

        # Find all sub-* folders in the workspace
        patient_dirs = sorted(
            [d for d in os.listdir(self.workspace_path) if d.startswith("sub-")]
        )

        total_patients = len(patient_dirs)
        eligible_count = 0
        not_eligible_count = 0

        # Create a grid of cards (2 columns)
        for idx, patient_id in enumerate(patient_dirs):
            patient_path = os.path.join(self.workspace_path, patient_id)

            # Determine eligibility and missing data
            is_eligible, missing_items = self._check_patient_requirements(patient_path)
            self.patient_status[patient_id] = (is_eligible, missing_items)

            # Build the card UI
            card = self._create_patient_frame(patient_id, is_eligible, missing_items)
            row, col = divmod(idx, self.column_count)
            self.grid_layout.addWidget(card, row, col)

            if is_eligible:
                eligible_count += 1
            else:
                not_eligible_count += 1

        # Update summary statistics
        self.total_label.value_label.setText(str(total_patients))
        self.eligible_label.value_label.setText(str(eligible_count))
        self.not_eligible_label.value_label.setText(str(not_eligible_count))

    def _check_patient_requirements(self, patient_path):
        """
        Verify if the given patient folder satisfies the requirements for pipeline analysis.

        The function checks for the following:
        - `FLAIR` image availability (e.g., *FLAIR.nii.gz*).
        - Skull stripping completion (`*_brainmask.nii.gz`).
        - Segmentation output (e.g., `seg_*.nii.gz`).

        Args:
            patient_path (str): Path to the patient's directory.

        Returns:
            tuple(bool, list[str]):
                - True if the patient has all required files.
                - List of missing or incomplete steps otherwise.
        """
        required = {
            "FLAIR": glob.glob(os.path.join(patient_path, "**", "*FLAIR*.nii*"), recursive=True),
            "SkullStripping": glob.glob(os.path.join(patient_path, "**", "*brainmask*.nii*"), recursive=True),
            "Segmentation": glob.glob(os.path.join(patient_path, "**", "seg_*.nii*"), recursive=True),
        }

        missing = [key for key, files in required.items() if not files]
        return len(missing) == 0, missing

    def _create_patient_frame(self, patient_id, is_eligible, missing_items):
        """
        Build a visual card for a patient with eligibility information.

        Each card contains:
        - The patient ID (e.g., sub-001)
        - Status (eligible / missing items)
        - A toggle button for selection

        Args:
            patient_id (str): Patient identifier.
            is_eligible (bool): Whether the patient meets all requirements.
            missing_items (list[str]): List of missing files or steps.

        Returns:
            QFrame: The completed patient card widget.
        """
        card = QFrame()
        card.setObjectName("patientCard")
        card.setStyleSheet("""
            QFrame#patientCard {
                border: 1px solid #bdc3c7;
                border-radius: 10px;
                background-color: #ffffff;
                margin: 5px;
            }
        """)

        layout = QVBoxLayout(card)

        # Patient title
        title = QLabel(patient_id)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px;")

        layout.addWidget(title)

        # Eligibility label
        status_label = QLabel()
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setWordWrap(True)

        if is_eligible:
            status_label.setText(QCoreApplication.translate("PipelinePatientSelectionPage", "✅ Eligible for pipeline"))
            status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            missing_str = ", ".join(missing_items)
            status_label.setText(
                QCoreApplication.translate(
                    "PipelinePatientSelectionPage",
                    f"❌ Missing: {missing_str}"
                )
            )
            status_label.setStyleSheet("color: #c0392b;")

        layout.addWidget(status_label)

        # Selection toggle button
        select_btn = QPushButton(QCoreApplication.translate("PipelinePatientSelectionPage", "Select"))
        select_btn.setCheckable(True)
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: #ecf0f1;
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: #3498db;
                color: white;
            }
        """)

        select_btn.setEnabled(is_eligible)
        select_btn.clicked.connect(lambda checked, pid=patient_id: self._toggle_selection(pid, checked))

        layout.addWidget(select_btn)

        self.patient_buttons[patient_id] = select_btn
        return card

    # ─────────────────────────────────────────────
    # USER ACTIONS
    # ─────────────────────────────────────────────
    def _toggle_selection(self, patient_id, checked):
        """
        Toggle patient selection when the user clicks a card's button.

        Args:
            patient_id (str): Patient identifier.
            checked (bool): True if selected, False if deselected.
        """
        if checked:
            self.selected_patients.add(patient_id)
        else:
            self.selected_patients.discard(patient_id)
        log.debug(f"Selected patients: {sorted(self.selected_patients)}")

    def _select_all_eligible_patients(self):
        """Select all patients marked as eligible for pipeline execution."""
        for patient_id, (is_eligible, _) in self.patient_status.items():
            if is_eligible:
                self.selected_patients.add(patient_id)
                self.patient_buttons[patient_id].setChecked(True)

    def _deselect_all_patients(self):
        """Deselect all patients."""
        for btn in self.patient_buttons.values():
            btn.setChecked(False)
        self.selected_patients.clear()

    def _refresh_patient_status(self):
        """Re-scan the workspace and refresh eligibility status."""
        self._load_patients()

    # ─────────────────────────────────────────────
    # NAVIGATION AND CONFIG EXPORT
    # ─────────────────────────────────────────────
    def is_ready_to_advance(self):
        """
        Indicate whether the user can proceed to the next page.

        Returns:
            bool: True if at least one patient is selected.
        """
        return len(self.selected_patients) > 0

    def next(self, context):
        """
        Proceed to the review page after validating the selection.

        Args:
            context (dict): Shared context dictionary.

        Returns:
            PipelineReviewPage: The next page in the wizard.
        """
        if not self.selected_patients:
            log.warning("No patients selected. Cannot proceed.")
            return None

        # Generate config file and pass to next page
        config_path = self._build_pipeline_config()
        context["pipeline_config"] = config_path
        next_page = PipelineReviewPage(context, previous_page=self)
        return next_page

    def _build_pipeline_config(self):
        """
        Create and save a JSON configuration file for the pipeline.

        The file includes:
        - Selected patient IDs
        - Workspace directory
        - Date/time of creation

        Returns:
            str: Path to the generated configuration file.
        """
        from datetime import datetime

        pipeline_dir = os.path.join(self.workspace_path, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)

        config_id = datetime.now().strftime("%Y%m%d%H%M%S")
        config_path = os.path.join(pipeline_dir, f"{config_id}_config.json")

        config_data = {
            "workspace_path": self.workspace_path,
            "selected_patients": sorted(self.selected_patients),
            "created_at": datetime.now().isoformat()
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)

        log.info(f"Pipeline configuration created at {config_path}")
        return config_path

    # ─────────────────────────────────────────────
    # TRANSLATION SUPPORT
    # ─────────────────────────────────────────────
    def _translate_ui(self):
        """Translate static UI text for internationalization."""
        self.title.setText(QCoreApplication.translate("PipelinePatientSelectionPage", "Select Patients for Pipeline Analysis"))
        self.select_eligible_btn.setText(QCoreApplication.translate("PipelinePatientSelectionPage", "Select All Eligible"))
        self.deselect_all_btn.setText(QCoreApplication.translate("PipelinePatientSelectionPage", "Deselect All"))
        self.refresh_btn.setText(QCoreApplication.translate("PipelinePatientSelectionPage", "Refresh Status"))
        self.title_summary.setText(QCoreApplication.translate("PipelinePatientSelectionPage", "Pipeline Requirements Summary"))
