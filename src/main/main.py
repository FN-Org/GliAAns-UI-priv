"""
Main entry point for the GliAAns-UI application.

This module initializes the PyQt6 application, sets up logging, and launches
the main `Controller`, which manages the GUI workflow.

It ensures that the environment and resources are correctly configured
before starting the event loop.
"""

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QGuiApplication
from PyQt6.QtWidgets import QApplication, QStyleFactory

from controller import Controller
from logger import setup_logger
from utils import resource_path, get_shell_path


if __name__ == "__main__":
    # Create the main Qt application instance
    app = QApplication(sys.argv)

    try:
        QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:
        # Fallback to a cross-platform style
        app.setStyle('Fusion')

    # Set the main window/application icon
    app.setWindowIcon(QIcon(resource_path(os.path.join("resources", "GliAAns-logo.ico"))))

    # Initialize and configure the logger
    # Logs to both console and compressed rotating file by default
    log = setup_logger(console=True)
    log.info("Program started")

    # Extend PATH environment variable to include shell utilities
    os.environ["PATH"] = get_shell_path()

    # Create and start the main application controller
    controller = Controller()
    controller.start()

    # Begin Qt event loop (blocking call)
    sys.exit(app.exec())
