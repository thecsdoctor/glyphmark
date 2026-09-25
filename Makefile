# GlyphMark — one place for every task CI runs.
# Run `make help` (the default target) to see the list.

UV      ?= uv
PORT    ?= 8123
HOST    ?= 127.0.0.1
PYTEST  ?= $(UV) run pytest
GM      := $(UV) run glyphmark

.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help bootstrap sync test test-fast lint fmt ui ui-smoke docs docs-check docs-serve \
        verify clean check serve ci release-check

help: ## Show this help
	@echo "GlyphMark - make targets"
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "  prerequisites: uv (https://docs.astral.sh/uv/), node only for 'make ui-smoke'"

bootstrap: ## Install every dependency (runtime, dev, docs) + the dev-only npm deps
	$(UV) sync --extra dev --extra docs
	@command -v npm >/dev/null && npm ci || echo "npm not found - skipping the jsdom UI test dependency"

sync: ## Re-resolve and install the locked dependency set
	$(UV) sync --frozen --extra dev --extra docs

test: ## Run the whole test suite
	$(PYTEST)

test-fast: ## Run the suite, stopping at the first failure, no coverage chatter
	$(PYTEST) -x -q

lint: ## ruff check + SPDX licence headers + JS syntax
	$(UV) run ruff check src tests tools
	$(UV) run ruff format --check src tests tools
	$(UV) run python tools/check_license_headers.py
	node --check src/glyphmark/web/static/app.js

fmt: ## Format Python the way CI expects it
	$(UV) run ruff format src tests tools
	$(UV) run python tools/check_license_headers.py --fix

ui: ## Serve the lab UI + API on http://$(HOST):$(PORT) (docs must be built for /docs/)
	$(MAKE) docs
	$(GM) serve --host $(HOST) --port $(PORT)

ui-smoke: ## Headless DOM tests against a server already running on $(PORT)
	GM_BASE=http://$(HOST):$(PORT) node tools/ui_smoke.mjs

docs: ## Build the documentation (served at /docs/ by 'make ui')
	$(GM) docs build --strict

docs-check: ## Strict build in a temp dir; fails on warnings or broken links (CI gate)
	$(GM) docs check --strict

docs-serve: ## Live-reload docs on :8000 while you edit docs/*.md (mkdocs, not the app)
	$(UV) run python -m mkdocs serve -a 127.0.0.1:8000

verify: ## Encode+extract round trip for every channel on this interpreter
	$(GM) verify

clean: ## Remove build output and caches
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache coverage.xml
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

check: ## Everything CI runs, locally
	$(MAKE) lint
	$(MAKE) verify
	$(UV) lock --check
	$(MAKE) test
	$(MAKE) docs-check

ci: check ## Alias of 'check', for muscle memory

release-check: ## Build release artefacts locally into dist/ (no publishing)
	$(UV) build --out-dir dist
	ls -l dist
