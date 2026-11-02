"""Dense retrieval: cosine search over chunks, collapsed to slides."""

from pgvector import Vector
from psycopg_pool import ConnectionPool

from insight.models import RetrievedSlide

HNSW_EF_SEARCH_MAX = 1000


def dedupe_to_slides(hits: list[RetrievedSlide], top_k: int) -> list[RetrievedSlide]:
    """Keep each slide's best-scoring chunk hit. `hits` must be sorted best first."""
    seen: dict[object, RetrievedSlide] = {}
    for hit in hits:
        seen.setdefault(hit.slide_id, hit)
    return list(seen.values())[:top_k]


def search_chunks(
    pool: ConnectionPool, query_vector: list[float], n_chunks: int
) -> list[RetrievedSlide]:
    """Return one row per matching chunk, best first, from documents that are ready."""
    with pool.connection() as conn:
        # The index only yields ef_search rows, so it must be at least the number requested.
        conn.execute(
            "SELECT set_config('hnsw.ef_search', %s, true)",
            (str(min(max(40, n_chunks), HNSW_EF_SEARCH_MAX)),),
        )
        rows = conn.execute(
            """
            SELECT s.id, s.doc_id, d.filename, s.slide_no, s.title, s.text, s.image_path,
                   1 - (c.embedding <=> %(query)s) AS score
              FROM chunks c
              JOIN slides s ON s.id = c.slide_id
              JOIN documents d ON d.id = s.doc_id
             WHERE d.status = 'ready'
             ORDER BY c.embedding <=> %(query)s
             LIMIT %(limit)s
            """,
            {"query": Vector(query_vector), "limit": n_chunks},
        ).fetchall()
    return [RetrievedSlide(*row) for row in rows]
