# Decisions

## 2026-11-01: Environment

macOS 15.5 (24F74), Apple M1, 16 GB RAM, about 57 GB free. Python 3.11.13 (Homebrew),
uv 0.13.6, Docker client 28.2.2 (daemon not running at the time of checking), Ollama 0.12.9.
LibreOffice is not installed yet.

## 2026-11-01: Bugs found in the prototype

Read from commit `1f4bf81`. The prototype is removed; these are not carried forward.

Listed in the spec, all confirmed:

1. `/upload` calls `summarize_image` on chunk text, but that function expects an image path.
2. `/upload` calls `build_index(conn, docs, embeddings)`; the signature is `build_index(file_path)`.
3. Chunk IDs such as `s1_txt0` restart per file, so a second file overwrites the first.
4. `msmarco-bert-base-dot-v5` is a dot-product model, but search uses cosine distance.
5. `DATABASE_URL` is hardcoded in three modules.
6. The Dockerfile is named `docker`, so `build: .` in compose can't find it.
7. Compose uses `postgres:14`, which has no pgvector.
8. The README claims hybrid retrieval and MMR; only dense search exists.
9. The UI accepts `.txt`, but the extractor rejects it.
10. `/tmp/{file.filename}` allows path traversal through the upload filename.
11. Models reload on each request, and `/query` runs retrieval twice.

Also found:

12. Compose sets no `POSTGRES_PASSWORD`, so the database container won't start.
13. The hardcoded URL points at `localhost`, which is the wrong host from inside a container.
14. The README documents `app/settings.py`, which doesn't exist.

## 2026-11-01: Facts verified so far (spec §3)

- **Ollama images (§3.1):** `/api/chat` takes an `images` array of base64 strings on a message
  (docs.ollama.com/capabilities/vision, read 2026-11-01). Tool calling and structured output
  are checked in the milestones that use them.
- **Installed vision models (§3.1, §3.3):** `/api/show` reports `qwen2.5vl:3b` and
  `qwen2.5vl:latest` as `completion` and `vision`, without `tools`. M7 needs a model that has
  `tools`, or a decision from the project owner.

The other §3 facts are checked and recorded here before the milestone that depends on them.

## 2026-11-01: Deviations from the spec

- **Web demo added.** The project owner asked for a clickable URL. It is a static GitHub Pages
  replay of real captured answers, labelled as recorded, first published in M2 and refreshed
  in M6 and M10. A live public app was rejected: it needs a paid server running a vision model
  and open uploads without auth, which the spec excludes. `BUILD_SPEC.md` is amended to match.
- **Employer name removed from `BUILD_SPEC.md`,** because this repository is public. The rule
  itself is unchanged.
- **CLI in M0 has one real command (`version`).** Spec M0 asks for a CLI stub, and §4 forbids
  stubs. Other commands arrive with the milestones that implement them.
- **Makefile targets arrive with their milestones,** for the same reason. M0 has `lint` and `test`.

## 2026-11-01: Facts verified for M1 (spec §3)

- **pgvector (§3.4):** image `pgvector/pgvector:0.8.7-pg17-trixie`, PostgreSQL 17.11, extension
  0.8.7. HNSW built on `vector(384)` and on `halfvec(3000)` here. The project docs give HNSW
  limits of 2,000 dims for `vector` and 4,000 for `halfvec`. Tag pinned rather than `pg18`
  because pg18's data-directory behaviour in the image has not been checked.
- **PPTX rendering (§3.5):** LibreOffice 26.8.2.2 from `brew install --cask libreoffice`,
  converted a generated PPTX headless, and pypdfium2 5.14.0 rasterized it. The Docker image is
  checked in M2. CI runs the same path on Ubuntu with `libreoffice-impress`.
- **LibreOffice drops hidden slides from its PDF.** Confirmed by the integration test.
  Extraction skips them too, so slide numbers match images, and ingest fails if counts differ.

## 2026-11-01: M1 choices

- **Text embedder:** `BAAI/bge-small-en-v1.5`, 384 dims, MIT, revision
  `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, run with sentence-transformers 6.2.0 on PyTorch.
  PyTorch is needed by the reranker and visual model later, so this keeps one ML stack. The cost
  is a virtual environment of about 950 MB.
- **Title prefix (spec addition):** a chunk's embedded text starts with its slide title, since
  a bare table or chart often doesn't say what it is about. `CHUNK_TITLE_PREFIX` turns it off,
  and the stored chunk text stays the raw block.
- **PDF tables:** text in a detected table is removed from the page text and stored only as a
  markdown table, so numbers aren't indexed twice. A detected table needs at least 2 rows and 2
  columns, because pdfplumber also reports single bordered boxes as tables.
- **Database port 5433:** this machine already runs a native Postgres on 5432. The compose
  database binds to localhost only, and `DB_PORT` changes the port.
- **`ingest/chunk.py` added to the §5 layout,** to keep splitting separate from extraction.
- **`updated_at` and `INGEST_STALE_MINUTES` added.** Without them, a process killed mid-ingest
  would leave a document unfinished, and re-ingesting would skip it forever.
- **Slide `image_path` is relative to `DATA_DIR`,** so paths work on the host and in containers.

## 2026-11-02: M2 facts and deferrals

- **Ollama upgraded to 0.40.13.** 0.12.9 got a 412 pulling `qwen3-vl`, despite the library page
  listing 0.12.7 as the minimum. `/api/show` reports `vision`, `tools`, and `thinking` for
  `qwen3-vl:4b` and `:8b`. `/api/chat` takes base64 `images`, and `options.num_ctx` sets context.
- **Context size:** 5 slides needed about 5,700 tokens, above the default 4,096, so
  `LLM_CONTEXT_TOKENS` defaults to 16,384.
- **Query instruction:** bge queries use "Represent this sentence for searching relevant
  passages: ", from the model card.
- **Timing (informal, not an evaluation):** on the Apple M1, `qwen3-vl:4b` with top-k 3 took 32 to
  46 s to generate each of 7 demo answers. Search took under 40 ms.
- **Deferred at the project owner's request, 2026-11-02,** to publish the URL first. These M2
  verification items in the spec are not done:
  - Comparing `qwen3-vl:4b` with `:8b`. `:4b` and top-k 3 are provisional. The spec's top-k 5 was
    not timed end to end after the context fix.
  - Building the Docker image, and the fresh-clone `make up && make ingest-sample` check. The
    README doesn't document them until this passes.
  - Opening the Streamlit UI in a browser.
- **Demo recording:** real answers from the API running natively, not in Docker, at commit
  `71eda97`. One of 7 questions, comparing Q3 with Q4 guidance, abstains because slide 7 isn't
  retrieved at top-k 3. It stays in the demo as recorded.
