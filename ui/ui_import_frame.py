import os
from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QApplication


class ImportFrame(QFrame):

    def __init__(self, parent=None, context=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.main_window_logic = context

        self.setEnabled(True)
        self.setStyleSheet("border: 2px dashed gray;")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        frame_layout = QHBoxLayout(self)
        self.drop_label = QLabel("Import or select patients' data")
        self.drop_label.setFont(QFont("", 14))
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.drop_label)

        self._retranslate_ui()
        if context and hasattr(context, "language_changed"):
            context.language_changed.connect(self._retranslate_ui)

    def on_enter(self, controller):
        """Hook chiamato quando si entra nella pagina."""
        pass

    def is_ready_to_advance(self):
        """Restituisce True se si può avanzare alla prossima pagina."""
        has_content = any(
            os.path.isdir(os.path.join(self.main_window_logic.workspace_path, name)) or
            os.path.islink(os.path.join(self.main_window_logic.workspace_path, name))
            for name in os.listdir(self.main_window_logic.workspace_path)
            if not name.startswith(".")
        )

        if has_content:
            return True
        else:
            return False

    def is_ready_to_go_back(self):
        """Restituisce True se si può tornare indietro alla pagina precedente."""
        return False

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            for url in urls:
                file_path = url.toLocalFile()
                if os.path.exists(file_path) and os.path.isdir(file_path):
                    self.main_window_logic._handle_folder_import(file_path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.main_window_logic.open_folder_dialog()

    def _retranslate_ui(self):
        _ = QCoreApplication.translate
        self.drop_label.setText(_("MainWindow", "Import or select patients' data"))

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    frame = ImportFrame()
    frame.show()
    sys.exit(app.exec())