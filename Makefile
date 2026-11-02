lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest -m "not integration"

.PHONY: lint test
