import json
import os
import glob

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QCoreApplication

from components.collapsible_info_frame import CollapsibleInfoFrame
from components.collapsible_patient_frame import CollapsiblePatientFrame
from ui.pipeline_execution_page import PipelineExecutionPage
from page import Page
from logger import get_logger

log = get_logger()


class PipelineReviewPage(Page):
    """
    GUI page that allows users to review and adjust the configuration
    before running the medical imaging pipeline.

    This page:
    - Loads the latest configuration JSON file.
    - Displays collapsible panels for each patient and data type.
    - Allows editing, saving, and validating configurations.
    - Transitions to the execution page once all data is ready.
    """

    def __init__(self, context=None, previous_page=None):
        """
        Initialize the review page and build its UI.

        Args:
            context (dict): Shared application context (workspace path, logger, signals, etc.).
            previous_page (Page): The previous page in the workflow.
        """
        super().__init__()
        self.context = context
        self.workspace_path = context["workspace_path"]
        self.previous_page = previous_page
        self.next_page = None

        # Locate and load the latest configuration file
        self.config_path = self._find_latest_config()
        self.pipeline_config = self._load_config()

        # Main layout container
        self.main_layout = QVBoxLayout(self)

        # Build interface
        self._setup_ui()

        # Apply translation and connect to language change signal (if available)
        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    # ─────────────────────────────────────────────
    # CONFIGURATION MANAGEMENT
    # ─────────────────────────────────────────────
    def _find_latest_config(self):
        """
        Find the most recent pipeline configuration file in the workspace.

        Returns:
            str: Absolute path to the newest configuration JSON file.
        """
        pipeline_dir = os.path.join(self.workspace_path, "pipeline")

        # Return a default path if the directory does not exist
        if not os.path.exists(pipeline_dir):
            return os.path.join(pipeline_dir, "pipeline_config.json")

        # Locate all files matching the *_config.json pattern
        config_files = glob.glob(os.path.join(pipeline_dir, "*_config.json"))

        if not config_files:
            return os.path.join(pipeline_dir, "pipeline_config.json")

        # Identify the latest config file by its numeric ID prefix
        max_id = 0
        latest_config = None
        for config_file in config_files:
            filename = os.path.basename(config_file)
            try:
                config_id = int(filename.split('_')[0])  # Extract numeric prefix
                if config_id > max_id:
                    max_id = config_id
                    latest_config = config_file
            except (ValueError, IndexError):
                continue  # Skip non-conforming filenames

        if latest_config:
            return latest_config

        return os.path.join(pipeline_dir, "pipeline_config.json")

    def _load_config_from_path(self, config_path):
        """
        Load configuration data from a specific JSON file.

        Args:
            config_path (str): Path to the configuration file.

        Returns:
            dict: Parsed configuration data, or an empty dict if load fails.
        """
        if not os.path.exists(config_path):
            log.warning(f"Config file not found: {config_path}")
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log.error(f"Error loading config {config_path}: {e}")
            return {}

    def _load_config(self):
        """Load the current configuration using the latest detected file."""
        return self._load_config_from_path(self.config_path)

    # ─────────────────────────────────────────────
    # UI SETUP AND LAYOUT
    # ─────────────────────────────────────────────
    def _setup_ui(self):
        """Construct the entire user interface for the review page."""
        layout = self.main_layout

        # Clear any existing widgets
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # ── Header ──────────────────────────────
        self.header = QLabel("Pipeline Configuration Review")
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(self.header)

        # ── Config file info ─────────────────────
        self.config_info = QLabel(f"Reviewing: {os.path.basename(self.config_path)}")
        self.config_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.config_info.setWordWrap(True)
        self.config_info.setStyleSheet("""
            font-size: 11px;
            color: #666;
            font-style: italic;
            margin-bottom: 6px;
        """)
        layout.addWidget(self.config_info)

        # ── Collapsible instructions ─────────────
        info_frame = CollapsibleInfoFrame(self.context)
        layout.addWidget(info_frame)

        # ── Info label ──────────────────────────
        self.info_label = QLabel(
            "<strong>Click</strong> a frame to review file selections. "
            "<strong>Save</strong> yellow frames after selection."
        )
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("""
            color: #666;
            font-size: 12px;
            margin: 6px 0;
        """)
        layout.addWidget(self.info_label)

        # ── Scroll area for patient panels ───────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        layout.addWidget(scroll)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(6, 6, 6, 6)
        content_layout.setSpacing(8)
        scroll.setWidget(content)

        # ── Patient frames ───────────────────────
        self.patient_widgets = {}

        # Define expected data categories and file patterns
        categories = {
            "mri": [os.path.join(self.workspace_path, "{pid}", "anat", "*_flair.nii*")],
            "mri_str": [os.path.join(self.workspace_path, "derivatives", "skullstrips", "{pid}", "anat", "*_brain.nii*")],
            "pet": [os.path.join(self.workspace_path, "{pid}", "ses-01", "pet", "*_pet.nii*")],
            "pet4d": [os.path.join(self.workspace_path, "{pid}", "ses-02", "pet", "*_pet.nii*")],
            "tumor_mri": [
                os.path.join(self.workspace_path, "derivatives", "manual_masks", "{pid}", "anat", "*_mask.nii*"),
                os.path.join(self.workspace_path, "derivatives", "deep_learning_seg", "{pid}", "anat", "*_seg.nii*"),
            ],
        }

        # Create collapsible frames for each patient
        for patient_id, files in self.pipeline_config.items():
            patient_patterns = {
                cat: [pat.format(pid=patient_id) for pat in pats]
                for cat, pats in categories.items()
            }
            multiple_choice = bool(files.get("need_revision", False))

            frame = CollapsiblePatientFrame(
                self.context,
                patient_id,
                files,
                patient_patterns,
                multiple_choice,
                save_callback=self._save_single_patient,
            )

            self.patient_widgets[patient_id] = frame
            content_layout.addWidget(frame)

        content_layout.addStretch()

    # ─────────────────────────────────────────────
    # SAVE & UPDATE LOGIC
    # ─────────────────────────────────────────────
    def _save_single_patient(self, patient_id, files):
        """
        Save the configuration for a single patient.

        Args:
            patient_id (str): Patient identifier.
            files (dict): Updated file paths and metadata.
        """
        self.pipeline_config[patient_id] = files
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.pipeline_config, f, indent=4)

    def on_enter(self):
        """
        Hook called when the page becomes visible.

        Checks for updated configuration files and refreshes the UI
        if any changes are detected.
        """
        new_config_path = self._find_latest_config()
        new_pipeline_config = self._load_config_from_path(new_config_path)

        config_changed = (
            new_config_path != self.config_path or
            new_pipeline_config != self.pipeline_config
        )

        if config_changed:
            log.info(f"Config changed, reloading UI: {os.path.basename(new_config_path)}")
            self.config_path = new_config_path
            self.pipeline_config = new_pipeline_config
            self._setup_ui()
        else:
            log.debug("Config unchanged, keeping existing UI")

    # ─────────────────────────────────────────────
    # NAVIGATION HANDLERS
    # ─────────────────────────────────────────────
    def next(self, context):
        """
        Proceed to the next page, executing the pipeline if all configurations are valid.

        Args:
            context (dict): Shared context.

        Returns:
            Page: The next page instance, or self if configuration is incomplete.
        """
        # Check for patients requiring revision
        unsaved_patients = [
            pid for pid, files in self.pipeline_config.items()
            if files.get("need_revision", False)
        ]

        if unsaved_patients:
            # Warn the user about unsaved patients
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle(QCoreApplication.translate("PipelineReviewPage", "Configuration Incomplete"))
            msg.setText(QCoreApplication.translate("PipelineReviewPage", "Some patients still require configuration review."))
            msg.setInformativeText(
                QCoreApplication.translate(
                    "PipelineReviewPage",
                    "Please review and save configuration for: {patients}"
                ).format(patients=", ".join(unsaved_patients))
            )
            msg.exec()
            return self  # Stay on current page

        # Proceed to pipeline execution page
        if not self.next_page:
            self.next_page = PipelineExecutionPage(context, self)
            self.context["history"].append(self.next_page)
        self.next_page.on_enter()
        return self.next_page

    def back(self):
        """
        Navigate back to the previous page.

        If the output folder for the current config does not exist,
        the config file is deleted to keep the workspace clean.
        """
        if os.path.exists(self.config_path):
            try:
                config_filename = os.path.basename(self.config_path)
                config_id = config_filename.split('_config.json')[0]
                pipeline_dir = os.path.dirname(self.config_path)
                output_folder_path = os.path.join(pipeline_dir, f"{config_id}_output")

                if not os.path.exists(output_folder_path):
                    os.remove(self.config_path)
                    log.info(f"Removed unused config file: {self.config_path}")
                else:
                    log.info(f"Keeping config file: {self.config_path}")
            except (OSError, IndexError, ValueError) as e:
                log.error(f"Error processing config file {self.config_path}: {e}")
        else:
            log.error(f"Invalid config path: {self.config_path}")

        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    # ─────────────────────────────────────────────
    # TRANSLATION
    # ─────────────────────────────────────────────
    def _translate_ui(self):
        """Translate all static text for internationalization."""
        self.header.setText(QCoreApplication.translate("PipelineReviewPage", "Pipeline Configuration Review"))
        self.config_info.setText(
            QCoreApplication.translate("PipelineReviewPage", "Reviewing: {0}").format(os.path.basename(self.config_path))
        )
        self.info_label.setText(
            QCoreApplication.translate(
                "PipelineReviewPage",
                "<strong>Click</strong> a frame to review file selections. <strong>Save</strong> yellow frames after selection."
            )
        )
