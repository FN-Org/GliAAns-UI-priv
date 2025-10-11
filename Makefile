# -------------------------
# Configurazioni principali
# -------------------------
VENV_DIR          = .venv
PIPELINE_DIR      = pediatric_fdopa_pipeline
DL_DIR 			  = deep_learning
REQUIREMENTS      = requirements.txt
PIPELINE_DIST     = pipeline_runner.dist
PIPELINE_NO_DIST  = pipeline_runner
COREGISTRATION_DIST = $(COREGISTRATION_EXE).dist
COREGISTRATION_NO_DIST = coregistration
REORIENTATION_DIST  = $(REORIENTATION_EXE).dist
REORIENTATION_NO_DIST = reorientation
PREPROCESS_DIST     = $(PREPROCESS_EXE).dist
PREPROCESS_NO_DIST = preprocess
DEEP_LEARNING_DIST  = $(DEEP_LEARNING_EXE).dist
DEEP_LEARNING_NO_DIST = deep_learning_runner
POSTPROCESS_DIST    = $(POSTPROCESS_EXE).dist
POSTPROCESS_NO_DIST = postprocess

# -------------------------
# Rilevamento OS
# -------------------------
ifeq ($(OS),Windows_NT)
    # ---- Windows ----
    PYTHON             = python3.11.exe
    SEP 			   = ;
    MAIN_PYTHON        = $(VENV_DIR)\Scripts\python.exe
    MAIN_PIP           = $(VENV_DIR)\Scripts\pip
    PIPELINE_VENV_DIR  = $(PIPELINE_DIR)\$(VENV_DIR)
    PIPELINE_PIP       = $(PIPELINE_VENV_DIR)\Scripts\pip
    PIPELINE_PYTHON    = $(PIPELINE_VENV_DIR)\Scripts\python.exe
    PIPELINE_RUNNER    = $(PIPELINE_DIR)\pipeline_runner.py
    PIPELINE_REQUIREMENTS = $(PIPELINE_DIR)\$(REQUIREMENTS)
    PIPELINE_EXE 	   = pipeline_runner.exe
    ICON               = resources\GliAAns-logo.ico
    ICON_FLAG          = --windows-icon-from-ico=$(ICON)
    PIPELINE_ATLAS     = $(PIPELINE_DIR)\atlas
    HD_BET             = $(VENV_DIR)\Scripts\hd-bet.exe
    DCM2NIIX           = $(VENV_DIR)\Scripts\dcm2niix.exe
else
    # ---- Linux / macOS ----
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Linux)
        ICON      = resources/GliAAns-logo.png
        ICON_FLAG = --linux-icon=$(ICON)
    endif
    ifeq ($(UNAME_S),Darwin)
        ICON      = resources/GliAAns-logo.icns
        ICON_FLAG = --macos-app-icon=$(ICON)
    endif
    PYTHON             = python3.11
    SEP		 		   = :
    MAIN_PYTHON        = $(VENV_DIR)/bin/python
    MAIN_PIP           = $(VENV_DIR)/bin/pip
    PIPELINE_VENV_DIR  = $(PIPELINE_DIR)/$(VENV_DIR)
    PIPELINE_PIP       = $(PIPELINE_VENV_DIR)/bin/pip
    PIPELINE_PYTHON    = $(PIPELINE_VENV_DIR)/bin/python
    PIPELINE_RUNNER    = $(PIPELINE_DIR)/pipeline_runner.py
    PIPELINE_REQUIREMENTS = $(PIPELINE_DIR)/$(REQUIREMENTS)
    PIPELINE_EXE 	   = pipeline_runner
    PIPELINE_ATLAS     = $(PIPELINE_DIR)/atlas
    HD_BET             = $(VENV_DIR)/bin/hd-bet
    DCM2NIIX           = $(VENV_DIR)/bin/dcm2niix
    NIPREPS_SYNTHSTRIP =
    DL_VENV_DIR  	   = $(DL_DIR)/$(VENV_DIR)
    DL_PIP       	   = $(DL_VENV_DIR)/bin/pip
    DL_PYTHON    	   = $(DL_VENV_DIR)/bin/python
    DL_REQUIREMENTS    = $(DL_DIR)/$(REQUIREMENTS)
    COREGISTRATION	   = $(DL_DIR)/coregistration.py
    COREGISTRATION_EXE = coregistration
    REORIENTATION	   = $(DL_DIR)/reorientation.py
    REORIENTATION_EXE  = reorientation
    PREPROCESS	   	   = $(DL_DIR)/preprocess.py
    PREPROCESS_EXE     = preprocess
    DEEP_LEARNING	   = $(DL_DIR)/deep_learning_runner.py
    DEEP_LEARNING_EXE  = deep_learning
    CHECKPOINTS		   = $(DL_DIR)/checkpoints
    POSTPROCESS	       = $(DL_DIR)/postprocess.py
    POSTPROCESS_EXE    = postprocess
    POSTPROCESS_ATLAS  = $(DL_DIR)/atlas
endif

# -------------------------
# Creazione virtualenv
# -------------------------
$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)

$(PIPELINE_VENV_DIR):
	$(PYTHON) -m venv $(PIPELINE_VENV_DIR)

$(DL_VENV_DIR):
	$(PYTHON) -m venv $(DL_VENV_DIR)

# -------------------------
# Installazione pacchetti
# -------------------------
.PHONY: main_python-setup
main_python-setup: $(VENV_DIR)
	$(MAIN_PIP) install -r $(REQUIREMENTS)

.PHONY: pipeline_python-setup
pipeline_python-setup: $(PIPELINE_VENV_DIR)
	$(PIPELINE_PIP) install -r $(PIPELINE_REQUIREMENTS)

.PHONY: dl_python-setup
dl_python-setup: $(DL_VENV_DIR)
	$(DL_PIP) install -r $(DL_REQUIREMENTS)

.PHONY: setup-all
setup-all: main_python-setup pipeline_python-setup dl_python-setup

# -------------------------
# Compilazione pipeline con Nuitka
# -------------------------
$(PIPELINE_DIST): $(PIPELINE_VENV_DIR)
	$(PIPELINE_PYTHON) -m nuitka $(PIPELINE_RUNNER) \
	    --standalone \
	    --follow-imports \
	    --remove-output \
	    --include-data-dir=$(PIPELINE_ATLAS)=atlas \
	    $(ICON_FLAG) \
	    --output-filename=$(PIPELINE_EXE)

$(PIPELINE_NO_DIST):$(PIPELINE_DIST)
ifeq ($(OS),Windows_NT)
	cmd /C move $(PIPELINE_DIST) $(PIPELINE_NO_DIST)
else
	mv $(PIPELINE_DIST) $(PIPELINE_NO_DIST)
endif

# -------------------------
# Compilazione coregistration con Nuitka
# -------------------------
$(COREGISTRATION_DIST): $(DL_VENV_DIR)
	$(DL_PYTHON) -m nuitka $(COREGISTRATION) \
	    --standalone \
	    --follow-imports \
	    --remove-output \
	    $(ICON_FLAG) \
	    --output-filename=$(COREGISTRATION_EXE)

$(COREGISTRATION_NO_DIST):$(COREGISTRATION_DIST)
	mv $(COREGISTRATION_DIST) $(COREGISTRATION_NO_DIST)

# -------------------------
# Compilazione reorientation con Nuitka
# -------------------------
$(REORIENTATION_DIST): $(DL_VENV_DIR)
	$(DL_PYTHON) -m nuitka $(REORIENTATION) \
	    --standalone \
	    --follow-imports \
	    --remove-output \
	    $(ICON_FLAG) \
	    --output-filename=$(REORIENTATION_EXE)

$(REORIENTATION_NO_DIST):$(REORIENTATION_DIST)
	mv $(REORIENTATION_DIST) $(REORIENTATION_NO_DIST)

# -------------------------
# Compilazione preprocess con Nuitka
# -------------------------
$(PREPROCESS_DIST): $(DL_VENV_DIR)
	$(DL_PYTHON) -m nuitka $(PREPROCESS) \
	    --standalone \
	    --follow-imports \
	    --remove-output \
	    $(ICON_FLAG) \
	    --output-filename=$(PREPROCESS_EXE)

$(PREPROCESS_NO_DIST):$(PREPROCESS_DIST)
	mv $(PREPROCESS_DIST) $(PREPROCESS_NO_DIST)

# -------------------------
# Compilazione deep learning con Nuitka
# -------------------------
$(DEEP_LEARNING_DIST): $(DL_VENV_DIR)
	$(DL_PYTHON) -m nuitka $(DEEP_LEARNING) \
	    --standalone \
	    --follow-imports \
	    --remove-output \
	    --include-data-dir=$(CHECKPOINTS)=checkpoints \
	    $(ICON_FLAG) \
	    --output-filename=$(DEEP_LEARNING_EXE)

$(DEEP_LEARNING_NO_DIST):$(DEEP_LEARNING_DIST)
	mv $(DEEP_LEARNING_DIST) $(DEEP_LEARNING_NO_DIST)

# -------------------------
# Compilazione postprocess con Nuitka
# -------------------------
$(POSTPROCESS_DIST): $(DL_VENV_DIR)
	$(DL_PYTHON) -m nuitka $(POSTPROCESS) \
	    --standalone \
	    --follow-imports \
	    --remove-output \
	    --include-data-dir=$(POSTPROCESS_ATLAS)=atlas \
	    $(ICON_FLAG) \
	    --output-filename=$(POSTPROCESS_EXE)

$(POSTPROCESS_NO_DIST):$(POSTPROCESS_DIST)
	mv $(POSTPROCESS_DIST) $(POSTPROCESS_NO_DIST)

# -------------------------
# Compilazione app con PyInstaller
# -------------------------
.PHONY: compile-app
compile-app: $(VENV_DIR)
	$(MAIN_PYTHON) -m PyInstaller \
	    --onedir \
	    --noconsole \
	    --icon=$(ICON) \
	    --add-data "resources$(SEP)resources" \
	    --add-data "translations$(SEP)translations" \
	    --add-data "$(PIPELINE_NO_DIST)$(SEP)pipeline_runner" \
	    --add-data "$(COREGISTRATION_NO_DIST)$(SEP)coregistration" \
	    --add-data "$(REORIENTATION_NO_DIST)$(SEP)reorientation" \
	    --add-data "$(PREPROCESS_NO_DIST)$(SEP)preprocess" \
	    --add-data "$(DEEP_LEARNING_NO_DIST)$(SEP)deep_learning_runner" \
	    --add-data "$(POSTPROCESS_NO_DIST)$(SEP)postprocess" \
	    --add-binary "$(HD_BET)$(SEP)hd-bet" \
	    --add-binary "$(DCM2NIIX)$(SEP)dcm2niix" \
	    --add-binary "$(NIPREPS_SYNTHSTRIP)$(SEP)nipreps_synthstrip" \
	    --name GliAAns-UI \
	    --noconfirm \
	    main.py

# -------------------------
# Target principali
# -------------------------
.PHONY: all
all: setup-all app

.PHONY: app
app: $(PIPELINE_NO_DIST) compile-dl compile-app

.PHONY: compile-dl
compile-dl: $(COREGISTRATION_NO_DIST) $(REORIENTATION_NO_DIST) $(PREPROCESS_NO_DIST) $(DEEP_LEARNING_NO_DIST) $(POSTPROCESS_NO_DIST)

# -------------------------
# Pulizia cross-platform
# -------------------------
.PHONY: clean
clean: clean-pipeline clean-dl
ifeq ($(OS),Windows_NT)
	if exist "$(VENV_DIR)" rmdir /S /Q "$(VENV_DIR)"
	if exist "$(PIPELINE_VENV_DIR)" rmdir /S /Q "$(PIPELINE_VENV_DIR)"
	if exist "build" rmdir /S /Q "build"
	if exist "dist" rmdir /S /Q "dist"
	if exist "*.spec" del /Q *.spec
else
	rm -rf $(VENV_DIR) $(PIPELINE_VENV_DIR) $(DL_VENV_DIR) build dist *.spec
endif

.PHONY: clean-pipeline
clean-pipeline:
ifeq ($(OS),Windows_NT)
	if exist "$(PIPELINE_DIST)" rmdir /S /Q "$(PIPELINE_DIST)"
	if exist "$(PIPELINE_NO_DIST)" rmdir /S /Q "$(PIPELINE_NO_DIST)"
else
	rm -rf $(PIPELINE_DIST) $(PIPELINE_NO_DIST)
endif

.PHONY: clean-dl
clean-dl:
	rm -rf $(COREGISTRATION_DIST) $(REORIENTATION_DIST) $(PREPROCESS_DIST) $(DEEP_LEARNING_DIST) $(POSTPROCESS_DIST) $(COREGISTRATION_NO_DIST) $(REORIENTATION_NO_DIST) $(PREPROCESS_NO_DIST) $(DEEP_LEARNING_NO_DIST) $(POSTPROCESS_NO_DIST)
