# Insight AI v1: build spec

> **For Claude Code.** Read this whole file before writing any code. Work milestone by
> milestone (M0 → M10). At the start of each milestone use plan mode: show me the plan
> and the 2–3 decisions that matter most, and let me choose before you build. Work on a
> branch per milestone (`m<N>-<slug>`), open a PR, and merge after I approve; the merge
> commit uses the message given. Stop and ask me whenever something here conflicts with
> the existing code, the official docs, or what you observe on this machine.

---

## 1. What we are building

**Insight AI** is a self-hosted question-answering system over slide decks and PDFs that
are full of charts, tables, and diagrams: earnings decks, dashboards, architecture
reviews. It runs on your own machine, or on GPUs you rent (a RunPod H100 running vLLM).
No third-party AI APIs are called.

The repo already has a prototype (FastAPI + Streamlit + pgvector + Ollama). It does not
run end to end today, and the README claims features that don't exist. v1 replaces it
with a working system **and a measured answer to one design question**:

> **For visually dense decks, what retrieves better: extracting the text from each slide,
> or embedding the slide image directly? Does combining them beat both? And what does
> each option cost?**

**Headline deliverable:** a results table in the README comparing retrieval pipelines on a
labeled question set, broken down by question type (text, table, chart, diagram,
multi-slide, unanswerable), with latency and storage next to quality.

**Primary metrics:** slide-level Recall@5 (retrieval) and answer accuracy (generation).
**Guardrails:** citation accuracy, correct abstention on unanswerable questions, p95 query
latency, ingestion seconds per slide.

**Who this is for:** hiring managers for applied AI engineer roles (agents, inference,
system design). The repo must be cloneable and runnable in one command, honest about
what it does, and reproducible.

**Out of scope for v1 (decided, not deferred):** vision-model captioning of slides,
inference performance benchmarks, a demo video/GIF, serverless deployment, auth and
multi-tenancy. None of these appear in the code, README, or docs as "coming soon".

---

## 2. Working with me (I'm learning while we build)

I'm using this project to learn RAG, evaluation, agents, MCP, and inference serving. So:

- **At the start of each milestone:** in plan mode, explain in a few sentences the core
  concept the milestone depends on (e.g. why late interaction differs from single-vector
  retrieval), then the plan and the key decisions with your recommendation.
- **At the end of each milestone:** write `docs/learning/M<N>.md` (under 60 lines): what
  was built, the decisions made and why, what surprised us, and **3 questions for me to
  answer** about it. Don't answer them.
- **Keep code readable over clever.** Prefer small modules with plain functions and type
  hints. No framework where 50 lines of our own code are clearer (this especially applies
  to the agent loop in M7).
- **The eval questions are mine.** In M4 you may draft candidate questions, but I review,
  edit, and label every one. Never generate gold answers without my review.

---

## 3. Facts to verify before relying on them

These change between versions. Before building anything that depends on one, check the
official docs and what's actually installed. Record what you found (with versions and
dates) in `docs/decisions.md`.

1. **Ollama HTTP API:** `/api/chat` accepts base64 images for vision models and supports
   tool calling for some models. Confirm the current request format, which installed
   models support images and tools, and the structured-output option.
2. **Ollama in Docker on macOS has no GPU access.** On a Mac, Ollama should run natively
   and containers reach it via `http://host.docker.internal:11434`. Confirm and design the
   compose file around it (an `ollama` service behind a Linux/GPU profile only).
3. **Current models.** Pick defaults from what is current and runs on my Mac:
   - a vision-language model for answer generation and the agent (Qwen-VL family or newer,
     with tool-calling support in Ollama),
   - a text embedding model (start from `BAAI/bge-small-en-v1.5` unless something newer
     and small is clearly better),
   - a cross-encoder reranker (bge-reranker family or similar),
   - a ColPali-family visual retriever (ColQwen or newer) that runs on Apple Silicon
     (MPS) at acceptable speed, and the current `colpali-engine` API.
   Record each choice with its size, license, and why.
4. **pgvector:** installed version, HNSW support, max indexed dimensions, `halfvec`
   availability. Use the `pgvector/pgvector` Docker image, not plain `postgres`.
5. **PPTX rendering:** LibreOffice headless (`soffice --headless --convert-to pdf`) then
   rasterize with `pypdfium2`. Confirm it works on macOS (`brew install --cask libreoffice`)
   and in the Docker image. Do **not** use PyMuPDF (AGPL).
6. **MCP Python SDK** (M8): current package name, server API, and transport options.
7. **vLLM and RunPod** (M9): whether vLLM serves the chosen VLM, its OpenAI-compatible
   API for image inputs, the `vllm serve` flags we need (`--api-key`, `--max-model-len`,
   multimodal limits, dtype), RunPod's current way to create/stop/terminate a GPU Pod
   from the CLI or API, how a Pod exposes an HTTP port (proxy URL format), and how to
   persist the Hugging Face model cache (network volume).

Also record: OS, chip/GPU, RAM, Python version, Docker version.

---

## 4. Rules for this build

- **No deferred work.** Every item in this spec ships in v1, or it is listed as out of
  scope in §1. No `TODO`, `FIXME`, placeholders, stub endpoints, or "coming soon" in code,
  README, or docs. If something can't be finished, stop and ask me; don't leave it half done.
- **Python 3.11+, `uv`, `ruff`, `pytest`, GitHub Actions CI.** Pin dependencies via the
  lockfile. Remove unused dependencies (`langchain` and `transformers` as direct deps
  unless actually used).
- **No hardcoded config.** Everything (DB URL, model names, LLM backend and endpoint,
  API keys, dims, top-k, paths) lives in `src/insight/config.py` (pydantic-settings) and
  is read from env / `.env`. Ship `.env.example`. Never commit `.env` or any key.
- **Never claim what isn't built.** The README only describes what works and has been
  measured. Known gaps go under "Limitations". There is no "Roadmap" section.
- **No documents in git.** Eval decks are downloaded by a script from a manifest (URL +
  sha256). Commit only questions, labels, configs, and aggregated results.
- **Don't use any material from my employer**, including its public decks.
  Use other companies' public investor material.
- **Security basics:** sanitize upload filenames (store by content hash, never by user
  filename), enforce size and type limits, never put user text into a shell command,
  parameterize all SQL, and never expose a vLLM server without an API key.
- **Models load once per process** (cached singletons), not per request.
- **Same generator and prompt across retrieval comparisons**, so we measure retrieval,
  not prompt luck. Generation runs with temperature 0 and a fixed seed where supported.
- **Everything runs on my Mac except M9.** Eval runs use local Ollama and local
  embedders. Keep them affordable: retrieval metrics run for every config (no LLM calls);
  generation and judging run only for the configs named in each milestone.
- **Tests:** unit tests for parsing, chunking, fusion, metrics, the calculator tool, and
  the LLM clients (against a mocked HTTP server), using synthetic fixtures (generate small
  PPTX/PDF fixtures in code with `python-pptx` and `reportlab`). DB and model integration
  tests are marked `@pytest.mark.integration` and run in CI against a `pgvector/pgvector`
  service container, with tiny or mocked models.
- **Every result is reproducible:** results files record git SHA, models (name, revision,
  quantization), hardware, settings, dataset version, and date.

---

## 5. Target layout

```
insight-ai/
├── CLAUDE.md                     # lean: purpose, commands, pointers to docs/
├── BUILD_SPEC.md                 # this file
├── README.md
├── LICENSE                       # MIT
├── pyproject.toml / uv.lock
├── .env.example
├── Dockerfile                    # api + ui image (includes LibreOffice)
├── docker-compose.yml            # db, api, ui; `ollama` under a linux-gpu profile
├── Makefile                      # up, down, test, lint, ingest-sample, eval, screenshots
├── src/insight/
│   ├── config.py                 # pydantic-settings
│   ├── models.py                 # Document, Slide, Chunk, Answer, Citation dataclasses
│   ├── cli.py                    # `insight` CLI (typer): db init, ingest, ask, eval, stats
│   ├── ingest/
│   │   ├── render.py             # PPTX→PDF→PNG per slide; PDF→PNG per page
│   │   ├── extract.py            # text frames, tables→markdown, chart data→table, notes
│   │   └── pipeline.py           # idempotent ingest job (by sha256), status tracking
│   ├── embed/
│   │   ├── text.py               # text embedder (normalized vectors)
│   │   └── visual.py             # ColPali-family multi-vector embedder + pooling
│   ├── store/
│   │   ├── schema.sql            # templated with embedding dims
│   │   └── db.py                 # connection pool, repositories
│   ├── retrieve/
│   │   ├── dense.py              # pgvector cosine search over text chunks
│   │   ├── lexical.py            # Postgres full-text (tsvector) search
│   │   ├── visual.py             # pooled-vector candidates → MaxSim rerank
│   │   ├── fusion.py             # reciprocal rank fusion
│   │   ├── rerank.py             # cross-encoder rerank
│   │   └── pipelines.py          # named pipelines A–C (see §6) from config
│   ├── generate/
│   │   ├── llm.py                # LLMClient: OllamaClient, OpenAICompatClient (vLLM)
│   │   ├── prompts.py
│   │   └── answer.py             # context assembly (text / image / both), citations, abstain
│   ├── agent/
│   │   ├── tools.py              # search_slides, get_slide, get_chart_data, calculate
│   │   └── loop.py               # plain tool-calling loop with step limit + trace
│   ├── mcp_server.py
│   ├── api/app.py                # FastAPI
│   └── ui/streamlit_app.py
├── eval/
│   ├── configs/                  # one YAML per pipeline config
│   ├── datasets/manifest.yaml    # decks: id, company, url, sha256, license/terms note
│   ├── datasets/questions.jsonl  # my labeled questions (schema in M4)
│   ├── download.py
│   ├── metrics.py
│   ├── judge.py
│   ├── run.py                    # runs configs × questions → runs/<id>.jsonl
│   └── report.py                 # → results/*.md + charts
├── deploy/runpod/                # vLLM on a RunPod GPU Pod (M9)
│   ├── README.md                 # step-by-step from zero, incl. account + API key
│   ├── pod.env.example
│   ├── create_pod.sh / stop_pod.sh / terminate_pod.sh
│   ├── serve.sh                  # the exact `vllm serve` command run inside the pod
│   └── smoke_test.py             # text + image request, then a full Insight AI answer
├── demo/                         # static GitHub Pages replay of captured answers
├── scripts/screenshots.py        # Playwright: drives the UI, saves README screenshots
├── results/                      # aggregated, committed results only
├── docs/
│   ├── architecture.md           # with a Mermaid diagram
│   ├── decisions.md              # dated decision log (ADR-lite)
│   ├── images/                   # generated screenshots
│   ├── learning/                 # M<N>.md notes for me
│   └── writeup.md                # final technical writeup
├── tests/
└── data/                         # gitignored: decks, rendered pages, runs
```

---

## 6. The pipelines we compare

The **retrieval unit is the slide** (a PDF page counts as a slide). Chunks within a slide
map back to it, and results are deduplicated to slides before scoring. Gold labels are
slide IDs.

| ID | Name | What gets indexed | How it's searched |
|---|---|---|---|
| **A** | Text | Extracted slide text, tables as markdown, chart series as tables, speaker notes | Dense (text embeddings) |
| **B** | Visual | Rendered slide images, ColPali-family multi-vector embeddings | Pooled-vector candidates, then MaxSim |
| **C** | Hybrid | Both of the above, plus lexical over slide text | RRF over (A dense, lexical, B), then cross-encoder rerank |

Intermediate ablations the runner expresses by config: A + lexical (RRF),
A + lexical + rerank, C without rerank.

**A second axis: context format for generation.** After retrieval, the top-k slides are
passed to the generator as `text`, `image`, or `both`. Default comparisons hold this
fixed (`both`); one experiment in M6 varies it with the best retriever.

---

## 7. Milestones

### M0: Repo reset and hygiene
- Read the existing code and README. Record in `docs/decisions.md` the bugs found (at
  least: `/upload` calls `summarize_image` on text and calls `build_index` with the wrong
  signature; chunk IDs collide across files; dot-product embedding model used with cosine
  distance; hardcoded DB URL; Dockerfile named `docker`; compose lacks pgvector; README
  claims hybrid + MMR; `.txt` accepted by UI but rejected by extractor; `/tmp/{filename}`
  path traversal; models reloaded per request; retrieval run twice per query).
- Set up `uv`, `ruff`, `pytest`, the `insight` CLI stub, `Makefile`, MIT `LICENSE`,
  `.gitignore` (`data/`, `.env`, `.venv/`, caches, `runs/`, `deploy/runpod/pod.env`),
  `.env.example`, lean `CLAUDE.md`, `docs/decisions.md` with the §3 facts verified so far.
- CI workflow: ruff + unit tests on every push/PR.
- Remove the old `app/` code (git history keeps it).
- Rewrite the README as a short, honest page: what it is, that v1 is being rebuilt, and
  how to run tests. No feature claims yet.
- **Acceptance:** `uv run insight --help` works; `make lint test` passes; CI is green.
- **Commit:** `M0: reset repo, tooling, CI, honest README`

### M1: Ingestion and storage
- `render.py`: PPTX → PDF via LibreOffice → PNG per slide (configurable DPI); PDF → PNG
  per page. Images stored at `data/pages/<doc_sha>/<n>.png`.
- `extract.py`: per slide: text frames in reading order, tables → markdown, chart
  categories/series → markdown table with series names, speaker notes. PDF: page text via
  `pdfplumber`, tables via `pdfplumber` where detected.
- Schema: `documents` (id, filename, sha256 unique, n_slides, status, error, created_at),
  `slides` (id, doc_id, slide_no, image_path, text, tsv generated column),
  `chunks` (id, slide_id, kind, text, embedding vector(dim)), with an HNSW index.
  Visual tables come in M6.
- `pipeline.py`: idempotent ingest (same sha256 → skip), status transitions
  (`queued → rendering → extracting → embedding → ready | failed`).
- Chunking: one chunk per text block / table / chart / notes, split if over a token
  limit; chunk IDs are UUIDs; every chunk carries `slide_id`.
- CLI: `insight db init`, `insight ingest <path>...`, `insight docs list`.
- **Acceptance:** ingesting two different decks keeps both intact (no ID collisions);
  re-ingesting is a no-op; unit tests cover extraction on synthetic PPTX/PDF fixtures
  (text, table, chart, notes); an integration test ingests a fixture into Postgres.
- **Commit:** `M1: ingestion pipeline with slide rendering, extraction, pgvector`

### M2: Query path, API, UI, one-command run
- Pipeline **A** end to end: dense retrieval → dedupe to slides → top-k → generation with
  citations (context format `both`: slide text plus slide images to the VLM).
- `answer.py`: the prompt requires citing slide IDs for every claim and replying
  "Not found in the documents" when the context doesn't support an answer. Parse the
  citations into structured `Citation(doc, slide_no)` objects; drop citations to slides
  that weren't in the context.
- `llm.py`: an `LLMClient` interface with `OllamaClient` and `OpenAICompatClient`
  (used for vLLM in M9; built and unit-tested now against a mocked server). Backend chosen
  by `LLM_BACKEND`. Timeouts, retries with backoff, clear errors.
- FastAPI:
  - `POST /documents` (upload → returns document ID; processing runs in the background)
  - `GET /documents`, `GET /documents/{id}` (status), `DELETE /documents/{id}`
  - `GET /slides/{id}/image`
  - `POST /query` `{question, pipeline, top_k, context_format}` → answer, citations,
    retrieved slides with scores, timings per stage
  - `GET /health` (checks DB and LLM reachability)
- Streamlit: upload with live status, chat, citations rendered as slide thumbnails you
  can expand, a sidebar to pick pipeline / top-k / context format, and per-stage timings.
  Only pipelines that exist at this point appear in the picker.
- Docker: a real `Dockerfile` (with LibreOffice), compose with `pgvector/pgvector`, api,
  ui, healthchecks, a named volume for `data/`, and `OLLAMA_URL` defaulting to the host on
  macOS. `make up` starts everything; `make ingest-sample` loads a small sample deck that
  we generate synthetically and commit.
- **Acceptance:** on a fresh clone: `cp .env.example .env && make up && make
  ingest-sample`, then a question in the UI returns a cited answer with thumbnails. The
  README quickstart matches exactly what was run.
- Web demo: a static GitHub Pages site in `demo/` replaying real captured answers on the
  sample deck (question, pipeline, answer, cited slides, timings), labelled as recorded.
  It takes no new questions or uploads. The README links to it.
- **Commit:** `M2: query path with citations, async API, Streamlit UI, one-command compose`

### M3: Observability
- Structured JSON logging with a request ID across API → retrieval → generation.
- Per-stage timings recorded for every query (embed, search, rerank, generate) and every
  ingest (render, extract, embed), stored in `query_log` / `ingest_log` tables.
- `insight stats` prints p50/p95 per stage.
- **Acceptance:** after 20 queries, `insight stats` shows believable per-stage latencies.
- **Commit:** `M3: structured logging and per-stage timings`

### M4: Evaluation harness and dataset
- `eval/datasets/manifest.yaml`: 6–10 public decks (investor/earnings presentations
  from several companies and sectors, plus 1–2 public technical decks with architecture
  diagrams). Each entry: id, company, title, url, sha256, retrieved date, terms note.
  `eval/download.py` fetches and verifies hashes. If a URL can't be fetched from this
  environment, stop and tell me; I'll download it into `data/decks/`.
- `questions.jsonl` schema:
  ```json
  {"id": "q001", "question": "...", "type": "text|table|chart|diagram|multi_slide|unanswerable",
   "gold_slides": [["deck_id", 7]], "gold_answer": "...", "answer_kind": "numeric|short|free",
   "numeric": {"value": 12.4, "unit": "%", "tolerance": 0.05}, "notes": "..."}
  ```
  Target ~100 questions with every type represented (≥ 10 each; ~10% unanswerable).
  You may draft candidates per deck into `eval/datasets/candidates/`; I write and label
  the final set.
- `metrics.py`: Recall@1/5/10 and MRR at slide level; numeric answers scored by tolerance;
  short/free answers by the judge; citation precision (cited slides ∩ gold); abstention
  accuracy on unanswerable questions; all reported overall and by type, with bootstrap
  95% confidence intervals.
- `judge.py`: a local LLM judge (via Ollama) with a written rubric that returns
  `correct | partial | incorrect` + a short reason. **Validate it:** I hand-label 30
  answers; report agreement. If agreement < 85%, improve the rubric before using it.
- `run.py`: `insight eval --configs eval/configs/*.yaml [--retrieval-only]` runs configs
  over questions, writes `runs/<run_id>.jsonl` (gitignored), caching retrieval and
  generation by input hash so re-runs are cheap.
- `report.py`: writes `results/<date>-<name>.md` with the environment block (§4), the
  tables, and charts (PNG) of Recall@5 and accuracy by type per config.
- Run pipeline **A** as the baseline (retrieval + generation + judge).
- **Acceptance:** one command produces a results file for pipeline A; judge agreement is
  reported; metrics have unit tests with hand-computed values.
- **Commit:** `M4: eval dataset, metrics, validated judge, baseline results`

### M5: Lexical search, fusion, reranking
- `lexical.py`: Postgres full-text search over slide text (`websearch_to_tsquery`,
  `ts_rank_cd`).
- `fusion.py`: reciprocal rank fusion (k configurable, default 60), with unit tests.
- `rerank.py`: cross-encoder over the top-N fused candidates.
- Configs: A, A+lexical, A+lexical+rerank. Retrieval metrics for all three; generation
  and judge for the best one.
- **Acceptance:** results table comparing the three, with retrieval latency per config.
- **Commit:** `M5: lexical search, RRF fusion, reranking`

### M6: Visual retrieval (pipeline B) and hybrid (pipeline C)
- `embed/visual.py`: ColPali-family multi-vector embeddings per slide image (computed at
  ingest, as a new `embedding` sub-stage); queries embedded with the same model.
- Storage: `slide_vectors` (slide_id, pooled vector, HNSW index) and `slide_patches`
  (slide_id, patch_idx, vector). Search = pooled-vector top-N candidates from pgvector,
  then exact MaxSim over their patch vectors in NumPy. Record this design and the
  alternatives (dedicated multi-vector store, brute force) in `decisions.md`, with
  storage size per slide.
- Pipeline **C**: RRF over (A dense, lexical, B) then rerank; plus C without rerank.
- Full retrieval ablation: A, A+lexical, A+lexical+rerank, B, C without rerank, C.
  Generation and judge for the best text config, B, and C.
- Context-format experiment: best retriever × {text, image, both}.
- Report quality by type, p50/p95 query latency, ingestion seconds per slide (text vs
  visual), and storage per slide.
- **Acceptance:** a single results file has the full comparison table, and
  `docs/decisions.md` states which pipeline is the default and why, in numbers.
- Refresh the web demo with pipelines A–C and link the results file.
- **Commit:** `M6: visual late-interaction retrieval, hybrid pipeline, full ablation`

### M7: Agentic answering for hard questions
- Tools (`agent/tools.py`), each with a JSON schema and unit tests:
  - `search_slides(query, k)` → slide IDs, titles, snippets (uses the default pipeline)
  - `get_slide(slide_id)` → text, tables, chart data, and the image
  - `get_chart_data(slide_id)` → structured series from the PPTX chart XML, when present
  - `calculate(expression)` → a safe arithmetic evaluator (AST whitelist; **never `eval`**)
- `agent/loop.py`: a plain tool-calling loop (no framework): system prompt, tool calls
  via the LLM client, max steps, max tokens, a trace of every step saved to the run, and a
  final answer with citations. If the local model's tool calling is unreliable, record it
  in `decisions.md` and switch to a local model that handles tools; stop and ask me if
  none on my Mac does.
- Eval: agent vs single-shot on `chart`, `table`, and `multi_slide` questions; report
  accuracy, steps per question, and latency. Explain the failure cases in the results file
  (read 5 traces and summarize).
- API/UI: `mode: single | agent`; the UI shows the agent's steps in an expander.
- **Acceptance:** results show where the agent helps and where it costs latency for nothing.
- **Commit:** `M7: tool-using agent for chart and multi-slide questions`

### M8: MCP server
- Expose Insight AI as an MCP server with tools `search_decks`, `get_slide`,
  `ask_decks`, and a resource listing indexed documents.
- Document how to connect it from Claude Code / Claude Desktop (config snippet in README).
- **Acceptance:** from Claude Code, I can ask a question that triggers `ask_decks` and get
  a cited answer; a test exercises the server in-process.
- **Commit:** `M8: MCP server`

### M9: vLLM on a RunPod GPU Pod
Setup and deployment only. No performance benchmarks.
- `deploy/runpod/README.md`: step by step from zero: create a RunPod account, add
  credit, create an API key, install the CLI, (optionally) create a network volume for
  the model cache, then create → use → stop → terminate a Pod. Include the cost warning:
  a running Pod bills until stopped or terminated.
- `pod.env.example`: RunPod API key, GPU type (H100 by default), image, volume, model ID,
  vLLM API key, max model length. The real `pod.env` is gitignored.
- `create_pod.sh` / `stop_pod.sh` / `terminate_pod.sh`: thin wrappers over RunPod's CLI
  or API (whichever §3.7 confirms), printing the Pod ID and the OpenAI-compatible base URL.
- `serve.sh`: the exact `vllm serve` command for the chosen VLM, with `--api-key`, dtype,
  `--max-model-len`, and multimodal limits set from env.
- Insight AI switches to the Pod by setting `LLM_BACKEND=openai_compat`,
  `LLM_BASE_URL`, `LLM_API_KEY` (all in `.env.example`, documented).
- `smoke_test.py`: checks `/v1/models`, sends one text request and one text+image request,
  then runs one full `insight ask` through `OpenAICompatClient`; exits non-zero on failure.
- Record in `docs/decisions.md`: vLLM version, image, GPU type, model revision, dtype,
  and every `vllm serve` flag, so the setup is reproducible.
- **Acceptance:** following `deploy/runpod/README.md` from zero, I create a Pod, the smoke
  test passes, the Streamlit UI answers a question using the Pod, and `terminate_pod.sh`
  removes it. Until I've done that run, the milestone is not merged.
- **Commit:** `M9: vLLM deployment on RunPod`

### M10: Ship
- `scripts/screenshots.py` (`make screenshots`): Playwright drives the running UI on the
  sample deck and saves 2–3 screenshots to `docs/images/` (chat with cited thumbnails,
  agent steps, pipeline picker).
- README, top to bottom:
  1. One-sentence pitch + the screenshots.
  2. **Results:** the headline table and one chart, with a two-sentence takeaway.
  3. Architecture: a Mermaid diagram of ingest and query paths.
  4. Quickstart (exactly what M2 verified).
  5. Run with vLLM on RunPod (link to `deploy/runpod/README.md`).
  6. Use from Claude Code via MCP.
  7. How to reproduce the results (download → ingest → eval → report).
  8. Design decisions (link to `docs/decisions.md`) and limitations.
- Final refresh of the web demo; its URL appears at the top of the README.
- `docs/writeup.md`: the technical writeup (problem, setup, results, what surprised us),
  ~1,500 words, written in first person for me to edit.
- Tag `v1.0.0` and create a GitHub release with the results table.
- **Acceptance:** a fresh clone on another machine follows the README to a cited answer;
  every number in the README links to a results file.
- **Commit:** `v1.0: results, README, writeup`

---

## 8. Definition of done for v1

- [ ] All milestones merged; CI green; `make test` passes locally.
- [ ] `make up && make ingest-sample` works on a fresh clone (macOS and Linux).
- [ ] Results file with pipelines A–C and the ablations, by question type, with CIs,
      latency, and storage.
- [ ] Judge agreement with my labels reported (≥ 85%).
- [ ] Agent vs single-shot comparison with failure analysis.
- [ ] MCP server usable from Claude Code.
- [ ] RunPod Pod deployment verified end to end with the smoke test, then terminated.
- [ ] `docs/decisions.md` records every model choice, version, and deviation from this spec.
- [ ] No documents, `.env`, `pod.env`, keys, or raw runs in git (`git log --stat` check).
- [ ] `grep -rnE "TODO|FIXME|coming soon|placeholder"` over `src/ docs/ README.md` finds nothing.
- [ ] README makes no claim that isn't backed by code or a results file.
- [ ] `docs/learning/M0.md` … `M10.md` exist.
