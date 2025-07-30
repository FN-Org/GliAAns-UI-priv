from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from wizard_state import WizardPage


class WorkInProgressPage(WizardPage):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        label = QLabel("Work in Progress \n\nThis page is under construction.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 40px;")
        layout.addWidget(label)

    def on_enter(self, controller):
        print("Entered WorkInProgressPage")

    def is_ready_to_advance(self):
        # Always allow to proceed from this page
        return True

    def is_ready_to_go_back(self):
        return True