import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.ui_button import UiButton
from ui.ui_import_frame import ImportFrame
from ui.ui_main_window import MainWindow
from ui.ui_nifti_viewer import NiftiViewer

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = MainWindow()

    # Import frame
    import_frame = ImportFrame(parent=gui.splitter, context=gui)
    nifti_viewer = NiftiViewer()
    nifti_viewer.show()
    gui.splitter.addWidget(import_frame)
    gui.splitter.setSizes([200, 600])
    gui.adjust_tree_columns()

    # Bottom button
    next_button = UiButton(parent=gui.footer, text="Next", context=gui)
    gui.footer_layout.addWidget(next_button, 0, Qt.AlignmentFlag.AlignRight)

    gui.show()
    sys.exit(app.exec())