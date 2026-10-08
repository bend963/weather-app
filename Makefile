# One-command workflows. `make help` lists them.
SHELL := /bin/bash
.DEFAULT_GOAL := help

DATABASE_URL ?= postgresql+psycopg://postgres:postgres@localhost:5432/weather
TEST_DATABASE_URL ?= postgresql+psycopg://postgres:postgres@localhost:5432/weather_test

.PHONY: help setup dev dev-down dev-local migrate ingest test test-api test-worker test-web e2e lint format typecheck build types docker-build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install Python (uv) and Node dependencies
	uv sync
	npm ci

dev: ## Start Postgres, API, ingestion and web with Docker (http://localhost:3000)
	docker compose up --build

dev-down: ## Stop the Docker dev stack (keeps the database volume)
	docker compose down

dev-local: ## Run API + web without Docker (needs a local Postgres at DATABASE_URL)
	cd apps/api && DATABASE_URL=$(DATABASE_URL) uv run alembic upgrade head
	DATABASE_URL=$(DATABASE_URL) uv run forecast-ingestion run
	trap 'kill 0' EXIT; \
	DATABASE_URL=$(DATABASE_URL) uv run uvicorn weather_api.app:app --reload --port 8000 & \
	API_ORIGIN=http://localhost:8000 npm run dev -w @weather/web & \
	wait

migrate: ## Apply database migrations
	cd apps/api && DATABASE_URL=$(DATABASE_URL) uv run alembic upgrade head

ingest: ## Run forecast ingestion once
	DATABASE_URL=$(DATABASE_URL) uv run forecast-ingestion run

test: test-api test-worker test-web ## Run all unit/integration tests

test-api: ## Backend tests (needs Postgres; uses TEST_DATABASE_URL)
	cd apps/api && TEST_DATABASE_URL=$(TEST_DATABASE_URL) uv run pytest

test-worker: ## Worker tests
	cd workers/forecast-ingestion && TEST_DATABASE_URL=$(TEST_DATABASE_URL) uv run pytest

test-web: ## Frontend unit tests (Vitest + React Testing Library)
	npm test

e2e: ## Playwright end-to-end tests (needs Postgres; database weather_e2e)
	npm run e2e

lint: ## Lint Python and TypeScript
	uv run ruff check .
	uv run ruff format --check .
	npm run lint

format: ## Auto-format Python
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Type-check Python and TypeScript
	uv run mypy apps/api/src workers/forecast-ingestion/src
	npm run typecheck

build: ## Production build of the web app
	npm run build

types: ## Regenerate TypeScript API types from the FastAPI schema
	npm run types:generate

docker-build: ## Build the API and worker images
	docker build -f apps/api/Dockerfile -t weather-api .
	docker build -f workers/forecast-ingestion/Dockerfile -t forecast-ingestion .

clean: ## Remove build artifacts
	rm -rf apps/web/.next apps/web/test-results apps/web/playwright-report
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
