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