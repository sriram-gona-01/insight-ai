"""Turn extracted blocks into chunks that fit the embedding model."""

from collections.abc import Callable
from dataclasses import dataclass

from insight.ingest.extract import Block, ExtractedSlide
from insight.models import ChunkKind

TokenCounter = Callable[[str], int]

MIN_CHUNK_TOKENS = 32


@dataclass(frozen=True)
class ChunkDraft:
    kind: ChunkKind
    text: str
    embedding_text: str


def split_text(
    text: str, limit: int, count: TokenCounter, separators: tuple[str, ...] = ("\n", " ")
) -> list[str]:
    """Split at line boundaries, then word boundaries, then by characters as a last resort."""
    if count(text) <= limit:
        return [text]
    if not separators:
        if len(text) < 2:
            return [text]
        middle = len(text) // 2
        return split_text(text[:middle], limit, count, ()) + split_text(
            text[middle:], limit, count, ()
        )

    separator, remaining = separators[0], separators[1:]
    parts = [part for part in text.split(separator) if part.strip()]
    if len(parts) <= 1:
        return split_text(text, limit, count, remaining)

    pieces: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current}{separator}{part}" if current else part
        if count(candidate) <= limit:
            current = candidate
            continue
        if current:
            pieces.append(current)
        if count(part) <= limit:
            current = part
        else:
            pieces.extend(split_text(part, limit, count, remaining))
            current = ""
    if current:
        pieces.append(current)
    return pieces


def split_table(text: str, limit: int, count: TokenCounter) -> list[str]:
    """Split a markdown table by rows, repeating its header so each piece stays readable."""
    if count(text) <= limit:
        return [text]
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if line.startswith("|")), None)
    if first is None or len(lines) < first + 3:
        return split_text(text, limit, count)
    header = "\n".join(lines[: first + 2])
    body = "\n".join(lines[first + 2 :])
    body_limit = max(limit - count(header), MIN_CHUNK_TOKENS)
    return [f"{header}\n{piece}" for piece in split_text(body, body_limit, count)]


def _with_title(title: str, text: str) -> str:
    return f"{title}\n{text}" if title and not text.startswith(title) else text


def chunk_block(
    block: Block, title: str, max_tokens: int, count: TokenCounter, title_prefix: bool
) -> list[ChunkDraft]:
    limit = max_tokens
    if title_prefix and title:
        limit = max(max_tokens - count(title), MIN_CHUNK_TOKENS)
    splitter = split_table if block.kind in ("table", "chart") else split_text
    return [
        ChunkDraft(block.kind, piece, _with_title(title, piece) if title_prefix else piece)
        for piece in splitter(block.text, limit, count)
    ]


def chunk_slide(
    slide: ExtractedSlide, max_tokens: int, count: TokenCounter, title_prefix: bool
) -> list[ChunkDraft]:
    return [
        draft
        for block in slide.blocks
        for draft in chunk_block(block, slide.title, max_tokens, count, title_prefix)
    ]
