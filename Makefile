.PHONY: install run test lint check

install:
	uv sync

run:
	uv run uvicorn assistant.api.app:app --reload --port 8000

test:
	uv run pytest tests/ --tb=short

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright

check: lint test
