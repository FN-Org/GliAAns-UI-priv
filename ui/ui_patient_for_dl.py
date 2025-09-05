import shutil
import glob

from PyQt6 import QtWidgets, QtGui
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QGridLayout, QHBoxLayout, \
    QMessageBox, QGroupBox
from PyQt6.QtCore import Qt
import os

from ui.ui_work_in_progress import WorkInProgressPage
from wizard_state import WizardPage
from logger import get_logger

log = get_logger()


class DlPatientSelectionPage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()

        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.workspace_path = context["workspace_path"]

        self.patient_buttons = {}
        self.selected_patients = set()
        self.patients_with_flair = {}  # Dict per tracciare i pazienti con FLAIR e i loro path
        self.patients_status = {}  # Dict per tracciare lo status dei pazienti (True=ha FLAIR, False=non ha FLAIR)

        self.layout = QVBoxLayout(self)
        self.title = QLabel("Select Patients to Analyze (FLAIR Required)")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.layout.addWidget(self.title)

        # Aggiungiamo una label informativa
        info_label = QLabel("🟢 Green: Patients with FLAIR images (selectable) | 🔴 Red: Patients without FLAIR images")
        info_label.setStyleSheet("font-size: 12px; color: #666666; margin: 5px 0px;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.layout.addWidget(info_label)

        top_buttons_layout = QHBoxLayout()

        select_all_btn = QPushButton("Select All Available")
        deselect_all_btn = QPushButton("Deselect All")
        refresh_btn = QPushButton("Refresh Status")

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

        select_all_btn.setStyleSheet(btn_style)
        deselect_all_btn.setStyleSheet(btn_style)
        refresh_btn.setStyleSheet(btn_style)

        select_all_btn.clicked.connect(self._select_all_available_patients)
        deselect_all_btn.clicked.connect(self._deselect_all_patients)
        refresh_btn.clicked.connect(self._refresh_patient_status)

        top_buttons_layout.addStretch()
        top_buttons_layout.addWidget(select_all_btn)
        top_buttons_layout.addWidget(deselect_all_btn)
        top_buttons_layout.addWidget(refresh_btn)

        self.layout.addLayout(top_buttons_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                font-size: 13px;
                border: 1px solid #bdc3c7;
                border-radius: 10px;
                padding: 5px;
            }
        """)
        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)

        self.column_count = 2  # default fallback

        self._load_patients()

        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area)

    def _check_flair_presence(self, patient_path):
        """Controlla se il paziente ha immagini FLAIR nel percorso sub-*/anat/*_flair.nii(.gz)"""
        patient_id = os.path.basename(patient_path)

        # Pattern per cercare file FLAIR (.nii e .nii.gz)
        flair_pattern_gz = os.path.join(patient_path, "anat", "*_flair.nii.gz")
        flair_pattern_nii = os.path.join(patient_path, "anat", "*_flair.nii")

        flair_files = glob.glob(flair_pattern_gz) + glob.glob(flair_pattern_nii)

        if flair_files:
            # Ritorna True e il primo file FLAIR trovato
            return True, flair_files[0]
        else:
            return False, None

    def _update_column_count(self):
        # Margine di sicurezza per padding/bordi
        available_width = self.scroll_area.viewport().width() - 40
        min_card_width = 250  # Larghezza minima per un patient_frame

        new_column_count = max(1, available_width // min_card_width)

        if new_column_count != self.column_count:
            self.column_count = new_column_count
            self._reload_patient_grid()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_column_count()

    def _reload_patient_grid(self):
        # Salva la selezione
        selected = self.selected_patients.copy()

        # Pulisci la griglia
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        # Ricarica con lo stesso layout adattato
        self._load_patients()
        self.selected_patients = selected

    def on_enter(self):
        # Cancella solo i widget, ma mantieni le selezioni
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        # Ricarica i pazienti mantenendo le selezioni
        self._load_patients()

    def is_ready_to_advance(self):
        return len(self.selected_patients) > 0

    def is_ready_to_go_back(self):
        return True

    def next(self, context):
        # Aggiungiamo le informazioni sui file FLAIR al context
        selected_flair_files = {}
        for patient_id in self.selected_patients:
            if patient_id in self.patients_with_flair:
                selected_flair_files[patient_id] = self.patients_with_flair[patient_id]

        # Salviamo i dati nel context per la prossima pagina
        context["selected_flair_files"] = selected_flair_files
        context["selected_patients"] = list(self.selected_patients)

        # Vai alla pagina successiva (che puoi sostituire con la tua nuova pagina)
        if not self.next_page:
            self.next_page = WorkInProgressPage(context, self)
            self.context["history"].append(self.next_page)

        self.next_page.on_enter()
        return self.next_page

    def back(self):
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page

        return None

    def _load_patients(self):
        patient_dirs = self._find_patient_dirs()
        patient_dirs.sort()

        self.patient_buttons.clear()
        self.patients_with_flair.clear()
        self.patients_status.clear()

        for i, patient_path in enumerate(patient_dirs):
            patient_id = os.path.basename(patient_path)

            # Controlla se il paziente ha file FLAIR
            has_flair, flair_path = self._check_flair_presence(patient_path)
            self.patients_status[patient_id] = has_flair

            if has_flair:
                self.patients_with_flair[patient_id] = flair_path

            # Frame principale del paziente (il "card")
            patient_frame = QFrame()
            patient_frame.setObjectName("patientCard")

            # Stile diverso per pazienti eligible/non-eligible
            if has_flair:
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
            pixmap = QtGui.QPixmap("./resources/user.png").scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio,
                                                                  Qt.TransformationMode.SmoothTransformation)
            image.setPixmap(pixmap)
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # ID del paziente
            patient_label = QLabel(f"{patient_id}")
            patient_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            patient_label.setStyleSheet("font-weight: bold; font-size: 12px;")

            # Status label
            if has_flair:
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
            # Per ora mostriamo solo FLAIR, ma si può estendere facilmente
            flair_indicator = QLabel()
            if has_flair:
                flair_indicator.setText("✓ FLAIR")
                flair_indicator.setStyleSheet("color: #4CAF50; font-size: 10px; padding: 1px;")
            else:
                flair_indicator.setText("✗ FLAIR")
                flair_indicator.setStyleSheet("color: #f44336; font-size: 10px; padding: 1px;")

            details_layout.addWidget(flair_indicator)

            # Pulsante di selezione (destra)
            button = QPushButton("Select")
            button.setCheckable(True)

            if has_flair:
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

                button.clicked.connect(
                    lambda checked, pid=patient_id, btn=button: self._toggle_patient(pid, checked, btn))
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

            # Inserimento nella griglia
            self.grid_layout.addWidget(patient_frame, i // self.column_count, i % self.column_count)

    def _refresh_patient_status(self):
        """Ricarica lo stato di tutti i pazienti mantenendo le selezioni valide"""
        # Salva le selezioni correnti
        current_selections = self.selected_patients.copy()

        # Pulisci la griglia
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        # Ricarica tutto da zero
        self._load_patients()

        # Ripristina le selezioni valide (solo pazienti che hanno ancora FLAIR)
        valid_selections = set()
        for patient_id in current_selections:
            if (patient_id in self.patients_status and
                    self.patients_status[patient_id] and  # Ha FLAIR
                    patient_id in self.patient_buttons):
                valid_selections.add(patient_id)
                button = self.patient_buttons[patient_id]
                button.setChecked(True)
                button.setText("Selected")

        self.selected_patients = valid_selections

        # Aggiorna i pulsanti principali se disponibili
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

        log.info(f"Patient status refreshed. {len(valid_selections)} patients remain selected.")

    def _select_all_available_patients(self):
        """Seleziona tutti i pazienti che hanno FLAIR"""
        for patient_id, button in self.patient_buttons.items():
            if self.patients_status.get(patient_id, False) and not button.isChecked():
                button.setChecked(True)
                button.setText("Selected")
                self.selected_patients.add(patient_id)
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def _deselect_all_patients(self):
        for patient_id, button in self.patient_buttons.items():
            if button.isChecked():
                button.setChecked(False)
                button.setText("Select")
                self.selected_patients.discard(patient_id)
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def _find_patient_dirs(self):
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

    def _toggle_patient(self, patient_id, is_selected, button):
        """Toggle selezione paziente - solo per pazienti con FLAIR"""
        if self.patients_status.get(patient_id, False):  # Solo se ha FLAIR
            if is_selected:
                self.selected_patients.add(patient_id)
                button.setText("Selected")
            else:
                self.selected_patients.discard(patient_id)
                button.setText("Select")
            if self.context and "update_main_buttons" in self.context:
                self.context["update_main_buttons"]()

    def get_selected_patients(self):
        return list(self.selected_patients)

    def get_selected_flair_files(self):
        """Restituisce un dizionario con i file FLAIR dei pazienti selezionati"""
        selected_flair = {}
        for patient_id in self.selected_patients:
            if patient_id in self.patients_with_flair:
                selected_flair[patient_id] = self.patients_with_flair[patient_id]
        return selected_flair

    def reset_page(self):
        # Pulisce la griglia
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        # Resetta tutte le strutture dati
        self.selected_patients.clear()
        self.patient_buttons.clear()
        self.patients_with_flair.clear()
        self.patients_status.clear()

        # Ricarica i pazienti da zero
        self._load_patients()