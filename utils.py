import os
import shutil
import subprocess
import platform
import sys
from PyQt6.QtCore import QStandardPaths
from pathlib import Path

def get_bin_path(name):
    exe_name = f"{name}.exe" if platform.system() == "Windows" else name

    # Caso 1: se estrae PyInstaller (usa sys._MEIPASS)
    if hasattr(sys, "_MEIPASS"):
        candidate = os.path.join(sys._MEIPASS, name, exe_name)
        if os.path.exists(candidate):
            return candidate

    # Caso 2: se distribuito accanto al tuo .py o .exe
    candidate = os.path.join(os.path.dirname(__file__), name, exe_name)
    if os.path.exists(candidate):
        return candidate

    # Caso 3: se installato nel PATH (es. pacchetto pip o sistema)
    path = shutil.which(exe_name)
    if path:
        return path

    raise FileNotFoundError(f"Impossibile trovare {exe_name}")

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

def setup_fsl_env():
    """
    Carica le variabili di ambiente di FSL (FSLDIR, FSLOUTPUTTYPE, ecc.)
    Restituisce una tupla (fsldir, fsloutputtype)
    """
    result = subprocess.run(
        ["/bin/zsh", "-l", "-c", "source $FSLDIR/etc/fslconf/fsl.sh && echo $FSLDIR && echo $FSLOUTPUTTYPE"],
        capture_output=True,
        text=True,
        check=True
    )

    lines = result.stdout.strip().splitlines()
    if len(lines) < 2:
        raise RuntimeError("Impossibile leggere FSLDIR e FSLOUTPUTTYPE")

    fsldir, fsloutputtype = lines[0], lines[1]
    return fsldir, fsloutputtype