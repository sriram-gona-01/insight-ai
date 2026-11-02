lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest -m integration

db:
	docker compose up -d --wait db

up:
	docker compose up -d --build --wait

down:
	docker compose down

ingest-sample:
	docker compose exec -T api insight ingest samples/northwind_kites_q3.pptx

.PHONY: lint test test-integration db up down ingest-sample
