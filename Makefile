.PHONY: install seed scrape index evaluate run ui dev tmux test lint check

install:
	uv sync

seed:
	uv run python manage.py seed

scrape:
	uv run python manage.py scrape

index:
	uv run python manage.py build-index

evaluate:
	uv run python manage.py evaluate

run:
	uv run uvicorn assistant.api.app:app --reload --port 8000

ui:
	uv run streamlit run app.py

dev:
	trap 'kill 0' EXIT; \
	uv run uvicorn assistant.api.app:app --reload --port 8000 & \
	uv run streamlit run app.py

tmux:
	uvx tmuxp load assistant_tmux.yaml

test:
	uv run pytest tests/ --tb=short

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright

check: lint test
