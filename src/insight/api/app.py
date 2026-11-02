"""HTTP API. Uploads return at once; processing continues in a background task."""

import logging
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field

from insight.config import Settings
from insight.embed.text import TextEmbedder, embedder_from_settings
from insight.generate.answer import answer_question
from insight.generate.llm import LLMClient, LLMError, get_llm_client
from insight.generate.prompts import ContextFormat
from insight.ingest.pipeline import (
    ALLOWED_SUFFIXES,
    InvalidDocument,
    admit_file,
    process_document,
)
from insight.models import Document
from insight.store import db

UPLOAD_READ_BYTES = 1024 * 1024
UNFINISHED = {"queued", "rendering", "extracting", "embedding"}

logging.getLogger("psycopg.pool").setLevel(logging.ERROR)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    pipeline: Literal["A"] = "A"
    top_k: int | None = Field(default=None, ge=1, le=20)
    context_format: ContextFormat = "both"


def _document_json(document: Document) -> dict[str, object]:
    return asdict(document)


def create_app(
    settings: Settings | None = None,
    pool: ConnectionPool | None = None,
    embedder: TextEmbedder | None = None,
    llm: LLMClient | None = None,
) -> FastAPI:
    settings = settings or Settings()
    pool = pool or db.get_pool(settings.database_url)
    embedder = embedder or embedder_from_settings(settings)
    llm = llm or get_llm_client(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        db.init_schema(settings.database_url, settings.embedding_dim)
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        yield

    app = FastAPI(title="Insight AI", lifespan=lifespan)
    app.state.data_dir = settings.data_dir

    @app.post("/documents", status_code=202)
    def upload_document(file: UploadFile, background: BackgroundTasks) -> dict[str, object]:
        filename = file.filename or "unnamed"
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(415, f"Unsupported file type '{suffix}'; use .pptx or .pdf")

        limit = settings.max_file_mb * 1024 * 1024
        uploads = settings.data_dir / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=uploads, suffix=suffix) as tmp:
            size = 0
            while block := file.file.read(UPLOAD_READ_BYTES):
                size += len(block)
                if size > limit:
                    raise HTTPException(
                        413, f"File is larger than the {settings.max_file_mb} MB limit"
                    )
                tmp.write(block)
            tmp.flush()
            try:
                admission = admit_file(Path(tmp.name), filename, settings, pool)
            except InvalidDocument as e:
                raise HTTPException(415, str(e)) from e

        if admission.should_process:
            background.add_task(process_document, admission, settings, pool, embedder)
        return {
            "id": admission.doc_id,
            "status": admission.status,
            "skipped": not admission.should_process,
        }

    @app.get("/documents")
    def list_documents() -> list[dict[str, object]]:
        return [_document_json(d) for d in db.list_documents(pool)]

    @app.get("/documents/{doc_id}")
    def get_document(doc_id: UUID) -> dict[str, object]:
        document = db.get_document(pool, doc_id)
        if document is None:
            raise HTTPException(404, "Document not found")
        return _document_json(document)

    @app.delete("/documents/{doc_id}", status_code=204)
    def delete_document(doc_id: UUID) -> Response:
        document = db.get_document(pool, doc_id)
        if document is None:
            raise HTTPException(404, "Document not found")
        if document.status in UNFINISHED:
            raise HTTPException(409, f"Document is still {document.status}")
        db.delete_document(pool, doc_id)
        # Files are named by content hash, and sha256 is unique, so no other document shares them.
        shutil.rmtree(settings.data_dir / "pages" / document.sha256, ignore_errors=True)
        for suffix in ALLOWED_SUFFIXES:
            (settings.data_dir / "decks" / f"{document.sha256}{suffix}").unlink(missing_ok=True)
        return Response(status_code=204)

    @app.get("/slides/{slide_id}/image")
    def slide_image(slide_id: UUID) -> FileResponse:
        image_path = db.get_slide_image_path(pool, slide_id)
        if image_path is None:
            raise HTTPException(404, "Slide not found")
        path = settings.data_dir / image_path
        if not path.exists():
            raise HTTPException(404, "Slide image is missing on disk")
        return FileResponse(path, media_type="image/png")

    @app.post("/query")
    def query(request: QueryRequest) -> dict[str, object]:
        try:
            result = answer_question(
                request.question,
                request.pipeline,
                request.top_k or settings.default_top_k,
                request.context_format,
                settings,
                pool,
                embedder,
                llm,
            )
        except LLMError as e:
            raise HTTPException(502, f"The model request failed: {e}") from e
        return {
            "answer": result.answer.text,
            "abstained": result.answer.abstained,
            "citations": [asdict(c) for c in result.answer.citations],
            "retrieved": [
                {
                    "slide_id": s.slide_id,
                    "doc": s.filename,
                    "slide_no": s.slide_no,
                    "title": s.title,
                    "score": s.score,
                }
                for s in result.retrieved
            ],
            "timings_ms": result.timings_ms,
            "model": llm.model,
        }

    @app.get("/health")
    def health(response: Response) -> dict[str, object]:
        """503 when the database is down. A missing model is `degraded`: ingest still works."""
        database = db.is_reachable(pool)
        model = llm.is_reachable()
        if not database:
            response.status_code = 503
        status = "ok" if database and model else "degraded"
        return {"status": status, "database": database, "llm": model, "model": llm.model}

    return app


def app() -> FastAPI:
    """Factory for `uvicorn --factory insight.api.app:app`."""
    return create_app()
