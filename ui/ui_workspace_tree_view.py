import os
import re

from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtWidgets import QTreeView, QMessageBox, QMenu, QFileDialog
from PyQt6.QtGui import QFileSystemModel, QDesktopServices, QAction

from components.file_role_dialog import FileRoleDialog
from logger import get_logger
from threads.utils_threads import CopyDeleteThread

log = get_logger()


class WorkspaceTreeView(QTreeView):
    """
    Custom QTreeView to manage files and folders within a workspace.

    This widget:
      - Displays the workspace directory structure using QFileSystemModel.
      - Handles context menus for file/folder operations (add, remove, export, open).
      - Supports multiple file selection and drag/drop-like functionality via threads.
      - Integrates with the main application context for shared signals and callbacks.
    """

    # Signal emitted when a background thread (Copy/Delete) is created
    new_thread = pyqtSignal(object)
    """**Signal(object):** Emitted when a new background thread (e.g., for copy or delete operations) is created.  
    Parameter:
    - `object`: Reference to the created thread instance.
    """

    def __init__(self, context):
        super().__init__()

        # Context dictionary (shared among pages/windows)
        self.context = context
        self.workspace_path = self.context["workspace_path"]

        self.selected_files = []

        # --- File System Model setup ---
        self.tree_model = QFileSystemModel()
        self.tree_model.setRootPath(self.workspace_path)

        # Apply model to the tree view
        self.setModel(self.tree_model)
        self.setRootIndex(self.tree_model.index(self.workspace_path))
        self.setMinimumSize(QtCore.QSize(200, 0))

        # Enable extended selection (multi-selection)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)

        # Enable custom context menu
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        # --- Signal connections ---
        self.clicked.connect(self.handle_workspace_click)
        self.doubleClicked.connect(self.handle_double_click)
        self.customContextMenuRequested.connect(self.open_tree_context_menu)

    # ---------------------------------------------------------------
    # Event Handlers
    # ---------------------------------------------------------------

    def handle_workspace_click(self):
        """Handle single-click event: update selected files and emit them via context signal."""
        selected_indexes = self.selectionModel().selectedRows()
        selected_files = [self.tree_model.filePath(idx) for idx in selected_indexes]

        self.selected_files = selected_files
        self.context["selected_files_signal"].emit(selected_files)

    def handle_double_click(self, index):
        """
        Handle double-click event:
        - If the selected item is a NIfTI file (.nii / .nii.gz), open it in the viewer.
        - Otherwise, open it with the system's default application.
        """
        file_path = self.tree_model.filePath(index)
        if not os.path.isfile(file_path):
            return

        if file_path.endswith((".nii", ".nii.gz")):
            try:
                self.context["open_nifti_viewer"](file_path)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    QtCore.QCoreApplication.translate("TreeView", "Error"),
                    QtCore.QCoreApplication.translate("TreeView", "Error when opening NIfTI file:\n{0}").format(str(e))
                )
                log.error(f"Error opening NIfTI file:\n{str(e)}")
        else:
            self._open_in_explorer(file_path)

    def adjust_tree_columns(self):
        """Automatically hide or show extra columns based on the widget width."""
        width = self.width()
        for i in range(1, self.tree_model.columnCount()):
            if width > 400:
                self.showColumn(i)
                self.setColumnWidth(i, 100)
            else:
                self.hideColumn(i)

    # ---------------------------------------------------------------
    # Context Menu
    # ---------------------------------------------------------------

    def open_tree_context_menu(self, position):
        """
        Open the right-click context menu dynamically, depending on the selected item:
        - Workspace root
        - Folder
        - File
        - Multiple files
        """
        index = self.indexAt(position)
        file_path = None
        is_dir = False
        is_nifty = False

        # Determine selected file/folder
        if self.selected_files and len(self.selected_files) == 1 and not index.isValid():
            file_path = self.selected_files[0]
            is_dir = self.tree_model.isDir(index) if index.isValid() else False
            is_nifty = file_path.endswith((".nii", ".nii.gz"))
        elif index.isValid():
            file_path = self.tree_model.filePath(index)
            is_dir = self.tree_model.isDir(index)

        menu = QMenu(self)
        actions = {}

        # Choose menu layout based on selection
        if not index.isValid() and not self.selected_files:
            actions.update(self._add_workspace_actions(menu))
        elif index.isValid() and file_path and len(self.selected_files) <= 1:
            if is_dir:
                actions.update(self._add_folder_actions(menu, file_path))
            else:
                actions.update(self._add_file_actions(menu, file_path, is_nifty))
        elif index.isValid() and len(self.selected_files) > 1:
            actions.update(self._add_multi_file_actions(menu))

        # Execute chosen action
        chosen_action = menu.exec(self.viewport().mapToGlobal(position))
        if chosen_action and chosen_action in actions:
            actions[chosen_action](file_path, is_dir, is_nifty)

    # --- Context Menu Definitions ---

    def _add_workspace_actions(self, menu):
        """Add actions available at the root workspace level."""
        open_in_explorer = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Open workspace in explorer"))
        menu.addSeparator()
        export_workspace = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Export workspace"))
        clear_workspace = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Clear workspace"))
        menu.addSeparator()
        add_single_file = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Add single file to workspace"))

        return {
            open_in_explorer: lambda *_: self._open_in_explorer(self.workspace_path),
            export_workspace: lambda *_: self.export_files([self.workspace_path], True),
            clear_workspace: lambda *_: self.context["main_window"].clear_folder(
                folder_path=self.workspace_path, folder_name="workspace", return_to_import=True
            ),
            add_single_file: lambda *_: self.add_file_to_workspace(None, False),
        }

    def _add_folder_actions(self, menu, file_path):
        """Add actions for a folder."""
        open_action = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Open folder in explorer"))
        menu.addSeparator()
        add_action = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Add single file to folder"))
        remove_action = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Remove folder from workspace"))
        export_action = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Export folder"))

        return {
            open_action: lambda *_: self._open_in_explorer(file_path),
            add_action: lambda *_: self.add_file_to_workspace(file_path, True),
            remove_action: lambda *_: self.remove_from_workspace([file_path]),
            export_action: lambda *_: self.export_files([file_path], True),
        }

    def _add_file_actions(self, menu, file_path, is_nifty):
        """Add actions for a single file."""
        open_action = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Open with system predefined"))
        actions = {open_action: lambda *_: self._open_in_explorer(file_path)}

        if is_nifty:
            nifti_action = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Open NIfTI file"))
            actions[nifti_action] = lambda *_: self._open_nifti(file_path)

        menu.addSeparator()
        add_action = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Add single file"))
        remove_action = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Remove file from workspace"))
        export_action = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Export file"))

        actions.update({
            add_action: lambda *_: self.add_file_to_workspace(file_path, False),
            remove_action: lambda *_: self.remove_from_workspace([file_path]),
            export_action: lambda *_: self.export_files([file_path], False),
        })
        return actions

    def _add_multi_file_actions(self, menu):
        """Add actions for multiple selected files."""
        export_action = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Export files"))
        remove_action = menu.addAction(QtCore.QCoreApplication.translate("TreeView", "Remove Files from workspace"))
        return {
            export_action: lambda *_: self.export_files(self.selected_files, False),
            remove_action: lambda *_: self.remove_from_workspace(self.selected_files),
        }

    # ---------------------------------------------------------------
    # Core Operations
    # ---------------------------------------------------------------

    def add_file_to_workspace(self, folder_path, is_dir):
        """
        Add a single file into the workspace.
        Opens a file dialog, optionally adds related JSON, and triggers background copy thread.
        """
        dialog = QFileDialog(self.context['main_window'], "Select File")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.Option.ReadOnly, True)
        dialog.setDirectory(os.path.expanduser("~"))

        if not dialog.exec():
            return

        file = dialog.selectedFiles()[0]
        file_name = os.path.basename(file)
        dir_name = os.path.dirname(file)
        name, ext = os.path.splitext(file_name)
        json_file = None

        # Handle potential .nii.gz format
        if ext == ".gz":
            name2, ext2 = os.path.splitext(name)
            if ext2 == ".nii":
                json_file = self._including_json(name2, dir_name)
        elif ext == ".nii":
            json_file = self._including_json(name, dir_name)

        # Determine destination folder
        if folder_path:
            if is_dir:
                folder = os.path.basename(folder_path)
            else:
                folder = os.path.dirname(folder_path)
        else:
            folder = "workspace"

        # Specialized behavior based on folder type
        if folder in ("anat", "pet"):
            self.new_thread.emit(CopyDeleteThread(src=file, dst=folder_path, is_folder=is_dir, copy=True))
        elif re.match(r"^ses-\d+$", folder):
            self.new_thread.emit(CopyDeleteThread(src=file, dst=os.path.join(folder_path, "pet"), is_folder=is_dir, copy=True))
        elif re.match(r"^sub-\d+$", folder):
            return self.open_role_dialog(files=[file, json_file], folder_path=folder_path, subj=folder)
        elif folder == "derivatives":
            return self.open_role_dialog(files=[file, json_file], folder_path=folder_path, main=folder)
        else:
            return self.open_role_dialog(files=[file, json_file], folder_path=self.workspace_path)

    def open_role_dialog(self, files, folder_path=None, subj=None, role=None, main=None):
        """Open a FileRoleDialog to determine where to place files in the workspace hierarchy."""
        dialog = FileRoleDialog(workspace_path=self.workspace_path, subj=subj, role=role, main=main, parent=self)
        if dialog.exec():
            relative_path = dialog.get_relative_path()
            path = os.path.join(folder_path, relative_path)
            os.makedirs(path, exist_ok=True)
            for file in files:
                if file:
                    self.new_thread.emit(CopyDeleteThread(src=file, dst=path, is_folder=False, copy=True))

    def _including_json(self, file_name, file_dir):
        """
        Ask the user whether to include an associated JSON file when adding a NIfTI file.
        Returns JSON path if available and confirmed, otherwise empty string.
        """
        answer = QMessageBox.information(
            self,
            QtCore.QCoreApplication.translate("TreeView", "Adding Json?"),
            QtCore.QCoreApplication.translate("TreeView", "Do you want to include the JSON file if present?"),
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if answer == QMessageBox.StandardButton.Ok:
            json_file_path = os.path.join(file_dir, file_name + ".json")
            if os.path.isfile(json_file_path):
                return json_file_path
        return ""

    # ---------------------------------------------------------------
    # Export / Remove / Open
    # ---------------------------------------------------------------


    def export_files(self, paths, is_dir):
        """Export selected files or folders to a chosen destination."""
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
        """Ask confirmation before deleting selected files/folders from workspace."""
        for path in paths:
            if not os.path.exists(path):
                return
        if len(paths)<2:
            is_dir = os.path.isdir(paths[0])
            item_type = QtCore.QCoreApplication.translate("TreeView", "this folder: ") if is_dir else QtCore.QCoreApplication.translate("TreeView", "this file:")
        else: item_type = QtCore.QCoreApplication.translate("TreeView", "these files")

        item_name = os.path.basename(paths[0]) if len(paths) == 1 else ""
        message = QtCore.QCoreApplication.translate("TreeView", "Are you sure you want to remove {0} {1}?").format(item_type, item_name)

        reply = QMessageBox.question(
            self,
            QtCore.QCoreApplication.translate("TreeView", "Confirm"),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            for path in paths:
                is_dir = os.path.isdir(path)
                self.new_thread.emit(CopyDeleteThread(src=path, is_folder=is_dir,delete=True))

    def _open_in_explorer(self, path):
        """Open a file or folder using the system's file explorer or default app."""
        try:
            url = QUrl.fromLocalFile(path)
            success = QDesktopServices.openUrl(url)

            if not success:
                # Extract file extension
                ext = os.path.splitext(path)[1] or QtCore.QCoreApplication.translate("TreeView", "(unknown)")
                QMessageBox.warning(
                    self,
                    QtCore.QCoreApplication.translate("TreeView", "No default application"),
                    QtCore.QCoreApplication.translate("TreeView", "No default application is registered for files with extension {0}.").format(ext)
                )
                log.debug(f"No default application is registered for files with extension {ext}.")
        except Exception as e:
            QMessageBox.critical(
                self,
                QtCore.QCoreApplication.translate("TreeView", "Error"),
                QtCore.QCoreApplication.translate("TreeView", "An unexpected error occurred while opening the file:\n{0}").format(e)
            )
            log.error(f"An unexpected error occurred while opening the file:\n{e}")

    def _open_nifti(self, file_path):
        """Open a NIfTI file in the integrated viewer."""
        try:
            self.context["open_nifti_viewer"](file_path)
        except Exception as e:
            QMessageBox.critical(
                self,
                QtCore.QCoreApplication.translate("TreeView", "Error"),
                QtCore.QCoreApplication.translate("TreeView", "Error opening file NIfTI:\n{0}").format(str(e)))
            log.error(f"Error opening file NIfTI:\n{str(e)}")
