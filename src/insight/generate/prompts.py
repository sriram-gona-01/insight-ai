"""Prompts. Retrieval comparisons all use these, so they measure retrieval and not wording."""

from typing import Literal

from insight.models import RetrievedSlide

ContextFormat = Literal["text", "image", "both"]

NOT_FOUND = "Not found in the documents"

SYSTEM_PROMPT = f"""You answer questions using only the slides provided.

Rules:
- Each slide is labelled like [S1]. Put the label of the supporting slide right after every \
claim, for example: Revenue grew 12% [S2].
- Use only what the slides show. Do not use outside knowledge.
- If the slides do not support an answer, reply with exactly: {NOT_FOUND}
- Be concise. Give numbers with their units exactly as the slide shows them."""


def build_user_prompt(
    question: str, slides: list[RetrievedSlide], context_format: ContextFormat
) -> str:
    sections = []
    for number, slide in enumerate(slides, start=1):
        header = f"[S{number}] {slide.filename}, slide {slide.slide_no}"
        if context_format != "text":
            header += f" (image {number})"
        if context_format == "image":
            sections.append(header)
        else:
            sections.append(f"{header}\n{slide.text}")
    context = "\n\n".join(sections)
    return f"Slides:\n\n{context}\n\nQuestion: {question}"
