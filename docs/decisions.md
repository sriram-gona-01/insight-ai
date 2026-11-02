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
