"""Ingest fixtures into a real Postgres and through real LibreOffice, with a fake embedder."""

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import psycopg
import psycopg.sql
import pytest
from fixtures import make_pdf, make_pptx
from pgvector.psycopg import register_vector
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool

from insight.config import Settings
from insight.ingest.pipeline import ingest_file
from insight.store import db

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://insight:insight@localhost:5433/insight_test"
)
DIM = 4


class FakeEmbedder:
    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0, 0.0]


def _ensure_test_database() -> None:
    maintenance = make_conninfo(TEST_DATABASE_URL, dbname="postgres")
    name = psycopg.conninfo.conninfo_to_dict(TEST_DATABASE_URL)["dbname"]
    with psycopg.connect(maintenance, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            conn.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))


@pytest.fixture
def pool() -> Iterator[ConnectionPool]:
    _ensure_test_database()
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        conn.execute("DROP TABLE IF EXISTS chunks, slides, documents")
    db.init_schema(TEST_DATABASE_URL, DIM)
    with ConnectionPool(TEST_DATABASE_URL, configure=register_vector, open=True) as connections:
        yield connections


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path / "data", embedding_dim=DIM)


def _count(pool: ConnectionPool, table: str, doc_id: UUID) -> int:
    queries = {
        "slides": "SELECT count(*) FROM slides WHERE doc_id = %s",
        "chunks": """SELECT count(*) FROM chunks c JOIN slides s ON s.id = c.slide_id
                     WHERE s.doc_id = %s""",
    }
    with pool.connection() as conn:
        return conn.execute(queries[table], (doc_id,)).fetchone()[0]


def test_two_decks_stay_intact_and_reingest_is_a_no_op(
    tmp_path: Path, pool: ConnectionPool, settings: Settings
) -> None:
    embedder = FakeEmbedder()
    first = ingest_file(make_pptx(tmp_path / "a.pptx", "Acme"), settings, pool, embedder)
    second = ingest_file(make_pptx(tmp_path / "b.pptx", "Globex"), settings, pool, embedder)
    pdf = ingest_file(make_pdf(tmp_path / "c.pdf"), settings, pool, embedder)
    assert (first.status, second.status, pdf.status) == ("ready", "ready", "ready"), (
        first.error,
        second.error,
        pdf.error,
    )

    # The hidden slide is left out, so images and slides line up.
    assert _count(pool, "slides", first.doc_id) == 3
    assert _count(pool, "slides", second.doc_id) == 3
    assert _count(pool, "slides", pdf.doc_id) == 2
    assert (settings.data_dir / "pages" / first.sha256 / "3.png").exists()
    assert not (settings.data_dir / "pages" / first.sha256 / "4.png").exists()

    before = _count(pool, "chunks", first.doc_id)
    assert before == _count(pool, "chunks", second.doc_id) > 0

    again = ingest_file(tmp_path / "a.pptx", settings, pool, embedder)
    assert again.skipped and again.doc_id == first.doc_id
    assert _count(pool, "chunks", first.doc_id) == before
    assert len(db.list_documents(pool)) == 3

    with pool.connection() as conn:
        titles = conn.execute(
            "SELECT title FROM slides WHERE doc_id = %s AND slide_no = 1", (second.doc_id,)
        ).fetchone()
    assert titles[0] == "Globex overview"


def test_failure_is_recorded_then_retried(
    tmp_path: Path, pool: ConnectionPool, settings: Settings
) -> None:
    path = make_pptx(tmp_path / "a.pptx")
    broken = settings.model_copy(update={"soffice_path": str(tmp_path / "missing")})

    failed = ingest_file(path, broken, pool, FakeEmbedder())
    assert failed.status == "failed"
    assert "LibreOffice not found" in failed.error
    assert db.list_documents(pool)[0].status == "failed"

    retried = ingest_file(path, settings, pool, FakeEmbedder())
    assert retried.status == "ready"
    assert retried.doc_id == failed.doc_id
    document = db.list_documents(pool)[0]
    assert document.status == "ready"
    assert document.error is None


def test_abandoned_ingest_is_reclaimed_only_when_stale(
    tmp_path: Path, pool: ConnectionPool, settings: Settings
) -> None:
    path = make_pptx(tmp_path / "a.pptx")
    first = ingest_file(path, settings, pool, FakeEmbedder())
    db.set_status(pool, first.doc_id, "embedding")

    assert ingest_file(path, settings, pool, FakeEmbedder()).skipped

    with pool.connection() as conn:
        conn.execute("UPDATE documents SET updated_at = now() - interval '1 day'")
    reclaimed = ingest_file(path, settings, pool, FakeEmbedder())
    assert reclaimed.status == "ready" and not reclaimed.skipped
    assert _count(pool, "slides", first.doc_id) == 3
