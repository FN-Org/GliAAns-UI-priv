# Compilation Guide
This document provides instructions on how to compile the GliAAns-UI project from source. The build system is automated using a [Makefile](./../../src/Makefile) that handles virtual environment creation, dependency installation, and binary compilation.

## 1. Prerequisites
Before compiling, ensure your development environment meets the following requirements:

**Operating System**: Windows 10/11, Linux (Ubuntu 20.04+), or macOS.

**Python**: Version 3.11

**Build Tools**:

- make (GNU Make).

- On Windows, ensure make and python3.11 are in your system PATH.

**C Compiler**: Required by Nuitka to compile the pipeline.

- Windows: MinGW64 or Visual Studio Build Tools.

- Linux/Mac: GCC or Clang (sudo apt install build-essential).

## 2. Build Architecture
The application uses a hybrid compilation strategy to ensure both performance and ease of distribution:

**Pediatric FDOPA Pipeline**: Compiled with Nuitka.

This converts Python to C++ for high-performance execution of the medical algorithms.

**GUI**: Bundled with PyInstaller.

This wraps the PyQt interface, the Nuitka-compiled pipeline, and external binaries into a single distribution folder.

## 3. Compilation Commands
Open your terminal in the root directory of the project and use the following commands:

#### A. Full Medical Build (Recommended)

This target compiles the application and includes the Deep Learning modules and models required for tumor segmentation.

```bash
make app-dl 
```
```bash
make all-dl # for also the virtual environments
```
What this does:

1. Sets up virtual environments (.venv, .venv/pipeline). 
2. Compiles the pipeline_runner using Nuitka. 
3. Bundles the GUI using PyInstaller. 
4. Copies the deep_learning/ directory and its specific Makefile into the final distribution folder.

> Important: Post-Compilation Deep Learning Setup 
> 
> The `make app-dl` command prepares the file structure, but does not automatically install the heavy Deep Learning dependencies in the final distribution. 
> 
> To enable Deep Learning features, you must perform the following steps after compilation:
> 
> - Navigate to the deep_learning folder inside the generated distribution (e.g., `src/main/dist/GliAAns-UI/deep_learning` or similar). 
> - Consult the [README.md](./../../src/main/deep_learning/README.md) file located there for specific hardware and driver requirements. 
> - Execute the Deep Learning [Makefile](./../../src/main/deep_learning/Makefile) (included in that folder) to generate the dedicated virtual environment containing all necessary dependencies.

#### B. Standard GUI Build (No Deep Learning)

If you only need the GUI and the standard pipeline (without the heavy Deep Learning models):

```bash
make app
```
```bash
make all # for also the virtual environments
```

#### C. Documentation

To generate the project API documentation (using pdoc):

```bash
make doc
```

#### 4. Build Artifacts
Upon successful compilation, the executable application will be located here:

**Location**: `main/dist/GliAAns-UI/`

**Executable**:

Windows: `GliAAns-UI.exe`

Linux/Mac: `GliAAns-UI`

#### 5. Cleaning Up
To remove build artifacts, temporary environments, and compiled binaries to start fresh:

```bash
make clean
```

#### 6. Troubleshooting
- **Nuitka Errors**: If Nuitka fails to compile, make sure you are using a proper C/C++ compiler toolchain. 

  On Windows, ensure you are running the build inside the "Developer Command Prompt for Visual Studio" (or the _Visual Studio Developer PowerShell_) so that the required build tools are available in your environment.
- **Python Version**: If the Makefile fails immediately, verify that `python3.11` is available. 

  If your Python executable has a different name (e.g., just `python`), you may need to edit the `PYTHON = python3.11` line in the Makefile.
