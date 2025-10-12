from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QFont
from PyQt6.QtWidgets import QWidget


class CircularProgress(QWidget):
    def __init__(self, color="#3498DB"):
        super().__init__()
        self.value = 0
        self.color = QColor(color)
        self.existing_files = []

    def setValue(self, val: int):
        self.value = max(0, min(100, int(val)))
        self.update()

    def setColor(self, color: str | QColor):
        if isinstance(color, str):
            self.color = QColor(color)
        else:
            self.color = color
        self.update()

    def sizeHint(self):
        return self.parentWidget().size() if self.parentWidget() else super().sizeHint()

    def paintEvent(self, event):
        width = self.width()
        height = self.height()
        size = min(width, height)  # make it square

        # Center the circle
        x_offset = int((width - size) / 2)
        y_offset = int((height - size) / 2)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f0f0f0"))
        painter.drawEllipse(x_offset, y_offset, int(size), int(size))

        # Progress arc
        pen_width = max(5, int(size / 12))
        pen = QPen(self.color)
        pen.setWidth(pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(x_offset + pen_width / 2, y_offset + pen_width / 2,
                      size - pen_width, size - pen_width)
        angle_span = int(360 * self.value / 100)
        painter.drawArc(rect, -90 * 16, -angle_span * 16)

        # Text
        font_size = max(5, int(size / 9))
        painter.setPen(QColor("#2C3E50"))
        painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self.value}%")
