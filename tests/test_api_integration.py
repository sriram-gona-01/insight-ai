"""The API against real Postgres and LibreOffice, with fake embedder and model."""

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fixtures import make_pptx
from test_ingest_integration import TEST_DATABASE_URL, _ensure_test_database

from insight.api.app import create_app
from insight.config import Settings
from insight.generate.prompts import NOT_FOUND

pytestmark = pytest.mark.integration


class FakeEmbedder:
    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0, 0.0]


class FakeLLM:
    model = "fake-vision"

    def __init__(self) -> None:
        self.reply = "Margin is 41% [S1]. Invented [S99]."
        self.images = 0
        self.reachable = True

    def generate(self, system: str, user: str, images: list[bytes]) -> str:
        self.images = len(images)
        return self.reply

    def is_reachable(self) -> bool:
        return self.reachable


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        database_url=TEST_DATABASE_URL,
        embedding_dim=4,
        max_file_mb=1,
    )


@pytest.fixture
def client(settings: Settings, llm: FakeLLM) -> Iterator[TestClient]:
    import psycopg
    from pgvector.psycopg import register_vector
    from psycopg_pool import ConnectionPool

    _ensure_test_database()
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        conn.execute("DROP TABLE IF EXISTS chunks, slides, documents")
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    with ConnectionPool(TEST_DATABASE_URL, configure=register_vector, open=True) as pool:
        app = create_app(settings, pool, FakeEmbedder(), llm)
        with TestClient(app) as test_client:
            yield test_client


def upload(client: TestClient, path: Path) -> dict:
    with path.open("rb") as f:
        response = client.post("/documents", files={"file": (path.name, f)})
    assert response.status_code == 202, response.text
    return response.json()


def wait_until_finished(client: TestClient, doc_id: str) -> dict:
    deadline = time.time() + 120
    while time.time() < deadline:
        document = client.get(f"/documents/{doc_id}").json()
        if document["status"] in ("ready", "failed"):
            return document
        time.sleep(0.2)
    raise AssertionError("Document did not finish")


def ingest(client: TestClient, tmp_path: Path) -> str:
    created = upload(client, make_pptx(tmp_path / "deck.pptx"))
    document = wait_until_finished(client, created["id"])
    assert document["status"] == "ready", document["error"]
    return created["id"]


def test_upload_query_image_delete(client: TestClient, tmp_path: Path, llm: FakeLLM) -> None:
    doc_id = ingest(client, tmp_path)

    again = upload(client, tmp_path / "deck.pptx")
    assert again["skipped"] and again["id"] == doc_id
    assert [d["id"] for d in client.get("/documents").json()] == [doc_id]

    response = client.post("/query", json={"question": "What is the margin?", "top_k": 2})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["answer"] == "Margin is 41% [S1]. Invented."
    assert len(result["citations"]) == 1
    assert len(result["retrieved"]) == 2
    assert llm.images == 2
    assert set(result["timings_ms"]) == {"embed", "search", "generate"}

    image = client.get(f"/slides/{result['citations'][0]['slide_id']}/image")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"

    text_only = client.post(
        "/query", json={"question": "Margin?", "top_k": 2, "context_format": "text"}
    )
    assert text_only.status_code == 200
    assert llm.images == 0

    document = client.get(f"/documents/{doc_id}").json()
    assert client.delete(f"/documents/{doc_id}").status_code == 204
    assert client.get(f"/documents/{doc_id}").status_code == 404
    assert client.get(f"/slides/{result['citations'][0]['slide_id']}/image").status_code == 404
    assert client.delete(f"/documents/{doc_id}").status_code == 404
    assert not (Path(client.app.state.data_dir) / "pages" / document["sha256"]).exists()


def test_query_without_documents_abstains_without_calling_the_model(
    client: TestClient, llm: FakeLLM
) -> None:
    llm.reply = "should not be used"
    result = client.post("/query", json={"question": "Anything?"}).json()
    assert result["abstained"] is True
    assert result["answer"] == NOT_FOUND
    assert result["retrieved"] == []


@pytest.mark.parametrize("name", ["notes.txt", "../../evil.exe"])
def test_rejects_wrong_type(client: TestClient, name: str) -> None:
    assert client.post("/documents", files={"file": (name, b"x")}).status_code == 415


def test_rejects_content_that_does_not_match_extension(client: TestClient) -> None:
    assert client.post("/documents", files={"file": ("a.pdf", b"nope")}).status_code == 415


def test_rejects_oversized_upload(client: TestClient) -> None:
    body = b"%PDF-" + b"0" * (1024 * 1024 + 1)
    assert client.post("/documents", files={"file": ("big.pdf", body)}).status_code == 413


def test_upload_path_traversal_name_stays_inside_data_dir(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    path = make_pptx(tmp_path / "deck.pptx")
    with path.open("rb") as f:
        response = client.post("/documents", files={"file": ("../../../escape.pptx", f)})
    assert response.status_code == 202
    document = wait_until_finished(client, response.json()["id"])
    assert document["filename"] == "escape.pptx"
    assert not (settings.data_dir.parent.parent / "escape.pptx").exists()
    assert (settings.data_dir / "decks" / f"{document['sha256']}.pptx").exists()


def test_query_validation(client: TestClient) -> None:
    assert client.post("/query", json={"question": ""}).status_code == 422
    assert client.post("/query", json={"question": "q", "pipeline": "Z"}).status_code == 422
    assert client.post("/query", json={"question": "q", "top_k": 0}).status_code == 422


def test_model_failure_returns_502(client: TestClient, tmp_path: Path, llm: FakeLLM) -> None:
    from insight.generate.llm import LLMError

    ingest(client, tmp_path)

    def fail(*_: object) -> str:
        raise LLMError("model is down")

    llm.generate = fail
    response = client.post("/query", json={"question": "q"})
    assert response.status_code == 502
    assert "model is down" in response.json()["detail"]


def test_health_reports_degraded_when_model_is_unreachable(
    client: TestClient, llm: FakeLLM
) -> None:
    assert client.get("/health").json()["status"] == "ok"
    llm.reachable = False
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_unknown_ids_return_404(client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/documents/{missing}").status_code == 404
    assert client.get(f"/slides/{missing}/image").status_code == 404
