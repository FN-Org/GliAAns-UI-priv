import os
import re

from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtWidgets import QTreeView, QMessageBox, QMenu, QFileDialog
from PyQt6.QtGui import QFileSystemModel, QDesktopServices

from components.file_role_dialog import FileRoleDialog
from logger import get_logger
from threads.utils_threads import CopyDeleteThread

log = get_logger()


class WorkspaceTreeView(QTreeView):

    new_thread = pyqtSignal(object)

    def __init__(self, workspace_path, context, parent=None):
        super().__init__(parent)

        self.workspace_path = workspace_path
        self.context = context

        self.selected_files = []

        # File System Model
        self.tree_model = QFileSystemModel()
        self.tree_model.setRootPath(self.workspace_path)

        # Apply model to tree
        self.setModel(self.tree_model)
        self.setRootIndex(self.tree_model.index(self.workspace_path))
        self.setMinimumSize(QtCore.QSize(200, 0))

        # Selection and interaction
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        # Connections
        self.clicked.connect(self.handle_workspace_click)
        self.doubleClicked.connect(self.handle_double_click)
        self.customContextMenuRequested.connect(self.open_tree_context_menu)


    def handle_workspace_click(self):
        selected_indexes = self.selectionModel().selectedRows()

        selected_files = []
        for idx in selected_indexes:
            path = self.tree_model.filePath(idx)
            selected_files.append(path)
        self.selected_files = selected_files
        # Save into context
        self.context["selected_files_signal"].emit(selected_files)

    def handle_double_click(self, index):
        file_path = self.tree_model.filePath(index)

        # Verifica che sia un file NIfTI
        if os.path.isfile(file_path) and (file_path.endswith(".nii") or file_path.endswith(".nii.gz")):
            try:
               self.context["open_nifti_viewer"](file_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error when opening NIfTI file:\n{str(e)}")
                log.error(f"Error opening file NIfTI:\n{str(e)}")

    def adjust_tree_columns(self):
        width = self.width()
        for i in range(1, self.tree_model.columnCount()):
            if width > 400:
                self.showColumn(i)
                self.setColumnWidth(i, 100)
            else:
                self.hideColumn(i)

    def open_tree_context_menu(self, position):
        index = self.indexAt(position)
        file_path = None
        is_dir = False
        is_nifty = False

        if self.selected_files and len(self.selected_files) == 1 and not index.isValid():
            file_path = self.selected_files[0]
            is_dir = self.tree_model.isDir(index) if index.isValid() else False
            is_nifty = file_path.endswith((".nii", ".nii.gz"))
        else:
            if index.isValid():
                file_path = self.tree_model.filePath(index)
                is_dir = self.tree_model.isDir(index)


        menu = QMenu(self)

        # Action registry (maps QAction → handler)
        actions = {}

        if not index.isValid() and not self.selected_files:
            actions.update(self._add_workspace_actions(menu))
        elif index.isValid() and file_path and len(self.selected_files) <= 1 :
            if is_dir:
                actions.update(self._add_folder_actions(menu, file_path))
            else:
                actions.update(self._add_file_actions(menu, file_path, is_nifty))
        elif index.isValid() and len(self.selected_files) > 1:
            actions.update(self._add_multi_file_actions(menu))

        # Execute selected action
        chosen_action = menu.exec(self.viewport().mapToGlobal(position))
        if chosen_action and chosen_action in actions:
            actions[chosen_action](file_path, is_dir, is_nifty)

    # --- Context Menu Action Groups ---
    def _add_workspace_actions(self, menu):
        return {
            menu.addAction("Open Workspace in Explorer"): lambda *_: self._open_in_explorer(self.workspace_path),
            menu.addAction("Add single File to Workspace"): lambda *_: self.add_file_to_workspace(None, False),
        }

    def _add_folder_actions(self, menu, file_path):
        open_action = menu.addAction("Open Folder in Explorer")
        menu.addSeparator()
        add_action = menu.addAction("Add single File to Folder")
        remove_action = menu.addAction("Remove Folder from Workspace")
        export_action = menu.addAction("Export Folder")

        return {
            open_action: lambda *_: self._open_in_explorer(file_path),
            add_action: lambda *_: self.add_file_to_workspace(file_path, True),
            remove_action: lambda *_: self.remove_from_workspace([file_path]),
            export_action: lambda *_: self.export_files([file_path], True),
        }

    def _add_file_actions(self, menu, file_path, is_nifty):
        open_action = menu.addAction("Open with system predefined")
        actions = {open_action: lambda *_: self._open_in_explorer(file_path)}

        if is_nifty:
            nifti_action = menu.addAction("Open Nifti File")
            actions[nifti_action] = lambda *_: self._open_nifti(file_path)

        menu.addSeparator()
        add_action = menu.addAction("Add single File")
        remove_action = menu.addAction("Remove File from Workspace")
        export_action = menu.addAction("Export File")

        actions.update({
            add_action: lambda *_: self.add_file_to_workspace(file_path, False),
            remove_action: lambda *_: self.remove_from_workspace([file_path]),
            export_action: lambda *_: self.export_files([file_path], False),
        })
        return actions

    def _add_multi_file_actions(self, menu):
        export_action = menu.addAction("Export Files")
        remove_action = menu.addAction("Remove Files from Workspace")
        return {
            export_action: lambda *_: self.export_files(self.selected_files, False),
            remove_action: lambda *_: self.remove_from_workspace(self.selected_files),
        }

    def add_file_to_workspace(self, folder_path,is_dir):

        if hasattr(self,"context"):
            dialog = QFileDialog(self.context['main_window'], "Select File")
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            dialog.setOption(QFileDialog.Option.ReadOnly, True)
            dialog.setDirectory(os.path.expanduser("~"))

            if dialog.exec():
                file = dialog.selectedFiles()[0]
                json_file = None
                file_name = os.path.basename(file)
                dir_name = os.path.dirname(file)
                name, ext = os.path.splitext(file_name)
                if ext == ".gz":
                    name2, ext2 = os.path.splitext(name)
                    if ext2 == ".nii":
                        json_file = self._including_json(name2,dir_name)
                elif ext == ".nii":
                    json_file = self._including_json(name,dir_name)

                if folder_path:
                    if is_dir:
                        folder = os.path.basename(folder_path)
                    else:
                        folder = os.path.dirname(folder_path)
                else: folder = "workspace"

                if folder == "anat" or folder == "pet":
                    self.new_thread.emit(CopyDeleteThread(src=file,dst=folder_path, is_folder=is_dir, copy=True))

                elif re.match(r"^ses-\d+$", folder):
                    self.new_thread.emit(CopyDeleteThread(src=file, dst=os.path.join(folder_path, "pet"), is_folder=is_dir, copy=True))

                elif re.match(r"^sub-\d+$", folder):
                    return self.open_role_dialog(files=[file,json_file], folder_path=folder_path, subj=folder)
                elif folder == "derivatives":
                    return self.open_role_dialog(files=[file,json_file], folder_path=folder_path, main=folder)
                else: return self.open_role_dialog(files=[file,json_file], folder_path=self.workspace_path)

    def open_role_dialog(self,files,folder_path = None, subj = None,role = None, main = None):
        dialog = FileRoleDialog(workspace_path=self.workspace_path,subj=subj,role=role,main=main,parent=self)
        if dialog.exec():
            relative_path = dialog.get_relative_path()
            path = os.path.join(folder_path, relative_path)
            os.makedirs(path, exist_ok=True)
            for file in files:
                if file:
                    self.new_thread.emit(CopyDeleteThread(src=file, dst=path, is_folder=False, copy=True))

        else:
            return
        
    
    def _including_json(self,file_name, file_dir):
        answer = QMessageBox.information(
            self,
            "Adding Json?",
            "You want to include the JSON file if present?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel  # <-- aggiungo due pulsanti
        )
        if answer == QMessageBox.StandardButton.Ok:
            json_file_name = file_name + ".json"
            json_file_path = os.path.join(file_dir, json_file_name)
            if os.path.isfile(json_file_path):
                return json_file_path
        return ""

    def export_files(self, paths, is_dir):
        """Export selected files or folders to a destination folder or file."""
        if not paths:
            return

        def _get_file_filter(ext):
            """Return the QFileDialog filter based on file extension."""
            if ext == ".nii.gz":
                return "NIfTI compressed (*.nii.gz);;NIfTI (*.nii);;All files (*.*)"
            elif ext == ".nii":
                return "NIfTI (*.nii);;All files (*.*)"
            elif ext == ".json":
                return "JSON (*.json);;All files (*.*)"
            return "All files (*.*)"

        def _get_json_file(path):
            """Return associated JSON file if it exists."""
            base, ext = os.path.splitext(path)
            if ext == ".gz" and base.endswith(".nii"):
                base2 = base[:-4]  # remove .nii
                json_file = os.path.join(os.path.dirname(path), base2 + ".json")
                return json_file if os.path.exists(json_file) else None
            elif ext == ".nii":
                json_file = os.path.join(os.path.dirname(path), base + ".json")
                return json_file if os.path.exists(json_file) else None
            return None

        if len(paths) == 1:
            path = paths[0]
            if is_dir:
                # Choose destination folder for a single directory
                dst_path = QFileDialog.getExistingDirectory(self, "Select destination folder")
                if dst_path:
                    dst_path = os.path.join(dst_path, os.path.basename(path))
                    self.new_thread.emit(CopyDeleteThread(src=path, dst=dst_path, is_folder=True, copy=True))
            else:
                # Single file export
                file_filter = _get_file_filter(os.path.splitext(path)[1])
                dst_path, _ = QFileDialog.getSaveFileName(self, "Save file as...", os.path.basename(path), file_filter)
                if not dst_path:
                    return

                self.new_thread.emit(CopyDeleteThread(src=path, dst=dst_path, is_folder=False, copy=True))

                # Copy associated JSON if exists
                json_file = _get_json_file(path)
                if json_file:
                    dst_json = os.path.splitext(dst_path)[0] + ".json"
                    self.new_thread.emit(CopyDeleteThread(src=json_file, dst=dst_json, is_folder=False, copy=True))
        else:
            # Multiple files/folders
            dst_dir = QFileDialog.getExistingDirectory(self, "Select destination folder")
            if not dst_dir:
                return

            for path in paths:
                if not os.path.exists(path):
                    continue

                is_folder = os.path.isdir(path)
                dst_path = os.path.join(dst_dir, os.path.basename(path)) if is_folder else os.path.join(dst_dir,
                                                                                                        os.path.basename(
                                                                                                            path))
                self.new_thread.emit(CopyDeleteThread(src=path, dst=dst_path, is_folder=is_folder, copy=True))



    def remove_from_workspace(self, paths):
        for path in paths:
            if not os.path.exists(path):
                return
        if len(paths)<2:
            is_dir = os.path.isdir(paths[0])
            item_type = "this folder: " if is_dir else "this file:"
        else: item_type = "these files"

        item_name = os.path.basename(paths[0]) if len(paths) == 1 else ""
        message = f"Are you sure you want to remove {item_type} {item_name}?"

        reply = QMessageBox.question(
            self,
            "Confirm",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            for path in paths:
                is_dir = os.path.isdir(path)
                self.new_thread.emit(CopyDeleteThread(src=path, is_folder=is_dir,delete=True))

    def _open_in_explorer(self,path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _open_nifti(self, file_path):
        try:
            self.context["open_nifti_viewer"](file_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error opening file NIfTI:\n{str(e)}")
            log.error(f"Error opening file NIfTI:\n{str(e)}")
