import sys

from PyQt6.QtWidgets import QApplication

from ui.ui_main_window import MainWindow
from ui.ui_nifti_viewer import NiftiViewer
from logger import setup_logger

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = MainWindow()
    log = setup_logger(console=True)
    log.info("Program started")

    # nifti_viewer = NiftiViewer()
    # nifti_viewer.show()

    gui.show()
    sys.exit(app.exec())