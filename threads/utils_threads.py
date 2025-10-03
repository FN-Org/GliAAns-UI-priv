import os
import shutil

from PyQt6.QtCore import QThread, pyqtSignal, QCoreApplication


class CopyDeleteThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, src, dst = None, is_folder=False, copy = False, delete = False):
        super().__init__()
        self.src = src
        self.dst = dst
        self.is_folder = is_folder
        self.copy = copy
        self.delete = delete

    def run(self):
        try:
            if self.copy:
                if self.src is None or self.dst is None:
                    raise ValueError(QCoreApplication.translate("Threads", "Missing src or dst"))
                if self.is_folder:
                    shutil.copytree(self.src, self.dst)
                else: shutil.copy(self.src, self.dst)

                self.finished.emit(QCoreApplication.translate("Threads", "Successfully copied {0} to {1}").format(self.src, self.dst))
            if self.delete:
                if self.src is None:
                    raise ValueError(QCoreApplication.translate("Threads", "Missing src"))
                if self.is_folder:
                    shutil.rmtree(self.src)
                else: os.remove(self.src)
                self.finished.emit(QCoreApplication.translate("Threads", "Successfully deleted {0}").format(self.src))
        except Exception as e:
            self.error.emit(QCoreApplication.translate("Threads", "Error src:{0}, dst:{1},{2}").format(self.src,self.dst,e))