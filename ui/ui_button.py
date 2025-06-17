from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QPushButton

class Ui_Button(QPushButton):
    def __init__(self, parent=None, text=None, context=None):
        super(Ui_Button, self).__init__(parent)

        self._retranslate_ui()
        if context and hasattr(context, "language_changed"):
            context.language_changed.connect(self._retranslate_ui)

    def _retranslate_ui(self):
        _ = QCoreApplication.translate
        self.setText(_("MainWindow", "Next"))