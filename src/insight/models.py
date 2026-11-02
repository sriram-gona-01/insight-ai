"""Plain data objects shared across ingestion and storage."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

ChunkKind = Literal["text", "table", "chart", "notes"]


@dataclass(frozen=True)
class Document:
    id: UUID
    filename: str
    sha256: str
    n_slides: int | None
    status: str
    error: str | None
    created_at: datetime


@dataclass(frozen=True)
class Slide:
    id: UUID
    doc_id: UUID
    slide_no: int
    image_path: str
    title: str
    text: str


@dataclass(frozen=True)
class Chunk:
    id: UUID
    slide_id: UUID
    kind: ChunkKind
    text: str
    embedding: list[float]


@dataclass(frozen=True)
class RetrievedSlide:
    slide_id: UUID
    doc_id: UUID
    filename: str
    slide_no: int
    title: str
    text: str
    image_path: str
    score: float


@dataclass(frozen=True)
class Citation:
    doc: str
    slide_no: int
    slide_id: UUID


@dataclass(frozen=True)
class Answer:
    text: str
    citations: list[Citation]
    abstained: bool
