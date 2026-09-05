.PHONY: install seed scrape index run test lint check

install:
	uv sync

seed:
	uv run python manage.py seed

scrape:
	uv run python manage.py scrape

index:
	uv run python manage.py build-index

run:
	uv run uvicorn assistant.api.app:app --reload --port 8000

test:
	uv run pytest tests/ --tb=short

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright

check: lint test
