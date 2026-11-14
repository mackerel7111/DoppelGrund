# DoppelGrund Makefile: the interface for humans, agents and CI. Run make targets, not raw tools.
# Python runs from .venv (created by `make setup`). Override with `make <target> PY=/path/to/python`.

ifeq ($(OS),Windows_NT)
SYS_PY ?= python
VENV_PY := .venv/Scripts/python.exe
else
SYS_PY ?= python3
VENV_PY := .venv/bin/python
endif
PY ?= $(VENV_PY)
# npm scripts run through a wrapper that fixes the drive-letter case on Windows (see the script).
NPM_RUN := node scripts/npm-run.mjs

.PHONY: setup lint fmt lint-py lint-web test-py test-web parity verify-quick verify \
	bundle-synthetic bundle tables-real dev build preview

setup:
	test -x "$(VENV_PY)" || $(SYS_PY) -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e "pipeline[dev]"
	cd web && npm ci --no-audit --no-fund

lint:
	$(PY) -m ruff check pipeline
	$(PY) -m ruff format --check pipeline
	cd web && $(NPM_RUN) lint

fmt:
	$(PY) -m ruff check --fix pipeline
	$(PY) -m ruff format pipeline
	cd web && $(NPM_RUN) format

lint-py:
	$(PY) -m ruff check --fix "$(FILE)"
	$(PY) -m ruff format "$(FILE)"

# FILE may be absolute or relative to the repo root.
lint-web:
	@f="$(FILE)"; case "$$f" in /*|?:*) ;; *) f="../$$f" ;; esac; \
	cd web && npx eslint --fix "$$f" && npx prettier --write "$$f"

test-py:
	$(PY) -m pytest pipeline/tests -m "not ee and not slow" -q

test-web:
	cd web && $(NPM_RUN) test -- --run

# Vectors come from the Python reference scorer (spec 02). Until doppelgrund/export/parity.py exists
# the TS parity test is skipped (override O3).
parity:
	@if [ -f pipeline/doppelgrund/export/parity.py ]; then \
		$(PY) -m doppelgrund.export.parity --out tests/parity/vectors.json; \
	else \
		echo "parity: doppelgrund.export.parity not yet implemented (spec 02/2.4); running TS parity test (skips without vectors)"; \
	fi
	cd web && $(NPM_RUN) test -- --run tests/parity.test.ts

verify-quick: lint test-py test-web

verify: verify-quick parity
	cd web && $(NPM_RUN) build

bundle-synthetic:
	$(PY) -m doppelgrund.fixtures.synthetic --bundle web/public/data --interim data/interim/synthetic --coverage land

# Real C2 tables -> data/interim/real. e.g. make tables-real ARGS="--ee-project MY_PROJECT" or ARGS="--no-ee --limit 200"
tables-real:
	$(PY) -m doppelgrund.real $(ARGS)

# Interim tables (needs scaler, clusters, novelty, layers and real textures too; see export/bundle.py) -> web bundle.
bundle:
	$(PY) -m doppelgrund.export.bundle --interim data/interim/real --out web/public/data --clean

dev:
	cd web && $(NPM_RUN) dev

build:
	cd web && $(NPM_RUN) build

preview:
	cd web && $(NPM_RUN) preview
