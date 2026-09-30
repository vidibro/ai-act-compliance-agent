# Developer commands. `make check` is the single gate: lint + types + tests.
# Tools are run from the project venv so no activation is needed.

VENV   := .venv
RUFF   := $(VENV)/bin/ruff
MYPY   := $(VENV)/bin/mypy
PYTEST := $(VENV)/bin/pytest

TARGETS := src tests scripts

.PHONY: check lint format types test ui

check: lint types test  ## run everything: lint, type-check, tests

lint:   ## ruff lint
	$(RUFF) check $(TARGETS)

format: ## ruff auto-format
	$(RUFF) format $(TARGETS)

types:  ## mypy type + protocol-conformance check
	$(MYPY)

test:   ## pytest
	$(PYTEST) -q

ui:     ## coverage map at http://127.0.0.1:8765
	$(VENV)/bin/uvicorn aiact.ui.app:app --port 8765
