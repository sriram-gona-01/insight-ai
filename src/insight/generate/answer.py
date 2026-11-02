"""Assemble context, call the model, and turn its reply into a checked, cited answer."""

import io
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image
from psycopg_pool import ConnectionPool

from insight.config import Settings
from insight.embed.text import TextEmbedder
from insight.generate.llm import LLMClient
from insight.generate.prompts import NOT_FOUND, SYSTEM_PROMPT, ContextFormat, build_user_prompt
from insight.models import Answer, Citation, RetrievedSlide
from insight.retrieve.pipelines import retrieve

TAG_GROUP = re.compile(r"\[\s*(S\d+(?:\s*[,;]\s*S\d+)*)\s*\]", re.IGNORECASE)
TAG = re.compile(r"S(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class QueryResult:
    answer: Answer
    retrieved: list[RetrievedSlide]
    timings_ms: dict[str, float] = field(default_factory=dict)


def load_context_image(path: Path, max_side: int) -> bytes:
    """Read a slide image, shrunk to fit `max_side`, as PNG bytes."""
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((max_side, max_side))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
    return buffer.getvalue()


def parse_answer(reply: str, slides: list[RetrievedSlide]) -> Answer:
    """Keep citations to slides in the context, and remove tags pointing anywhere else."""
    if NOT_FOUND.lower() in reply.lower():
        return Answer(text=NOT_FOUND, citations=[], abstained=True)

    cited: dict[int, Citation] = {}

    def keep_valid(match: re.Match[str]) -> str:
        kept = []
        for number in TAG.findall(match.group(1)):
            index = int(number)
            if 1 <= index <= len(slides):
                slide = slides[index - 1]
                cited.setdefault(index, Citation(slide.filename, slide.slide_no, slide.slide_id))
                kept.append(f"S{index}")
        return f"[{', '.join(kept)}]" if kept else ""

    text = TAG_GROUP.sub(keep_valid, reply)
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    return Answer(text=text, citations=list(cited.values()), abstained=False)


def answer_question(
    question: str,
    pipeline: str,
    top_k: int,
    context_format: ContextFormat,
    settings: Settings,
    pool: ConnectionPool,
    embedder: TextEmbedder,
    llm: LLMClient,
) -> QueryResult:
    slides, timings = retrieve(pipeline, question, top_k, settings, pool, embedder)
    if not slides:
        return QueryResult(Answer(NOT_FOUND, [], True), [], timings)

    images = []
    if context_format != "text":
        images = [
            load_context_image(settings.data_dir / s.image_path, settings.context_image_max_side)
            for s in slides
        ]
    prompt = build_user_prompt(question, slides, context_format)

    start = time.perf_counter()
    reply = llm.generate(SYSTEM_PROMPT, prompt, images)
    timings["generate"] = (time.perf_counter() - start) * 1000
    return QueryResult(parse_answer(reply, slides), slides, timings)
