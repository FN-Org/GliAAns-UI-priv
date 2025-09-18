import os
import re

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QWidget, QLabel, QRadioButton, QButtonGroup, QFrame, QGroupBox, \
    QComboBox, QDialogButtonBox


class FileRoleDialog(QDialog):
    def __init__(self, workspace_path=None, subj = None, role = None, main = None, parent=None):
        super().__init__(parent)

        self.subj = subj
        self.role = role
        self.main = main

        self.setWindowTitle("File role")
        self.workspace_path = workspace_path
        layout = QVBoxLayout(self)
        if main is None and subj is None:
            # --- Livello Main/Derivatives ---
            self.level1_widget = QWidget()
            level1_layout = QVBoxLayout(self.level1_widget)
            self.pos_label = QLabel("Position:")
            level1_layout.addWidget(self.pos_label)
            self.opt_main = QRadioButton("main subject files")
            self.opt_derivatives = QRadioButton("derivatives")
            level1_layout.addWidget(self.opt_main)
            level1_layout.addWidget(self.opt_derivatives)


            self.button_first_group = QButtonGroup(self)
            self.button_first_group.addButton(self.opt_main)
            self.button_first_group.addButton(self.opt_derivatives)

            layout.addWidget(self.level1_widget)  # aggiungi il widget del livello 1

            self.button_first_group.buttonToggled.connect(self.first_level_toggled)

            self.derivative_extra_frame = QFrame()
            derivative_extra_layout = QVBoxLayout(self.derivative_extra_frame)
            self.derivative_extra_label = QLabel("What derivative:")
            derivative_extra_layout.addWidget(self.derivative_extra_label)

            self.derivative_extra_button_group = QButtonGroup(self)
            self.skull_strip_btn = QRadioButton("skullstrips")
            derivative_extra_layout.addWidget(self.skull_strip_btn)
            self.derivative_extra_button_group.addButton(self.skull_strip_btn)

            self.manual_mask_btn = QRadioButton("manual_masks")
            derivative_extra_layout.addWidget(self.manual_mask_btn)
            self.derivative_extra_button_group.addButton(self.manual_mask_btn)

            self.deep_learning_mask = QRadioButton("deep_learning_masks")
            derivative_extra_layout.addWidget(self.deep_learning_mask)
            self.derivative_extra_button_group.addButton(self.deep_learning_mask)

            self.derivative_extra_frame.hide()  # nascondi di default
            layout.addWidget(self.derivative_extra_frame)

        elif main == "derivatives":
            self.derivative_extra_frame = QFrame(self)
            derivative_extra_layout = QVBoxLayout(self.derivative_extra_frame)
            self.derivative_extra_label = QLabel("What derivative:")
            derivative_extra_layout.addWidget(self.derivative_extra_label)

            self.derivative_extra_button_group = QButtonGroup(self)
            self.skull_strip_btn = QRadioButton("skullstrips")
            derivative_extra_layout.addWidget(self.skull_strip_btn)
            self.derivative_extra_button_group.addButton(self.skull_strip_btn)

            self.manual_mask_btn = QRadioButton("manual_masks")
            derivative_extra_layout.addWidget(self.manual_mask_btn)
            self.derivative_extra_button_group.addButton(self.manual_mask_btn)

            self.deep_learning_mask = QRadioButton("deep_learning_masks")
            derivative_extra_layout.addWidget(self.deep_learning_mask)
            self.derivative_extra_button_group.addButton(self.deep_learning_mask)

            layout.addWidget(self.derivative_extra_frame)

            self.button_first_group = None
        else:
            self.button_first_group = None
            self.derivative_extra_button_group = None

        if subj is None:
            # --- Livello Subject ---
            self.level2_widget = QGroupBox("Subject")
            level2_layout = QVBoxLayout(self.level2_widget)

            subjects = [os.path.basename(p) for p in self._find_patient_dirs()]

            # uso QComboBox al posto dei RadioButton
            self.subj_combo = QComboBox()
            self.subj_combo.addItems(subjects)
            level2_layout.addWidget(self.subj_combo)

            # mantengo compatibilità con la logica esistente
            self.subj_buttons = []  # non serve più ma resta definito
            self.button_second_group = None

            layout.addWidget(self.level2_widget)
        else:
            self.button_second_group = None

        if role is None:
            # --- Livello Anat/Sess ---
            self.level3_widget = QWidget()
            level3_layout = QVBoxLayout(self.level3_widget)
            self.role_label = QLabel("Role:")
            level3_layout.addWidget(self.role_label)
            self.button_third_group = QButtonGroup(self)
            self.anat_button = QRadioButton("anat")
            self.button_third_group.addButton(self.anat_button)
            level3_layout.addWidget(self.anat_button)
            self.ses_1_button = QRadioButton("ses-01")
            self.button_third_group.addButton(self.ses_1_button)
            level3_layout.addWidget(self.ses_1_button)
            self.ses_2_button = QRadioButton("ses-02")
            self.button_third_group.addButton(self.ses_2_button)
            level3_layout.addWidget(self.ses_2_button)
            layout.addWidget(self.level3_widget)
        else: self.button_third_group = None
        # --- Pulsanti OK/Annulla ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # salva il pulsante OK e disabilitalo
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)

        # ogni volta che cambia qualcosa → ricontrolla
        if self.button_first_group:
            self.button_first_group.buttonToggled.connect(self.update_ok_button)

        if self.derivative_extra_button_group:
            self.derivative_extra_button_group.buttonToggled.connect(self.update_ok_button)

        if hasattr(self, "subj_combo"):
            self.subj_combo.currentIndexChanged.connect(self.update_ok_button)

        if self.button_third_group:
            self.button_third_group.buttonToggled.connect(self.update_ok_button)

    def filter_subjects(self, text):
        """Filtro live per la lista dei subject."""
        if hasattr(self, "subj_list"):
            for i in range(self.subj_list.count()):
                item = self.subj_list.item(i)
                item.setHidden(text.lower() not in item.text().lower())

    def get_selections(self):

        selections = {}


        # Livello 1: Main/Derivatives
        if self.button_first_group:
            btn = self.button_first_group.checkedButton()
            selections["main"] = btn.text() if btn else None

        if self.derivative_extra_button_group:
            btn = self.derivative_extra_button_group.checkedButton()
            selections["derivative"] = btn.text() if btn else None

        # Livello 2: Subject
        if self.button_second_group:
            btn = self.button_second_group.checkedButton()
            selections["subj"] = btn.text() if btn else None
        elif hasattr(self, "subj_combo"):
            selections["subj"] = self.subj_combo.currentText()


        # Livello 3: Role
        if self.button_third_group:
            btn = self.button_third_group.checkedButton()
            selections["role"] = btn.text() if btn else None


        return selections

    def get_relative_path(self):
        parts = []
        selections = self.get_selections()

        # gestisci eventuali valori None
        main = selections.get("main")
        subj = selections.get("subj")
        role = selections.get("role")
        derivative = selections.get("derivative")

        if main == "derivatives":
            parts.append("derivatives")
            if derivative:
                parts.append(derivative)


        if subj:
            parts.append(subj)

        if role:
            if re.match(r"^ses-\d+$", role):
                parts.append(role)
                parts.append("pet")
            else:
                parts.append(role)

        return os.path.join(*parts) if parts else None

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

        return patient_dirs


    def first_level_toggled(self, button, checked):
        if not checked:
            return
        if button == self.opt_main:
            self.derivative_extra_frame.hide()
            self.adjustSize()
        if button == self.opt_derivatives:
            self.derivative_extra_frame.show()
            self.adjustSize()

    def update_ok_button(self):
        selections = self.get_selections()
        enable = True

        # Main o Derivatives deve essere selezionato
        if not selections.get("main"):
            enable = False

        # Se "Derivatives" è selezionato, deve esserci anche il tipo di derivato
        if selections.get("main") == "derivatives" and not selections.get("derivative"):
            enable = False

        # Subject deve essere selezionato
        if not selections.get("subj"):
            enable = False

        # Role deve essere selezionato
        if not selections.get("role"):
            enable = False

        # abilita o disabilita OK
        self.ok_button.setEnabled(enable)

