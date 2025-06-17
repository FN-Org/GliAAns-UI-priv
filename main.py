import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTreeView, QFileDialog, QListView, QMessageBox
)
from importa_paziente_ui import UiMainWindow
import shutil
from PyQt6.QtGui import QStandardItem, QFileSystemModel
from PyQt6.QtWidgets import QFileIconProvider
from PyQt6.QtCore import QTranslator, QLocale, QFileInfo

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = UiMainWindow()
        self.ui.setupUi(self)

        # self.tree = self.ui.treeView

        self.splitter = self.ui.splitter

        self.splitter.splitterMoved.connect(self.update_tree_columns) # type: ignore
        self.update_tree_columns()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
 
 