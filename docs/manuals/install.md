# Installation & Environment Setup
This guide details how to set up the development environment for the GliAAns-UI project.

# 1. System Requirements
Before cloning the repository, ensure your host machine meets the following criteria.

**Software**

- Python: Version 3.11 (Strictly required).

- OS: Windows 10/11, Linux (Ubuntu 20.04+ recommended), or macOS.

**Deep Learning Hardware (Required for Segmentation)**

To run the tumor segmentation pipeline based on deep learning nnunet, the machine must meet these specifications:

- RAM: Minimum 24GB recommended for optimal performance.

- GPU: NVIDIA GPU with at least 6GB VRAM (Tested on GeForce GTX 1060 6GB).

- **Drivers**:
  - NVIDIA Driver: Version 560.94 or newer. 
  - CUDA: Compatible with version 12.x (Tested on CUDA 12.6). 
- Windows Users: Must use WSL (Windows Subsystem for Linux) for the Deep Learning module.

## 2. Clone the Repository
Open your terminal and clone the project source code:

```bash
git clone https://github.com/your-university-org/your-project-name.git
```
```bash
cd se25-p03
```

## 3. Python Environment Setup
To run the application via `main.py` (Developer Mode) or to prepare for compilation, you must set up a virtual environment with the necessary dependencies.

### A. Create Virtual Environment

We recommend creating a virtual environment named .venv.

**For Windows**:

```bash
python -m venv .venv
```
Activate the environment
```bash
.venv\Scripts\activate
```
**For Linux / macOS**:

```bash
python3.11 -m venv .venv
```
Activate the environment
```bash
source .venv/bin/activate
```

### B. Install Dependencies

Once the environment is active, install the project requirements.

Note: If you intend to run the full application including Deep Learning locally without compiling, you may need to install requirements from multiple modules.

```bash
pip install --upgrade pip
```
```bash
pip install -r main/requirements.txt
```
```bash
pip install -r main/pediatric_fdopa_pipeline/requirements.txt
```
#### If developing the Deep Learning module, also install:
```bash
pip install -r main/deep_learning/requirements.txt
```

## 5. Next Steps
Now that your environment is installed:

To directly run the app, you can execute the GUI directly.

```bash
python main.py
```
(see [run.md](./run.md) for detailed usage instructions).

To compile the app; if you wish to build the standalone executable (.exe or binary), see [compile.md](./compile.md) for Nuitka/PyInstaller compiling automations.