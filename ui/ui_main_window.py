import os
import json
import re
import shutil

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QTranslator, pyqtSignal, Qt, QUrl
from PyQt6.QtWidgets import (
    QApplication, QMainWindow,
    QTreeView, QVBoxLayout,
    QSplitter, QMenuBar, QHBoxLayout, QSizePolicy, QMessageBox, QMenu, QFileDialog, QDialog, QLabel, QRadioButton,
    QButtonGroup, QGroupBox, QFrame, QWidget, QDialogButtonBox
)
from PyQt6.QtGui import QFileSystemModel, QAction, QActionGroup, QDesktopServices

from ui.ui_button import UiButton
from ui.ui_nifti_viewer import NiftiViewer
from wizard_controller import WizardController

LANG_CONFIG_PATH = os.path.join(os.getcwd(), "config_lang.json")
TRANSLATIONS_DIR = os.path.join(os.getcwd(), "translations")




class FileRoleDialog(QDialog):
    def __init__(self, workspace_path=None, subj = None, role = None, main = None, parent=None):
        super().__init__(parent)

        self.subj = subj
        self.role = role
        self.main = main

        self.setWindowTitle("File role")
        self.workspace_path = workspace_path
        layout = QVBoxLayout(self)
        if main is None and subj is None:
            # --- Livello Main/Derivatives ---
            self.level1_widget = QWidget()
            level1_layout = QVBoxLayout(self.level1_widget)
            self.pos_label = QLabel("Position:")
            level1_layout.addWidget(self.pos_label)
            self.opt_main = QRadioButton("Main subject files")
            self.opt_derivatives = QRadioButton("derivatives")
            level1_layout.addWidget(self.opt_main)
            level1_layout.addWidget(self.opt_derivatives)


            self.button_first_group = QButtonGroup(self)
            self.button_first_group.addButton(self.opt_main)
            self.button_first_group.addButton(self.opt_derivatives)

            layout.addWidget(self.level1_widget)  # aggiungi il widget del livello 1

            self.button_first_group.buttonToggled.connect(self.first_level_toggled)

            self.derivative_extra_frame = QFrame()
            derivative_extra_layout = QVBoxLayout(self.derivative_extra_frame)
            self.derivative_extra_label = QLabel("What derivative:")
            derivative_extra_layout.addWidget(self.derivative_extra_label)

            self.derivative_extra_button_group = QButtonGroup(self)
            self.skull_strip_btn = QRadioButton("fsl_skullstrips")
            derivative_extra_layout.addWidget(self.skull_strip_btn)
            self.derivative_extra_button_group.addButton(self.skull_strip_btn)

            self.manual_mask_btn = QRadioButton("manual_masks")
            derivative_extra_layout.addWidget(self.manual_mask_btn)
            self.derivative_extra_button_group.addButton(self.manual_mask_btn)

            self.deep_learning_mask = QRadioButton("deep_learning_masks")
            derivative_extra_layout.addWidget(self.deep_learning_mask)
            self.derivative_extra_button_group.addButton(self.deep_learning_mask)

            self.derivative_extra_frame.hide()  # nascondi di default
            layout.addWidget(self.derivative_extra_frame)

        elif main == "derivatives":
            self.derivative_extra_frame = QFrame(self)
            derivative_extra_layout = QVBoxLayout(self.derivative_extra_frame)
            self.derivative_extra_label = QLabel("What derivative:")
            derivative_extra_layout.addWidget(self.derivative_extra_label)

            self.derivative_extra_button_group = QButtonGroup(self)
            self.skull_strip_btn = QRadioButton("fsl_skullstrips")
            derivative_extra_layout.addWidget(self.skull_strip_btn)
            self.derivative_extra_button_group.addButton(self.skull_strip_btn)

            self.manual_mask_btn = QRadioButton("manual_masks")
            derivative_extra_layout.addWidget(self.manual_mask_btn)
            self.derivative_extra_button_group.addButton(self.manual_mask_btn)

            self.deep_learning_mask = QRadioButton("deep_learning_masks")
            derivative_extra_layout.addWidget(self.deep_learning_mask)
            self.derivative_extra_button_group.addButton(self.deep_learning_mask)

            layout.addWidget(self.derivative_extra_frame)

            self.button_first_group = None
        else:
            self.button_first_group = None
            self.derivative_extra_button_group = None


        if subj is None:
            # --- Livello Subject ---
            self.level2_widget = QWidget()
            level2_layout = QVBoxLayout(self.level2_widget)
            self.sub_label = QLabel("Subject:")
            level2_layout.addWidget(self.sub_label)

            self.subj_buttons = []
            self.button_second_group = QButtonGroup(self)
            for subj_path in self._find_patient_dirs():
                subj = os.path.basename(subj_path)
                button = QRadioButton(subj)
                self.subj_buttons.append(button)
                level2_layout.addWidget(button)
                self.button_second_group.addButton(button)

            layout.addWidget(self.level2_widget)
        else: self.button_second_group = None

        if role is None:
            # --- Livello Anat/Sess ---
            self.level3_widget = QWidget()
            level3_layout = QVBoxLayout(self.level3_widget)
            self.role_label = QLabel("Role:")
            level3_layout.addWidget(self.role_label)
            self.button_third_group = QButtonGroup(self)
            self.anat_button = QRadioButton("anat")
            self.button_third_group.addButton(self.anat_button)
            level3_layout.addWidget(self.anat_button)
            self.ses_1_button = QRadioButton("ses-01")
            self.button_third_group.addButton(self.ses_1_button)
            level3_layout.addWidget(self.ses_1_button)
            self.ses_2_button = QRadioButton("ses-02")
            self.button_third_group.addButton(self.ses_2_button)
            level3_layout.addWidget(self.ses_2_button)
            layout.addWidget(self.level3_widget)
        else: self.button_third_group = None
        # --- Pulsanti OK/Annulla ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


    def get_selections(self):

        selections = {}


        # Livello 1: Main/Derivatives
        if self.button_first_group:
            btn = self.button_first_group.checkedButton()
            selections["main"] = btn.text() if btn else None

        if self.derivative_extra_button_group:
            btn = self.derivative_extra_button_group.checkedButton()
            selections["derivative"] = btn.text() if btn else None

        # Livello 2: Subject
        if self.button_second_group:
            btn = self.button_second_group.checkedButton()
            selections["subj"] = btn.text() if btn else None


        # Livello 3: Role
        if self.button_third_group:
            btn = self.button_third_group.checkedButton()
            selections["role"] = btn.text() if btn else None


        return selections

    def get_relative_path(self):
        parts = []
        selections = self.get_selections()

        # gestisci eventuali valori None
        main = selections.get("main")
        subj = selections.get("subj")
        role = selections.get("role")
        derivative = selections.get("derivative")

        if derivative:
            parts.append(derivative)

        if subj:
            parts.append(subj)

        if role:
            if re.match(r"^ses-\d+$", role):
                parts.append(role)
                parts.append("pet")
            else:
                parts.append(role)

        return os.path.join(*parts) if parts else None

    def _find_patient_dirs(self):
        patient_dirs = []

        for root, dirs, files in os.walk(self.workspace_path):
            # Salta la cartella 'derivatives'
            if "derivatives" in dirs:
                dirs.remove("derivatives")

            for dir_name in dirs:
                if dir_name.startswith("sub-"):
                    full_path = os.path.join(root, dir_name)
                    patient_dirs.append(full_path)

        return patient_dirs


    def first_level_toggled(self, button, checked):
        if not checked:
            return
        if button == self.opt_main:
            self.derivative_extra_frame.hide()
            self.adjustSize()
        if button == self.opt_derivatives:
            self.derivative_extra_frame.show()
            self.adjustSize()

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

    # --------------------------
    # UI SETUP
    # --------------------------
    def _setup_ui(self):
        self.setObjectName("MainWindow")
        self.resize(840, 441)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        self._setup_splitter()
        self._setup_footer()

    def _setup_splitter(self):
        # Splitter
        self.splitter = QSplitter(QtCore.Qt.Orientation.Horizontal)

        # TreeView
        self.tree_view = QTreeView()
        self.tree_model = QFileSystemModel()
        self.tree_model.setRootPath(self.workspace_path)
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setRootIndex(self.tree_model.index(self.workspace_path))
        self.tree_view.setMinimumSize(QtCore.QSize(200, 0))
        self.splitter.addWidget(self.tree_view)
        self.tree_view.clicked.connect(self.handle_workspace_click)
        self.tree_view.doubleClicked.connect(self.handle_double_click)
        self.tree_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree_view.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.open_tree_context_menu)

        self.main_layout.addWidget(self.splitter)
        self.splitter.setSizes([200, 600])
        self.splitter.splitterMoved.connect(self.adjust_tree_columns)

    def _setup_footer(self):
        self.footer = QtWidgets.QWidget()
        self.footer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(0, 0, 0, 0)

        self.back_button = UiButton(text="Back", context=self)
        self.back_button.clicked.connect(lambda: self.controller.go_to_previous_page())
        self.footer_layout.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.next_button = UiButton(text="Next", context=self)
        self.next_button.clicked.connect(lambda: self.controller.go_to_next_page())
        self.footer_layout.addWidget(self.next_button, 0, Qt.AlignmentFlag.AlignRight)

        self.main_layout.addWidget(self.footer)

    def _setup_menus(self):
        self.menu_bar = QMenuBar()
        self.setMenuBar(self.menu_bar)

        # File
        self.file_menu = self.menu_bar.addMenu("File")
        self.import_action = QAction("Import File", self)
        self.export_action = QAction("Export", self)
        self.file_menu.addAction(self.import_action)
        self.file_menu.addAction(self.export_action)
        self.import_action.triggered.connect(
            lambda: self.add_file_to_workspace(folder_path=self.workspace_path, is_dir=True)
        )

        # Workspace
        self.workspace_menu = self.menu_bar.addMenu("Workspace")
        self.clear_all_action = QAction("Clear workspace", self)
        self.workspace_menu.addAction(self.clear_all_action)
        self.clear_all_action.triggered.connect(self.clear_workspace)

        # Settings
        self.settings_menu = self.menu_bar.addMenu("Settings")
        self.language_menu = self.settings_menu.addMenu("Language")
        self.language_action_group = QActionGroup(self)
        self.language_action_group.setExclusive(True)

        self._add_language_option("English", "en")
        self._add_language_option("Italiano", "it")

        self.help_menu = self.menu_bar.addMenu("Help")

    # --------------------------
    # WIZARD CONTROLLER SETUP
    # --------------------------
    def _setup_controller(self):
        self.controller = WizardController(
            next_button=self.next_button,
            back_button=self.back_button,
            main_window=self
        )

        self.context = self.controller.context

    # --------------------------
    # WORKSPACE & TREEVIEW
    # --------------------------
    def handle_workspace_click(self):
        selected_indexes = self.tree_view.selectionModel().selectedRows()

        selected_files = []
        for idx in selected_indexes:
            path = self.tree_model.filePath(idx)
            selected_files.append(path)

        # Save into context
        self.controller.context["selected_files"] = selected_files

        # Notify the current page
        self.controller.current_page.update_selected_files(selected_files)

    def handle_double_click(self, index):
        file_path = self.tree_model.filePath(index)

        # Verifica che sia un file NIfTI
        if os.path.isfile(file_path) and (file_path.endswith(".nii") or file_path.endswith(".nii.gz")):
            try:
                if "nifti_viewer" in self.context and self.context["nifti_viewer"]:
                    self.context["nifti_viewer"].open_file(file_path)
                    self.context["nifti_viewer"].show()
                    pass
                else:
                    self.context["nifti_viewer"] = NiftiViewer(self.context)
                    self.context["nifti_viewer"].open_file(file_path)
                    self.context["nifti_viewer"].show()
                    pass
                # viewer.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)  # Libera memoria alla chiusura
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile aprire il file NIfTI:\n{str(e)}")

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
            if self.context and "return_to_import" in self.context:
                self.context["return_to_import"]()

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

    def open_tree_context_menu(self, position):
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            return

        file_path = self.tree_model.filePath(index)
        is_dir = self.tree_model.isDir(index)

        menu = QMenu()

        if is_dir:
            # Folder actions
            open_action = menu.addAction("Open folder in explorer")
            menu.addSeparator()
            add_action = menu.addAction("Add File to folder")
            remove_action = menu.addAction("Remove Folder from Workspace")
            info_action = menu.addAction("Folder Info")
        else:
            # File actions
            open_action = menu.addAction("Open with system predefined")
            menu.addSeparator()
            add_action = menu.addAction("Add File")
            remove_action = menu.addAction("Remove File from Workspace")
            menu.addSeparator()
            info_action = menu.addAction("File Info")

        action = menu.exec(self.tree_view.viewport().mapToGlobal(position))


        if action == open_action:
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        elif action == add_action:
            self.add_file_to_workspace(file_path,is_dir)
        elif action == remove_action:
            self.remove_from_workspace(file_path)
        elif action == info_action:
            self.show_file_info(file_path)

        # ---- Actions ----


    def add_file_to_workspace(self, folder_path,is_dir):
        if hasattr(self,"context"):
            dialog = QFileDialog(self.context['main_window'], "Select File")
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            dialog.setOption(QFileDialog.Option.ReadOnly, True)
            dialog.setDirectory(os.path.expanduser("~"))

            if dialog.exec():
                file = dialog.selectedFiles()[0]

                if is_dir:
                    folder = os.path.basename(folder_path)
                else:
                    folder = os.path.dirname(folder_path)
                if folder == "anat" or folder == "pet":
                    shutil.copy(file, folder_path)
                elif re.match(r"^ses-\d+$", folder):
                    shutil.copy(file, os.path.join(folder_path, "pet"))
                elif re.match(r"^sub-\d+$", folder):
                    self.open_role_dialog(file=file, folder_path=folder_path, subj=folder)
                elif folder == "derivatives":
                    self.open_role_dialog(file=file, folder_path=folder_path, main=folder)
                else: self.open_role_dialog(file=file, folder_path=self.workspace_path)


    def open_role_dialog(self, file = None,folder_path = None, subj = None,role = None, main = None):
        dialog = FileRoleDialog(workspace_path=self.workspace_path,subj=subj,role=role,main=main,parent=self)
        if dialog.exec():
            relative_path = dialog.get_relative_path()
            path = os.path.join(folder_path, relative_path)
            os.makedirs(path, exist_ok=True)
            shutil.copy(file, path)
        else:
            return

    def remove_from_workspace(self, path):
        if not os.path.exists(path):
            return

        is_dir = os.path.isdir(path)
        item_type = "folder" if is_dir else "file"

        reply = QMessageBox.question(
            self,
            "Confirm",
            f"Are you sure you want to remove this {item_type}: \"{os.path.basename(path)}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if is_dir:
                shutil.rmtree(path)
            else:
                os.remove(path)

    def show_file_info(self, path):
        print(f"File info for: {path}")


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())