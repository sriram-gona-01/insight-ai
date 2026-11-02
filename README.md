# Insight AI

A self-hosted question-answering system over slide decks and PDFs, being rebuilt as v1.

The earlier prototype did not run end to end, so it has been removed (git history keeps
it). This repository currently contains project tooling only: no ingestion, retrieval, or
answering yet. This page describes only what exists today.

## Run the tests

Requires [uv](https://docs.astral.sh/uv/) and `make`.

```bash
uv sync
make lint test
uv run insight --help
```

## License

MIT
