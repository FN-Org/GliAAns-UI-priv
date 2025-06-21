from PyQt6.QtWidgets import QWidget, QVBoxLayout


class WizardPage(QWidget):
    def on_enter(self, controller):
        """Hook chiamato quando si entra nella pagina."""
        pass

    def is_ready_to_advance(self):
        """Restituisce True se si può avanzare alla prossima pagina."""
        return True

    def is_ready_to_go_back(self):
        """Restituisce True se si può tornare indietro alla pagina precedente."""
        return True

class WizardController:
    def __init__(self, next_button, back_button, main_window):
        self.pages = []  # Lista delle pagine del wizard
        self.current_page_index = 0
        self.current_page = None
        self.next_button = next_button
        self.back_button = back_button
        self.main_window = main_window

    def add_page(self, page):
        self.pages.append(page)

    def start(self):
        """Avvia il wizard e mostra la prima pagina."""
        if not self.pages:
            return

        self.current_page_index = 0
        self.current_page = self.pages[0]
        self._show_current_page()
        self.update_buttons_state()

    def _show_current_page(self):
        """Mostra la pagina corrente nella finestra principale."""
        # if self.main_window.right_panel is not None:
        #     self.main_window.right_panel.hide()

        self.main_window.set_right_widget(self.current_page)
        self.current_page.on_enter(self)

    def go_to_next_page(self):
        """Vai alla pagina successiva."""
        if self.current_page.is_ready_to_advance() and self.current_page_index < len(self.pages) - 1:
            self.current_page_index += 1
            self.current_page = self.pages[self.current_page_index]
            self._show_current_page()
            self.update_buttons_state()

    def go_to_previous_page(self):
        """Vai alla pagina precedente."""
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self.current_page = self.pages[self.current_page_index]
            self._show_current_page()
            self.update_buttons_state()

    def update_buttons_state(self):
        """Controlla se la pagina corrente è pronta per avanzare e aggiorna il pulsante Next."""
        is_first_page = self.current_page_index == 0
        is_last_page = self.current_page_index == len(self.pages) - 1
        self.next_button.setEnabled(
            self.current_page.is_ready_to_advance() and not is_last_page
        )
        self.back_button.setEnabled(
            self.current_page.is_ready_to_go_back() and not is_first_page
        )