SHELL=/bin/bash -e
VE=VE
ACTIVATE=source $(VE)/bin/activate;
PY=$(ACTIVATE) python
PIP=$(ACTIVATE) pip
MYHOST=$(shell hostname)

install: build
	$(PIP) install -U dist/*.whl

/etc/thermodog.json: etc/config/$(MYHOST)-config.json
	sudo cp etc/config/$(MYHOST)-config.json /etc/thermodog.json

install-service: install /etc/thermodog.json
	sudo cp etc/thermodog.service /etc/systemd/system/
	sudo ln -sf /etc/systemd/system/thermodog.service /etc/systemd/system/multi-user.target.wants/
	sudo systemctl daemon-reload

build: $(VE)
	$(PY) setup.py bdist_wheel

develop:
	$(PIP) install -e .

test: build
	cd tests && $(PY) -m unittest discover --failfast -v -t ..

lint:
	$(ACTIVATE) flake8 thermodog

requirements.txt: requirements.in
	pip install --upgrade pip-tools
	pip-compile --upgrade > requirements.txt

$(VE): requirements.txt
	rm -rf $(VE)
	virtualenv $(VE)
	unset PYTHONPATH; $(PIP) install --requirement=requirements.txt
	virtualenv $(VE)

clean:
	-rm -rf build dist
	-rm -rf thermodog.egg-info
	-find . -name "*.pyc" -delete

uninstall:
	-rm -rf $(VE)

.PHONY: uninstall lint install develop clean build test
