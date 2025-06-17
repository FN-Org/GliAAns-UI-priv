import os

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QFrame

class ImportFrame(QFrame):
    folderDropped = pyqtSignal(str)  # path of the drag&dropped folder

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            for url in urls:
                file_path = os.path.dirname(url.toLocalFile())
                if os.path.exists(file_path):
                    self.parent().parent().parent().handle_folder_drop(file_path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent().parent().parent().open_file_dialog()