# Insight AI

A self-hosted question-answering system over slide decks and PDFs, being rebuilt as v1.

**[Try the demo](https://sriram-gona-01.github.io/insight-ai/)**: recorded answers from a sample
deck about a fictional company. The page doesn't run a model, so you can't ask new questions there.

**What works today:** ingesting PPTX and PDF files, and answering questions over them through an
HTTP API, with citations to the slides used. Answers come from a local vision model through Ollama,
which sees the slide images as well as their text. The Docker setup and the Streamlit UI are written
but haven't been run end to end yet, so the steps below don't use them.

## Run it

Requires [uv](https://docs.astral.sh/uv/), `make`, Docker for the database,
[Ollama](https://ollama.com) 0.40 or newer, and LibreOffice for PPTX files
(`brew install --cask libreoffice` on macOS). The first ingest downloads the embedding model.

```bash
cp .env.example .env
uv sync
ollama pull qwen3-vl:4b
make db
uv run insight db init
uv run insight ingest samples/northwind_kites_q3.pptx
uv run uvicorn --factory insight.api.app:app --host 127.0.0.1 --port 8000
```

Then, in a second terminal:

```bash
curl -s localhost:8000/query -H 'Content-Type: application/json' -d '{"question": "What was revenue in Q2 2026?"}'
```

Ingesting the same file again does nothing, because documents are identified by content hash.
Decks and rendered pages are stored under `data/`, which git ignores.

## Speed

On an Apple M1 with 16 GB of RAM, using `qwen3-vl:4b` and 3 slides of context, each answer took
32 to 46 seconds in the recorded demo. Nearly all of that is the model.

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
- Only text retrieval exists, so a question can fail if the slide it needs isn't retrieved. In the
  demo, the question comparing Q3 revenue with Q4 guidance gets "Not found in the documents"
  because the guidance slide isn't among the 3 retrieved.
- There is no authentication, so keep the API on localhost.

## License

MIT
