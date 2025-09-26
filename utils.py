import os
import subprocess
import platform
import sys
from PyQt6.QtCore import QStandardPaths
from pathlib import Path

def get_app_dir():
    # cartella dove salvare i dati dell'app (scrivibile dall'utente)
    base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)) / "GliAAns-UI"
    base.mkdir(parents=True, exist_ok=True)
    return base

def resource_path(relative_path):
    """Restituisce il path assoluto sia in dev che in exe PyInstaller"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_shell_path():
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            # usa la login shell di default (zsh su macOS moderni)
            result = subprocess.run(
                ["/bin/zsh", "-l", "-c", "echo $PATH"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()

        elif system == "Linux":
            # usa la login shell (di solito bash, ma l’utente può cambiare)
            # leggiamo SHELL dall’ambiente, fallback a /bin/bash
            shell = os.environ.get("SHELL", "/bin/bash")
            result = subprocess.run(
                [shell, "-l", "-c", "echo $PATH"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()

        elif system == "Windows":
            # su Windows il PATH è già completo in os.environ
            # per sicurezza possiamo usare "where" per verificare
            return os.environ.get("PATH", "")

        else:
            # fallback generico
            return os.environ.get("PATH", "")

    except Exception as e:
        print(f"Errore nel recuperare PATH dalla shell: {e}")
        return os.environ.get("PATH", "")


import os
import shutil
from pathlib import Path


def setup_fsl_env(log=None):
    """Configura le variabili di ambiente FSL necessarie"""
    fsl_exe = shutil.which("fsl")
    if not fsl_exe:
        raise RuntimeError("FSL non trovato nel PATH")

    fsl_dir = Path(fsl_exe).resolve().parent.parent  # .../bin/fsl -> .../
    os.environ["FSLDIR"] = str(fsl_dir)
    os.environ["PATH"] = str(fsl_dir / "bin") + os.pathsep + os.environ.get("PATH", "")

    # formato output (FSL richiede che sia definito)
    if "FSLOUTPUTTYPE" not in os.environ:
        os.environ["FSLOUTPUTTYPE"] = "NIFTI_GZ"

    if log:
        log.info(f"FSLDIR set to {os.environ['FSLDIR']}")
        log.info(f"FSLOUTPUTTYPE = {os.environ['FSLOUTPUTTYPE']}")