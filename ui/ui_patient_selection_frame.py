import shutil
import sys

from PyQt6 import QtGui
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QGridLayout, QHBoxLayout, \
    QMessageBox, QSizePolicy
from PyQt6.QtCore import Qt
import os

from ui.ui_tool_selection_frame import ToolChoicePage
from utils import resource_path
from wizard_state import WizardPage
from logger import get_logger

log = get_logger()


class PatientSelectionPage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()

        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.workspace_path = context["workspace_path"]

        self.patient_buttons = {}
        self.selected_patients = set()

        self.layout = QVBoxLayout(self)
        self.title = QLabel("Select Patients to Analyze")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.layout.addWidget(self.title)

        top_buttons_layout = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        deselect_all_btn = QPushButton("Deselect All")

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

        select_all_btn.clicked.connect(self._select_all_patients)
        deselect_all_btn.clicked.connect(self._deselect_all_patients)

        top_buttons_layout.addStretch()
        top_buttons_layout.addWidget(select_all_btn)
        top_buttons_layout.addWidget(deselect_all_btn)

        self.layout.addLayout(top_buttons_layout)

        # self.scroll_area = QScrollArea()
        # self.scroll_area.setWidgetResizable(True)
        # self.scroll_area.setStyleSheet("""
        #     QScrollArea {
        #         font-size: 13px;
        #         border: 1px solid #bdc3c7;
        #         border-radius: 10px;
        #         padding: 5px;
        #     }
        # """)
        # self.scroll_content = QWidget()
        # self.grid_layout = QGridLayout(self.scroll_content)

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

        self.column_count = 2  # default fallback

        self._load_patients()

        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area)

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
        # NON cancellare patient_buttons qui
        # self.patient_buttons.clear()  # RIMOSSO

    def is_ready_to_advance(self):
        if self.selected_patients:
            return True
        else:
            return False

    def is_ready_to_go_back(self):
        return True

    def next(self, context):
        to_delete = [
            p for p in self._find_patient_dirs()
            if os.path.basename(p) not in self.selected_patients and os.path.basename(p) != "derivatives"
        ]

        unselected_ids = [os.path.basename(p) for p in to_delete]

        if to_delete:
            reply = QMessageBox.question(self, "Confirm Cleanup",
                                         f"{len(to_delete)} unselected patient(s) will be removed from the workspace. Continue?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.No:
                return None

            # If reply == Yes
            for patient_path in to_delete:
                try:

                    shutil.rmtree(patient_path)
                    patient_id = os.path.basename(patient_path)
                    self.selected_patients.discard(patient_id)
                    log.info(f"Deleted patient directory: {patient_path}")
                except Exception as e:
                    log.error(f"Failed to delete {patient_path}: {e}")

            # Rimozione da 'derivatives'
            derivatives_root = os.path.join(self.workspace_path, "derivatives")
            if os.path.exists(derivatives_root):
                for root, dirs, files in os.walk(derivatives_root, topdown=False):
                    for dir_name in dirs:
                        if dir_name in unselected_ids:
                            full_path = os.path.join(root, dir_name)
                            try:
                                shutil.rmtree(full_path)
                                log.info(f"Deleted from derivatives: {full_path}")
                            except Exception as e:
                                log.error(f"Failed to delete from derivatives: {full_path}: {e}")

        if not self.next_page:
            self.next_page = ToolChoicePage(context, self)
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

        for i, patient_path in enumerate(patient_dirs):
            patient_id = os.path.basename(patient_path)

            # Frame principale del paziente (il "card")
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
            # Adattabile in verticale ma con un limite
            patient_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            patient_frame.setMaximumHeight(140)

            # Usa QHBoxLayout invece di QVBoxLayout per allineare orizzontalmente
            patient_layout = QHBoxLayout(patient_frame)
            patient_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            profile = QFrame()
            profile.setObjectName("patientCard")
            profile_layout = QVBoxLayout(profile)

            # Immagine
            image = QLabel()
            pixmap = QtGui.QPixmap(resource_path("resources/user.png")).scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio,
                                                                  Qt.TransformationMode.SmoothTransformation)
            image.setPixmap(pixmap)
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Etichetta
            label = QLabel(f"{patient_id}")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            # Pulsante di selezione
            button = QPushButton("Select")
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

            is_selected = patient_id in self.selected_patients
            button.setChecked(is_selected)
            button.setText("Selected" if is_selected else "Select")

            button.clicked.connect(lambda checked, pid=patient_id, btn=button: self._toggle_patient(pid, checked, btn))

            self.patient_buttons[patient_id] = button

            # Aggiunta di tutti i widget nello stesso contenitore (stesso "card")
            profile_layout.addWidget(image)
            profile_layout.addWidget(label)
            # patient_layout.addWidget(image)
            # patient_layout.addWidget(label)
            patient_layout.addWidget(profile)
            patient_layout.addStretch()  # Aggiunge spazio tra label e pulsante
            patient_layout.addWidget(button)

            # Inserimento nella griglia
            self.grid_layout.addWidget(patient_frame, i // self.column_count, i % self.column_count)

    def _select_all_patients(self):
        for patient_id, button in self.patient_buttons.items():
            if not button.isChecked():
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

    def reset_page(self):
        # Pulisce la griglia
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        # Resetta selezioni e bottoni
        self.selected_patients.clear()
        self.patient_buttons.clear()

        # Ricarica i pazienti da zero
        self._load_patients()