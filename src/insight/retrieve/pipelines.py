"""Named retrieval pipelines. Each returns slides plus per-stage timings in milliseconds."""

import time

from psycopg_pool import ConnectionPool

from insight.config import Settings
from insight.embed.text import TextEmbedder
from insight.models import RetrievedSlide
from insight.retrieve.dense import dedupe_to_slides, search_chunks

PIPELINES = {"A": "Text: dense search over extracted slide text"}


def _pipeline_a(
    question: str, top_k: int, settings: Settings, pool: ConnectionPool, embedder: TextEmbedder
) -> tuple[list[RetrievedSlide], dict[str, float]]:
    start = time.perf_counter()
    vector = embedder.embed_query(question)
    embedded = time.perf_counter()
    hits = search_chunks(pool, vector, top_k * settings.retrieval_overfetch)
    searched = time.perf_counter()
    timings = {"embed": (embedded - start) * 1000, "search": (searched - embedded) * 1000}
    return dedupe_to_slides(hits, top_k), timings


def retrieve(
    pipeline: str,
    question: str,
    top_k: int,
    settings: Settings,
    pool: ConnectionPool,
    embedder: TextEmbedder,
) -> tuple[list[RetrievedSlide], dict[str, float]]:
    if pipeline != "A":
        raise ValueError(f"Unknown pipeline '{pipeline}'; available: {', '.join(PIPELINES)}")
    return _pipeline_a(question, top_k, settings, pool, embedder)
