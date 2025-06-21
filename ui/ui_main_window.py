import os
import shutil
import json

import subprocess
import pydicom
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QTranslator, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QFileDialog,
    QListView, QTreeView, QVBoxLayout,
    QSplitter, QMenuBar, QHBoxLayout, QSizePolicy
)
from PyQt6.QtGui import QFileSystemModel, QAction, QActionGroup

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

        self._init_ui()

        saved_lang = self._load_saved_language()
        self.set_language(saved_lang)

    def _init_ui(self):
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

        # self.tree_model.directoryLoaded.connect(self._update_footer_visibility)

        self.main_layout.addWidget(self.splitter)
        self.splitter.splitterMoved.connect(self.adjust_tree_columns)

        self.footer = QtWidgets.QWidget()
        self.footer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self._update_footer_visibility()

        self.main_layout.addWidget(self.footer)

        self._setup_menus()

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
        self.clear_links_action = QAction("Clear link", self)
        self.clear_copies_action = QAction("Clear copies", self)
        self.clear_all_action = QAction("Clear all", self)
        self.workspace_menu.addAction(self.clear_links_action)
        self.workspace_menu.addAction(self.clear_copies_action)
        self.workspace_menu.addAction(self.clear_all_action)

        # Settings
        self.settings_menu = self.menu_bar.addMenu("Settings")

        self.help_menu = self.menu_bar.addMenu("Help")

        # Language menu
        self.language_menu = self.settings_menu.addMenu("Language")
        self.language_action_group = QActionGroup(self)
        self.language_action_group.setExclusive(True)

        self._add_language_option("English", "en")
        self._add_language_option("Italiano", "it")

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
        self.clear_links_action.setText(_("MainWindow", "Clear link"))
        self.clear_copies_action.setText(_("MainWindow", "Clear copies"))
        self.clear_all_action.setText(_("MainWindow", "Clear all"))
        self.language_actions["en"].setText(_("MainWindow", "English"))
        self.language_actions["it"].setText(_("MainWindow", "Italiano"))

    def adjust_tree_columns(self):
        width = self.tree_view.width()
        for i in range(1, self.tree_model.columnCount()):
            if width > 350:
                self.tree_view.showColumn(i)
                self.tree_view.setColumnWidth(i, 100)
            else:
                self.tree_view.hideColumn(i)

    def _update_footer_visibility(self):
        has_content = any(
            os.path.isdir(os.path.join(self.workspace_path, name)) or
            os.path.islink(os.path.join(self.workspace_path, name))
            for name in os.listdir(self.workspace_path)
            if not name.startswith(".")
        )

        if has_content:
            self.footer.show()
        else:
            self.footer.hide()

    def open_folder_dialog(self):
        dialog = QFileDialog(self, "Select Folder")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.Option.ReadOnly, True)
        dialog.setDirectory(os.path.expanduser("~"))

        for view in dialog.findChildren((QListView, QTreeView)):
            view.setSelectionMode(view.SelectionMode.MultiSelection)

        if dialog.exec():
            folders = [os.path.abspath(path) for path in dialog.selectedFiles() if os.path.isdir(path)]
            unique_folders = [f for f in folders if not any(f != other and other.startswith(f + os.sep) for other in folders)]
            for folder in unique_folders:
                self._handle_folder_import(folder)

    def _handle_folder_import(self, path):
        if not os.path.isdir(path):
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Import Resource")
        msg.setText(f"You're about to import the resource:\n\"{path}\"\n\nHow do you want to import it?")
        link_button = msg.addButton("Link", QMessageBox.ButtonRole.AcceptRole)
        copy_button = msg.addButton("Copy", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

        msg.exec()
        folder_name = os.path.basename(os.path.normpath(path))
        target_path = os.path.join(self.workspace_path, folder_name)

        if msg.clickedButton() == link_button:
            if os.path.exists(target_path):
                os.unlink(target_path) if os.path.islink(target_path) else shutil.rmtree(target_path)
            try:
                os.symlink(path, target_path)
                self._update_footer_visibility()
            except Exception as e:
                QMessageBox.critical(self, "Link Error", f"Failed to create symlink: {e}")

        elif msg.clickedButton() == copy_button:
            # if os.path.exists(target_path):
            #     shutil.rmtree(target_path)
            # shutil.copytree(path, target_path)
            self._handle_import(path)
            self._update_footer_visibility()

    def _is_nifti_file(self, file_path):
        return file_path.endswith(".nii") or file_path.endswith(".nii.gz")

    def _is_dicom_file(self, file_path):
        try:
            dcm = pydicom.dcmread(file_path, stop_before_pixels=True)
            return True
        except Exception:
            return False

    def _convert_dicom_folder_to_nifti(self, dicom_folder, output_folder):
        try:
            command = [
                "dcm2niix",
                "-f", "%f_%p_%t_%s",  # Naming format (filename_patient_series_time_slice)
                "-p", "y",  # Preserve original acquisition order
                "-z", "y",  # Compress output as .nii.gz
                "-o", output_folder,  # Destination folder
                dicom_folder  # Source DICOM folder
            ]
            subprocess.run(command, check=True)
            print(f"Converted DICOM in {dicom_folder} to NIfTI using dcm2niix (optimized)")
        except subprocess.CalledProcessError as e:
            print(f"Conversion error: {e}")
        except Exception as e:
            print(f"Failed to convert DICOM: {e}")

    def _handle_import(self, folder_path):
        if not os.path.isdir(folder_path):
            return

        nifti_files = []
        dicom_files = []

        for root, _, files in os.walk(folder_path):
            dest_dir = os.path.join(self.workspace_path, os.path.basename(os.path.normpath(folder_path)))
            os.makedirs(dest_dir, exist_ok=True)

            for file in files:
                file_path = os.path.join(root, file)

                if self._is_nifti_file(file):
                    nifti_files.append(file_path)

                elif self._is_dicom_file(file_path):
                    dicom_files.append(file_path)

                else:
                    shutil.copy2(file_path, dest_dir)
                    print(f"Imported other file: {file}")

            # Importa tutti i NIfTI senza problemi
            for nifti in nifti_files:
                shutil.copy2(nifti, dest_dir)
                print(f"Imported NIfTI file: {os.path.basename(nifti)}")

        # 🚀 Converte solo una volta se ha trovato DICOM
        if dicom_files:
            self._convert_dicom_folder_to_nifti(folder_path, dest_dir)

        print("Import completed.")

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())