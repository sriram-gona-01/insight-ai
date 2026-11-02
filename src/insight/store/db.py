"""Connection pool and repository functions. All values go through query parameters."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import class_row
from psycopg_pool import ConnectionPool

from insight.models import Chunk, Document, Slide

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def render_schema(embedding_dim: int) -> str:
    return SCHEMA_PATH.read_text().replace("{{embedding_dim}}", str(int(embedding_dim)))


def init_schema(database_url: str, embedding_dim: int) -> None:
    with psycopg.connect(database_url) as conn:
        conn.execute(render_schema(embedding_dim))


@lru_cache(maxsize=1)
def get_pool(database_url: str) -> ConnectionPool:
    return ConnectionPool(
        database_url, min_size=1, max_size=5, timeout=10, configure=register_vector, open=True
    )


@dataclass(frozen=True)
class Claim:
    doc_id: UUID
    status: str
    should_process: bool


def claim_document(pool: ConnectionPool, filename: str, sha256: str, stale_minutes: int) -> Claim:
    """Create the document or reclaim a failed or abandoned one. Otherwise leave it alone."""
    with pool.connection() as conn:
        inserted = conn.execute(
            """
            INSERT INTO documents (id, filename, sha256, status)
            VALUES (%s, %s, %s, 'queued')
            ON CONFLICT (sha256) DO NOTHING
            RETURNING id
            """,
            (uuid4(), filename, sha256),
        ).fetchone()
        if inserted:
            return Claim(inserted[0], "queued", True)

        reclaimed = conn.execute(
            """
            UPDATE documents
               SET status = 'queued', error = NULL, updated_at = now()
             WHERE sha256 = %s
               AND (status = 'failed'
                    OR (status <> 'ready'
                        AND updated_at < now() - make_interval(mins => %s)))
            RETURNING id
            """,
            (sha256, stale_minutes),
        ).fetchone()
        if reclaimed:
            return Claim(reclaimed[0], "queued", True)

        doc_id, status = conn.execute(
            "SELECT id, status FROM documents WHERE sha256 = %s", (sha256,)
        ).fetchone()
        return Claim(doc_id, status, False)


def set_status(pool: ConnectionPool, doc_id: UUID, status: str, error: str | None = None) -> None:
    with pool.connection() as conn:
        conn.execute(
            "UPDATE documents SET status = %s, error = %s, updated_at = now() WHERE id = %s",
            (status, error, doc_id),
        )


def save_slides(
    pool: ConnectionPool, doc_id: UUID, slides: list[Slide], chunks: list[Chunk]
) -> None:
    """Replace the document's slides and chunks and mark it ready, all in one transaction."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM slides WHERE doc_id = %s", (doc_id,))
        cur.executemany(
            """
            INSERT INTO slides (id, doc_id, slide_no, image_path, title, text)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [(s.id, s.doc_id, s.slide_no, s.image_path, s.title, s.text) for s in slides],
        )
        if chunks:
            cur.executemany(
                """
                INSERT INTO chunks (id, slide_id, kind, text, embedding)
                VALUES (%s, %s, %s, %s, %s::vector)
                """,
                [(c.id, c.slide_id, c.kind, c.text, c.embedding) for c in chunks],
            )
        cur.execute(
            """
            UPDATE documents
               SET status = 'ready', error = NULL, n_slides = %s, updated_at = now()
             WHERE id = %s
            """,
            (len(slides), doc_id),
        )


def list_documents(pool: ConnectionPool) -> list[Document]:
    with pool.connection() as conn, conn.cursor(row_factory=class_row(Document)) as cur:
        return cur.execute(
            """
            SELECT id, filename, sha256, n_slides, status, error, created_at
              FROM documents
             ORDER BY created_at
            """
        ).fetchall()
