from ui.ui_import_frame import ImportFrame
from ui.ui_nifti_viewer import NiftiViewer


class WizardController:
    def __init__(self, next_button, back_button, main_window):
        self.next_button = next_button
        self.back_button = back_button
        self.main_window = main_window

        self.context = {
            "main_window": self.main_window,
            "workspace_path": self.main_window.workspace_path,
            "update_main_buttons": self.update_buttons_state,
            "return_to_import": self.return_to_import,
            "selected_files": [],
            "history": []
        }
        self.context['import_frame'] = ImportFrame(self.context)
        self.context['nifti_viewer'] = NiftiViewer(self.context)

        self.start_page = self.context['import_frame']

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