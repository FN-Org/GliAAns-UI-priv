# Deep Learning Setup

This file explains how to enable the **Deep Learning module** required by the GUI application.

You only need to run **one command** in the terminal to create the Python virtual environment.

---

## Requirements

### Operating System
* **Linux** or **Windows with WSL** (Windows Subsystem for Linux).

### Hardware & Drivers
The model relies on CUDA. Please ensure your setup meets the requirements below.
* **GPU:** NVIDIA GPU with at least **6GB** of VRAM (specifically tested on **NVIDIA GeForce GTX 1060 6GB**).
* **NVIDIA Driver:** Version **560.94** or newer.
* **CUDA Version:** Compatible with CUDA **12.x** (tested on CUDA **12.6**).

---

## Steps

1. **Open a terminal**

   * Linux: open your Terminal
   * Windows: open *WSL* (e.g., Ubuntu on WSL)

2. **Go to the folder where this README is located**, for example:

   ```bash
   cd /path/to/the/unzipped/folder
   ```

3. **Create the Deep Learning virtual environment** by running:

   ```bash
   make dl-venv
   ```

This command will automatically create a Python virtual environment in this folder and install all required Deep Learning dependencies.

---

## After setup

You can now start the GUI application. The Deep Learning module will work automatically.

If any error appears, please contact technical support.
