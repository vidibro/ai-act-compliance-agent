# Developer commands. `make check` is the single gate: lint + types + tests.
# Tools are run from the project venv so no activation is needed.

VENV   := .venv
RUFF   := $(VENV)/bin/ruff
MYPY   := $(VENV)/bin/mypy
PYTEST := $(VENV)/bin/pytest

TARGETS := src tests scripts

.PHONY: check lint format types test ui app

check: lint types test  ## run everything: lint, type-check, tests

lint:   ## ruff lint
	$(RUFF) check $(TARGETS)

format: ## ruff auto-format
	$(RUFF) format $(TARGETS)

types:  ## mypy type + protocol-conformance check
	$(MYPY)

test:   ## pytest
	$(PYTEST) -q

ui:     ## coverage UI at http://127.0.0.1:8765, live on data and code edits
	$(VENV)/bin/uvicorn aiact.ui.app:app --port 8765 --reload --reload-dir src/aiact

app:    ## report app at http://127.0.0.1:8766 (model keys from .env)
	$(VENV)/bin/uvicorn aiact.report_app.app:app --port 8766 --reload --reload-dir src/aiact
