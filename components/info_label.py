from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QToolTip, QLabel


class InfoLabel(QLabel):
    """Label con icona informativa che mostra tooltip al passaggio del mouse"""

    def __init__(self,text="", tooltip_text=""):
        super().__init__()
        self.tooltip_text = tooltip_text
        self.text = text
        self.setFixedSize(25, 25)
        self.setStyleSheet("""
            QLabel {
                border: 1px solid #3498db;
                border-radius: 12px;
                background-color: #3498db;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        self.setText(self.text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setToolTip(tooltip_text)

    def enterEvent(self, event):
        """Mostra il tooltip quando il mouse entra nell'area"""
        QToolTip.showText(event.globalPosition().toPoint(), self.tooltip_text, self)
        super().enterEvent(event)
