from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from wizard_state import WizardPage


class WorkInProgressPage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        label = QLabel("Work in Progress \n\nThis page is under construction.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 40px;")
        layout.addWidget(label)

    def is_ready_to_advance(self):
        return False

    def is_ready_to_go_back(self):
        return True

    def back(self):
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page

        return None