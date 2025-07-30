from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QRadioButton,
    QGroupBox, QButtonGroup
)
from PyQt6.QtCore import Qt
from wizard_controller import WizardPage


class ToolChoicePage(WizardPage):
    def __init__(self, context=None):
        super().__init__()
        self.context = context
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        # Titolo
        title = QLabel("Select the next processing step")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.layout.addWidget(title)

        # Group box con radio buttons
        self.radio_group_box = QGroupBox("Available processes")
        radio_layout = QVBoxLayout()

        self.radio_group = QButtonGroup(self)

        self.radio_skull = QRadioButton("Skull Stripping")
        self.radio_draw = QRadioButton("Manual / Automatic Drawing")
        self.radio_dl = QRadioButton("Deep Learning Segmentation")
        self.radio_analysis = QRadioButton("Pipeline")
        self.radio_group.buttonToggled.connect(lambda: self.on_selection())

        for i, btn in enumerate([self.radio_skull, self.radio_draw, self.radio_dl, self.radio_analysis]):
            self.radio_group.addButton(btn, id=i)
            radio_layout.addWidget(btn)

        self.radio_group_box.setLayout(radio_layout)
        self.layout.addWidget(self.radio_group_box)

        self.selected_option = None

    def on_selection(self):
        selected_id = self.radio_group.checkedId()
        self.selected_option = selected_id + 1
        self.context.controller.next_page_index += self.selected_option
        self.context.controller.previous_page_index = self.context.controller.current_page_index
        self.context.controller.update_buttons_state()

    def on_enter(self, controller):
        # Reset selezione
        self.radio_group.setExclusive(False)
        for btn in self.radio_group.buttons():
            btn.setChecked(False)
        self.radio_group.setExclusive(True)
        self.selected_option = None

        self.controller = controller
        self.controller.next_page_index = 2
        self.controller.previous_page_index = 1
        self.controller.update_buttons_state()

    def is_ready_to_advance(self):
        selected_id = self.radio_group.checkedId()
        if selected_id != -1:
            # self.context.selected_processing_step = selected_id
            return True
        return False

    def is_ready_to_go_back(self):
        return True
