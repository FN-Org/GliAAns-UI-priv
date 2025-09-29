import gc
import os


from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QFileDialog, QListView, QTreeView, QMessageBox, \
    QProgressDialog

from threads.import_thread import ImportThread
from ui.ui_patient_selection_frame import PatientSelectionPage
from wizard_state import WizardPage
from logger import get_logger

log = get_logger()

class ImportFrame(WizardPage):

    def __init__(self, context=None):
        super().__init__()

        self.context = context
        self.next_page = None
        self.workspace_path = context["workspace_path"]
        self.threads = []
        self.progress_dialogs = []

        self.setAcceptDrops(True)
        self.setEnabled(True)
        self.setStyleSheet("border: 2px dashed gray;")

        frame_layout = QHBoxLayout(self)
        self.drop_label = QLabel("Import or select patients' data")
        self.drop_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.drop_label.setFont(QFont("", 14))
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.drop_label)

        self._retranslate_ui()
        if context and hasattr(context, "language_changed"):
            context.language_changed.connect(self._retranslate_ui)

    def is_ready_to_advance(self):
        """Restituisce True se si può avanzare alla prossima pagina."""
        has_content = any(
            os.path.isdir(os.path.join(self.workspace_path, name)) or
            os.path.islink(os.path.join(self.workspace_path, name))
            for name in os.listdir(self.workspace_path)
            if not name.startswith(".")
        )

        if has_content:
            return True
        else:
            return False

    def is_ready_to_go_back(self):
        """Restituisce True se si può tornare indietro alla pagina precedente."""
        return False

    def next(self, context):
        if self.next_page:
            self.next_page.on_enter()
            return self.next_page
        else:
            self.next_page = PatientSelectionPage(context, self)
            self.context["history"].append(self.next_page)
            return self.next_page

    def back(self):
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
                    self._handle_import([file_path])

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_folder_dialog()

    def open_folder_dialog(self):
        dialog = QFileDialog(self.context["main_window"], "Select Folder")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.Option.ReadOnly, True)
        dialog.setDirectory(os.path.expanduser("~"))

        # Imposta ExtendedSelection su QListView e QTreeView del dialog
        for view in dialog.findChildren((QListView, QTreeView)):
            view.setSelectionMode(view.SelectionMode.ExtendedSelection)

        if dialog.exec():
            folders = [os.path.abspath(path) for path in dialog.selectedFiles() if os.path.isdir(path)]
            unique_folders = [
                f for f in folders
                if not any(f != other and other.startswith(f + os.sep) for other in folders)
            ]
            self._handle_import(unique_folders)

    def _handle_import(self, folders_path):

        self.progress_dialogs.append(QProgressDialog("Importing files...","Cancel",
                                               0, 100, self.context["main_window"]))
        self.progress_dialogs[-1].setWindowModality(Qt.WindowModality.NonModal)
        self.progress_dialogs[-1].setMinimumDuration(0)

        # Start importing thread
        self.threads.append(ImportThread(self.context, folders_path, self.workspace_path))
        self.threads[-1].finished.connect(self.on_import_finished)
        self.threads[-1].error.connect(self.on_import_error)
        self.threads[-1].progress.connect(self.progress_dialogs[-1].setValue)
        self.threads[-1].start()

        self.progress_dialogs[-1].canceled.connect(self.on_import_canceled)

    def on_import_error(self, error):
        """Handle file loading errors"""
        thread = self.sender()
        if thread not in self.threads:  # evita ValueError se già rimosso
            log.warning(f"Ignored error from already removed thread: {error}")
            return

        index = self.threads.index(thread)

        self.progress_dialogs[index].close()
        QMessageBox.critical(
            self.context["main_window"],
            "Error Importing Files",
            "Failed to import files" + f":\n{error}"
        )
        log.error(f"Error Importing Files: {error}")

    def on_import_finished(self):
        thread = self.sender()
        index = self.threads.index(thread)
        self.threads.remove(thread)

        self.progress_dialogs[index].close()
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()
        log.info("Import completed.")

    def on_import_canceled(self):
        dialog = self.sender()
        index = self.progress_dialogs.index(dialog)

        if len(self.threads)>index:
            thread = self.threads[index]
            thread.cancel()
            thread.terminate()
            thread.wait()
            self.threads.remove(thread)

    def closeEvent(self, event):
        """Clean up on application exit"""
        for dialog in self.progress_dialogs:
            dialog.destroy()
            self.progress_dialogs.remove(dialog)
        for thread in self.threads:
            thread.cancel()
            self.threads.remove(thread)

        gc.collect()

        event.accept()

    def _retranslate_ui(self):
        _ = QCoreApplication.translate
        self.drop_label.setText(_("MainWindow", "Import or select patients' data"))