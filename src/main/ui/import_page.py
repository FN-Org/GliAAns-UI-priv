import gc
import os

from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QFileDialog, QListView, QTreeView, QMessageBox,
    QProgressDialog, QApplication
)

from threads.import_thread import ImportThread
from ui.patient_selection_page import PatientSelectionPage
from page import Page
from logger import get_logger

log = get_logger()


class ImportPage(Page):
    """
    GUI page that allows importing patient data directories.

    This class provides both drag-and-drop and dialog-based import options.
    It starts a background thread for each import operation and displays
    progress with cancellable dialogs.

    Attributes
    ----------
    context : dict
        Shared context across application pages (contains settings, paths, signals, etc.).
    next_page : Page | None
        Reference to the next page in the workflow.
    workspace_path : str
        Root path where imported data is stored.
    threads : list[ImportThread]
        Active import threads currently running.
    progress_dialogs : list[QProgressDialog]
        Dialogs tracking progress of ongoing imports.
    """

    def __init__(self, context=None):
        """
        Initialize the ImportPage with the given context.

        Parameters
        ----------
        context : dict, optional
            Application context including 'workspace_path', 'main_window', and signals.
        """
        super().__init__()

        self.context = context
        self.next_page = None
        self.workspace_path = context["workspace_path"]
        self.threads = []
        self.progress_dialogs = []

        # Enable drag & drop and apply a dashed border
        self.setAcceptDrops(True)
        self.setEnabled(True)
        self.setStyleSheet("border: 2px dashed gray;")

        # Central label
        frame_layout = QHBoxLayout(self)
        self.drop_label = QLabel("Import or select patients' data")
        self.drop_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        font = QApplication.font()
        font.setPointSize(14)
        self.drop_label.setFont(font)
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.drop_label)

        # Handle localization updates
        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    # ----------------------------
    # Navigation
    # ----------------------------

    def is_ready_to_advance(self):
        """
        Check if the page can advance to the next step.

        Returns
        -------
        bool
            True if the workspace contains at least one visible directory or link.
        """
        has_content = any(
            os.path.isdir(os.path.join(self.workspace_path, name)) or
            os.path.islink(os.path.join(self.workspace_path, name))
            for name in os.listdir(self.workspace_path)
            if not name.startswith(".")
        )
        return has_content

    def is_ready_to_go_back(self):
        """
        Check if the user can navigate back to the previous page.

        Returns
        -------
        bool
            Always returns False (first step in workflow).
        """
        return False

    def next(self, context):
        """
        Transition to the next page (PatientSelectionPage).

        Returns
        -------
        Page
            The newly created or existing PatientSelectionPage.
        """
        if self.next_page:
            self.next_page.on_enter()
            return self.next_page
        else:
            self.next_page = PatientSelectionPage(context, self)
            self.context["history"].append(self.next_page)
            return self.next_page

    def back(self):
        """This page has no previous step."""
        return False

    # ----------------------------
    # Drag & Drop Import
    # ----------------------------

    def dragEnterEvent(self, event):
        """Accept drag if the event contains file URLs."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle dropped folders."""
        urls = event.mimeData().urls()
        if urls:
                file_path = [url.toLocalFile() for url in urls]
                self._handle_import(file_path)

    # ----------------------------
    # Folder Selection Dialog
    # ----------------------------

    def mousePressEvent(self, event):
        """Open a folder dialog on left-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_folder_dialog()

    def open_folder_dialog(self):
        """Open dialog to select one or more folders for import."""
        dialog = QFileDialog(
            self.context["main_window"],
            QCoreApplication.translate("ImportPage", "Select Folder")
        )
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.Option.ReadOnly, True)
        dialog.setDirectory(os.path.expanduser("~"))

        # Allow multi-selection in both list and tree views
        for view in dialog.findChildren((QListView, QTreeView)):
            view.setSelectionMode(view.SelectionMode.ExtendedSelection)

        if dialog.exec():
            folders = [os.path.abspath(path) for path in dialog.selectedFiles() if os.path.isdir(path)]
            # Avoid nested duplicates (e.g., selecting parent + child folder)
            unique_folders = [
                f for f in folders
                if not any(f != other and other.startswith(f + os.sep) for other in folders)
            ]
            self._handle_import(unique_folders)

    # ----------------------------
    # Import Handling
    # ----------------------------

    def _handle_import(self, folders_path):
        self.progress_dialogs.append(QProgressDialog(QCoreApplication.translate("ImportFrame", "Importing files..."), QCoreApplication.translate("ImportFrame", "Cancel"),
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

    # ----------------------------
    # Thread Callbacks
    # ----------------------------

    def on_import_error(self, error):
        """Handle file import errors from background threads."""
        thread = self.sender()
        if thread not in self.threads:
            log.warning(f"Ignored error from already removed thread: {error}")
            return

        index = self.threads.index(thread)
        self.progress_dialogs[index].close()
        QMessageBox.critical(
            self.context["main_window"],
            QCoreApplication.translate("ImportPage", "Error Importing Files"),
            QCoreApplication.translate("ImportPage", "Failed to import files:\n{0}").format(error),
        )
        log.error(f"Error Importing Files: {error}")

    def on_import_finished(self):
        """Cleanup after an import finishes successfully."""
        thread = self.sender()
        if thread not in self.threads:
            log.warning("Ignored 'finished' signal from an already removed thread.")
            return

        index = self.threads.index(thread)
        self.threads.remove(thread)
        self.progress_dialogs[index].close()

        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()
        log.info("Import completed.")

    def on_import_canceled(self):
        """Handle user-canceled import operations."""
        dialog = self.sender()
        index = self.progress_dialogs.index(dialog)

        if len(self.threads) > index:
            thread = self.threads[index]
            thread.cancel()
            thread.terminate()
            thread.wait()
            self.threads.remove(thread)

    def closeEvent(self, event):
        """Clean up threads and dialogs on application exit."""
        for dialog in self.progress_dialogs:
            dialog.destroy()
            self.progress_dialogs.remove(dialog)
        for thread in self.threads:
            thread.cancel()
            self.threads.remove(thread)
        gc.collect()
        event.accept()

    # ----------------------------
    # Translation
    # ----------------------------

    def _translate_ui(self):
        """Apply translated text to UI elements."""
        self.drop_label.setText(QCoreApplication.translate("ImportPage", "Import or select patients' data"))
