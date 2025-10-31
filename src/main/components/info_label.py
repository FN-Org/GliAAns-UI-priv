from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QToolTip, QLabel


class InfoLabel(QLabel):
    """A custom QLabel styled as an info icon that shows a tooltip on hover."""

    def __init__(self, text="", tooltip_text=""):
        """
        Initialize the InfoLabel widget.

        Args:
            text (str): The text to display inside the circular label (e.g., "i").
            tooltip_text (str): The text to display when hovering over the label.
        """
        super().__init__()

        # Store the tooltip text for later use (shown on hover)
        self.tooltip_text = tooltip_text

        # Store and display the main text (e.g., "i")
        self.text = text

        # Define a fixed circular size for the label
        self.setFixedSize(25, 25)

        # Apply a modern blue circular style with white text
        self.setStyleSheet("""
            QLabel {
                border: 1px solid #3498db;        /* Blue border */
                border-radius: 12px;              /* Rounded for circular shape */
                background-color: #3498db;        /* Blue background */
                color: white;                     /* White text */
                font-weight: bold;                /* Bold for emphasis */
                font-size: 12px;                  /* Compact, readable size */
            }
        """)

        # Set the text (e.g., "i" or "?") and center it in the label
        self.setText(self.text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Set the tooltip text for accessibility and hover feedback
        self.setToolTip(tooltip_text)

    def enterEvent(self, event):
        """
        Override the enter event to show a tooltip when the mouse hovers over the label.

        Args:
            event (QEnterEvent): The Qt event triggered when the mouse enters the widget area.
        """
        # Display the tooltip near the current mouse position
        QToolTip.showText(event.globalPosition().toPoint(), self.tooltip_text, self)

        # Call the base implementation to preserve default behavior
        super().enterEvent(event)
