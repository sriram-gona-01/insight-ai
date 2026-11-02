# Insight AI

A self-hosted question-answering system over slide decks and PDFs, being rebuilt as v1.

**What works today:** ingestion. Each PPTX or PDF is rendered to one PNG per slide, its text,
tables, chart data, and speaker notes are extracted and embedded, and everything is stored in
Postgres with pgvector. Searching and answering questions are not built yet.

## Run it

Requires [uv](https://docs.astral.sh/uv/), `make`, Docker, and LibreOffice for PPTX files
(`brew install --cask libreoffice` on macOS). The first ingest downloads the embedding model.

```bash
cp .env.example .env
uv sync
make db
uv run insight db init
uv run insight ingest path/to/deck.pptx path/to/report.pdf
uv run insight docs list
```

Ingesting the same file again does nothing, because documents are identified by content hash.
Decks and rendered pages are stored under `data/`, which git ignores.

## Run the tests

```bash
make lint test
make test-integration
```

Integration tests need `make db` running and LibreOffice installed.

## Limitations

- Only `.pptx` and `.pdf` are accepted, up to 200 MB by default.
- Slide reading order is geometric (top, then left), so unusual layouts may read out of order.
- Charts that are pictures, and all charts in PDFs, yield no structured data.
- Scanned PDFs yield no text, because there is no OCR.
- Hidden PPTX slides are skipped.

## License

MIT
