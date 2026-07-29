# Akaion Runner — developer entry points.
#
# Everything here works offline. `make demo` runs a real agentic loop with real
# tool execution and no credentials, which is the fastest way to see what this
# repository actually does.

PY  := env/bin/python
PIP := env/bin/pip

.DEFAULT_GOAL := help
.PHONY: help setup test test-cov lint format typecheck contracts check demo run docs docs-serve clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Create the venv and install runtime + dev dependencies
	@test -d env || python3 -m venv env
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements-dev.txt
	$(PIP) install --quiet -e .
	@echo "ready — try 'make demo' or 'make check'"

test: ## Run the test suite
	$(PY) -m pytest

test-cov: ## Run the test suite with a coverage report
	$(PY) -m pytest --cov=runner --cov-report=term-missing --cov-report=html

lint: ## Lint (ruff)
	$(PY) -m ruff check runner tests

format: ## Format (ruff)
	$(PY) -m ruff format runner tests
	$(PY) -m ruff check --fix runner tests

typecheck: ## Static types (mypy)
	$(PY) -m mypy

contracts: ## Verify the architectural import contracts
	env/bin/lint-imports

check: lint typecheck contracts test ## Everything CI runs

demo: ## Offline end-to-end agentic run: no credentials, no network
	$(PY) -m runner.demo

run: ## Start the daemon and local UI on 127.0.0.1:7070
	./start.sh

docs: ## Build the documentation site
	$(PY) -m mkdocs build --strict

docs-serve: ## Serve the documentation site with live reload
	$(PY) -m mkdocs serve

clean: ## Remove build and test artefacts
	rm -rf build dist htmlcov .coverage .pytest_cache .mypy_cache .ruff_cache site
	find . -type d -name __pycache__ -not -path "./env/*" -exec rm -rf {} +
