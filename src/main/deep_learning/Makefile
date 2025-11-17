.PHONY: dl-venv

dl-venv:
	@if [ -d ".venv-dl" ]; then \
		echo "Virtual environment '.venv-dl' already exists."; \
		echo "If you want to recreate it, delete the folder first."; \
	else \
		echo "Creating Python 3.11 virtual environment (.venv-dl)..."; \
		python3.11 -m venv .venv-dl; \
		echo "Virtual environment created."; \
	fi
	@echo "Activating environment and installing dependencies..."
	@. .venv-dl/bin/activate && pip install --upgrade pip
	@. .venv-dl/bin/activate && pip install -r deep_learning/requirements.txt
	@echo "Deep Learning environment ready."
