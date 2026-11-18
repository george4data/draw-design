PY ?= .venv/bin/python
DDRAW = $(PY) -m ddraw
export PYTHONPATH := skills/draw-design/scripts

.PHONY: venv check lint types test gallery gen render shapes

venv:
	uv venv .venv --python 3.13 && uv pip install --python .venv/bin/python -r requirements-dev.txt

lint:
	$(PY) -m ruff check skills/draw-design/scripts tests scripts
	$(PY) -m ruff format --check skills/draw-design/scripts tests scripts

types:
	$(PY) -m mypy

test:
	$(PY) -m pytest

gen:
	$(PY) scripts/gen-docs.py

check: lint types test
	$(PY) scripts/gen-docs.py --check
	$(PY) scripts/verify-plugin-package.py

gallery:
	$(PY) scripts/build-gallery.py

render:
	$(PY) scripts/build-gallery.py --render

# Rebuild the vendor shape catalog from the pinned index and verify it with draw.io Desktop.
shapes:
	$(PY) scripts/build-shape-catalog.py --fetch --verify
