# -------------------------
# Configurazioni principali
# -------------------------
VENV_DIR          = .venv
PIPELINE_DIR      = pediatric_fdopa_pipeline
REQUIREMENTS      = requirements.txt
PIPELINE_DIST     = pipeline_runner.dist
PIPELINE_NO_DIST  = pipeline_runner
DOC_DIR			  = docs

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
    ATLAS              = $(PIPELINE_DIR)\atlas
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
    ATLAS              = $(PIPELINE_DIR)/atlas
    HD_BET             = $(VENV_DIR)/bin/hd-bet
    DCM2NIIX           = $(VENV_DIR)/bin/dcm2niix
endif

# -------------------------
# Creazione virtualenv
# -------------------------
$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)

$(PIPELINE_VENV_DIR):
	$(PYTHON) -m venv $(PIPELINE_VENV_DIR)

# -------------------------
# Installazione pacchetti
# -------------------------
.PHONY: main_python-setup
main_python-setup: $(VENV_DIR)
	$(MAIN_PIP) install -r $(REQUIREMENTS)

.PHONY: pipeline_python-setup
pipeline_python-setup: $(PIPELINE_VENV_DIR)
	$(PIPELINE_PIP) install -r $(PIPELINE_REQUIREMENTS)

.PHONY: setup-all
setup-all: main_python-setup pipeline_python-setup

# -------------------------
# Compilazione pipeline con Nuitka
# -------------------------
$(PIPELINE_DIST): $(PIPELINE_VENV_DIR)
	$(PIPELINE_PYTHON) -m nuitka $(PIPELINE_RUNNER) \
	    --standalone \
	    --remove-output \
	    --nofollow-import-to=unittest \
	    --nofollow-import-to=test \
	    --nofollow-import-to=tkinter \
	    --nofollow-import-to=email \
	    --nofollow-import-to=distutils \
	    --lto=yes \
	    --python-flag=-OO \
	    --include-data-dir=$(ATLAS)=atlas \
	    $(ICON_FLAG) \
	    --output-filename=$(PIPELINE_EXE) \
	    --show-progress \
	    --show-modules


$(PIPELINE_NO_DIST):$(PIPELINE_DIST)
ifeq ($(OS),Windows_NT)
	cmd /C move $(PIPELINE_DIST) $(PIPELINE_NO_DIST)
else
	mv $(PIPELINE_DIST) $(PIPELINE_NO_DIST)
endif

# -------------------------
# Compilazione app con PyInstaller
# -------------------------
.PHONY: compile-app
compile-app: $(VENV_DIR)
	$(MAIN_PYTHON) -OO -m PyInstaller \
		--clean \
	    --onedir \
	    --noconsole \
	    --icon=$(ICON) \
	    --add-data "resources$(SEP)resources" \
	    --add-data "translations$(SEP)translations" \
	    --add-data "$(PIPELINE_NO_DIST)$(SEP)pipeline_runner" \
	    --add-binary "$(HD_BET)$(SEP)hd-bet" \
	    --add-binary "$(DCM2NIIX)$(SEP)dcm2niix" \
	    --exclude-module test \
	    --exclude-module unittest \
	    --name GliAAns-UI \
	    --noconfirm \
	    main.py

# -------------------------
# Target principali
# -------------------------
.PHONY: all
all: setup-all app

.PHONY: app
app: $(PIPELINE_NO_DIST) compile-app

# -------------------------
# Pulizia cross-platform
# -------------------------
.PHONY: clean
clean: clean-pipeline
ifeq ($(OS),Windows_NT)
	if exist "$(VENV_DIR)" rmdir /S /Q "$(VENV_DIR)"
	if exist "$(PIPELINE_VENV_DIR)" rmdir /S /Q "$(PIPELINE_VENV_DIR)"
	if exist "build" rmdir /S /Q "build"
	if exist "dist" rmdir /S /Q "dist"
	if exist "*.spec" del /Q *.spec
else
	rm -rf $(VENV_DIR) $(PIPELINE_VENV_DIR) build dist *.spec
endif

.PHONY: clean-pipeline
clean-pipeline:
ifeq ($(OS),Windows_NT)
	if exist "$(PIPELINE_DIST)" rmdir /S /Q "$(PIPELINE_DIST)"
	if exist "$(PIPELINE_NO_DIST)" rmdir /S /Q "$(PIPELINE_NO_DIST)"
else
	rm -rf $(PIPELINE_DIST) $(PIPELINE_NO_DIST)
endif

.PHONY: doc
doc:
ifeq ($(OS),Windows_NT)
	if exist "$(DOC_DIR)" rmdir /S /Q "$(DOC_DIR)"
	pdoc -o $(DOC_DIR) --logo $(abspath resources\GliAAns-logo.png) --template-dir pdoc_template .\main.py .\controller.py .\utils.py .\logger.py .\ui .\threads .\components
else
	rm -rf $(DOC_DIR)
	pdoc -o $(DOC_DIR) --logo $(abspath resources/GliAAns-logo.png) --template-dir pdoc_template ./main.py ./controller.py ./utils.py ./logger.py ./ui ./threads ./components
endif
