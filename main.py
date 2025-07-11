import sys

from PyQt6.QtWidgets import QApplication

from ui.ui_main_window import MainWindow
from ui.ui_nifti_viewer import NiftiViewer

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = MainWindow()
    
    gui.show()
    sys.exit(app.exec())