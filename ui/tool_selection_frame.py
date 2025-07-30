from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QRadioButton,
    QGroupBox, QButtonGroup
)
from PyQt6.QtCore import Qt

from ui.ui_fsl_frame import SkullStrippingPage
from ui.ui_nifti_selection import NiftiSelectionPage
from ui.ui_work_in_progress import WorkInProgressPage
from wizard_state import WizardPage


class ToolChoicePage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        title = QLabel("Select the next processing step")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.layout.addWidget(title)

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
        self.selected_option = selected_id
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def on_enter(self):
        self.radio_group.setExclusive(False)
        for btn in self.radio_group.buttons():
            btn.setChecked(False)
        self.radio_group.setExclusive(True)
        self.selected_option = None

    def is_ready_to_advance(self):
        selected_id = self.radio_group.checkedId()
        if selected_id != -1:
            return True
        return False

    def is_ready_to_go_back(self):
        return True

    def next(self, context):
        if self.selected_option == 0:
            self.next_page = SkullStrippingPage(context, self)
        elif self.selected_option == 1:
            self.next_page = NiftiSelectionPage(context, self)
        elif self.selected_option == 2:
            self.next_page = WorkInProgressPage()
        elif self.selected_option == 3:
            self.next_page = WorkInProgressPage()
        else:
            return None

        self.on_exit()
        self.next_page.on_enter()
        return self.next_page

    def back(self, context):
        if self.previous_page:
            self.on_exit()
            self.previous_page.on_enter()
            return self.previous_page

        return None