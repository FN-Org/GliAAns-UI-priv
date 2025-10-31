from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QLabel


class CollapsibleInfoFrame(QFrame):
    """
    A collapsible information panel displaying contextual help or configuration instructions.

    This widget provides a styled information box with a toggle button that expands
    or collapses its content. It’s particularly useful for showing optional user
    guidance (e.g., color-coding legends, usage tips, or data selection rules).

    ---
    **Features**
    - Collapsible/expandable content area
    - Styled using Qt stylesheets for a clean look
    - Supports dynamic translation through Qt's `QCoreApplication.translate`
    - Automatically reacts to external language change signals (if provided in `context`)
    ---

    **Parameters**
    - `context (dict | None)`: Optional application context dictionary.
      If it includes a `"language_changed"` signal, the frame will update its text automatically when the language changes.

    **Example**
    ```python
    frame = CollapsibleInfoFrame(context)
    frame.show()
    ```
    """

    def __init__(self, context):
        """
        Initialize the collapsible information frame.

        Args:
            context (dict | None): Optional dictionary providing signal connections
                                   for language translation updates.
        """
        super().__init__()

        # --- Frame styling ---
        self.setObjectName("info_frame")
        self.setStyleSheet("""
            QFrame#info_frame {
                background-color: #e3f2fd;      /* Soft blue background */
                border: 1px solid #2196f3;      /* Blue border */
                border-radius: 6px;
                margin: 6px 0;
            }
        """)

        # --- Main layout configuration ---
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 6, 8, 6)
        self.layout.setSpacing(4)

        # --- Toggle button ---
        self.toggle_button = QPushButton("Configuration Instructions")
        self.toggle_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                color: #1976d2;
                background: none;
                border: none;
                text-align: left;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #bbdefb;       /* Hover highlight */
                border-radius: 4px;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle_content)
        self.layout.addWidget(self.toggle_button)

        # --- Content area ---
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(8, 4, 8, 4)
        self.content_layout.setSpacing(4)

        # --- Informational text ---
        self.info_text = QLabel("""
            <style>
                .info-list { margin: 0; padding-left: 1rem; }
                .info-list li { margin-bottom: 0.3rem; line-height: 1.3; }
            </style>
            <ul class="info-list" role="list">
              <li><strong>Yellow frames</strong> indicate patients with <strong>multiple files</strong>. 
                <br> Requires <strong>medical review</strong> and manual selection.</li>
              <li><strong>White frames</strong> show patients with auto-selected files.</li>
            </ul>
        """)
        self.info_text.setStyleSheet("""
            color: #000000;
            font-size: 12px;
            line-height: 1.4;
            padding: 2px 0;
        """)
        self.info_text.setWordWrap(True)

        self.content_layout.addWidget(self.info_text)
        self.layout.addWidget(self.content_frame)

        # --- Internal state ---
        self.is_collapsed = False  # Whether the content is hidden

        # --- Language translation support ---
        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    # -------------------------------------------------------------------------

    def toggle_content(self):
        """
        Toggle the visibility of the content section.

        This method inverts the current state of the frame (expanded ↔ collapsed).
        It is connected to the toggle button’s `clicked` signal.
        """
        self.is_collapsed = not self.is_collapsed
        self.content_frame.setVisible(not self.is_collapsed)

    # -------------------------------------------------------------------------

    def _translate_ui(self):
        """
        Update the text of the UI elements for the current language.

        This method is automatically called during initialization and whenever
        the `"language_changed"` signal is emitted from the application context.
        """
        self.toggle_button.setText(QCoreApplication.translate("Components", "Configuration Instructions"))
        self.info_text.setText(QCoreApplication.translate("Components", """
            <style>
                .info-list { margin: 0; padding-left: 1rem; }
                .info-list li { margin-bottom: 0.3rem; line-height: 1.3; }
            </style>
            <ul class="info-list" role="list">
              <li><strong>Yellow frames</strong> indicate patients with <strong>multiple files</strong>. 
                <br> Requires <strong>medical review</strong> and manual selection.</li>
              <li><strong>White frames</strong> show patients with auto-selected files.</li>
            </ul>
        """))
