import json
import logging
import os
from typing import Any

from PyQt6.QtCore import pyqtSignal, QObject, QTranslator, QSettings
from PyQt6.QtWidgets import QApplication, QPushButton

from logger import set_log_level
from ui.workspace_tree_view import WorkspaceTreeView
from ui.import_page import ImportPage
from ui.main_window import MainWindow
from ui.nifti_viewer import NiftiViewer
from utils import resource_path, get_app_dir


class Controller(QObject):
    """
    Main application controller managing navigation, language, and shared state.

    This class orchestrates the application logic, connecting the UI components
    (pages, windows, viewers) and maintaining shared context across them.
    It also handles language translation, logging configuration, and navigation
    between pages.
    """

    # Signal emitted when language changes
    language_changed = pyqtSignal(str)
    """pyqtSignal(str): Emitted when the application's language changes, with the code as parameter."""

    # Signal emitted when a set of files is selected
    selected_files_signal = pyqtSignal(list)
    """pyqtSignal(list): Emitted when one or more files are selected, with the files as parameter (as a list)."""

    def __init__(self):
        """Initialize the controller and set up the application context."""
        super().__init__(None)
        self.back_button = None
        self.next_button = None

        # --- Application Settings ---
        self.translator = QTranslator()
        self.settings = QSettings("GliAAns")
        self.saved_lang = self.settings.value("language", "en", type=str)

        # Enable debug logging if user has this setting enabled
        log_debug = self.settings.value("debug_log", False, type=bool)
        if log_debug:
            set_log_level(logging.DEBUG)

        # --- Language setup ---
        self.set_language(self.saved_lang)
        self.language_changed.connect(self.set_language)

        # --- Workspace setup ---
        self.workspace_path = str(get_app_dir() / "workspace")
        if not os.path.exists(self.workspace_path):
            os.makedirs(self.workspace_path)

        # --- Shared application context ---
        # This context dictionary allows pages and components to access
        # common utilities and shared data.
        self.context: dict[str, Any] = {
            "workspace_path"      : str(self.workspace_path),
            "update_main_buttons" : self.update_buttons_state,
            "return_to_import"    : self.return_to_import,
            "history"             : [],
            "language_changed"    : self.language_changed,
            "create_buttons"      : self.create_buttons,
            "selected_files_signal": self.selected_files_signal,
            "open_nifti_viewer"   : self.open_nifti_viewer,
            "settings"            : self.settings
        }

        # --- UI Components ---
        # Instantiate all main UI elements and inject shared context
        self.context["import_page"] = ImportPage(self.context)
        self.context["tree_view"] = WorkspaceTreeView(self.context)
        self.context["main_window"] = MainWindow(self.context)
        self.context["nifti_viewer"] = NiftiViewer(self.context)

        # --- Page & Navigation Setup ---
        self.main_window = self.context["main_window"]
        self.tree_view = self.context["tree_view"]
        self.start_page = self.context["import_page"]

        self.context["history"].append(self.start_page)
        self.current_page = self.start_page

        # Apply saved language again to ensure proper UI translation
        self.set_language(self.saved_lang)

        # Display the initial page
        self._show_current_page()

    def _show_current_page(self):
        """
        Display the current page in the main window.
        Updates navigation buttons if they are already created.
        """
        self.main_window.set_widgets(self.tree_view, self.current_page)

        # Only update navigation buttons if they already exist
        if self.next_button and self.back_button:
            self.update_buttons_state()

    def go_to_next_page(self):
        """
        Move to the next logical page in the workflow.

        Returns:
            Page: The new current page after navigation.
        """
        next_page = self.current_page.next(self.context)
        if next_page:
            self.current_page = next_page
            self._show_current_page()
        return self.current_page

    def go_to_previous_page(self):
        """
        Navigate back to the previous page.

        Returns:
            Page: The new current page after going back.
        """
        previous_page = self.current_page.back()
        if previous_page:
            self.current_page = previous_page
            self._show_current_page()
        return self.current_page

    def return_to_import(self):
        """
        Reset the workflow and return to the import page.

        This clears all pages in the navigation history and resets their states.
        """
        if self.context["history"]:
            for page in self.context["history"]:
                page.reset_page()
            self.current_page = self.start_page
            self._show_current_page()
        return self.current_page

    def update_buttons_state(self):
        """
        Update the enabled/disabled state of navigation buttons
        based on the current page readiness.
        """
        self.next_button.setEnabled(bool(self.current_page.is_ready_to_advance()))
        self.back_button.setEnabled(bool(self.current_page.is_ready_to_go_back()))

    def create_buttons(self):
        """
        Create and return the navigation buttons (Next and Back).

        Returns:
            tuple[QPushButton, QPushButton]: The next and back buttons.
        """
        self.next_button = QPushButton("Next")
        self.back_button = QPushButton("Back")

        self.next_button.clicked.connect(self.go_to_next_page)
        self.back_button.clicked.connect(self.go_to_previous_page)

        return self.next_button, self.back_button

    def start(self):
        """Show the main application window and start the event loop."""
        self.main_window.show()

    def open_nifti_viewer(self, path: str):
        """
        Open a NIfTI file in the viewer window.

        Args:
            path (str): The file path to open.
        """
        self.context["nifti_viewer"].open_file(path)
        self.context["nifti_viewer"].show()

    def set_language(self, lang_code: str):
        """
        Load and apply a new language translation.

        Args:
            lang_code (str): The language code (e.g., 'en', 'it').
        """
        self.save_language(lang_code)
        translation_file = f"{resource_path('translations')}/{lang_code}.qm"
        if self.translator.load(translation_file):
            QApplication.instance().installTranslator(self.translator)

    def save_language(self, lang_code: str):
        """
        Persist the selected language in application settings.

        Args:
            lang_code (str): The language code to save.
        """
        self.settings.setValue("language", lang_code)
