import os
import json
import shutil

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QTranslator, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow,
    QTreeView, QVBoxLayout,
    QSplitter, QMenuBar, QHBoxLayout, QSizePolicy, QMessageBox
)
from PyQt6.QtGui import QFileSystemModel, QAction, QActionGroup

from ui.tool_selection_frame import ToolChoicePage
from ui.ui_button import UiButton
from ui.ui_fsl_frame import SkullStrippingPage
from ui.ui_import_frame import ImportFrame
from ui.ui_nifti_selection import NiftiSelectionPage
from ui.ui_nifti_viewer import NiftiViewer
from ui.ui_patient_selection_frame import PatientSelectionPage
from ui.ui_work_in_progress import WorkInProgressPage
from wizard_controller import WizardController

LANG_CONFIG_PATH = os.path.join(os.getcwd(), "config_lang.json")
TRANSLATIONS_DIR = os.path.join(os.getcwd(), "translations")

class MainWindow(QMainWindow):

    language_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.translator = QTranslator()
        self.language_actions = {}
        self.workspace_path = os.path.join(os.getcwd(), ".workspace")
        os.makedirs(self.workspace_path, exist_ok=True)

        # Setup
        self._setup_ui()
        self._setup_menus()
        self._setup_controller()

        saved_lang = self._load_saved_language()
        self.set_language(saved_lang)

    def _setup_ui(self):
        self.setObjectName("MainWindow")
        self.resize(840, 441)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        self.main_layout = QVBoxLayout(central_widget)

        # Splitter with TreeView and ImportFrame
        self.splitter = QSplitter(QtCore.Qt.Orientation.Horizontal)

        # TreeView
        self.tree_view = QTreeView()
        self.tree_model = QFileSystemModel()
        self.tree_model.setRootPath(self.workspace_path)
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setRootIndex(self.tree_model.index(self.workspace_path))
        self.tree_view.setMinimumSize(QtCore.QSize(200, 0))
        self.splitter.addWidget(self.tree_view)

        # Tree view già esistente nella tua UI
        self.tree_view.clicked.connect(self.handle_workspace_click)
        self.tree_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)

        self.main_layout.addWidget(self.splitter)
        self.splitter.setSizes([200, 600])
        self.splitter.splitterMoved.connect(self.adjust_tree_columns)

        self.footer = QtWidgets.QWidget()
        self.footer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        # self._update_footer_visibility()

        self.back_button = UiButton(text="Back", context=self)
        self.back_button.clicked.connect(lambda: self.controller.go_to_previous_page())
        self.footer_layout.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.next_button = UiButton(text="Next", context=self)
        self.next_button.clicked.connect(lambda: self.controller.go_to_next_page())
        self.footer_layout.addWidget(self.next_button, 0, Qt.AlignmentFlag.AlignRight)

        self.main_layout.addWidget(self.footer)

    def handle_workspace_click(self, index):
        selected_indexes = self.tree_view.selectionModel().selectedIndexes()

        selected_files = []
        for idx in selected_indexes:
            if idx.column() == 0:  # Solo la colonna principale (file name), evita ripetizioni
                path = self.tree_model.filePath(idx)
                if path.endswith(".nii") or path.endswith(".nii.gz"):
                    selected_files.append(path)

        # Passa i file alla pagina corrente, se implementa set_selected_files()
        if selected_files and hasattr(self.controller.current_page, "set_selected_files"):
            self.controller.current_page.set_selected_files(selected_files)

    def _setup_menus(self):
        self.menu_bar = QMenuBar()
        self.setMenuBar(self.menu_bar)

        # File
        self.file_menu = self.menu_bar.addMenu("File")
        self.import_action = QAction("Import", self)
        self.export_action = QAction("Export", self)
        self.file_menu.addAction(self.import_action)
        self.file_menu.addAction(self.export_action)

        # Workspace
        self.workspace_menu = self.menu_bar.addMenu("Workspace")
        self.clear_all_action = QAction("Clear workspace", self)
        self.workspace_menu.addAction(self.clear_all_action)
        self.clear_all_action.triggered.connect(self.clear_workspace)

        # Settings
        self.settings_menu = self.menu_bar.addMenu("Settings")

        self.help_menu = self.menu_bar.addMenu("Help")

        # Language menu
        self.language_menu = self.settings_menu.addMenu("Language")
        self.language_action_group = QActionGroup(self)
        self.language_action_group.setExclusive(True)

        self._add_language_option("English", "en")
        self._add_language_option("Italiano", "it")

    def _setup_controller(self):
        self.controller = WizardController(self.next_button, self.back_button, self)

        import_page = ImportFrame(self)
        self.controller.add_page(import_page)

        patient_selection_page = PatientSelectionPage(self)
        self.controller.add_page(patient_selection_page)

        tool_page = ToolChoicePage(self)
        self.controller.add_page(tool_page)

        fsl_page = SkullStrippingPage(self)
        self.controller.add_page(fsl_page)

        nifti_selection = NiftiSelectionPage(self)
        self.controller.add_page(nifti_selection)

        nifti_viewer = NiftiViewer()
        self.controller.add_page(nifti_viewer)

        work2 = WorkInProgressPage()
        self.controller.add_page(work2)

        work3 = WorkInProgressPage()
        self.controller.add_page(work3)

        self.controller.start()

    def _add_language_option(self, name, code):
        action = QAction(name, self, checkable=True)
        self.language_action_group.addAction(action)
        self.language_menu.addAction(action)
        action.triggered.connect(lambda: self.set_language(code))
        self.language_actions[code] = action

    def _load_saved_language(self):
        if os.path.exists(LANG_CONFIG_PATH):
            with open(LANG_CONFIG_PATH, "r") as f:
                return json.load(f).get("lang", "en")
        return "en"

    def save_language(self, lang_code):
        with open(LANG_CONFIG_PATH, "w") as f:
            json.dump({"lang": lang_code}, f)

    def set_language(self, lang_code):
        self.save_language(lang_code)

        if self.translator.load(f"{TRANSLATIONS_DIR}/{lang_code}.qm"):
            QApplication.instance().installTranslator(self.translator)

        if lang_code in self.language_actions:
            self.language_actions[lang_code].setChecked(True)

        self._retranslate_ui()
        self.language_changed.emit(lang_code)

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

    def adjust_tree_columns(self):
        width = self.tree_view.width()
        for i in range(1, self.tree_model.columnCount()):
            if width > 400:
                self.tree_view.showColumn(i)
                self.tree_view.setColumnWidth(i, 100)
            else:
                self.tree_view.hideColumn(i)

    def clear_workspace(self):
        reply = QMessageBox.question(
            self,
            "Conferma eliminazione",
            "Sei sicuro di voler cancellare completamente il workspace?\n"
            "ATTENZIONE: Tutti i dati verranno rimossi e tornerai alla pagina di import.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            for item in os.listdir(self.workspace_path):
                item_path = os.path.join(self.workspace_path, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception as e:
                    QMessageBox.warning(self, "Errore", f"Errore durante la rimozione di {item}:\n{str(e)}")

            print("Workspace svuotato.")
            self.controller.current_page_index = 0
            self.controller.current_page = self.controller.pages[0]
            self.controller._show_current_page()
            self.controller.update_buttons_state()

    def set_right_widget(self, new_widget):
        if self.splitter.count() > 1:
            old_widget = self.splitter.widget(1)
            self.splitter.replaceWidget(1, new_widget)
            self.splitter.setSizes([200, 600])
            self.adjust_tree_columns()
            # old_widget.deleteLater()
        else:
            self.splitter.addWidget(new_widget)
            self.splitter.setSizes([200, 600])
            self.adjust_tree_columns()
        self.right_panel = new_widget  # utile per riferimenti futuri

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())