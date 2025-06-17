import os
import shutil

from PyQt6.QtGui import QStandardItem, QFileSystemModel

from ui_import_frame import ImportFrame

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QTranslator, QFileInfo
from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog, QFileIconProvider

import json

LANG_CONFIG_PATH = "config_lang.json"

class UiMainWindow(object):
    def __init__(self):
        self.languageActionGroup = None
        self.actionItalian = None
        self.actionEnglish = None
        self.menuLanguage = None
        self.actionImport = None
        self.actionClear_all = None
        self.actionClear_copies = None
        self.actionClear_links = None
        self.actionExport = None
        self.menuWorkspace = None
        self.menuHelp = None
        self.menuSettings = None
        self.menuFile = None
        self.menubar = None
        self.pushButton = None
        self.labelDropText = None
        self.horizontalLayout_2 = None
        self.importFrame = None
        self.treeView = None
        self.splitter = None
        self.verticalLayout_3 = None
        self.centralwidget = None

        workspace_path = os.path.join(os.getcwd(), ".workspace")
        os.makedirs(workspace_path, exist_ok=True)

        self.model = QFileSystemModel()
        self.model.setRootPath(workspace_path)

        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(840, 441)
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout_3.setObjectName("verticalLayout_3")

        # --- Splitter and its children ---
        self.splitter = QtWidgets.QSplitter(parent=self.centralwidget)
        self.splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setObjectName("splitter")

        self.splitter.splitterMoved.connect(self.update_tree_columns)  # type: ignore
        self.update_tree_columns()

        self.treeView = QtWidgets.QTreeView(parent=self.splitter)
        self.treeView.setMinimumSize(QtCore.QSize(200, 0))
        self.treeView.setObjectName("treeView")
        self.treeView.setModel(self.model)
        self.treeView.setRootIndex(self.model.index(workspace_path))
        self.treeView.setHeaderHidden(False)

        self.importFrame = ImportFrame(parent=self.splitter)
        self.importFrame.setEnabled(True)
        self.importFrame.setStyleSheet("border: 2px dashed gray;")
        self.importFrame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.importFrame.setObjectName("dropFrame")

        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.importFrame)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.labelDropText = QtWidgets.QLabel(parent=self.importFrame)
        font = QtGui.QFont()
        font.setPointSize(14)
        self.labelDropText.setFont(font)
        self.labelDropText.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.labelDropText.setObjectName("labelDropText")
        self.horizontalLayout_2.addWidget(self.labelDropText)

        # Re-size the splitter with its children
        self.splitter.setSizes([200, 600])

        self.verticalLayout_3.addWidget(self.splitter)

        # --- Push button at the bottom ---
        self.pushButton = QtWidgets.QPushButton(parent=self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.pushButton.setSizePolicy(sizePolicy)
        self.pushButton.setLayoutDirection(QtCore.Qt.LayoutDirection.LeftToRight)
        self.pushButton.setObjectName("pushButton")
        self.verticalLayout_3.addWidget(self.pushButton, 0, QtCore.Qt.AlignmentFlag.AlignRight)

        MainWindow.setCentralWidget(self.centralwidget)

        ##
        ### --- Language ---
        ##

        # --- Menu setup ---
        self.menubar = QtWidgets.QMenuBar(parent=MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 840, 24))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(parent=self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menuSettings = QtWidgets.QMenu(parent=self.menubar)
        self.menuSettings.setObjectName("menuSettings")
        self.menuHelp = QtWidgets.QMenu(parent=self.menubar)
        self.menuHelp.setObjectName("menuHelp")
        self.menuWorkspace = QtWidgets.QMenu(parent=self.menubar)
        self.menuWorkspace.setObjectName("menuWorkspace")
        self.menuLanguage = QtWidgets.QMenu(parent=self.menubar)
        self.menuLanguage.setObjectName("menuLanguage")
        MainWindow.setMenuBar(self.menubar)

        self.actionExport = QtGui.QAction(parent=MainWindow)
        self.actionExport.setObjectName("actionExport")
        self.actionClear_links = QtGui.QAction(parent=MainWindow)
        self.actionClear_links.setObjectName("actionClear_links")
        self.actionClear_copies = QtGui.QAction(parent=MainWindow)
        self.actionClear_copies.setObjectName("actionClear_copies")
        self.actionClear_all = QtGui.QAction(parent=MainWindow)
        self.actionClear_all.setObjectName("actionClear_all")
        self.actionImport = QtGui.QAction(parent=MainWindow)
        self.actionImport.setObjectName("actionImport")
        self.actionEnglish = QtGui.QAction(parent=MainWindow)
        self.actionEnglish.setObjectName("actionEnglish")
        self.actionItalian = QtGui.QAction(parent=MainWindow)
        self.actionItalian.setObjectName("actionItalian")

        self.actionEnglish.triggered.connect(lambda: self.set_language("en"))
        self.actionItalian.triggered.connect(lambda: self.set_language("it"))

        self.languageActionGroup = QtGui.QActionGroup(MainWindow)
        self.languageActionGroup.setExclusive(True)

        self.actionEnglish.setCheckable(True)
        self.actionItalian.setCheckable(True)

        self.languageActionGroup.addAction(self.actionEnglish)
        self.languageActionGroup.addAction(self.actionItalian)

        # English as a default language
        self.actionEnglish.setChecked(True)

        self.menuFile.addAction(self.actionImport)
        self.menuFile.addAction(self.actionExport)
        self.menuWorkspace.addAction(self.actionClear_links)
        self.menuWorkspace.addAction(self.actionClear_copies)
        self.menuWorkspace.addAction(self.actionClear_all)
        self.menuLanguage.addAction(self.actionEnglish)
        self.menuLanguage.addAction(self.actionItalian)

        self.menuSettings.addMenu(self.menuLanguage)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuWorkspace.menuAction())
        self.menubar.addAction(self.menuSettings.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def get_saved_language(self):
        if not os.path.exists(LANG_CONFIG_PATH):
            return "en"
        with open(LANG_CONFIG_PATH, "r") as f:
            return json.load(f).get("lang", "en")

    def save_language(self, lang_code):
        with open(LANG_CONFIG_PATH, "w") as f:
            json.dump({"lang": lang_code}, f)

    def load_language(self, lang_code):
        self.translator = QTranslator()
        qm_file = f"translations/{lang_code}.qm"
        if self.translator.load(qm_file):
            QApplication.instance().installTranslator(self.translator)
            self.retranslateUi(self)

    def set_language(self, lang_code):
        self.save_language(lang_code)
        self.load_language(lang_code)

    def load_workspace_content(self):
        workspace_dir = os.path.join(os.getcwd(), ".workspace")
        os.makedirs(workspace_dir, exist_ok=True)
        self.treeView.setRootIndex(self.model.index(workspace_dir))

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Glioma Patient Data Importer"))
        self.labelDropText.setText(_translate("MainWindow", "Import or select patients' data"))
        self.pushButton.setText(_translate("MainWindow", "Next"))
        self.menuFile.setTitle(_translate("MainWindow", "File"))
        self.menuSettings.setTitle(_translate("MainWindow", "Settings"))
        self.menuHelp.setTitle(_translate("MainWindow", "Help"))
        self.menuWorkspace.setTitle(_translate("MainWindow", "Workspace"))
        self.actionExport.setText(_translate("MainWindow", "Export"))
        self.actionClear_links.setText(_translate("MainWindow", "Clear link"))
        self.actionClear_copies.setText(_translate("MainWindow", "Clear copies"))
        self.actionClear_all.setText(_translate("MainWindow", "Clear all"))
        self.actionImport.setText(_translate("MainWindow", "Import"))
        self.menuLanguage.setTitle(_translate("MainWindow", "Language"))
        self.actionEnglish.setText(_translate("MainWindow", "English"))
        self.actionItalian.setText(_translate("MainWindow", "Italiano"))


    ##
    ### Backend
    ##

    def populate_subitems(self, parent_item, path):
        try:
            for item_name in os.listdir(path):
                full_path = os.path.join(path, item_name)
                item = self._create_item_from_path(full_path)
                parent_item.appendRow([item])

                if os.path.isdir(full_path):
                    self.populate_subitems(item, full_path)

        except Exception as e:
            print(f"Errore nel leggere '{path}': {e}")

    def update_tree_columns(self):
        tree_width = self.treeView.width()
        threshold = 350  # larghezza a cui iniziare a mostrare le altre colonne

        for col in range(1, self.model.columnCount()):
            if tree_width > threshold:
                if self.treeView.isColumnHidden(col):
                    self.treeView.showColumn(col)
                    self.treeView.setColumnWidth(col, 100)  # o altro valore utile
            else:
                if not self.treeView.isColumnHidden(col):
                    self.treeView.setColumnWidth(col, 0)
                    self.treeView.hideColumn(col)

    def handle_folder_drop(self, path):
        if not os.path.isdir(path):
            return

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Importa risorsa")
        msg_box.setText(f"Stai per importare la risorsa:\n\"{path}\"\n\nIn che modo vuoi importarla?")

        link_button = msg_box.addButton("Link", QMessageBox.ButtonRole.AcceptRole)
        copy_button = msg_box.addButton("Copy", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        if msg_box.clickedButton() == link_button:
            workspace_dir = os.path.join(os.getcwd(), ".workspace")
            os.makedirs(workspace_dir, exist_ok=True)

            # Estrai il nome della cartella/file dalla path originale
            # Assicurati di rimuovere eventuali slash finali per basename
            folder_or_file_name = os.path.basename(os.path.normpath(path))

            # Percorso dove verrà creato il link simbolico all'interno di '.workspace'
            link_path = os.path.join(workspace_dir, folder_or_file_name)

            # Rimuovi il link esistente se già presente per evitare errori
            if os.path.exists(link_path) or os.path.islink(link_path):
                if os.path.islink(link_path):
                    os.unlink(link_path)  # Rimuove il link simbolico
                elif os.path.isdir(link_path):
                    shutil.rmtree(link_path)  # Rimuove la directory se per qualche motivo era una copia
                else:
                    os.remove(link_path)  # Rimuove il file se per qualche motivo era una copia

            try:
                os.symlink(path, link_path)
                # self.load_workspace_content()
            except OSError as e:
                # Gestione degli errori, ad esempio se l'utente non ha i permessi
                # o se il sistema operativo non supporta i symlink in quel contesto
                print(f"Errore nella creazione del link simbolico: {e}")
                # Potresti mostrare un messaggio di errore all'utente qui
                QMessageBox.critical(self, "Errore Link", f"Impossibile creare il collegamento simbolico: {e}")

        elif msg_box.clickedButton() == copy_button:
            workspace_dir = os.path.join(os.getcwd(), ".workspace")
            os.makedirs(workspace_dir, exist_ok=True)

            folder_name = os.path.basename(path.rstrip("/\\"))
            dest_path = os.path.join(workspace_dir, folder_name)

            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)

            shutil.copytree(path, dest_path)
            # self.load_workspace_content()

    def open_file_dialog(self):
        dialog = QFileDialog(self)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ReadOnly, True)
        dialog.setDirectory(os.path.expanduser("~"))

        # Forza il dialogo a mostrare cartelle come selezionabili
        for view in dialog.findChildren((QListView, QTreeView)):  # type: ignore
            view.setSelectionMode(view.SelectionMode.MultiSelection)

        if dialog.exec():
            selected_paths = dialog.selectedFiles()
            folders = [os.path.abspath(path) for path in selected_paths if os.path.isdir(path)]

            # Mantieni solo le cartelle più profonde (interne)
            final_folders = []
            for folder in folders:
                is_nested = False
                for other in folders:
                    if other != folder and folder.startswith(other + os.sep):
                        is_nested = True
                        break
                if not is_nested:
                    final_folders.append(folder)

            # Rimuovi i genitori, tieni solo le più profonde
            # (inverti la logica precedente)
            deepest_folders = []
            for f in folders:
                if not any(f != other and other.startswith(f + os.sep) for other in folders):
                    deepest_folders.append(f)

            for folder_path in deepest_folders:
                self.handle_folder_drop(folder_path)

    @staticmethod
    def _create_item_from_path(path):
        icon_provider = QFileIconProvider()
        info = QFileInfo(path)
        icon = icon_provider.icon(info)
        item = QStandardItem(info.fileName())
        item.setIcon(icon)
        item.setToolTip(info.absoluteFilePath())
        return item

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = UiMainWindow()
    MainWindow.show()
    sys.exit(app.exec())