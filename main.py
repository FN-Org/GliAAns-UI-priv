import os
import shutil
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from logger import setup_logger
from utils import get_shell_path
from wizard_controller import WizardController

logfile = os.path.expanduser("~/GliAAns.log")
sys.stdout = open(logfile, "w")
sys.stderr = open(logfile, "w")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # app.setWindowIcon(QIcon(os.path.join("resources","GliAAns-logo.ico")))

    log = setup_logger(console=True)
    log.info("Program started")
    os.environ["PATH"] = get_shell_path()
    controller = WizardController()
    controller.start()

    sys.exit(app.exec())