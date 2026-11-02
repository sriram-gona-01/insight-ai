"""Idempotent ingest job: same content hash, same document, no repeated work."""

import hashlib
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from psycopg_pool import ConnectionPool

from insight.config import Settings
from insight.embed.text import TextEmbedder
from insight.ingest.chunk import chunk_slide
from insight.ingest.extract import ExtractedSlide, extract_document
from insight.ingest.render import render_document
from insight.models import Chunk, Slide
from insight.store import db

ALLOWED_SUFFIXES = {".pdf", ".pptx"}


class InvalidDocument(ValueError):
    pass


@dataclass(frozen=True)
class IngestResult:
    doc_id: UUID
    sha256: str
    status: str
    skipped: bool
    error: str | None = None


def validate_file(path: Path, max_mb: int) -> None:
    """Check extension, size, and that the content really is that type."""
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise InvalidDocument(f"Unsupported file type '{suffix}'; use .pptx or .pdf")
    if path.stat().st_size > max_mb * 1024 * 1024:
        raise InvalidDocument(f"File is larger than the {max_mb} MB limit")
    if suffix == ".pdf":
        with path.open("rb") as f:
            if f.read(5) != b"%PDF-":
                raise InvalidDocument("File has a .pdf extension but isn't a PDF")
    elif not _is_pptx(path):
        raise InvalidDocument("File has a .pptx extension but isn't a PowerPoint file")


def _is_pptx(path: Path) -> bool:
    if not zipfile.is_zipfile(path):
        return False
    with zipfile.ZipFile(path) as archive:
        return "ppt/presentation.xml" in archive.namelist()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_filename(name: str) -> str:
    """Filenames are only ever displayed; files on disk are stored by content hash."""
    return "".join(c for c in Path(name).name if c.isprintable())[:255] or "unnamed"


def _store_original(path: Path, decks_dir: Path, sha256: str) -> Path:
    decks_dir.mkdir(parents=True, exist_ok=True)
    stored = decks_dir / f"{sha256}{path.suffix.lower()}"
    if not stored.exists():
        with tempfile.NamedTemporaryFile(dir=decks_dir, delete=False) as tmp:
            shutil.copyfile(path, tmp.name)
        os.replace(tmp.name, stored)
    return stored


def _build_records(
    doc_id: UUID,
    sha256: str,
    extracted: list[ExtractedSlide],
    embedder: TextEmbedder,
    settings: Settings,
) -> tuple[list[Slide], list[Chunk]]:
    slides: list[Slide] = []
    pending: list[tuple[UUID, str, str, str]] = []
    for item in extracted:
        slide_id = uuid4()
        slides.append(
            Slide(
                id=slide_id,
                doc_id=doc_id,
                slide_no=item.slide_no,
                image_path=f"pages/{sha256}/{item.slide_no}.png",
                title=item.title,
                text=item.text,
            )
        )
        drafts = chunk_slide(
            item, settings.chunk_max_tokens, embedder.count_tokens, settings.chunk_title_prefix
        )
        pending += [(slide_id, d.kind, d.text, d.embedding_text) for d in drafts]

    vectors = embedder.embed([p[3] for p in pending]) if pending else []
    chunks = [
        Chunk(id=uuid4(), slide_id=slide_id, kind=kind, text=text, embedding=vector)
        for (slide_id, kind, text, _), vector in zip(pending, vectors, strict=True)
    ]
    return slides, chunks


@dataclass(frozen=True)
class Admission:
    """A file that passed validation and has a document row."""

    doc_id: UUID
    sha256: str
    stored: Path
    status: str
    should_process: bool


def admit_file(path: Path, filename: str, settings: Settings, pool: ConnectionPool) -> Admission:
    """Validate, store by content hash, and claim the document. Bad input raises InvalidDocument."""
    validate_file(path, settings.max_file_mb)
    sha256 = file_sha256(path)
    stored = _store_original(path, settings.data_dir / "decks", sha256)
    claim = db.claim_document(pool, clean_filename(filename), sha256, settings.ingest_stale_minutes)
    return Admission(claim.doc_id, sha256, stored, claim.status, claim.should_process)


def process_document(
    admission: Admission, settings: Settings, pool: ConnectionPool, embedder: TextEmbedder
) -> IngestResult:
    """Run render, extract, and embed. Any failure is recorded on the document."""
    doc_id, sha256 = admission.doc_id, admission.sha256
    try:
        db.set_status(pool, doc_id, "rendering")
        pages_dir = settings.data_dir / "pages" / sha256
        shutil.rmtree(pages_dir, ignore_errors=True)
        images = render_document(
            admission.stored,
            pages_dir,
            settings.render_dpi,
            settings.soffice_path,
            settings.soffice_timeout_seconds,
        )

        db.set_status(pool, doc_id, "extracting")
        extracted = extract_document(admission.stored)
        if not extracted:
            raise ValueError("The document has no slides or pages")
        if len(images) != len(extracted):
            raise ValueError(f"Rendered {len(images)} images but extracted {len(extracted)} slides")

        db.set_status(pool, doc_id, "embedding")
        slides, chunks = _build_records(doc_id, sha256, extracted, embedder, settings)
        db.save_slides(pool, doc_id, slides, chunks)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"[:1000]
        db.set_status(pool, doc_id, "failed", error)
        return IngestResult(doc_id, sha256, "failed", skipped=False, error=error)

    return IngestResult(doc_id, sha256, "ready", skipped=False)


def ingest_file(
    path: Path, settings: Settings, pool: ConnectionPool, embedder: TextEmbedder
) -> IngestResult:
    """Admit and process one file in the current thread."""
    admission = admit_file(path, path.name, settings, pool)
    if not admission.should_process:
        return IngestResult(admission.doc_id, admission.sha256, admission.status, skipped=True)
    return process_document(admission, settings, pool, embedder)
