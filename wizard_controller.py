import os

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtWidgets import QMainWindow

from components.ui_button import UiButton
from ui.ui_import_frame import ImportFrame
from ui.ui_main_window import MainWindow
from ui.ui_nifti_viewer import NiftiViewer


class WizardController(QObject):
    language_changed = pyqtSignal(str)
    selected_files_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__(None)
        self.back_button = None
        self.next_button = None

        self.workspace_path = os.path.join(os.getcwd(), ".workspace")
        if not os.path.exists(self.workspace_path):
            os.makedirs(self.workspace_path)


        self.context = {
            "workspace_path": self.workspace_path,
            "update_main_buttons": self.update_buttons_state,
            "return_to_import": self.return_to_import,
            "selected_files": [],
            "history": [],
            "language_changed": self.language_changed,
            "create_buttons": self.create_buttons,
            "selected_files_signal": self.selected_files_signal,
            "open_nifti_viewer":self.open_nifti_viewer
        }
        self.context['import_frame'] = ImportFrame(self.context)
        self.context["main_window"] = MainWindow(self.context)
        self.context['nifti_viewer'] = NiftiViewer(self.context)


        self.start_page = self.context['import_frame']
        self.main_window = self.context['main_window']

        self.context["history"].append(self.start_page)
        self.current_page = self.start_page

        self._show_current_page()

    def _show_current_page(self):
        self.main_window.set_right_widget(self.current_page)
        self.update_buttons_state()

    def go_to_next_page(self):
        next_page = self.current_page.next(self.context)
        if next_page:
            self.current_page = next_page
            self._show_current_page()
        return self.current_page

    def go_to_previous_page(self):
        previous_page = self.current_page.back()
        if previous_page:
            self.current_page = previous_page
            self._show_current_page()
        return self.current_page

    def return_to_import(self):
        if self.context["history"]:
            for page in self.context["history"]:
                page.reset_page()
            self.current_page = self.start_page
            self._show_current_page()
        return self.current_page

    def update_buttons_state(self):
        self.next_button.setEnabled(
            self.current_page.is_ready_to_advance()
        )
        self.back_button.setEnabled(
            self.current_page.is_ready_to_go_back()
        )

    def create_buttons(self):
        self.next_button = UiButton(text="Next", context=self)
        self.back_button = UiButton(text="Back", context=self)
        self.next_button.clicked.connect(self.go_to_next_page)
        self.back_button.clicked.connect(self.go_to_previous_page)

        return self.next_button, self.back_button

    def start(self):
        self.main_window.show()

    def open_nifti_viewer(self,path):
        self.context["nifti_viewer"].open_file(path)
        self.context["nifti_viewer"].show()