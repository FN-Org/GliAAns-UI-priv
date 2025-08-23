import json
import os
import glob

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QScrollArea,
    QHBoxLayout, QFrame, QGraphicsDropShadowEffect
)

from ui.ui_pipeline_execution import PipelineExecutionPage
from wizard_state import WizardPage

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QComboBox, QToolButton, QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor, QFont


class ClickableFrame(QFrame):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()


class CollapsiblePatientFrame(QFrame):
    def __init__(self, patient_id, files, workspace_path, patterns, multiple_choice=False, parent=None,
                 save_callback=None):
        super().__init__(parent)
        self.patient_id = patient_id
        self.workspace_path = workspace_path
        self.patterns = patterns
        self.files = files
        self.multiple_choice = multiple_choice
        self.is_expanded = False
        self.category_widgets = {}
        self.save_callback = save_callback
        self.locked = not multiple_choice  # se no multiple_choice, già bloccato

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("collapsiblePatientFrame")

        # Ombra leggera
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 1)
        self.setGraphicsEffect(shadow)

        self._build_ui()
        self._apply_style()

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

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        frame_header = ClickableFrame(self)
        frame_header_layout = QHBoxLayout(frame_header)
        subject_name = QLabel(self)
        subject_name.setText(f"Patient: {self.patient_id}")
        subject_name.setStyleSheet("font-size: 13px; font-weight: bold;")
        frame_header_layout.addWidget(subject_name)

        # Header con QToolButton
        self.toggle_button = QToolButton(text=f"Patient: {self.patient_id}", checkable=True, checked=False)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setIconSize(QSize(14, 14))
        self.toggle_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.toggle_button.clicked.connect(self._toggle_expand)
        frame_header.clicked.connect(self._on_header_clicked)

        frame_header_layout.addWidget(self.toggle_button)
        layout.addWidget(frame_header)

        # Contenuto espandibile
        self.content_frame = QFrame()
        self.content_frame.setStyleSheet("QFrame { border-radius: 4px; padding: 4px; }")
        self.content_frame.setMaximumHeight(0)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(8, 4, 8, 4)
        self.content_layout.setSpacing(6)

        self._populate_content()
        layout.addWidget(self.content_frame)

        # Animazione apertura/chiusura
        self.animation = QPropertyAnimation(self.content_frame, b"maximumHeight")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def _populate_content(self):
        # Svuota layout
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for category, pat_list in self.patterns.items():

            category_container = QFrame()
            category_layout = QVBoxLayout(category_container)
            category_layout.setContentsMargins(6, 4, 6, 4)
            category_layout.setSpacing(4)

            category_label = QLabel(category.replace("_", " ").title())
            category_label.setStyleSheet("font-size: 13px; font-weight: bold;")

            all_files = []
            for pat in pat_list:
                all_files.extend(glob.glob(pat))
            all_files_rel = [os.path.relpath(f, self.workspace_path) for f in all_files]

            if self.locked:
                chosen_file = self.files.get(category, "")
                file_label = QLabel(chosen_file if chosen_file else "Nessun file trovato")
                category_layout.addWidget(category_label)
                category_layout.addWidget(file_label)

                # Caso speciale: se è pet4d, mostriamo anche il relativo JSON
                if category == "pet4d":
                    self._add_pet4d_json_display(category_layout, chosen_file)

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
                    # label di sola lettura per il json
                    self.pet4d_json_label = QLabel()
                    self.pet4d_json_label.setWordWrap(True)
                    category_layout.addWidget(self.pet4d_json_label)

                    # collego il segnale per aggiornare automaticamente il json mostrato
                    combo.currentIndexChanged.connect(self._update_pet4d_json_display)
                    # inizializzo subito
                    self._update_pet4d_json_display()

            self.content_layout.addWidget(category_container)

        if not self.locked:
            save_container = QFrame()
            save_layout = QHBoxLayout(save_container)
            save_layout.setContentsMargins(6, 10, 6, 4)

            save_btn = QPushButton("Save Patient Configuration")
            save_btn.setMinimumHeight(32)
            save_btn.setStyleSheet("""
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
            save_btn.clicked.connect(self._save_patient)

            save_layout.addStretch()
            save_layout.addWidget(save_btn)
            save_layout.addStretch()

            self.content_layout.addWidget(save_container)

    def _add_pet4d_json_display(self, parent_layout, pet4d_file_rel):
        """Mostra il JSON associato al file pet4d scelto (solo in modalità locked)."""
        if not pet4d_file_rel:
            label = QLabel("<span style='color:red;'>Nessun file PET4D selezionato</span>")
            parent_layout.addWidget(label)
            return

        abs_pet4d_path = os.path.join(self.workspace_path, pet4d_file_rel)
        json_candidate = abs_pet4d_path.replace(".nii.gz", ".json").replace(".nii", ".json")

        if os.path.exists(json_candidate):
            rel_json = os.path.relpath(json_candidate, self.workspace_path)
            label = QLabel(f"JSON associato: <strong>{rel_json}</strong>")
            label.setStyleSheet("color: black; font-size: 12px;")
            self.files["pet4d_json"] = rel_json
        else:
            label = QLabel("<span style='color:red;'>Errore: file JSON associato non trovato</span>")
            self.files["pet4d_json"] = ""

        label.setWordWrap(True)
        parent_layout.addWidget(label)

    def _update_pet4d_json_display(self):
        """Aggiorna il label che mostra il JSON associato al file pet4d scelto."""
        if "pet4d" not in self.category_widgets:
            return

        combo = self.category_widgets["pet4d"]
        selected_file = combo.currentText()
        if not selected_file:
            self.pet4d_json_label.setText("<span style='color:red;'>Nessun file PET4D selezionato</span>")
            return

        # Ricava percorso assoluto e costruisce quello del json
        abs_pet4d_path = os.path.join(self.workspace_path, selected_file)
        json_candidate = abs_pet4d_path.replace(".nii.gz", ".json").replace(".nii", ".json")

        if os.path.exists(json_candidate):
            rel_json = os.path.relpath(json_candidate, self.workspace_path)
            self.pet4d_json_label.setText(f"JSON associato: <strong>{rel_json}</strong>")
            self.pet4d_json_label.setStyleSheet("color: black; font-size: 12px;")
            self.files["pet4d_json"] = rel_json  # salvo nel dict dei files
        else:
            self.pet4d_json_label.setText("<span style='color:red;'>Errore: file JSON associato non trovato</span>")
            self.files["pet4d_json"] = ""  # segno che manca

    def _on_header_clicked(self):
        # Cambia lo stato checked del toggle_button (toggle manuale)
        new_state = not self.toggle_button.isChecked()
        self.toggle_button.setChecked(new_state)

        # Chiama _toggle_expand con il nuovo stato
        self._toggle_expand(new_state)

    def _toggle_expand(self, checked):
        self.is_expanded = checked
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        if checked:
            self.animation.setStartValue(self.content_frame.maximumHeight())
            self.animation.setEndValue(self.content_frame.sizeHint().height())
        else:
            self.animation.setStartValue(self.content_frame.maximumHeight())
            self.animation.setEndValue(0)
        self.animation.start()

    def _save_patient(self):
        # Aggiorna files scelti
        for category, combo in self.category_widgets.items():
            self.files[category] = combo.currentText()

        # Quando l'utente salva, metti need_revision a False
        self.files["need_revision"] = False

        # Salva nel JSON tramite callback
        if self.save_callback:
            self.save_callback(self.patient_id, self.files)

        # Blocca frame e aggiorna UI
        self.locked = True
        self._apply_style()
        self._populate_content()


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
            print(f"Using latest config file: {latest_config}")
            return latest_config
        else:
            # Se non è stato trovato nessun file valido, usa il path di default
            return os.path.join(pipeline_dir, "pipeline_config.json")

    def _setup_ui(self):
        layout = self.main_layout
        # prima svuota
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        header = QLabel("Pipeline Configuration Review")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Mostra quale config file si sta utilizzando
        config_info = QLabel(f"Reviewing: {os.path.basename(self.config_path)}")
        config_info.setStyleSheet("font-size: 12px; color: #666; font-style: italic;")
        config_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(config_info)

        # Informative message for the doctor
        info_frame = QFrame()
        info_frame.setObjectName("info_frame")
        info_frame.setStyleSheet("""
            QFrame#info_frame {
                background-color: #e3f2fd;
                border: 1px solid #2196f3;
                border-radius: 8px;
                padding: 12px;
                margin: 8px 0px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(6)

        info_title = QLabel("Configuration Instructions")
        info_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #1976d2; 
            margin-bottom: 5px;
        """)

        info_text = QLabel("""
            <style>
                  .info-list { margin: 0; padding-left: 1.25rem; }
                  .info-list li { margin-bottom: 0.5rem; line-height: 1.4; }
            </style>
            <ul class="info-list" role="list">
              <li><strong>Yellow frames</strong> indicate patients with <strong>multiple files found</strong> for one or more categories. 
                <br> These patients require <strong>medical review and manual selection</strong> of the appropriate files.
              </li>
              <li><strong>White frames</strong> show patients with files automatically selected (only one option available).</li>
            </ul>
        """
                           )
        info_text.setStyleSheet("""
            color: #000000;
            font-size: 13px;
            line-height: 30px;
            padding: 4px 0px;
        """)
        info_text.setWordWrap(True)

        info_layout.addWidget(info_title)
        info_layout.addWidget(info_text)
        layout.addWidget(info_frame)

        # Info label
        info_label = QLabel(
            "<strong>Click</strong> on any frame to expand and <strong>review</strong> the file selection for that patient, and <strong>save the configuration</strong> for each yellow frame after making your selections."
        )
        info_label.setStyleSheet("color: #666; font-size: 13px;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(10)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        self.patient_widgets = {}

        categories = {
            "mri": [os.path.join(self.workspace_path, "{pid}", "anat", "*_flair.nii*")],
            "mri_str": [
                os.path.join(self.workspace_path, "derivatives", "fsl_skullstrips", "{pid}", "anat", "*_brain.nii*")],
            "pet": [os.path.join(self.workspace_path, "{pid}", "ses-01", "pet", "*_pet.nii*")],
            "pet4d": [os.path.join(self.workspace_path, "{pid}", "ses-02", "pet", "*_pet.nii*")],
            "tumor_mri": [
                os.path.join(self.workspace_path, "derivatives", "manual_masks", "{pid}", "anat", "*_mask.nii*")]
        }

        for patient_id, files in self.pipeline_config.items():
            patient_patterns = {
                cat: [pat.format(pid=patient_id) for pat in pats]
                for cat, pats in categories.items()
            }

            # Usa direttamente il flag salvato nel JSON
            multiple_choice = bool(files.get("need_revision", False))

            frame = CollapsiblePatientFrame(
                patient_id, files, self.workspace_path,
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
            print(f"Config changed, reloading UI. New config: {os.path.basename(new_config_path)}")
            self.config_path = new_config_path
            self.pipeline_config = new_pipeline_config
            self._setup_ui()
        else:
            print("Config unchanged, keeping existing UI")

    def _load_config_from_path(self, config_path):
        """Carica il file di configurazione da un path specifico."""
        if not os.path.exists(config_path):
            print(f"Warning: Config file not found at {config_path}")
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config file {config_path}: {e}")
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
            msg.setWindowTitle("Configuration Incomplete")
            msg.setText("Some patients still require configuration review.")
            msg.setInformativeText(f"Please review and save configuration for: {', '.join(unsaved_patients)}")
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
                os.remove(self.config_path)
                print(f"Removed config file: {self.config_path}")
            except OSError as e:
                print(f"Error removing config file {self.config_path}: {e}")

        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None