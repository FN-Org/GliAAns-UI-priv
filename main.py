import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFrame, QLabel, QVBoxLayout, QTreeView, QSplitter, QFileDialog, QListView, QMessageBox
)
 
from PyQt6.QtCore import Qt
from importa_paziente_ui import Ui_MainWindow  # Generato da pyuic6
 
from PyQt6.QtCore import pyqtSignal

import shutil

from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtGui import QIcon

from PyQt6.QtWidgets import QFileIconProvider
from PyQt6.QtCore import QFileInfo

class DropFrame(QFrame):
    folderDropped = pyqtSignal(str)  # path della cartella droppata

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            for url in urls:
                file_path = os.path.dirname(url.toLocalFile())
                if os.path.exists(file_path):
                    self.parent().parent().handle_folder_drop(file_path)  # chiama la funzione nel MainWindow
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent().parent().open_file_dialog()
 
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
 
        # Trova e sostituisce il QFrame con il DropFrame personalizzato
        old_frame = self.findChild(QFrame, "dropFrame")
        self.dropFrame = DropFrame(self)
        self.dropFrame.setObjectName("dropFrame")
        self.dropFrame.setStyleSheet("border: 2px dashed gray;")

        self.dropFrame.folderDropped.connect(self.handle_folder_drop)
 
        self.ui.horizontalLayout.replaceWidget(old_frame, self.dropFrame)
        old_frame.deleteLater()
 
        label = self.findChild(QLabel, "labelDropText")
        if label:
            label.setParent(self.dropFrame)
            if not self.dropFrame.layout():
                self.dropFrame.setLayout(QVBoxLayout())
            self.dropFrame.layout().addWidget(label)
 
        tree = self.findChild(QTreeView,'treeView')

        # TreeView basato su modello personalizzato
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Nome", "Tipo", "Percorso"])

        self.tree = self.findChild(QTreeView, "treeView")
        self.tree.setModel(self.tree_model)
        self.tree.setHeaderHidden(False)
        self.tree.setColumnWidth(0, 250)

        # Aggiungiamo il TreeView in uno splitter accanto al dropFrame
        splitter = QSplitter()
        splitter.addWidget(tree)
        splitter.addWidget(self.dropFrame)
        splitter.setSizes([200, 600])
        self.setCentralWidget(splitter)

        # Memorizza riferimenti
        self.tree = tree
        self.model = self.tree_model
        self.splitter = splitter

        # Connetti evento di ridimensionamento
        splitter.splitterMoved.connect(self.update_tree_columns)
        self.update_tree_columns()  # Chiamalo subito per lo stato iniziale

        # Popola la treeView con il contenuto del .workspace all'avvio
        self.load_workspace_content()

    def load_workspace_content(self):
        workspace_dir = os.path.join(os.getcwd(), ".workspace")
        # Assicurati che la directory esista, altrimenti non c'è nulla da caricare
        if not os.path.exists(workspace_dir):
            os.makedirs(workspace_dir, exist_ok=True)
            return # Se non esiste, l'abbiamo appena creata, quindi è vuota

        # Cancella tutti gli elementi esistenti nel modello prima di caricare
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Nome", "Tipo", "Percorso"]) # Ricrea le header

        try:
            for item_name in os.listdir(workspace_dir):
                full_path = os.path.join(workspace_dir, item_name)

                # Determina il tipo di importazione ("Link" o "Copy")
                # Basandoci sulla natura dell'elemento nel .workspace
                if os.path.islink(full_path):
                    import_type = "Link"
                    # Se è un link simbolico, vogliamo che 'Percorso' mostri il target reale
                    # E che 'Nome' sia il nome del link, non del target
                    target_path = os.path.realpath(full_path)
                    # Crea un QFileInfo basato sul target per l'icona e il tooltip
                    item = self._create_item_from_path(full_path) # L'item principale è il link
                    path_to_display = target_path # Mostra il target nel percorso
                else:
                    import_type = "Copy"
                    item = self._create_item_from_path(full_path)
                    path_to_display = full_path # Mostra il percorso della copia

                type_item = QStandardItem(import_type)
                type_item.setEditable(False)

                path_item = QStandardItem(path_to_display)
                path_item.setEditable(False)

                self.tree_model.appendRow([item, type_item, path_item])

                # Popola i sotto-elementi se è una directory o un link a una directory
                if os.path.isdir(full_path): # os.path.isdir() funziona anche per symlink a directory
                    self.populate_subitems(item, full_path)

        except Exception as e:
            print(f"Errore durante il caricamento del workspace: {e}")

    def add_folder_to_tree(self, path, import_type):
        folder_item = self._create_item_from_path(path)

        type_item = QStandardItem(import_type)
        type_item.setEditable(False)

        path_item = QStandardItem(path)
        path_item.setEditable(False)

        self.tree_model.appendRow([folder_item, type_item, path_item])
        
        # Opzionale: carica anche contenuto interno (ricorsivo)
        self.populate_subitems(folder_item, path)

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
        tree_width = self.tree.width()
        threshold = 350  # larghezza a cui iniziare a mostrare le altre colonne

        for col in range(1, self.model.columnCount()):
            if tree_width > threshold:
                if self.tree.isColumnHidden(col):
                    self.tree.showColumn(col)
                    self.tree.setColumnWidth(col, 100)  # o altro valore utile
            else:
                if not self.tree.isColumnHidden(col):
                    self.tree.setColumnWidth(col, 0)
                    self.tree.hideColumn(col)

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
            
            # Percorso dove verrà creato il link simbolico all'interno di .workspace
            link_path = os.path.join(workspace_dir, folder_or_file_name)

            # Rimuovi il link esistente se già presente per evitare errori
            if os.path.exists(link_path) or os.path.islink(link_path):
                if os.path.islink(link_path):
                    os.unlink(link_path) # Rimuove il link simbolico
                elif os.path.isdir(link_path):
                    shutil.rmtree(link_path) # Rimuove la directory se per qualche motivo era una copia
                else:
                    os.remove(link_path) # Rimuove il file se per qualche motivo era una copia
            
            try:
                # Crea il collegamento simbolico
                # path è la sorgente (il file/cartella originale)
                # link_path è la destinazione (dove verrà creato il link in .workspace)
                os.symlink(path, link_path)
                self.add_folder_to_tree(link_path, "Link")
                # print(f"Creato link simbolico da '{path}' a '{link_path}'") # Per debug
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
            self.add_folder_to_tree(dest_path, "Copy")

    def open_file_dialog(self):
        dialog = QFileDialog(self)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ReadOnly, True)
        dialog.setDirectory(os.path.expanduser("~"))

        # Forza il dialogo a mostrare cartelle come selezionabili
        for view in dialog.findChildren((QListView, QTreeView)):
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

    def _create_item_from_path(self, path):
        icon_provider = QFileIconProvider()
        info = QFileInfo(path)
        icon = icon_provider.icon(info)
        item = QStandardItem(info.fileName())
        item.setIcon(icon)
        item.setToolTip(info.absoluteFilePath())
        return item
 
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
 
 