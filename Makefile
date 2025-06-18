#
# Python environment
#

.venv:
	python3 -m venv $@

.PHONY: python-setup
python-setup: .venv
	. .venv/bin/activate \
		&& pip install --upgrade pip \
		&& pip install -r requirements.txt

.PHONY: install-dcm2niix
install-dcm2niix:
	@if [ "$(shell uname)" = "Linux" ]; then \
		sudo apt install -y dcm2niix; \
	elif [ "$(shell uname)" = "Darwin" ]; then \
		brew install dcm2niix; \
	elif [ "$(shell uname -s)" = "MINGW32_NT" ] || [ "$(shell uname -s)" = "MINGW64_NT" ]; then \
		choco install dcm2niix; \
	else \
		echo "Sistema operativo non supportato!"; \
	fi

.PHONY: setup-all
setup-all: python-setup install-dcm2niix