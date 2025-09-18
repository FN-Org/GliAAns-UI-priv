import os

from PyQt6.QtCore import pyqtProperty, QPropertyAnimation
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QScrollArea, QLabel, QDialog, QListWidget


class FolderCard(QWidget):
    def __init__(self, folder):
        super().__init__()

        self.folder = folder
        self.files = []
        self.existing_files = set(os.listdir(folder)) if os.path.isdir(folder) else set()
        self.animation = None
        self._bg_color = QColor("#ecf0f1")
        self.expanded = False

        # --- Layout ---
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # main button
        self.button = QPushButton(os.path.basename(folder))
        self.button.setFixedHeight(60)
        self.button.setStyleSheet("background-color: #ecf0f1; color: #2C3E50; border-radius: 8px;")
        self.button.clicked.connect(self.show_files)
        self.layout.addWidget(self.button)

        # expandable area
        self.file_area = QScrollArea()
        self.file_area.setWidgetResizable(True)
        self.file_list = QWidget()
        self.file_list_layout = QVBoxLayout(self.file_list)
        self.file_area.setWidget(self.file_list)
        self.file_area.setVisible(False)
        self.layout.addWidget(self.file_area)

    # --- property for animating background color ---
    def get_bg_color(self):
        return self._bg_color

    def set_bg_color(self, color):
        self._bg_color = color
        self.button.setStyleSheet(
            f"background-color: {color.name()}; color: white; border-radius: 8px;"
        )

    bgColor = pyqtProperty(QColor, fget=get_bg_color, fset=set_bg_color)

    # --- logic ---
    def add_files(self, new_files):
        self.files.extend(new_files)
        self.start_blinking()

    def start_blinking(self):
        if self.animation:  # already blinking
            return
        self.animation = QPropertyAnimation(self, b"bgColor")
        self.animation.setDuration(800)
        self.animation.setLoopCount(-1)  # blink until clicked
        self.animation.setKeyValueAt(0, QColor("#2ECC71"))
        self.animation.setKeyValueAt(0.5, QColor("#27AE60"))
        self.animation.setKeyValueAt(1, QColor("#2ECC71"))
        self.animation.start()

    def reset_state(self):
        if self.animation:
            self.animation.stop()
            self.animation = None
        self._bg_color = QColor("#ecf0f1")
        self.button.setStyleSheet("background-color: #ecf0f1; color: #2C3E50; border-radius: 8px;")

    def show_files(self):
        if not self.files and not self.expanded:
            return

        if not self.expanded:
            # expand and list files
            for i in reversed(range(self.file_list_layout.count())):
                w = self.file_list_layout.itemAt(i).widget()
                if w:
                    w.deleteLater()
            for f in self.files:
                self.file_list_layout.addWidget(QLabel(f))
            self.file_area.setVisible(True)
            self.expanded = True
            self.files.clear()
            self.reset_state()
        else:
            # collapse
            self.file_area.setVisible(False)
            self.expanded = False

    def check_new_files(self):
        if not os.path.isdir(self.folder):
            return
        current_files = set(os.listdir(self.folder))
        new_files = current_files - self.existing_files
        if new_files:
            self.add_files(list(new_files))
        self.existing_files = current_files

# Dialog che mostra i file di una cartella
class FileDialog(QDialog):
    def __init__(self, folder, files, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Nuovi file in {folder}")
        layout = QVBoxLayout()
        list_widget = QListWidget()
        for f in files:
            list_widget.addItem(f)
        layout.addWidget(list_widget)
        self.setLayout(layout)
        self.resize(400, 300)