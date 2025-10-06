import os
import shutil
import subprocess
import platform
import sys
from PyQt6.QtCore import QStandardPaths
from pathlib import Path


def get_bin_path(name):
    """
    Locate the executable path for a given binary name across different environments.

    This function attempts to find the full path of an executable following these steps:
    1. Check if running from a PyInstaller bundle (using `sys._MEIPASS`).
    2. Check if the binary exists in the same directory as the current script.
    3. Search the system PATH using `shutil.which()`.

    Args:
        name (str): The base name of the executable (without extension).

    Returns:
        str: The absolute path to the executable.

    Raises:
        FileNotFoundError: If the executable cannot be found.
    """
    exe_name = f"{name}.exe" if platform.system() == "Windows" else name

    # Case 1: Running from a PyInstaller bundle
    if hasattr(sys, "_MEIPASS"):
        candidate = os.path.join(sys._MEIPASS, name, exe_name)
        if os.path.exists(candidate):
            return candidate

    # Case 2: Located next to the script or executable
    candidate = os.path.join(os.path.dirname(__file__), name, exe_name)
    if os.path.exists(candidate):
        return candidate

    # Case 3: Found in the system PATH
    path = shutil.which(exe_name)
    if path:
        return path

    raise FileNotFoundError(f"Could not find executable: {exe_name}")


def get_app_dir():
    """
    Get the writable directory used to store user-specific application data.

    On all operating systems, this directory is located under the user's home folder
    (e.g., `~/GliAAns-UI` on Linux and macOS, or `C:\\Users\\<User>\\GliAAns-UI` on Windows).

    Returns:
        pathlib.Path: The absolute path to the application data directory.
    """
    base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)) / "GliAAns-UI"
    base.mkdir(parents=True, exist_ok=True)
    return base


def resource_path(relative_path):
    """
    Resolve the absolute path to a resource file.

    Works in both development environments and PyInstaller-built executables.

    Args:
        relative_path (str): The relative path to the resource file.

    Returns:
        str: The absolute path to the resource file.
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)


def get_shell_path():
    """
    Retrieve the system PATH from the user's login shell environment.

    This is necessary because on Unix-based systems (macOS, Linux), GUI applications
    do not always inherit the user's shell environment (especially when launched from
    the desktop or a shortcut).

    Behavior by platform:
    - **macOS:** Uses the default login shell (`zsh`) to read PATH.
    - **Linux:** Reads from the user's current shell (usually `bash`).
    - **Windows:** Returns the PATH from the current environment.

    Returns:
        str: The PATH environment variable as a string.
    """
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            result = subprocess.run(
                ["/bin/zsh", "-l", "-c", "echo $PATH"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()

        elif system == "Linux":  # Linux
            shell = os.environ.get("SHELL", "/bin/bash")
            result = subprocess.run(
                [shell, "-l", "-c", "echo $PATH"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()

        elif system == "Windows":  # Windows
            return os.environ.get("PATH", "")

        # Fallback for unknown platforms
        return os.environ.get("PATH", "")

    except Exception as e:
        print(f"Error while retrieving PATH from shell: {e}")
        return os.environ.get("PATH", "")


def setup_fsl_env():
    """
    Load environment variables for FSL (FMRIB Software Library).

    This function runs a shell command to source the FSL configuration script
    (`fsl.sh`) and extract the environment variables `FSLDIR` and `FSLOUTPUTTYPE`.

    Returns:
        tuple[str, str]: A tuple containing:
            - `FSLDIR`: The root installation directory of FSL.
            - `FSLOUTPUTTYPE`: The default FSL output format (e.g., NIFTI_GZ).

    Raises:
        RuntimeError: If FSLDIR or FSLOUTPUTTYPE cannot be retrieved.
    """
    result = subprocess.run(
        ["/bin/zsh", "-l", "-c", "source $FSLDIR/etc/fslconf/fsl.sh && echo $FSLDIR && echo $FSLOUTPUTTYPE"],
        capture_output=True,
        text=True,
        check=True
    )

    lines = result.stdout.strip().splitlines()
    if len(lines) < 2:
        raise RuntimeError("Could not read FSLDIR and FSLOUTPUTTYPE")

    fsldir, fsloutputtype = lines[0], lines[1]
    return fsldir, fsloutputtype
