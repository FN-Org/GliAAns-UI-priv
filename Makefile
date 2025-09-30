# Nome della cartella del venv
VENV_DIR = .venv

PIPELINE_DIR = pediatric_fdopa_pipeline
REQUIREMENTS = requirements.txt

PIPELINE_DIST = pipeline_runner

# Comandi diversi per sistemi operativi
ifeq ($(OS),Windows_NT)
	PYTHON   = python3.11.exe
	MAIN_PYTHON = $(VENV_DIR)\Scripts\python.exe
	MAIN_PIP    = $(VENV_DIR)\Scripts\pip
	PIPELINE_VENV_DIR = $(PIPELINE_DIR)\$(VENV_DIR)
	PIPELINE_PIP = $(PIPELINE_VENV_DIR)\Scripts\pip
	PIPELINE_REQUIREMENTS = $(PIPELINE_DIR)\$(REQUIREMENTS)
	PIPELINE_PYTHON = $(PIPELINE_VENV_DIR)\Scripts\python.exe
	PIPELINE_RUNNER = $(PIPELINE_DIR)\pipeline_runner.py
	ICON = resources\GliAAns-logo.ico
	ICON_FLAG = --windows-icon-from-ico=$(ICON)
	ATLAS = $(PIPELINE_DIR)\atlas
	HD_BET = $(VENV_DIR)\Scripts\hd-bet.exe
	DCM2NIIX = $(VENV_DIR)\Scripts\dcm2niix.exe
else
	UNAME_S := $(shell uname -s)
	ifeq ($(UNAME_S),Linux)
		ICON = resources/GliAAns-logo.png
		ICON_FLAG = --linux-icon=$(ICON)
	endif
	ifeq ($(UNAME_S),Darwin)
		ICON = resources/GliAAns-logo.icns
		ICON_FLAG = --macos-app-icon=$(ICON)
	endif
	PYTHON   = python3.11
	MAIN_PYTHON = $(VENV_DIR)/bin/python
	MAIN_PIP    = $(VENV_DIR)/bin/pip
	PIPELINE_VENV_DIR = $(PIPELINE_DIR)/$(VENV_DIR)
	PIPELINE_PIP = $(PIPELINE_VENV_DIR)/bin/pip
	PIPELINE_REQUIREMENTS = $(PIPELINE_DIR)/$(REQUIREMENTS)
	PIPELINE_PYTHON = $(PIPELINE_VENV_DIR)/bin/python
	PIPELINE_RUNNER = $(PIPELINE_DIR)/pipeline_runner.py
	ATLAS = $(PIPELINE_DIR)/atlas
	HD_BET = $(VENV_DIR)/bin/hd-bet
	DCM2NIIX = $(VENV_DIR)/bin/dcm2niix
endif

$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)

$(PIPELINE_VENV_DIR):
	$(PYTHON) -m venv $(PIPELINE_VENV_DIR)

.PHONY: main_python-setup
main_python-setup: $(VENV_DIR)
	$(MAIN_PIP) install -r $(REQUIREMENTS)

.PHONY: pipeline_python-setup
pipeline_python-setup: $(PIPELINE_VENV_DIR)
	$(PIPELINE_PIP) install -r $(PIPELINE_REQUIREMENTS)

.PHONY: setup-all
setup-all: main_python-setup pipeline_python-setup

$(PIPELINE_DIST): $(PIPELINE_VENV_DIR)
	$(PIPELINE_PYTHON) -m nuitka $(PIPELINE_RUNNER) \
	    --standalone \
	    --follow-imports \
	    --remove-output \
	    --output-dir=$(PIPELINE_DIST) \
	    --include-data-dir=$(ATLAS)=atlas \
	    $(ICON_FLAG) \
	    --output-filename=pipeline_runner.exe

.PHONY: compile_app
compile_app: $(VENV_DIR) $(PIPELINE_DIST)
	$(MAIN_PYTHON) -m PyInstaller \
	    --onedir \
	    --noconsole \
	    --icon=$(ICON) \
	    --add-data "resources;resources" \
	    --add-data "translations;translations" \
	    --add-data "$(PIPELINE_DIST);pipeline_runner" \
	    --add-binary "$(HD_BET);hd-bet" \
	    --add-binary "$(DCM2NIIX);dcm2niix" \
	    --name GliAAns-UI \
	    --noconfirm \
	    main.py

.PHONY: all
all: setup-all $(PIPELINE_DIST) compile_app

.PHONY: app
app: $(PIPELINE_DIST) compile_app