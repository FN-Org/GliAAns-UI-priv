import glob
import os

from PyQt6.QtCore import pyqtSignal, Qt, QSize, QPropertyAnimation, QEasingCurve, QCoreApplication
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QComboBox, \
    QPushButton


class ClickableFrame(QFrame):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()

class CollapsiblePatientFrame(QFrame):
    def __init__(self, context, patient_id, files, patterns, multiple_choice=False, save_callback=None):
        super().__init__()
        self.patient_id = patient_id
        self.workspace_path = context["workspace_path"]
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

        self._retranslate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._retranslate_ui)

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
        self.subject_name = QLabel(self)
        self.subject_name.setText(QCoreApplication.translate("Components", "Patient: {0}").format(self.patient_id))
        self.subject_name.setStyleSheet("font-size: 13px; font-weight: bold;")
        frame_header_layout.addWidget(self.subject_name)

        # Header con QToolButton
        self.toggle_button = QToolButton(self)
        self.toggle_button.setText(
            QCoreApplication.translate(
                "Components",
                "Patient: {patient}"
            ).format(patient=self.patient_id)
        )
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
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

            if self.locked or len(all_files_rel) == 1:
                self.chosen_file = self.files.get(category, "")
                self.file_label = QLabel(self.chosen_file if self.chosen_file else QCoreApplication.translate("Components", "No file found"))
                category_layout.addWidget(category_label)
                category_layout.addWidget(self.file_label)

                # Caso speciale: se è pet4d, mostriamo anche il relativo JSON
                if category == "pet4d":
                    self._add_pet4d_json_display(category_layout, self.chosen_file)

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

            self.save_btn = QPushButton(QCoreApplication.translate("Components", "Save Patient Configuration"))
            self.save_btn.setMinimumHeight(32)
            self.save_btn.setStyleSheet("""
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
            self.save_btn.clicked.connect(self._save_patient)

            save_layout.addStretch()
            save_layout.addWidget(self.save_btn)
            save_layout.addStretch()

            self.content_layout.addWidget(save_container)

    def _add_pet4d_json_display(self, parent_layout, pet4d_file_rel):
        """Mostra il JSON associato al file pet4d scelto (solo in modalità locked)."""
        if not pet4d_file_rel:
            label = QLabel(QCoreApplication.translate("Components", "<span style='color:red;'>No PET4D file selected</span>"))
            parent_layout.addWidget(label)
            return

        abs_pet4d_path = os.path.join(self.workspace_path, pet4d_file_rel)
        json_candidate = abs_pet4d_path.replace(".nii.gz", ".json").replace(".nii", ".json")

        if os.path.exists(json_candidate):
            rel_json = os.path.relpath(json_candidate, self.workspace_path)
            label = QLabel(QCoreApplication.translate("Components", "JSON related: <strong>{rel_json}</strong>").format(rel_json=rel_json))
            label.setStyleSheet("color: black; font-size: 12px;")
            self.files["pet4d_json"] = rel_json
        else:
            label = QLabel(QCoreApplication.translate("Components", "<span style='color:red;'>Error: associated JSON file not found</span>"))
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
            self.pet4d_json_label.setText(QCoreApplication.translate("Components", "<span style='color:red;'>No PET4D file selected</span>"))
            return

        # Ricava percorso assoluto e costruisce quello del json
        abs_pet4d_path = os.path.join(self.workspace_path, selected_file)
        json_candidate = abs_pet4d_path.replace(".nii.gz", ".json").replace(".nii", ".json")

        if os.path.exists(json_candidate):
            rel_json = os.path.relpath(json_candidate, self.workspace_path)
            self.pet4d_json_label.setText(QCoreApplication.translate("Components", "JSON related: <strong>{rel_json}</strong>").format(rel_json=rel_json))
            self.pet4d_json_label.setStyleSheet("color: black; font-size: 12px;")
            self.files["pet4d_json"] = rel_json  # salvo nel dict dei files
        else:
            self.pet4d_json_label.setText(QCoreApplication.translate("Components", "<span style='color:red;'>Error: associated JSON file not found</span>"))
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

    def _retranslate_ui(self):
        # Aggiorna solo i testi, senza ricreare widget
        self.toggle_button.setText(
            QCoreApplication.translate(
                "Components",
                "Patient: {patient}"
            ).format(patient=self.patient_id)
        )

        self.subject_name.setText(QCoreApplication.translate("Components", "Patient: {0}").format(self.patient_id))

        if self.locked:
            self.file_label.setText(self.chosen_file if self.chosen_file else QCoreApplication.translate("Components", "No file found"))
        if not self.locked:
            self.save_btn.setText(QCoreApplication.translate("Components", "Save Patient Configuration"))

        self._populate_content()