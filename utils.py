import os
import sys
from PyQt6.QtCore import QStandardPaths
from pathlib import Path

def get_app_dir():
    # cartella dove salvare i dati dell'app (scrivibile dall'utente)
    base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    base.mkdir(parents=True, exist_ok=True)
    return base

def resource_path(relative_path):
    """Restituisce il path assoluto sia in dev che in exe PyInstaller"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)