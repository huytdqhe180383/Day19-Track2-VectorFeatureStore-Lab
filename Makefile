## Day 19 — Vector Store + Feature Store lab.
## Two paths: lightweight (default, no Docker) and full Docker.

VENV     := .venv
ifeq ($(OS),Windows_NT)
PY       := $(VENV)/Scripts/python.exe
SETUP_LITE := powershell -NoProfile -ExecutionPolicy Bypass -File setup-lite.ps1
SETUP_DOCKER := powershell -NoProfile -ExecutionPolicy Bypass -File setup-docker.ps1
CLEAN_LITE := powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item -Recurse -Force .venv, data/corpus_vn.jsonl, data/golden_set.jsonl, data/qdrant_storage, app/feast_repo/data, app/feast_repo/registry.db, app/feast_repo/online_store.db, notebooks/*.ipynb, notebooks/.ipynb_checkpoints -ErrorAction SilentlyContinue"
else
PY       := $(VENV)/bin/python
SETUP_LITE := bash setup-lite.sh
SETUP_DOCKER := bash setup-docker.sh
CLEAN_LITE := rm -rf $(VENV) data/corpus_vn.jsonl data/golden_set.jsonl data/qdrant_storage \
	app/feast_repo/data app/feast_repo/registry.db app/feast_repo/online_store.db \
	notebooks/*.ipynb notebooks/.ipynb_checkpoints
endif
PIP      := $(PY) -m pip
JUPYTER  := $(PY) -m jupyter
JUPYTEXT := $(PY) -m jupytext
UVICORN  := $(PY) -m uvicorn
PYTEST   := $(PY) -m pytest

.DEFAULT_GOAL := help

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nLightweight path (default):\n"} \
	      /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ─────────────────────────────────────────────────────────────
# Lightweight path (default) — no Docker, in-process Qdrant
# ─────────────────────────────────────────────────────────────

setup-lite: ## [lite] Create venv + install + seed corpus + smoke test
	@$(SETUP_LITE)

verify-lite: ## [lite] 5-second smoke test (Qdrant memory + BM25 + Feast SQLite)
	@$(PY) scripts/verify_lite.py

seed: ## [both] (Re)generate data/corpus_vn.jsonl + data/golden_set.jsonl
	@$(PY) scripts/seed_corpus.py

api: ## [lite] Start FastAPI /search on http://localhost:8000
	@$(UVICORN) app.main:app --reload --port 8000

lab: ## [lite] Open Jupyter Lab on http://localhost:8888
	@$(JUPYTEXT) --to notebook --update notebooks/*.py 2>/dev/null || true
	@$(JUPYTER) lab --notebook-dir=notebooks --ServerApp.token='' --no-browser

benchmark: ## [both] Precision@10 (keyword/semantic/hybrid) + P99 latency table
	@$(PY) scripts/benchmark.py

test: ## [both] Run pytest (app + scripts)
	@$(PYTEST) -q

clean-lite: ## [lite] Wipe venv + data + Feast registry
	@$(CLEAN_LITE)

# ─────────────────────────────────────────────────────────────
# Docker path (full stack: Qdrant + Redis + Postgres)
# ─────────────────────────────────────────────────────────────

setup-docker: ## [docker] Bring up Docker stack + venv + seed + smoke test
	@$(SETUP_DOCKER)

verify-docker: ## [docker] Verify all 3 services reachable + Feast wired
	@$(PY) scripts/verify_docker.py

docker-up: ## [docker] Just bring services up (no venv changes)
	docker compose up -d

docker-down: ## [docker] Stop services (data persists)
	docker compose down

docker-clean: ## [docker] Stop AND wipe Qdrant + Redis + Postgres volumes
	docker compose down -v

.PHONY: help setup-lite verify-lite seed api lab benchmark test clean-lite \
        setup-docker verify-docker docker-up docker-down docker-clean
