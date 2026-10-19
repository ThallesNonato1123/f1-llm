PNPM := $(shell command -v pnpm 2>/dev/null || echo "npx pnpm@10.34.3")

.PHONY: install test test-integration api dev build run

install:
	uv sync
	cd frontend && $(PNPM) install

test:
	uv run pytest

test-integration:
	uv run pytest -m integration -v

api:
	uv run uvicorn f1llm.api.app:app --reload

dev:
	cd frontend && $(PNPM) dev

build:
	cd frontend && $(PNPM) build

run: build api
