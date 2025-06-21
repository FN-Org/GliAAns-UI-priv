from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QPushButton

class UiButton(QPushButton):
    def __init__(self, parent=None, text=None, context=None):
        super(UiButton, self).__init__(parent)

        self.text = text
        self._retranslate_ui()
        if context and hasattr(context, "language_changed"):
            context.language_changed.connect(self._retranslate_ui)

    def _retranslate_ui(self):
        _ = QCoreApplication.translate
        self.setText(_("MainWindow", self.text))