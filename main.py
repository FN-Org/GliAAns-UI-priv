import sys

from PyQt6.QtWidgets import QApplication

from logger import setup_logger
from wizard_controller import WizardController

if __name__ == "__main__":
    app = QApplication(sys.argv)

    log = setup_logger(console=True)
    log.info("Program started")
    controller = WizardController()
    controller.start()

    sys.exit(app.exec())