import shutil

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QGridLayout, QHBoxLayout, \
    QMessageBox
from PyQt6.QtCore import Qt
import os

from ui.tool_selection_frame import ToolChoicePage
from wizard_state import WizardPage


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
        self.label = QLabel("Select Patients to Analyze")
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.layout.addWidget(self.label)

        top_buttons_layout = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        deselect_all_btn = QPushButton("Deselect All")

        select_all_btn.clicked.connect(self._select_all_patients)
        deselect_all_btn.clicked.connect(self._deselect_all_patients)

        top_buttons_layout.addStretch()
        top_buttons_layout.addWidget(select_all_btn)
        top_buttons_layout.addWidget(deselect_all_btn)

        self.layout.addLayout(top_buttons_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)

        self._load_patients()

        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area)

    def on_exit(self):
        # NON cancellare più selected_patients qui
        # self.selected_patients.clear()  # RIMOSSO

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
                    # Rimuovi anche dalle selezioni se presente
                    patient_id = os.path.basename(patient_path)
                    self.selected_patients.discard(patient_id)
                    print(f"Deleted: {patient_path}")
                except Exception as e:
                    print(f"Failed to delete {patient_path}: {e}")

        if not self.next_page:
            self.next_page = ToolChoicePage(context, self)

        self.on_exit()
        return self.next_page

    def back(self):
        if self.previous_page:
            self.on_exit()
            return self.previous_page

        return None

    def _load_patients(self):
        patient_dirs = self._find_patient_dirs()
        patient_dirs.sort()

        # Pulisci i riferimenti ai bottoni precedenti
        self.patient_buttons.clear()

        for i, patient_path in enumerate(patient_dirs):
            patient_id = os.path.basename(patient_path)

            # Container "card"
            patient_frame = QFrame()
            patient_frame.setStyleSheet("""
                QFrame {
                    border: 1px solid #CCCCCC;
                    border-radius: 10px;
                    background-color: #F9F9F9;
                    padding: 10px;
                }
            """)
            patient_layout = QHBoxLayout(patient_frame)

            # Etichetta con nome paziente
            label = QLabel(f"Patient: {patient_id}")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            # Pulsante selezione
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

            # CORREZIONE: Ripristina lo stato del bottone basato sulle selezioni esistenti
            is_selected = patient_id in self.selected_patients
            button.setChecked(is_selected)
            button.setText("Selected" if is_selected else "Select")

            button.clicked.connect(lambda checked, pid=patient_id, btn=button: self._toggle_patient(pid, checked, btn))

            # Layout
            patient_layout.addWidget(label)
            patient_layout.addStretch()
            patient_layout.addWidget(button)

            self.patient_buttons[patient_id] = button

            # Aggiungi alla griglia
            self.grid_layout.addWidget(patient_frame, i // 2, i % 2)

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