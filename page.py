from PyQt6.QtWidgets import QWidget


class Page(QWidget):
    def _setup_ui(self):
        pass

    def is_ready_to_advance(self):
        """Restituisce True se si può avanzare alla prossima pagina."""
        return True

    def is_ready_to_go_back(self):
        """Restituisce True se si può tornare indietro alla pagina precedente."""
        return True

    def reset_page(self):
        pass

    def on_enter(self):
        """Hook chiamato quando si lascia la pagina (es: clic su Next)."""
        pass

    def next(self, context):
        pass

    def back(self):
        pass

    def _translate_ui(self):
        pass