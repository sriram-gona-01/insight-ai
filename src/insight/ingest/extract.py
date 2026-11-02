"""Extract text, tables, chart data, and notes from each slide or PDF page."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from insight.models import ChunkKind


@dataclass(frozen=True)
class Block:
    kind: ChunkKind
    text: str


@dataclass(frozen=True)
class ExtractedSlide:
    slide_no: int
    title: str
    blocks: list[Block]

    @property
    def text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks)


def to_markdown_table(rows: list[list[Any]]) -> str:
    def cell(value: Any) -> str:
        text = "" if value is None else str(value)
        return " ".join(text.split()).replace("|", "\\|")

    width = max(len(row) for row in rows)
    lines = []
    for row in rows:
        cells = [cell(value) for value in row] + [""] * (width - len(row))
        lines.append("| " + " | ".join(cells) + " |")
    lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
    return "\n".join(lines)


def _format_number(value: float | None) -> str:
    if value is None:
        return ""
    return str(int(value)) if float(value).is_integer() else str(value)


def _chart_to_markdown(chart: Any) -> str:
    plots = list(chart.plots)
    series = [s for plot in plots for s in plot.series]
    if not series:
        return ""
    categories = next((list(p.categories) for p in plots if len(p.categories) > 0), [])
    values = [list(s.values) for s in series]
    n_rows = max(len(v) for v in values)

    rows: list[list[Any]] = [["Category"] + [s.name for s in series]]
    for i in range(n_rows):
        label = categories[i] if i < len(categories) else i + 1
        rows.append([label] + [_format_number(v[i]) if i < len(v) else "" for v in values])

    table = to_markdown_table(rows)
    if chart.has_title and chart.chart_title.text_frame.text.strip():
        return f"{chart.chart_title.text_frame.text.strip()}\n{table}"
    return table


def _reading_order(shapes: Iterable[Any]) -> Iterator[Any]:
    """Yield shapes top to bottom, then left to right, descending into groups."""
    for shape in sorted(shapes, key=lambda s: (s.top or 0, s.left or 0)):
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _reading_order(shape.shapes)
        else:
            yield shape


def _shape_block(shape: Any) -> Block | None:
    if getattr(shape, "has_table", False):
        rows = [[cell.text for cell in row.cells] for row in shape.table.rows]
        return Block("table", to_markdown_table(rows)) if rows else None
    if getattr(shape, "has_chart", False):
        markdown = _chart_to_markdown(shape.chart)
        return Block("chart", markdown) if markdown else None
    if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
        return Block("text", shape.text_frame.text.strip())
    return None


def _first_line(text: str) -> str:
    return text.splitlines()[0].strip() if text.strip() else ""


def extract_pptx(path: Path) -> list[ExtractedSlide]:
    """Extract visible slides. LibreOffice omits hidden slides from its PDF, so numbering
    here matches the rendered images."""
    slides: list[ExtractedSlide] = []
    visible = [s for s in Presentation(str(path)).slides if s._element.get("show") != "0"]
    for number, slide in enumerate(visible, start=1):
        blocks = [b for b in map(_shape_block, _reading_order(slide.shapes)) if b]

        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                blocks.append(Block("notes", notes))

        title_shape = slide.shapes.title
        title = title_shape.text_frame.text.strip() if title_shape is not None else ""
        if not title:
            title = next((_first_line(b.text) for b in blocks if b.kind == "text"), "")
        slides.append(ExtractedSlide(number, " ".join(title.split()), blocks))
    return slides


def _real_tables(page: Any) -> list[Any]:
    """Keep tables with at least 2 rows and 2 columns; a lone bordered box isn't a table."""
    tables = []
    for table in page.find_tables():
        rows = table.extract()
        if len(rows) >= 2 and max(len(row) for row in rows) >= 2:
            tables.append(table)
    return tables


def extract_pdf(path: Path) -> list[ExtractedSlide]:
    slides: list[ExtractedSlide] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            tables = _real_tables(page)

            def outside_tables(obj: dict[str, Any], tables: list[Any] = tables) -> bool:
                if obj["object_type"] != "char":
                    return True
                x = (obj["x0"] + obj["x1"]) / 2
                y = (obj["top"] + obj["bottom"]) / 2
                return not any(
                    t.bbox[0] <= x <= t.bbox[2] and t.bbox[1] <= y <= t.bbox[3] for t in tables
                )

            text = (page.filter(outside_tables).extract_text() or "").strip()
            blocks = [Block("text", text)] if text else []
            blocks += [Block("table", to_markdown_table(t.extract())) for t in tables]
            slides.append(ExtractedSlide(number, _first_line(text), blocks))
    return slides


def extract_document(path: Path) -> list[ExtractedSlide]:
    if path.suffix.lower() == ".pdf":
        return extract_pdf(path)
    return extract_pptx(path)
