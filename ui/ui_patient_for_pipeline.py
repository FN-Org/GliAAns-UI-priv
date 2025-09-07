import json
import shutil
import os
import glob

from PyQt6 import QtWidgets, QtGui
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea,
                             QFrame, QGridLayout, QHBoxLayout,
                             QTextEdit, QSplitter, QSizePolicy)
from PyQt6.QtCore import Qt

from ui.ui_pipeline_review import PipelineReviewPage
from ui.ui_work_in_progress import WorkInProgressPage
from wizard_state import WizardPage
from logger import get_logger

log = get_logger()


class PipelinePatientSelectionPage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()

        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.workspace_path = context["workspace_path"]

        self.patient_buttons = {}
        self.selected_patients = set()
        self.patient_status = {}  # Memorizza lo stato di ogni paziente

        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)

        # Titolo
        self.title = QLabel("Select Patients for Pipeline Analysis")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.layout.addWidget(self.title)

        # Pulsanti di selezione in alto
        top_buttons_layout = QHBoxLayout()

        self.select_eligible_btn = QPushButton("Select All Eligible")
        self.deselect_all_btn = QPushButton("Deselect All")
        self.refresh_btn = QPushButton("Refresh Status")

        self.buttons = [self.select_eligible_btn, self.deselect_all_btn, self.refresh_btn]

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

        self.select_eligible_btn.clicked.connect(self._select_all_eligible_patients)
        self.deselect_all_btn.clicked.connect(self._deselect_all_patients)
        self.refresh_btn.clicked.connect(self._refresh_patient_status)

        top_buttons_layout.addStretch()
        top_buttons_layout.addWidget(self.select_eligible_btn)
        top_buttons_layout.addWidget(self.deselect_all_btn)
        top_buttons_layout.addWidget(self.refresh_btn)

        self.layout.addLayout(top_buttons_layout)

        # Area scroll per i pazienti
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

        # Area resoconto
        self.summary_widget = self._create_summary_widget()

        self.layout.addWidget(self.summary_widget)
        self.layout.addWidget(self.scroll_area)

        self.column_count = 2
        self._load_patients()

    def _create_summary_widget(self):
        """Crea il widget per il resoconto dei pazienti in stile moderno"""
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

        # Salvo come attributo per gestire font in resizeEvent
        self.title_summary = QLabel("Pipeline Requirements Summary")
        self.title_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_summary.setStyleSheet("font-size: 16px; font-weight: bold; color: #000000; margin-bottom: 10px;")
        main_layout.addWidget(self.title_summary)

        # Layout delle pillole
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)

        self.total_label = self._create_stat_pill("./resources/icon_total.png", "Total Patients", "0")
        self.eligible_label = self._create_stat_pill("./resources/icon_check.png", "Eligible", "0", color="#27ae60")
        self.not_eligible_label = self._create_stat_pill("./resources/icon_cross.png", "Not Eligible", "0",
                                                         color="#c0392b")

        for pill in [self.total_label, self.eligible_label, self.not_eligible_label]:
            pill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            stats_layout.addWidget(pill)

        main_layout.addLayout(stats_layout)

        return summary_frame

    def _create_stat_pill(self, icon_path, label_text, value_text, color="#000000"):
        """Crea una card con icona, etichetta e valore"""
        pill = QFrame()
        pill.setObjectName("summaryCard")
        pill.setStyleSheet(f"""
            QFrame#summaryCard {{
                border: 1px solid #CCCCCC;
                border-radius: 10px;
                background-color: #f9f9f9;
            }}
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

        # Salvo i riferimenti per il resize dinamico
        pill.label = label
        pill.value_label = value

        pill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        pill.setMinimumHeight(50)
        pill.setMaximumHeight(120)

        return pill

    def _check_patient_requirements(self, patient_path, patient_id):
        """Verifica i requisiti per un paziente specifico"""
        requirements = {
            'flair': False,
            'skull_stripping': False,
            'segmentation': False
        }

        missing_files = []

        # 1. Verifica FLAIR
        flair_patterns = [
            os.path.join(patient_path, "anat", "*_flair.nii"),
            os.path.join(patient_path, "anat", "*_flair.nii.gz")
        ]

        flair_found = False
        for pattern in flair_patterns:
            if glob.glob(pattern):
                flair_found = True
                break

        requirements['flair'] = flair_found
        if not flair_found:
            missing_files.append("FLAIR image (anat/*_flair.nii[.gz])")

        # 2. Verifica Skull Stripping
        skull_strip_patterns = [
            os.path.join(self.workspace_path, "derivatives", "skullstrips", patient_id, "anat", "*_brain.nii"),
            os.path.join(self.workspace_path, "derivatives", "skullstrips", patient_id, "anat", "*_brain.nii.gz")
        ]

        skull_strip_found = False
        for pattern in skull_strip_patterns:
            if glob.glob(pattern):
                skull_strip_found = True
                break

        requirements['skull_stripping'] = skull_strip_found
        if not skull_strip_found:
            missing_files.append("Skull stripped image (derivatives/skullstrips/.../anat/*_brain.nii[.gz])")

        # 3. Verifica Segmentation o Manual Mask
        segmentation_patterns = [
            # Manual masks
            os.path.join(self.workspace_path, "derivatives", "manual_masks", patient_id, "anat", "*_mask.nii"),
            os.path.join(self.workspace_path, "derivatives", "manual_masks", patient_id, "anat", "*_mask.nii.gz"),
            # nnU-net segmentation
            os.path.join(self.workspace_path, "derivatives", "nnU_net", patient_id, "anat", "*_dseg.nii"),
            os.path.join(self.workspace_path, "derivatives", "nnU_net", patient_id, "anat", "*_dseg.nii.gz")
        ]

        segmentation_found = False
        segmentation_type = None
        for pattern in segmentation_patterns:
            if glob.glob(pattern):
                segmentation_found = True
                if "manual-masks" in pattern:
                    segmentation_type = "Manual Mask"
                elif "nnU-net" in pattern:
                    segmentation_type = "nnU-net Segmentation"
                break

        requirements['segmentation'] = segmentation_found
        if not segmentation_found:
            missing_files.append("Segmentation (manual_masks/*_mask.nii[.gz] or nnU-net/*_dseg.nii[.gz])")

        # Determina se il paziente è eligible
        is_eligible = all(requirements.values())

        return {
            'eligible': is_eligible,
            'requirements': requirements,
            'missing_files': missing_files,
            'segmentation_type': segmentation_type
        }

    def _load_patients(self):
        """Carica i pazienti e verifica i loro requisiti"""
        patient_dirs = self._find_patient_dirs()
        patient_dirs.sort()

        self.patient_buttons.clear()
        self.patient_status.clear()

        eligible_count = 0
        total_count = len(patient_dirs)

        for i, patient_path in enumerate(patient_dirs):
            patient_id = os.path.basename(patient_path)

            # Verifica i requisiti per questo paziente
            status = self._check_patient_requirements(patient_path, patient_id)
            self.patient_status[patient_id] = status

            if status['eligible']:
                eligible_count += 1

            # Crea il frame del paziente
            patient_frame = self._create_patient_frame(patient_id, patient_path, status)

            # Inserimento nella griglia
            self.grid_layout.addWidget(patient_frame, i // self.column_count, i % self.column_count)

        # Aggiorna il resoconto
        self._update_summary(eligible_count, total_count)

    def _create_patient_frame(self, patient_id, patient_path, status):
        """Crea il frame per un singolo paziente"""
        patient_frame = QFrame()
        patient_frame.setObjectName("patientCard")
        patient_frame.setMaximumHeight(140)  # Altezza massima
        patient_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Stile diverso per pazienti eligible/non-eligible
        if status['eligible']:
            frame_style = """
                QFrame#patientCard {
                    border: 2px solid #4CAF50;
                    border-radius: 10px;
                    background-color: #f0fff0;
                    padding: 10px;
                    margin: 2px;
                }
            """
        else:
            frame_style = """
                QFrame#patientCard {
                    border: 2px solid #f44336;
                    border-radius: 10px;
                    background-color: #fff0f0;
                    padding: 10px;
                    margin: 2px;
                }
            """

        patient_frame.setStyleSheet(frame_style)

        # Layout principale orizzontale
        patient_layout = QHBoxLayout(patient_frame)

        # Sezione profilo (sinistra)
        profile_frame = QFrame()
        profile_layout = QVBoxLayout(profile_frame)
        profile_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Immagine
        image = QLabel()
        if status['eligible']:
            pixmap = QtGui.QPixmap("./resources/user.png").scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio,
                                                                  Qt.TransformationMode.SmoothTransformation)
        else:
            # Potresti voler usare un'icona diversa per pazienti non eligible
            pixmap = QtGui.QPixmap("./resources/user.png").scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio,
                                                                  Qt.TransformationMode.SmoothTransformation)
        image.setPixmap(pixmap)
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ID del paziente
        patient_label = QLabel(f"{patient_id}")
        patient_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        patient_label.setStyleSheet("font-weight: bold; font-size: 12px;")

        # Status label
        if status['eligible']:
            status_label = QLabel("✓ Ready for Pipeline")
            status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 10px;")
        else:
            status_label = QLabel("✗ Missing Requirements")
            status_label.setStyleSheet("color: #f44336; font-weight: bold; font-size: 10px;")

        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        profile_layout.addWidget(image)
        profile_layout.addWidget(patient_label)
        profile_layout.addWidget(status_label)

        # Sezione dettagli (centro)
        details_frame = QFrame()
        details_layout = QVBoxLayout(details_frame)
        details_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Indicatori dei requisiti
        req_indicators = []
        req_labels = {
            'flair': 'FLAIR',
            'skull_stripping': 'Skull Strip',
            'segmentation': 'Segmentation'
        }

        for req, label in req_labels.items():
            indicator = QLabel()
            if status['requirements'][req]:
                indicator.setText(f"✓ {label}")
                indicator.setStyleSheet("color: #4CAF50; font-size: 10px; padding: 1px;")
            else:
                indicator.setText(f"✗ {label}")
                indicator.setStyleSheet("color: #f44336; font-size: 10px; padding: 1px;")
            req_indicators.append(indicator)
            details_layout.addWidget(indicator)

        # Mostra tipo di segmentazione se disponibile
        if status['segmentation_type']:
            seg_type_label = QLabel(f"({status['segmentation_type']})")
            seg_type_label.setStyleSheet("color: #666666; font-size: 9px; font-style: italic;")
            details_layout.addWidget(seg_type_label)

        # Pulsante di selezione (destra)
        button = QPushButton("Select")
        button.setCheckable(True)

        if status['eligible']:
            button.setStyleSheet("""
                QPushButton {
                    border-radius: 12px;
                    padding: 8px 16px;
                    background-color: #DADADA;
                    font-weight: bold;
                    min-width: 80px;
                }
                QPushButton:checked {
                    background-color: #4CAF50;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #c0c0c0;
                }
                QPushButton:checked:hover {
                    background-color: #45a049;
                }
            """)

            # Mantieni la selezione precedente se presente
            is_selected = patient_id in self.selected_patients
            button.setChecked(is_selected)
            button.setText("Selected" if is_selected else "Select")

            button.clicked.connect(lambda checked, pid=patient_id, btn=button: self._toggle_patient(pid, checked, btn))
        else:
            button.setText("Not Eligible")
            button.setEnabled(False)
            button.setStyleSheet("""
                QPushButton {
                    border-radius: 12px;
                    padding: 8px 16px;
                    background-color: #f0f0f0;
                    color: #888888;
                    font-weight: bold;
                    min-width: 80px;
                }
            """)

        self.patient_buttons[patient_id] = button

        # Assemblaggio del layout
        patient_layout.addWidget(profile_frame)
        patient_layout.addWidget(details_frame)
        patient_layout.addStretch()
        patient_layout.addWidget(button)

        return patient_frame

    def _update_summary(self, eligible_count, total_count):
        self.total_label.value_label.setText(str(total_count))
        self.eligible_label.value_label.setText(str(eligible_count))
        self.not_eligible_label.value_label.setText(str(total_count - eligible_count))

    def _select_all_eligible_patients(self):
        """Seleziona tutti i pazienti eligible"""
        for patient_id, button in self.patient_buttons.items():
            if self.patient_status[patient_id]['eligible'] and not button.isChecked():
                button.setChecked(True)
                button.setText("Selected")
                self.selected_patients.add(patient_id)
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def _deselect_all_patients(self):
        """Deseleziona tutti i pazienti"""
        for patient_id, button in self.patient_buttons.items():
            if button.isChecked() and button.isEnabled():
                button.setChecked(False)
                button.setText("Select")
                self.selected_patients.discard(patient_id)
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def _refresh_patient_status(self):
        """Ricarica lo stato di tutti i pazienti"""
        # Salva le selezioni correnti
        current_selections = self.selected_patients.copy()

        # Pulisci la griglia
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        # Ricarica tutto
        self._load_patients()

        # Ripristina le selezioni valide
        valid_selections = set()
        for patient_id in current_selections:
            if (patient_id in self.patient_status and
                    self.patient_status[patient_id]['eligible'] and
                    patient_id in self.patient_buttons):
                valid_selections.add(patient_id)
                button = self.patient_buttons[patient_id]
                button.setChecked(True)
                button.setText("Selected")

        self.selected_patients = valid_selections

    def _toggle_patient(self, patient_id, is_selected, button):
        """Gestisce la selezione/deselezione di un paziente"""
        if is_selected:
            self.selected_patients.add(patient_id)
            button.setText("Selected")
        else:
            self.selected_patients.discard(patient_id)
            button.setText("Select")
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def _find_patient_dirs(self):
        """Trova tutte le directory dei pazienti"""
        patient_dirs = []

        for root, dirs, files in os.walk(self.workspace_path):
            # Salta la cartella 'derivatives'
            if "derivatives" in dirs:
                dirs.remove("derivatives")

            if "pipeline" in dirs:
                dirs.remove("pipeline")

            for dir_name in dirs:
                if dir_name.startswith("sub-"):
                    full_path = os.path.join(root, dir_name)
                    patient_dirs.append(full_path)

            # Esclude le sottocartelle dei sub-*
            dirs[:] = [d for d in dirs if not d.startswith("sub-")]

        return patient_dirs

    def _update_column_count(self):
        """Aggiorna il numero di colonne in base alla larghezza disponibile"""
        available_width = self.scroll_area.viewport().width() - 40
        min_card_width = 400  # Aumentato per le card più dettagliate

        new_column_count = max(1, available_width // min_card_width)

        if new_column_count != self.column_count:
            self.column_count = new_column_count
            self._reload_patient_grid()

    def _reload_patient_grid(self):
        """Ricarica la griglia mantenendo le selezioni"""
        selected = self.selected_patients.copy()

        # Pulisci la griglia
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        # Ricarica con il nuovo layout
        self._load_patients()

        # Ripristina le selezioni valide
        valid_selections = set()
        for patient_id in selected:
            if (patient_id in self.patient_status and
                    self.patient_status[patient_id]['eligible'] and
                    patient_id in self.patient_buttons):
                valid_selections.add(patient_id)
                button = self.patient_buttons[patient_id]
                button.setChecked(True)
                button.setText("Selected")

        self.selected_patients = valid_selections


    def _build_pipeline_config(self):
        """Crea e salva un file JSON con la configurazione iniziale della pipeline.
        Tutti i path nel JSON sono relativi a workspace_path.
        Il file viene salvato con un ID numerico sequenziale.
        """
        config = {}

        for patient_id in self.selected_patients:
            patient_entry = {}
            need_revision = False  # Flag per capire se il medico deve rivedere

            # MRI (FLAIR)
            flair_patterns = [
                os.path.join(self.workspace_path, patient_id, "anat", "*_flair.nii"),
                os.path.join(self.workspace_path, patient_id, "anat", "*_flair.nii.gz")
            ]
            flair_files = []
            for p in flair_patterns:
                flair_files.extend(glob.glob(p))
            if len(flair_files) > 1:
                need_revision = True
            patient_entry["mri"] = os.path.relpath(flair_files[0], self.workspace_path) if flair_files else None

            # MRI Skull Stripped
            mri_str_patterns = [
                os.path.join(self.workspace_path, "derivatives", "skullstrips", patient_id, "anat", "*_brain.nii"),
                os.path.join(self.workspace_path, "derivatives", "skullstrips", patient_id, "anat",
                             "*_brain.nii.gz")
            ]
            mri_str_files = []
            for p in mri_str_patterns:
                mri_str_files.extend(glob.glob(p))
            if len(mri_str_files) > 1:
                need_revision = True
            patient_entry["mri_str"] = os.path.relpath(mri_str_files[0], self.workspace_path) if mri_str_files else None

            # PET statica
            pet_patterns = [
                os.path.join(self.workspace_path, patient_id, "ses-01", "pet", "*_pet.nii"),
                os.path.join(self.workspace_path, patient_id, "ses-01", "pet", "*_pet.nii.gz")
            ]
            pet_files = []
            for p in pet_patterns:
                pet_files.extend(glob.glob(p))
            if len(pet_files) > 1:
                need_revision = True
            patient_entry["pet"] = os.path.relpath(pet_files[0], self.workspace_path) if pet_files else None

            # PET dinamica (facoltativa)
            pet4d_patterns = [
                os.path.join(self.workspace_path, patient_id, "ses-02", "pet", "*_pet.nii"),
                os.path.join(self.workspace_path, patient_id, "ses-02", "pet", "*_pet.nii.gz")
            ]
            pet4d_files = []
            for p in pet4d_patterns:
                pet4d_files.extend(glob.glob(p))
            if len(pet4d_files) > 1:
                need_revision = True
            pet4d_file = pet4d_files[0] if pet4d_files else None
            patient_entry["pet4d"] = os.path.relpath(pet4d_files[0], self.workspace_path) if pet4d_files else None

            # PET JSON sidecar
            pet_json_file = None
            if pet4d_file:
                # prende stesso prefix e cerca il file .json
                basename = os.path.basename(pet4d_file)
                stem_no_ext = basename.split('.')[0]
                candidate = os.path.join(os.path.dirname(pet4d_file), stem_no_ext + '.json')
                if os.path.exists(candidate):
                    pet_json_file = candidate
            patient_entry["pet4d_json"] = os.path.relpath(pet_json_file, self.workspace_path) if pet_json_file else None

            # Tumor MRI (mask)
            tumor_patterns = [
                os.path.join(self.workspace_path, "derivatives", "manual_masks", patient_id, "anat", "*_mask.nii"),
                os.path.join(self.workspace_path, "derivatives", "manual_masks", patient_id, "anat", "*_mask.nii.gz")
            ]
            tumor_files = []
            for p in tumor_patterns:
                tumor_files.extend(glob.glob(p))
            if len(tumor_files) > 1:
                need_revision = True
            patient_entry["tumor_mri"] = os.path.relpath(tumor_files[0], self.workspace_path) if tumor_files else None

            # Aggiunge la flag finale
            patient_entry["need_revision"] = need_revision

            config[patient_id] = patient_entry

        # Gestione della cartella pipeline e del nome file
        pipeline_dir = os.path.join(self.workspace_path, "pipeline")

        # Crea la cartella pipeline se non esiste
        if not os.path.exists(pipeline_dir):
            os.makedirs(pipeline_dir)
            log.info(f"Created pipeline directory: {pipeline_dir}")

        # Trova il prossimo numero sequenziale disponibile
        config_id = self._get_next_config_id(pipeline_dir)

        # Nome del file con ID numerico
        filename = f"{config_id:02d}_config.json"
        output_path = os.path.join(pipeline_dir, filename)

        # Salva il file JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        log.info(f"Pipeline configuration saved to: {output_path}")
        return output_path

    def _get_next_config_id(self, pipeline_dir):
        """Trova il prossimo ID numerico sequenziale disponibile per i file config.

        Args:
            pipeline_dir (str): Path della directory pipeline

        Returns:
            int: Il prossimo ID numerico disponibile
        """
        # Pattern per trovare i file config esistenti
        config_pattern = os.path.join(pipeline_dir, "*_config.json")
        existing_configs = glob.glob(config_pattern)

        if not existing_configs:
            return 1  # se non ci sono file, parti da 1

        existing_ids = []
        for config_file in existing_configs:
            filename = os.path.basename(config_file)  # es: "12_config.json"
            try:
                # prendi la parte prima di "_config.json"
                id_str = filename.split("_")[0]  # "12"
                config_id = int(id_str)
                existing_ids.append(config_id)
            except (ValueError, IndexError):
                continue  # ignora file con nomi strani

        if not existing_ids:
            return 1

        return max(existing_ids) + 1

    def on_enter(self):
        """Chiamato quando si entra nella pagina"""
        self._refresh_patient_status()

    def is_ready_to_advance(self):
        """Verifica se si può procedere alla pagina successiva"""
        return len(self.selected_patients) > 0

    def is_ready_to_go_back(self):
        """Verifica se si può tornare alla pagina precedente"""
        return True

    def next(self, context):
        self._build_pipeline_config()

        if self.next_page:
            self.next_page.on_enter()
            return self.next_page
        else:
            self.next_page = PipelineReviewPage(context, self)
            self.context["history"].append(self.next_page)
            return self.next_page

    def back(self):
        """Torna alla pagina precedente"""
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def get_selected_patients(self):
        """Restituisce la lista dei pazienti selezionati"""
        return list(self.selected_patients)

    def get_eligible_patients(self):
        """Restituisce la lista dei pazienti eligible"""
        return [pid for pid, status in self.patient_status.items() if status['eligible']]

    def get_patient_status_summary(self):
        """Restituisce un riassunto dello stato dei pazienti"""
        total = len(self.patient_status)
        eligible = len([s for s in self.patient_status.values() if s['eligible']])
        selected = len(self.selected_patients)

        return {
            'total': total,
            'eligible': eligible,
            'selected': selected,
            'not_eligible': total - eligible
        }

    def reset_page(self):
        """Reset completo della pagina"""
        # Pulisce la griglia
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        # Resetta tutti gli stati
        self.selected_patients.clear()
        self.patient_buttons.clear()
        self.patient_status.clear()

        # Ricarica tutto
        self._load_patients()

    def resizeEvent(self, event):
        """Rende l'interfaccia responsiva in base all'altezza della finestra"""
        super().resizeEvent(event)

        self._update_column_count()

        height = self.height()

        # Titolo più piccolo su finestra bassa
        if height < 500:
            self.title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 5px;")
            btn_padding = "5px 10px"
            font_size_btn = 11
            max_pill_height = 70
            font_size_title = 12
            font_size_value = 14
            font_size_label = 10
            max_pill_height = 60
        else:
            self.title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
            btn_padding = "10px 20px"
            font_size_btn = 13
            font_size_title = 16
            font_size_value = 20
            font_size_label = 13
            max_pill_height = 100

        # Aggiorna pulsanti
        for btn in self.buttons:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #e0e0e0;
                    padding: {btn_padding};
                    border-radius: 10px;
                    border: 1px solid #bdc3c7;
                    font-weight: bold;
                    font-size: {font_size_btn}px;
                    margin: 2px;
                }}
                QPushButton:hover {{
                    background-color: #d0d0d0;
                }}
                QPushButton:disabled {{
                    background-color: #f0f0f0;
                    color: #888888;
                }}
            """)

        self.title_summary.setStyleSheet(
            f"font-size: {font_size_title}px; font-weight: bold; color: #000000; margin-bottom: 8px;"
        )

        for pill in [self.total_label, self.eligible_label, self.not_eligible_label]:
            pill.label.setStyleSheet(f"font-size: {font_size_label}px; font-weight: bold;")
            pill.value_label.setStyleSheet(
                f"font-size: {font_size_value}px; font-weight: bold; color: {pill.value_label.palette().color(pill.value_label.foregroundRole()).name()};"
            )
            pill.setMaximumHeight(max_pill_height)


