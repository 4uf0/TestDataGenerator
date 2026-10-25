.PHONY: setup generate upload clean

VENV_DIR ?= .venv

setup:
	./setup.sh

generate:
	source $(VENV_DIR)/bin/activate && python generate_fit.py

upload:
	source $(VENV_DIR)/bin/activate && python upload_to_garmin.py out/

clean:
	rm -rf $(VENV_DIR) out/
