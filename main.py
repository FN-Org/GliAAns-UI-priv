import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.ui_button import UiButton
from ui.ui_import_frame import ImportFrame
from ui.ui_main_window import MainWindow
from ui.ui_patient_selection_frame import PatientSelectionPage

def advance_to_patient_selection(gui: MainWindow):
    selection_page = PatientSelectionPage(gui.workspace_path)
    gui.set_right_widget(selection_page)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = MainWindow()

    # Import frame
    import_frame = ImportFrame(parent=gui.splitter, context=gui)
    gui.splitter.addWidget(import_frame)
    gui.splitter.setSizes([200, 600])
    gui.adjust_tree_columns()

    # Bottom button
    next_button = UiButton(parent=gui.footer, text="Next", context=gui)
    gui.footer_layout.addWidget(next_button, 0, Qt.AlignmentFlag.AlignRight)

    next_button.clicked.connect(lambda: advance_to_patient_selection(gui))

    gui.show()
    sys.exit(app.exec())