lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest -m integration

db:
	docker compose up -d --wait db

.PHONY: lint test test-integration db
