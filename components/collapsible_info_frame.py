from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QLabel


class CollapsibleInfoFrame(QFrame):
    def __init__(self, context):
        super().__init__()
        self.setObjectName("info_frame")
        self.setStyleSheet("""
            QFrame#info_frame {
                background-color: #e3f2fd;
                border: 1px solid #2196f3;
                border-radius: 6px;
                margin: 6px 0;
            }
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 6, 8, 6)
        self.layout.setSpacing(4)

        # Toggle button
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
                background-color: #bbdefb;
                border-radius: 4px;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle_content)
        self.layout.addWidget(self.toggle_button)

        # Content frame (initially visible)
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(8, 4, 8, 4)
        self.content_layout.setSpacing(4)

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
        self.is_collapsed = False

        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def toggle_content(self):
        self.is_collapsed = not self.is_collapsed
        self.content_frame.setVisible(not self.is_collapsed)

    def _translate_ui(self):
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