# -------------------------
# Main configuration
# -------------------------
VENV_DIR          = .venv
PIPELINE_DIR      = pediatric_fdopa_pipeline
REQUIREMENTS      = requirements.txt
PIPELINE_DIST     = pipeline_runner.dist
PIPELINE_NO_DIST  = pipeline_runner
DOC_DIR			  = ../pdoc/docs

# -------------------------
# OS Management
# -------------------------
ifeq ($(OS),Windows_NT)
    # ---- Windows ----
    PYTHON             = python3.11.exe
    SEP 			   = ;
    APP_VENV_DIR       = main\$(VENV_DIR)
    MAIN_PYTHON        = $(VENV_DIR)\Scripts\python.exe
    MAIN_PIP           = $(VENV_DIR)\Scripts\pip
    PIPELINE_VENV_DIR  = $(PIPELINE_DIR)\$(VENV_DIR)
    PIPELINE_PIP       = $(PIPELINE_VENV_DIR)\Scripts\pip
    PIPELINE_PYTHON    = $(PIPELINE_VENV_DIR)\Scripts\python.exe
    PIPELINE_RUNNER    = $(PIPELINE_DIR)\pipeline_runner.py
    PIPELINE_REQUIREMENTS = $(PIPELINE_DIR)\$(REQUIREMENTS)
    PIPELINE_EXE 	   = pipeline_runner.exe
    DL_VENV_DIR		   = .venv-dl
    DL_PIP			   = dist/GliAAns-UI/$(DL_VENV_DIR)/Scripts/pip
    TESTS_VENV_DIR	   = tests\$(VENV_DIR)
    TESTS_PIP 		   = $(TESTS_VENV_DIR)\Scripts\pip
    TESTS_PYTHON       = $(TESTS_VENV_DIR)\Scripts\python
    TESTS_REQUIREMENTS = $(TESTS_DIR)\requirements-test.txt
    ICON               = resources\GliAAns-logo.ico
    ICON_FLAG          = --windows-icon-from-ico=$(ICON)
    ATLAS              = $(PIPELINE_DIR)\atlas
    HD_BET             = $(VENV_DIR)\Scripts\hd-bet.exe
    DCM2NIIX           = $(VENV_DIR)\Scripts\dcm2niix.exe
    NIPREPS_SYNTHSTRIP = $(VENV_DIR)/Scripts/nipreps-synthstrip
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
    APP_VENV_DIR       = main/$(VENV_DIR)
    MAIN_PYTHON        = $(VENV_DIR)/bin/python
    MAIN_PIP           = $(VENV_DIR)/bin/pip
    PIPELINE_VENV_DIR  = $(PIPELINE_DIR)/$(VENV_DIR)
    PIPELINE_PIP       = $(PIPELINE_VENV_DIR)/bin/pip
    PIPELINE_PYTHON    = $(PIPELINE_VENV_DIR)/bin/python
    PIPELINE_RUNNER    = $(PIPELINE_DIR)/pipeline_runner.py
    PIPELINE_REQUIREMENTS = $(PIPELINE_DIR)/requirements.txt
    PIPELINE_EXE 	   = pipeline_runner
    DL_VENV_DIR		   = .venv-dl
    DL_PIP			   = dist/GliAAns-UI/$(DL_VENV_DIR)/bin/pip
    DL_REQUIREMENTS	   = deep_learning/requirements.txt
    TESTS_VENV_DIR	   = tests/$(VENV_DIR)
    TESTS_PIP 		   = $(TESTS_VENV_DIR)/bin/pip
    TESTS_PYTHON       = $(TESTS_VENV_DIR)/bin/python
    TESTS_REQUIREMENTS = tests/requirements-test.txt
    ATLAS              = $(PIPELINE_DIR)/atlas
    HD_BET             = $(VENV_DIR)/bin/hd-bet
    DCM2NIIX           = $(VENV_DIR)/lib/python3.11/site-packages/dcm2niix/dcm2niix
    NIPREPS_SYNTHSTRIP = $(VENV_DIR)/bin/nipreps-synthstrip
	TESTS_PDOC         = ../$(TESTS_VENV_DIR)/bin/pdoc
endif

# -------------------------
# Virtualenv creation
# -------------------------
$(APP_VENV_DIR):
	$(PYTHON) -m venv $(APP_VENV_DIR)

$(PIPELINE_VENV_DIR):
	cd main && $(PYTHON) -m venv $(PIPELINE_VENV_DIR)

$(DL_VENV_DIR):
	cd main/dist/GliAAns-UI && $(PYTHON) -m venv $(DL_VENV_DIR)

$(TESTS_VENV_DIR):
	$(PYTHON) -m venv $(TESTS_VENV_DIR)

# -------------------------
# Package installation
# -------------------------
.PHONY: main_python-setup
main_python-setup: $(APP_VENV_DIR)
	cd main && $(MAIN_PIP) install -r $(REQUIREMENTS)

.PHONY: pipeline_python-setup
pipeline_python-setup: $(PIPELINE_VENV_DIR)
	cd main && $(PIPELINE_PIP) install -r $(PIPELINE_REQUIREMENTS)

.PHONY: dl_python-setup
dl_python-setup: $(DL_VENV_DIR)
	cd main && $(DL_PIP) install -r $(DL_REQUIREMENTS)

.PHONY: tests_python-setup
tests_python-setup: $(TESTS_VENV_DIR)
	$(TESTS_PIP) install -r $(TESTS_REQUIREMENTS)

.PHONY: setup-all
setup-all: main_python-setup pipeline_python-setup

# -------------------------
# Pipeline compilation with Nuitka
# -------------------------
$(PIPELINE_DIST): $(PIPELINE_VENV_DIR)
	cd main && $(PIPELINE_PYTHON) -m nuitka $(PIPELINE_RUNNER) \
	    --standalone \
	    --remove-output \
		--assume-yes-for-downloads \
	    --nofollow-import-to=unittest \
	    --nofollow-import-to=test \
	    --nofollow-import-to=tkinter \
	    --enable-plugin=no-qt \
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
	cd main && mv $(PIPELINE_DIST) $(PIPELINE_NO_DIST)
endif

.PHONY: compile-pipeline
compile-pipeline: $(PIPELINE_NO_DIST)

# -------------------------
# App compilation with PyInstaller
# -------------------------
.PHONY: compile-app
compile-app: $(APP_VENV_DIR)
	cd main && $(MAIN_PIP) install --upgrade pyinstaller-hooks-contrib && $(MAIN_PYTHON) -OO -m PyInstaller \
		--clean \
	    --onedir \
	    --noconsole \
	    --icon=$(ICON) \
	    --add-data "resources$(SEP)resources" \
	    --add-data "translations$(SEP)translations" \
	    --add-data "pipeline_runner$(SEP)pipeline_runner" \
	    --add-binary "$(HD_BET)$(SEP)hd-bet" \
	    --add-binary "$(DCM2NIIX)$(SEP)dcm2niix" \
	    --add-binary "$(NIPREPS_SYNTHSTRIP)$(SEP)nipreps-synthstrip" \
		--collect-all "HD_BET" \
		--collect-all "nipreps_synthstrip" \
		--collect-all "typing_extensions" \
		--collect-all "nnunetv2" \
	    --collect-all "dynamic_network_architectures" \
	    --collect-all "acvl_utils" \
	    --collect-all "batchgenerators" \
	    --collect-all "batchgeneratorsv2" \
	    --collect-all "simpleitk" \
	    --collect-all "connected_components_3d" \
	    --collect-all "timm" \
	    --collect-all "scipy" \
	    --collect-all "skimage" \
	    --collect-all "pandas" \
	    --collect-all "imagecodecs" \
	    --collect-all "tifffile" \
	    --collect-all "torch" \
	    --collect-all "triton" \
	    --collect-all "sklearn" \
	    --hidden-import "torchgen.model" \
	    --hidden-import "sklearn.utils._cython_blas" \
	    --hidden-import "sklearn.neighbors.typedefs" \
	    --hidden-import "sklearn.neighbors.quad_tree" \
	    --hidden-import "sklearn.tree._utils" \
	    --hidden-import "scipy.special.cython_special" \
	    --name GliAAns-UI \
	    --noconfirm \
	    main.py

# -------------------------
# Principal targets
# -------------------------
.PHONY: all
all: setup-all app

.PHONY: app
app: compile-pipeline compile-app

.PHONY: app-dl
app-dl: app
	cd main && cp -r deep_learning/ dist/GliAAns-UI
	cd main/dist/GliAAns-UI && mv deep_learning/Makefile .
	cd main/dist/GliAAns-UI && mv deep_learning/README.md .

.PHONY: all-dl
all-dl: setup-all app-dl

# -------------------------
# Cleaning
# -------------------------
.PHONY: clean
clean: clean-pipeline
ifeq ($(OS),Windows_NT)
	if exist "$(APP_VENV_DIR)" rmdir /S /Q "$(APP_VENV_DIR)"
	if exist "$main/(PIPELINE_VENV_DIR)" rmdir /S /Q "main/$(PIPELINE_VENV_DIR)"
	if exist "$(TESTS_VENV_DIR)" rmdir /S /Q "$(TESTS_VENV_DIR)"
	if exist "main/build" rmdir /S /Q "main/build"
	if exist "main/dist" rmdir /S /Q "main/dist"
	if exist "main/*.spec" del /Q "main/*.spec"
else
	rm -rf $(APP_VENV_DIR) main/$(PIPELINE_VENV_DIR) $(TESTS_VENV_DIR) main/build main/dist main/*.spec
endif

.PHONY: clean-pipeline
clean-pipeline:
ifeq ($(OS),Windows_NT)
	if exist "$(PIPELINE_DIST)" rmdir /S /Q "$(PIPELINE_DIST)"
	if exist "$(PIPELINE_NO_DIST)" rmdir /S /Q "$(PIPELINE_NO_DIST)"
else
	rm -rf main/$(PIPELINE_DIST) main/$(PIPELINE_NO_DIST)
endif

# -------------------------
# Tests
# -------------------------
SRC_DIR      := main
TEST_SCRIPT  := tests/run_all_tests.sh

.PHONY: tests
tests:
	env PATH=tests/.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
	    PYTHONPATH=main \
	    VIRTUAL_ENV=tests/.venv \
	    /bin/bash tests/run_all_tests.sh

.PHONY: tests-coverage
tests-coverage:
	env PATH=tests/.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
	    PYTHONPATH=main \
	    VIRTUAL_ENV=tests/.venv \
	    /bin/bash tests/run_all_tests.sh -c

# -------------------------
# Create documentation
# -------------------------
.PHONY: doc
doc:
ifeq ($(OS),Windows_NT)
	if exist "$(DOC_DIR)" rmdir /S /Q "$(DOC_DIR)"
	cd main && set PYTHONPATH=. && pdoc -o "$(DOC_DIR)" --logo "$(abspath main\resources\GliAAns-logo.png)" --template-dir ../pdoc/pdoc_template . ui threads components
	cd ..
else
	rm -rf $(DOC_DIR)
	cd main && PYTHONPATH=. $(TESTS_PDOC) -o $(DOC_DIR) --logo "https://fn-org.github.io/GliAAns-UI-priv/GliAAns-logo.png" --template-dir ../pdoc/pdoc_template . ui threads components && cd ..
endif
