import json
import os
import glob

from PyQt6.QtWidgets import QWidget, QScrollArea

from components.collapsible_info_frame import CollapsibleInfoFrame
from components.collapsible_patient_frame import CollapsiblePatientFrame
from ui.ui_pipeline_execution import PipelineExecutionPage
from wizard_state import WizardPage
from logger import get_logger

from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtWidgets import QVBoxLayout, QLabel

log = get_logger()


class PipelineReviewPage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.workspace_path = context["workspace_path"]
        self.previous_page = previous_page
        self.next_page = None

        # Trova l'ultimo config file creato
        self.config_path = self._find_latest_config()
        self.pipeline_config = self._load_config()

        self.main_layout = QVBoxLayout(self)

        self._setup_ui()

        self._retranslate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._retranslate_ui)

    def _find_latest_config(self):
        """Trova il file config con l'ID più alto nella cartella pipeline."""
        pipeline_dir = os.path.join(self.workspace_path, "pipeline")

        # Se la cartella pipeline non esiste, ritorna il path di default
        if not os.path.exists(pipeline_dir):
            return os.path.join(pipeline_dir, "pipeline_config.json")

        # Cerca tutti i file config con pattern XX_config.json
        config_pattern = os.path.join(pipeline_dir, "*_config.json")
        config_files = glob.glob(config_pattern)

        if not config_files:
            # Se non ci sono file config, ritorna il path di default
            return os.path.join(pipeline_dir, "pipeline_config.json")

        # Estrae gli ID dai nomi dei file e trova il massimo
        max_id = 0
        latest_config = None

        for config_file in config_files:
            filename = os.path.basename(config_file)
            try:
                # Estrae il numero dal pattern "XX_config.json"
                # Il numero è all'inizio, prima del "_"
                id_str = filename.split('_')[0]  # Prende la parte prima del primo underscore
                config_id = int(id_str)
                if config_id > max_id:
                    max_id = config_id
                    latest_config = config_file
            except (ValueError, IndexError):
                # Ignora file con nomi non conformi al pattern
                continue

        if latest_config:
            log.info(f"Using latest config file: {latest_config}")
            return latest_config
        else:
            # Se non è stato trovato nessun file valido, usa il path di default
            return os.path.join(pipeline_dir, "pipeline_config.json")

    def _setup_ui(self):
        layout = self.main_layout
        # Clear existing layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Header
        self.header = QLabel("Pipeline Configuration Review")
        self.header.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            margin: 6px 0;
        """)
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.header)

        # Config file info
        self.config_info = QLabel(f"Reviewing: {os.path.basename(self.config_path)}")
        self.config_info.setStyleSheet("""
            font-size: 11px;
            color: #666;
            font-style: italic;
            margin-bottom: 6px;
        """)
        self.config_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.config_info.setWordWrap(True)
        layout.addWidget(self.config_info)

        # Collapsible instructions
        info_frame = CollapsibleInfoFrame(self.context)
        layout.addWidget(info_frame)

        # Info label
        self.info_label = QLabel(
            "<strong>Click</strong> a frame to review file selections. <strong>Save</strong> yellow frames after selection."
        )
        self.info_label.setStyleSheet("""
            color: #666;
            font-size: 12px;
            margin: 6px 0;
        """)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(6, 6, 6, 6)
        content_layout.setSpacing(8)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        self.patient_widgets = {}

        categories = {
            "mri": [os.path.join(self.workspace_path, "{pid}", "anat", "*_flair.nii*")],
            "mri_str": [
                os.path.join(self.workspace_path, "derivatives", "skullstrips", "{pid}", "anat", "*_brain.nii*")],
            "pet": [os.path.join(self.workspace_path, "{pid}", "ses-01", "pet", "*_pet.nii*")],
            "pet4d": [os.path.join(self.workspace_path, "{pid}", "ses-02", "pet", "*_pet.nii*")],
            "tumor_mri": [
                os.path.join(self.workspace_path, "derivatives", "manual_masks", "{pid}", "anat", "*_mask.nii*"),
                # nnU-net segmentation
                os.path.join(self.workspace_path, "derivatives", "deep_learning_seg", "{pid}", "anat", "*_seg.nii*"),
            ]
        }

        for patient_id, files in self.pipeline_config.items():
            patient_patterns = {
                cat: [pat.format(pid=patient_id) for pat in pats]
                for cat, pats in categories.items()
            }
            multiple_choice = bool(files.get("need_revision", False))
            frame = CollapsiblePatientFrame(
                self.context,
                patient_id, files,
                patient_patterns, multiple_choice,
                save_callback=self._save_single_patient
            )
            self.patient_widgets[patient_id] = frame
            content_layout.addWidget(frame)

        content_layout.addStretch()

    def _save_single_patient(self, patient_id, files):
        """Salva la configurazione di un singolo paziente."""
        self.pipeline_config[patient_id] = files
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.pipeline_config, f, indent=4)

    def on_enter(self):
        """Chiamato quando si entra nella pagina."""
        # Ricarica il config più recente
        new_config_path = self._find_latest_config()
        new_pipeline_config = self._load_config_from_path(new_config_path)

        # Verifica se è cambiato il file config o il contenuto
        config_changed = (
                new_config_path != self.config_path or
                new_pipeline_config != self.pipeline_config
        )

        if config_changed:
            log.info(f"Config changed, reloading UI. New config: {os.path.basename(new_config_path)}")
            self.config_path = new_config_path
            self.pipeline_config = new_pipeline_config
            self._setup_ui()
        else:
            log.debug("Config unchanged, keeping existing UI")

    def _load_config_from_path(self, config_path):
        """Carica il file di configurazione da un path specifico."""
        if not os.path.exists(config_path):
            log.warning(f"Warning: Config file not found at {config_path}")
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log.error(f"Error loading config file {config_path}: {e}")
            return {}

    def _load_config(self):
        """Carica il file di configurazione corrente."""
        return self._load_config_from_path(self.config_path)

    def next(self, context):
        """Procede alla fase successiva avviando la pipeline."""
        # Verifica che tutti i pazienti con need_revision siano stati salvati
        unsaved_patients = []
        for patient_id, files in self.pipeline_config.items():
            if files.get("need_revision", False):
                unsaved_patients.append(patient_id)

        if unsaved_patients:
            # Mostra un messaggio di avviso se ci sono pazienti non salvati
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle(QCoreApplication.translate("PipelineReviewPage", "Configuration Incomplete"))
            msg.setText(QCoreApplication.translate("PipelineReviewPage", "Some patients still require configuration review."))
            patients_list = ", ".join(unsaved_patients)
            msg.setInformativeText(
                QCoreApplication.translate(
                    "PipelineReviewPage",
                    "Please review and save configuration for: {patients}"
                ).format(patients=patients_list)
            )
            msg.exec()
            return self  # Resta sulla pagina corrente

        # Tutti i pazienti sono stati configurati, procedi alla pagina di esecuzione
        if self.next_page:
            self.next_page.on_enter()
            return self.next_page
        else:
            self.next_page = PipelineExecutionPage(context, self)
            self.context["history"].append(self.next_page)
            self.next_page.on_enter()
            return self.next_page

    def back(self):
        """Torna alla pagina precedente."""
        if os.path.exists(self.config_path):
            try:
                # Estrae l'ID dal nome del file config
                config_filename = os.path.basename(self.config_path)
                # Il pattern è "XX_config.json", quindi prendiamo la parte prima di "_config.json"
                config_id = config_filename.split('_config.json')[0]

                # Costruisce il path della cartella output corrispondente
                pipeline_dir = os.path.dirname(self.config_path)
                output_folder_path = os.path.join(pipeline_dir, f"{config_id}_output")

                # Controlla se esiste la cartella output
                if os.path.exists(output_folder_path):
                    log.info(f"Output folder exists ({output_folder_path}), keeping config file: {self.config_path}")
                else:
                    # La cartella output non esiste, quindi possiamo cancellare il config file
                    os.remove(self.config_path)
                    log.info(f"Output folder does not exist, removed config file: {self.config_path}")

            except (OSError, IndexError, ValueError) as e:
                log.error(f"Error processing config file {self.config_path}: {e}")

        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def _retranslate_ui(self):
        self.header.setText(QCoreApplication.translate("PipelineReviewPage", "Pipeline Configuration Review"))
        self.config_info.setText(QCoreApplication.translate("PipelineReviewPage", "Reviewing: {0}").format(os.path.basename(self.config_path)))
        self.info_label.setText(QCoreApplication.translate("PipelineReviewPage", "<strong>Click</strong> a frame to review file selections. <strong>Save</strong> yellow frames after selection."))