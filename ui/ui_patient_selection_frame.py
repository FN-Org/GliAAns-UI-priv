import shutil

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QGridLayout, QHBoxLayout, \
    QMessageBox
from PyQt6.QtCore import Qt
import os

from wizard_controller import WizardPage


class PatientSelectionPage(WizardPage):
    def __init__(self, context=None):
        super().__init__()

        self.patient_buttons = {}  # patient_id -> QPushButton
        self.context = context

        self.workspace_path = context.workspace_path
        self.selected_patients = set()

        self.layout = QVBoxLayout(self)
        self.label = QLabel("Select Patients to Analyze")
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.layout.addWidget(self.label)

        # Pulsanti Seleziona/Deseleziona Tutti
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

    def on_enter(self, controller):
        """Hook chiamato quando si entra nella pagina."""
        self._load_patients()
        pass

    def on_exit(self, controller):
        to_delete = [p for p in self._find_patient_dirs() if os.path.basename(p) not in self.selected_patients]

        if not to_delete:
            return

        reply = QMessageBox.question(self, "Confirm Cleanup",
                                     f"{len(to_delete)} unselected patient(s) will be removed from the workspace. Continue?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            for patient_path in to_delete:
                try:
                    shutil.rmtree(patient_path)
                    print(f"Deleted: {patient_path}")
                except Exception as e:
                    print(f"Failed to delete {patient_path}: {e}")

    def is_ready_to_advance(self):
        """Restituisce True se si può avanzare alla prossima pagina."""
        if self.selected_patients:
            return True
        else:
            return False

    def is_ready_to_go_back(self):
        """Restituisce True se si può tornare indietro alla pagina precedente."""
        return True

    def _load_patients(self):
        patient_dirs = self._find_patient_dirs()
        patient_dirs.sort()

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
            button.setChecked(False)
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
        self.context.controller.update_buttons_state()

    def _deselect_all_patients(self):
        for patient_id, button in self.patient_buttons.items():
            if button.isChecked():
                button.setChecked(False)
                button.setText("Select")
                self.selected_patients.discard(patient_id)
        self.context.controller.update_buttons_state()

    def _find_patient_dirs(self):
        patient_dirs = []

        for root, dirs, files in os.walk(self.workspace_path):
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
        self.context.controller.update_buttons_state()

    def get_selected_patients(self):
        return list(self.selected_patients)
