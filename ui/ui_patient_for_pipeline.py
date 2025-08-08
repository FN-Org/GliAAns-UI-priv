import shutil
import os
import glob

from PyQt6 import QtWidgets, QtGui
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea,
                             QFrame, QGridLayout, QHBoxLayout, QMessageBox, QGroupBox,
                             QTextEdit, QSplitter)
from PyQt6.QtCore import Qt

from wizard_state import WizardPage


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

        select_eligible_btn = QPushButton("Select All Eligible")
        deselect_all_btn = QPushButton("Deselect All")
        refresh_btn = QPushButton("Refresh Status")

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

        for btn in [select_eligible_btn, deselect_all_btn, refresh_btn]:
            btn.setStyleSheet(btn_style)

        select_eligible_btn.clicked.connect(self._select_all_eligible_patients)
        deselect_all_btn.clicked.connect(self._deselect_all_patients)
        refresh_btn.clicked.connect(self._refresh_patient_status)

        top_buttons_layout.addStretch()
        top_buttons_layout.addWidget(select_eligible_btn)
        top_buttons_layout.addWidget(deselect_all_btn)
        top_buttons_layout.addWidget(refresh_btn)

        self.layout.addLayout(top_buttons_layout)

        # Splitter per dividere la vista dei pazienti e il resoconto
        # splitter = QSplitter(Qt.Orientation.Horizontal)

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
        """Crea il widget per il resoconto dei pazienti"""
        summary_frame = QFrame()
        summary_frame.setObjectName("summaryCard")
        summary_frame.setStyleSheet("""
            QFrame#summaryCard {
                border: 1px solid #bdc3c7;
                border-radius: 10px;
                background-color: #ffffff;
                padding: 5px;
            }
        """)

        summary_layout = QVBoxLayout(summary_frame)

        summary_title = QLabel("Pipeline Requirements Summary")
        summary_title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        summary_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_layout.addWidget(summary_title)

        self.summary_text = QLabel()
        self.summary_text.setStyleSheet("""
            QLabel {
                border: 1px solid #CCCCCC;
                border-radius: 5px;
                padding-left: 20px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                background-color: #f8f8f8;
            }
        """)
        summary_layout.addWidget(self.summary_text)

        return summary_frame

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
            os.path.join(self.workspace_path, "derivatives", "fsl_skullstrips", patient_id, "anat", "*_brain.nii"),
            os.path.join(self.workspace_path, "derivatives", "fsl_skullstrips", patient_id, "anat", "*_brain.nii.gz")
        ]

        skull_strip_found = False
        for pattern in skull_strip_patterns:
            if glob.glob(pattern):
                skull_strip_found = True
                break

        requirements['skull_stripping'] = skull_strip_found
        if not skull_strip_found:
            missing_files.append("Skull stripped image (derivatives/fsl_skullstrips/.../anat/*_brain.nii[.gz])")

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
        """Aggiorna il resoconto nel pannello laterale"""
        summary_text = f"""
Total Patients: {total_count}
Eligible for Pipeline: {eligible_count}
Not Eligible: {total_count - eligible_count}
"""

        self.summary_text.setText(summary_text)

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_column_count()

    def on_enter(self):
        """Chiamato quando si entra nella pagina"""
        self._refresh_patient_status()

    def is_ready_to_advance(self):
        """Verifica se si può procedere alla pagina successiva"""
        return len(self.selected_patients) > 0

    def is_ready_to_go_back(self):
        """Verifica se si può tornare alla pagina precedente"""
        return True

    # def next(self, context):
    #     """Procede alla pagina successiva dopo aver rimosso i pazienti non selezionati"""
    #     # Lista dei pazienti da eliminare (solo tra quelli eligible non selezionati)
    #     eligible_patients = {pid for pid, status in self.patient_status.items() if status['eligible']}
    #     to_delete = []
    #
    #     for pid in eligible_patients:
    #         if pid not in self.selected_patients:
    #             # Trova il path del paziente
    #             patient_dirs = self._find_patient_dirs()
    #             for patient_path in patient_dirs:
    #                 if os.path.basename(patient_path) == pid:
    #                     to_delete.append(patient_path)
    #                     break
    #
    #     unselected_ids = [os.path.basename(p) for p in to_delete]
    #
    #     if to_delete:
    #         reply = QMessageBox.question(
    #             self,
    #             "Confirm Cleanup",
    #             f"{len(to_delete)} eligible but unselected patient(s) will be removed from the workspace.\n\n"
    #             f"Selected patients: {len(self.selected_patients)}\n"
    #             f"Eligible but unselected: {len(to_delete)}\n"
    #             f"Not eligible (will remain): {len(self.patient_status) - len(eligible_patients)}\n\n"
    #             f"Continue?",
    #             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    #         )
    #
    #         if reply == QMessageBox.StandardButton.No:
    #             return None
    #
    #         # Rimuovi le directory dei pazienti non selezionati
    #         for patient_path in to_delete:
    #             try:
    #                 shutil.rmtree(patient_path)
    #                 patient_id = os.path.basename(patient_path)
    #                 self.selected_patients.discard(patient_id)
    #                 print(f"Deleted patient directory: {patient_path}")
    #             except Exception as e:
    #                 print(f"Failed to delete {patient_path}: {e}")
    #
    #         # Rimozione da 'derivatives'
    #         derivatives_root = os.path.join(self.workspace_path, "derivatives")
    #         if os.path.exists(derivatives_root):
    #             for root, dirs, files in os.walk(derivatives_root, topdown=False):
    #                 for dir_name in dirs:
    #                     if dir_name in unselected_ids:
    #                         full_path = os.path.join(root, dir_name)
    #                         try:
    #                             shutil.rmtree(full_path)
    #                             print(f"Deleted from derivatives: {full_path}")
    #                         except Exception as e:
    #                             print(f"Failed to delete from derivatives: {full_path}: {e}")
    #
    #     # Procedi alla pagina successiva
    #     if not self.next_page:
    #         self.next_page = ToolChoicePage(context, self)
    #         self.context["history"].append(self.next_page)
    #
    #     self.next_page.on_enter()
    #     return self.next_page

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