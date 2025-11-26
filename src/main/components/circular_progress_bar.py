from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QFont
from PyQt6.QtWidgets import QWidget


class CircularProgress(QWidget):
    """
    A customizable **circular progress bar widget** for PyQt6 applications.

    This widget visually represents a percentage-based progress value (0–100)
    as a circular arc with a numeric label at its center. It is lightweight,
    anti-aliased, and supports dynamic color changes.

    ---
    **Features**
    - Smooth circular progress rendering with anti-aliasing
    - Adjustable color via `setColor()`
    - Automatically scales with parent widget size
    - Displays numeric percentage text in the center
    ---

    **Parameters**
    - `color (str | QColor)`: Initial color for the progress arc.
      Accepts either a hex string (e.g., "#3498DB") or a `QColor` instance.

    **Example**
    ```python
    progress = CircularProgress("#00B894")
    progress.setValue(75)
    ```
    """

    def __init__(self, color: str = "#3498DB"):
        """
        Initialize the circular progress widget.

        Args:
            color (str): Hex color string for the progress arc (default: "#3498DB").
        """
        super().__init__()
        self.value = 0  # Current progress value (0–100)
        self.color = QColor(color)  # Active progress color

        self.setMaximumSize(300, 300)

    def setValue(self, val: int):
        """
        Update the progress value and refresh the widget.

        Args:
            val (int): New progress value (0–100). Values outside this range are clamped.

        Notes:
            This method triggers a repaint using `update()`.
        """
        self.value = max(0, min(100, int(val)))
        self.update()

    def setColor(self, color: str | QColor):
        """
        Change the color of the progress arc.

        Args:
            color (str | QColor): The new color for the progress indicator.
                                  Can be a hex string or a `QColor` instance.

        Example:
            ```python
            progress.setColor("#E74C3C")  # Set to red
            ```
        """
        if isinstance(color, str):
            self.color = QColor(color)
        else:
            self.color = color
        self.update()

    def sizeHint(self):
        """
        Suggest an appropriate default size for the widget.

        Returns:
            QSize: The preferred size of the widget, matching its parent if available.
        """
        return self.parentWidget().size() if self.parentWidget() else super().sizeHint()

    def paintEvent(self, event):
        """
        Handle the paint event to draw the circular progress indicator.

        The widget draws:
        1. A **light gray background circle**
        2. A **colored progress arc** proportional to the current value
        3. A **percentage label** centered within the circle

        Args:
            event (QPaintEvent): The paint event object automatically provided by Qt.
        """
        width = self.width()
        height = self.height()
        size = min(width, height)  # Ensure square aspect ratio

        # Center the circle in the available space
        x_offset = int((width - size) / 2)
        y_offset = int((height - size) / 2)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # --- Draw background circle ---
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f0f0f0"))  # Light gray background
        painter.drawEllipse(x_offset, y_offset, int(size), int(size))

        # --- Draw progress arc ---
        pen_width = max(5, int(size / 12))  # Adaptive thickness
        pen = QPen(self.color)
        pen.setWidth(pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Define drawing area for the arc
        rect = QRectF(
            x_offset + pen_width / 2,
            y_offset + pen_width / 2,
            size - pen_width,
            size - pen_width
        )
        angle_span = int(360 * self.value / 100)
        painter.drawArc(rect, -90 * 16, -angle_span * 16)  # Start from top center

        # --- Draw percentage text ---
        font_size = max(5, int(size / 9))
        painter.setPen(QColor("#2C3E50"))  # Dark blue-gray text
        painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self.value}%")
