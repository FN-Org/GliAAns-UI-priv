import os
import shutil

from PyQt6.QtCore import QThread, pyqtSignal, QCoreApplication


class CopyDeleteThread(QThread):
    """
    Background worker thread for performing **file or directory copy and delete operations**
    without blocking the PyQt GUI.

    This class provides an asynchronous way to execute potentially long file system tasks
    (copying large files, removing folders, etc.) in a background thread, while emitting
    progress and error signals that can be handled by the main thread safely.

    ---

    **Signals:**

    - `finished (str)`: Emitted when the operation completes successfully with a message.
    - `error (str)`: Emitted when an error occurs, providing an error message.

    ---

    **Parameters:**

    - `src` (*str*): Source file or folder path.
    - `dst` (*str | None*): Destination path (required for copy operations).
    - `is_folder` (*bool*): If `True`, the operation targets a folder instead of a file.
    - `copy` (*bool*): If `True`, performs a copy operation.
    - `delete` (*bool*): If `True`, performs a delete operation.
    """

    # Signal emitted when the operation finishes successfully.
    finished = pyqtSignal(str)
    """**Signal(str):** Emitted when the operation completes successfully.  
    The parameter is a status message describing the result or outcome.
    """

    # Signal emitted when an error occurs during execution.
    error = pyqtSignal(str)
    """**Signal(str):** Emitted when an error occurs during the operation.  
    The parameter contains a descriptive error message.
    """

    def __init__(self, src, dst=None, is_folder=False, copy=False, delete=False):
        """
        Initialize the worker thread with operation parameters.

        Args:
            src (str): Path to the source file or directory.
            dst (str | None): Destination path for copy operations.
            is_folder (bool): Whether the source represents a folder.
            copy (bool): Whether to perform a copy operation.
            delete (bool): Whether to perform a delete operation.
        """
        super().__init__()
        self.src = src
        self.dst = dst
        self.is_folder = is_folder
        self.copy = copy
        self.delete = delete

    def run(self):
        """
        Executes the file system operation.

        Depending on the configuration flags (`copy`, `delete`, `is_folder`),
        this method performs one or both operations:
        - **Copy**: Copies a file or directory from `src` to `dst`.
        - **Delete**: Removes a file or directory at `src`.

        Emits:
            - `finished (str)`: On successful completion.
            - `error (str)`: On any exception during execution.
        """
        try:
            # --- COPY OPERATION ---
            if self.copy:
                if self.src is None or self.dst is None:
                    raise ValueError(QCoreApplication.translate("Threads", "Missing src or dst"))

                if self.is_folder:
                    # Copy entire directory recursively
                    shutil.copytree(self.src, self.dst, dirs_exist_ok=True)
                else:
                    # Copy single file
                    shutil.copy(self.src, self.dst)

                self.finished.emit(
                    QCoreApplication.translate(
                        "Threads",
                        "Successfully copied {0} to {1}"
                    ).format(self.src, self.dst)
                )

            # --- DELETE OPERATION ---
            if self.delete:
                if self.src is None:
                    raise ValueError(QCoreApplication.translate("Threads", "Missing src"))

                if self.is_folder:
                    # Remove entire folder tree
                    shutil.rmtree(self.src)
                else:
                    # Remove single file
                    os.remove(self.src)

                self.finished.emit(
                    QCoreApplication.translate(
                        "Threads",
                        "Successfully deleted {0}"
                    ).format(self.src)
                )

        except Exception as e:
            # Emit a formatted error message including source, destination, and exception details
            self.error.emit(
                QCoreApplication.translate(
                    "Threads",
                    "Error src:{0}, dst:{1}, {2}"
                ).format(self.src, self.dst, e)
            )
