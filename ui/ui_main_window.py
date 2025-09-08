import os
import json


from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QTranslator, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow,QVBoxLayout,
    QSplitter, QMenuBar, QHBoxLayout, QSizePolicy, QMessageBox,
)
from PyQt6.QtGui import QAction, QActionGroup


from components.workspace_tree_view import WorkspaceTreeView
from threads.utils_threads import CopyDeleteThread
from logger import get_logger

LANG_CONFIG_PATH = os.path.join(os.getcwd(), "config_lang.json")
TRANSLATIONS_DIR = os.path.join(os.getcwd(), "translations")

log = get_logger()

class MainWindow(QMainWindow):


    def __init__(self,context):
        super().__init__()
        self.context = context
        self.context["language_changed"].connect(self._retranslate_ui)
        self.language_actions = {}
        self.workspace_path = self.context["workspace_path"]

        self.threads = []

        # Setup
        self._setup_ui()
        self._setup_menus()

        self._retranslate_ui()

    # --------------------------
    # UI SETUP
    # --------------------------
    def _setup_ui(self):
        self.setObjectName("MainWindow")
        self.resize(840, 440)
        self.setMinimumSize(840, 440)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        self._setup_splitter()
        self._setup_footer()

    def _setup_splitter(self):
        # Splitter
        self.splitter = QSplitter(QtCore.Qt.Orientation.Horizontal)

        # TreeView
        self.tree_view = WorkspaceTreeView(context=self.context,parent=self,workspace_path=self.workspace_path)
        self.splitter.addWidget(self.tree_view)
        self.tree_view.new_thread.connect(self.new_thread)

        self.main_layout.addWidget(self.splitter)
        self.splitter.setSizes([200, 600])
        self.splitter.splitterMoved.connect(self.tree_view.adjust_tree_columns)

    def _setup_footer(self):
        self.footer = QtWidgets.QWidget()
        self.footer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(0, 0, 0, 0)


        self.next_button, self.back_button = self.context["create_buttons"]()
        self.footer_layout.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.footer_layout.addWidget(self.next_button, 0, Qt.AlignmentFlag.AlignRight)

        self.main_layout.addWidget(self.footer)

    def _setup_menus(self):
        self.menu_bar = QMenuBar()
        self.setMenuBar(self.menu_bar)

        # File
        self.file_menu = self.menu_bar.addMenu("File")
        self.import_action = QAction("Import File", self)
        self.export_action = QAction("Export File/Folder", self)
        self.file_menu.addAction(self.import_action)
        self.file_menu.addAction(self.export_action)

        if "import_frame" in self.context and self.context["import_frame"]:
            self.import_action.triggered.connect(self.context["import_frame"].open_folder_dialog)
        else:
            raise RuntimeError("Error setupping menus")
        self.export_action.triggered.connect(self.export_file_info)

        # Workspace
        self.workspace_menu = self.menu_bar.addMenu("Workspace")
        self.clear_all_action = QAction("Clear workspace", self)
        self.export_workspace_action = QAction("Export workspace", self)
        self.workspace_menu.addSeparator()
        self.clear_outputs_action = QAction("Clear pipeline outputs", self)
        self.workspace_menu.addAction(self.clear_all_action)
        self.workspace_menu.addAction(self.export_workspace_action)
        self.workspace_menu.addAction(self.clear_outputs_action)
        self.clear_all_action.triggered.connect(lambda: self.clear_folder(folder_path=self.workspace_path,folder_name="workspace",return_to_import=True))
        self.export_workspace_action.triggered.connect(lambda:
                                             self.tree_view.export_files(self.workspace_path, is_dir=True))
        self.clear_outputs_action.triggered.connect(lambda: self.clear_folder(folder_path=os.path.join(self.workspace_path,"pipeline"),folder_name="outputs",return_to_import=False))

        # Settings
        self.settings_menu = self.menu_bar.addMenu("Settings")
        self.language_menu = self.settings_menu.addMenu("Language")
        self.language_action_group = QActionGroup(self)
        self.language_action_group.setExclusive(True)

        self._add_language_option("English", "en")
        self._add_language_option("Italiano", "it")

        self.help_menu = self.menu_bar.addMenu("Help")


    # --------------------------
    # WORKSPACE & TREEVIEW
    # --------------------------

    def _add_language_option(self, name, code):
        action = QAction(name, self, checkable=True)
        self.language_action_group.addAction(action)
        self.language_menu.addAction(action)
        action.triggered.connect(lambda: self.set_language(code))
        self.language_actions[code] = action
        if self.context["language"] == code:
            self.language_actions[code].setChecked(True)




    def set_language(self, lang_code):
        self.context["language_changed"].emit(lang_code)

        if lang_code in self.language_actions:
            self.language_actions[lang_code].setChecked(True)



    def _retranslate_ui(self):
        _ = QtCore.QCoreApplication.translate
        self.setWindowTitle(_("MainWindow", "Glioma Patient Data Importer"))
        self.file_menu.setTitle(_("MainWindow", "File"))
        self.workspace_menu.setTitle(_("MainWindow", "Workspace"))
        self.settings_menu.setTitle(_("MainWindow", "Settings"))
        self.help_menu.setTitle(_("MainWindow", "Help"))
        self.language_menu.setTitle(_("MainWindow", "Language"))

        self.import_action.setText(_("MainWindow", "Import"))
        self.export_action.setText(_("MainWindow", "Export"))
        self.clear_all_action.setText(_("MainWindow", "Clear workspace"))
        self.language_actions["en"].setText(_("MainWindow", "English"))
        self.language_actions["it"].setText(_("MainWindow", "Italiano"))



    def clear_folder(self,folder_path,folder_name,return_to_import):
        message = f"Sei sicuro di voler cancellare completamente {folder_name}?\n"
        if return_to_import:
            message += "ATTENZIONE: Tutti i dati verranno rimossi e tornerai alla pagina di import."
        reply = QMessageBox.question(
            self,
            "Conferma eliminazione",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                self.threads.append(CopyDeleteThread(src=item_path, is_folder=os.path.isdir(item_path), delete=True))
                self.threads[-1].error.connect(lambda msg,it=item: self.copydelete_thread_error(f"Error while clearing {it}:{msg}"))
                self.threads[-1].finished.connect(lambda msg,show=False: self.copydelete_thread_success(msg,show))
                self.threads[-1].start()
            log.info(f"{folder_name} emptied")
            if return_to_import:
                if self.context and "return_to_import" in self.context:
                    self.context["return_to_import"]()

    def set_right_widget(self, new_widget):
        if self.splitter.count() > 1:
            old_widget = self.splitter.widget(1)
            self.splitter.replaceWidget(1, new_widget)
            self.splitter.setSizes([200, 600])
            self.tree_view.adjust_tree_columns()
            # old_widget.deleteLater()
        else:
            self.splitter.addWidget(new_widget)
            self.splitter.setSizes([200, 600])
            self.tree_view.adjust_tree_columns()
        self.right_panel = new_widget  # utile per riferimenti futuri





    def copydelete_thread_error(self, msg):
        QMessageBox.warning(
            self,
            "Error",
            msg
        )
        log.error(msg)
        thread_to_remove = self.sender()
        if thread_to_remove in self.threads:
            self.threads.remove(thread_to_remove)
        log.error(f"Error while copying/deleting: {msg}")

    def copydelete_thread_success(self, msg,show = True):
        if show:
            QMessageBox.information(
                self,
                "Success!",
                msg
                )
        thread_to_remove = self.sender()
        log.debug("Success:"+msg)
        if thread_to_remove in self.threads:
            self.threads.remove(thread_to_remove)
        log.debug("Success while copy/deleting:"+msg)


    def closeEvent(self, event):
        if hasattr(self, "threads"):
            for thread in self.threads:
                thread.finished.disconnect()
                thread.error.disconnect()
                thread.wait()
                self.threads.remove(thread)
        event.accept()

    def export_file_info(self):
        QMessageBox.information(
            self,
            "Export file info",
            "To export a file/folder, right click on it in the left view"
        )

    def new_thread(self,thread):
        self.threads.append(thread)
        self.threads[-1].error.connect(
            lambda msg: self.copydelete_thread_error(f"Error :{msg}"))
        self.threads[-1].finished.connect(self.copydelete_thread_success)
        self.threads[-1].start()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())