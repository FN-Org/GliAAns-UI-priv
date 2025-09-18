from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QGroupBox, QRadioButton, QButtonGroup, QSizePolicy
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from ui.ui_mask_selection import NiftiSelectionPage
from ui.ui_dl_selection import DlPatientSelectionPage
from ui.ui_pipeline_patient_selection import PipelinePatientSelectionPage
from ui.ui_skull_stripping_frame import SkullStrippingPage
from wizard_state import WizardPage


class ToolChoicePage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_skull_stripping = None
        self.next_manual_draw = None
        self.next_deep_learning = None
        self.next_pipeline = None

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(30)
        self.setLayout(self.layout)

        # Titolo principale
        self.title = QLabel("Select the Next Processing Step")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.layout.addWidget(self.title)

        # Gruppo processi con stile card moderno
        self.radio_group_box = QGroupBox("Available Processes")
        self.radio_group_box.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                border: 1px solid #bdc3c7;
                border-radius: 10px;
                padding: 20px;
                background-color: #e5e5e5;
            }
        """)
        self.radio_group_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.radio_group_box.setMaximumHeight(400)
        radio_layout = QVBoxLayout()
        radio_layout.setSpacing(20)
        radio_layout.setContentsMargins(10, 10, 10, 10)

        self.radio_group = QButtonGroup(self)

        # Radio buttons con stile migliorato
        self.radio_skull = QRadioButton("Skull Stripping")
        self.radio_draw = QRadioButton("Manual / Automatic Drawing")
        self.radio_dl = QRadioButton("Deep Learning Segmentation")
        self.radio_analysis = QRadioButton("Full Pipeline")

        self.radio_buttons = [
            self.radio_skull, self.radio_draw, self.radio_dl, self.radio_analysis
        ]

        for btn in self.radio_buttons:
            btn.setFont(QFont("Arial", 14))
            btn.setStyleSheet("""
                QRadioButton {
                    padding: 5px;
                    border: 1px solid #bdc3c7;
                    border-radius: 8px;
                    background-color: white;
                    spacing: 10px;
                }
                QRadioButton::hover {
                    background-color: #dff9fb;
                    border: 1px solid #3498db;
                }
                QRadioButton::checked {
                    background-color: #d6eaf8;
                    border: 2px solid #2980b9;
                }
            """)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        for i, btn in enumerate(self.radio_buttons):
            self.radio_group.addButton(btn, id=i)
            radio_layout.addWidget(btn)

        self.radio_group.buttonToggled.connect(lambda: self.on_selection())

        self.radio_group_box.setLayout(radio_layout)
        self.layout.addWidget(self.radio_group_box)

        self.selected_option = None

    def resizeEvent(self, event):
        """
        Ridimensiona dinamicamente i font in base alle dimensioni della finestra
        considerando sia larghezza che altezza per un risultato più equilibrato
        """
        # Ottieni le dimensioni correnti
        window_width = self.width()
        window_height = self.height()

        # Calcola una dimensione di riferimento basata su entrambe le dimensioni
        # Usando la media geometrica per bilanciare larghezza e altezza
        reference_size = (window_width * window_height) ** 0.5

        # Metodo 1: Basato su dimensione di riferimento
        base_font_size = max(10, int(reference_size / 45))
        title_font_size = max(14, int(base_font_size * 1.4))

        # Applica i font
        self.title.setFont(QFont("Arial", title_font_size, QFont.Weight.Bold))

        for btn in self.radio_buttons:
            btn.setFont(QFont("Arial", base_font_size))

        # Chiama il metodo padre
        super().resizeEvent(event)

    def on_selection(self):
        selected_id = self.radio_group.checkedId()
        self.selected_option = selected_id
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def is_ready_to_advance(self):
        return self.radio_group.checkedId() != -1

    def is_ready_to_go_back(self):
        return True

    def next(self, context):
        page_classes = {
            0: ("next_skull_stripping", SkullStrippingPage),
            1: ("next_manual_draw", NiftiSelectionPage),
            2: ("next_deep_learning", DlPatientSelectionPage),
            3: ("next_pipeline", PipelinePatientSelectionPage),
        }

        if self.selected_option not in page_classes:
            return None

        attr_name, page_class = page_classes[self.selected_option]

        next_page = getattr(self, attr_name, None)

        if not next_page:
            next_page = page_class(context, self)
            setattr(self, attr_name, next_page)
            self.context["history"].append(next_page)

        next_page.on_enter()
        return next_page

    def back(self):
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def reset_page(self):
        self.radio_group.setExclusive(False)
        for button in self.radio_group.buttons():
            button.setChecked(False)
        self.radio_group.setExclusive(True)
        self.selected_option = None
