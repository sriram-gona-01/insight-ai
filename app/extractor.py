# app/extractor.py

import os
import io
import tempfile
from typing import List, Dict
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from PIL import Image
import pdfplumber

from app.summarizer import summarize_image

def extract_documents(path: str) -> List[Dict[str, str]]:
    """
    Given a .pptx/.ppt or .pdf, return a list of chunks:
      [
        {"id": "s1_img_summary", "text": "<OCR+VLM summary>"},
        {"id": "s1_txt0",        "text": "<first text block>"},
        {"id": "s1_tbl1",        "text": "<first table>"},
        {"id": "s1_cht2",        "text": "<first chart>"},
        ... repeat for slide 2 ...
      ]
      or for PDF:
      [
        {"id": "p1_txt0",        "text": "<page1 text>"},
        {"id": "p2_txt0",        "text": "<page2 text>"},
        ...
      ]
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    chunks: List[Dict[str, str]] = []

    if ext in (".pptx", ".ppt"):
        prs = Presentation(path)
        for si, slide in enumerate(prs.slides, start=1):
            # 1) Image summary via VLM on the first picture
            for shape in slide.shapes:
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    img = Image.open(io.BytesIO(shape.image.blob)).convert("RGB")
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        img.save(tmp.name, format="PNG")
                        tmp_path = tmp.name

                    try:
                        summary = summarize_image(tmp_path)
                    finally:
                        os.unlink(tmp_path)

                    chunks.append({
                        "id": f"s{si}_img_summary",
                        "text": summary
                    })
                    break  # only one summary per slide

            # prepare a running counter for mixed text/table/chart chunks
            cnt = 0

            # 2) Text frames
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    txt = shape.text_frame.text.strip()
                    if txt:
                        chunks.append({
                            "id": f"s{si}_txt{cnt}",
                            "text": txt
                        })
                        cnt += 1

            # 3) Tables
            for shape in slide.shapes:
                if getattr(shape, "has_table", False):
                    rows = [
                        " | ".join(cell.text.strip() for cell in row.cells)
                        for row in shape.table.rows
                    ]
                    txt = "\n".join(rows).strip()
                    if txt:
                        chunks.append({
                            "id": f"s{si}_tbl{cnt}",
                            "text": txt
                        })
                        cnt += 1

            # 4) Charts
            for shape in slide.shapes:
                if getattr(shape, "has_chart", False):
                    parts: List[str] = []
                    for series in shape.chart.series:
                        parts.append("Categories: " + ", ".join(map(str, series.categories)))
                        parts.append("Values:     " + ", ".join(map(str, series.values)))
                    txt = "\n".join(parts).strip()
                    if txt:
                        chunks.append({
                            "id": f"s{si}_cht{cnt}",
                            "text": txt
                        })
                        cnt += 1

    elif ext == ".pdf":
        with pdfplumber.open(path) as pdf:
            for pi, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                cleaned = "\n\n".join(
                    line.strip() for line in text.splitlines() if line.strip()
                )
                chunks.append({
                    "id": f"p{pi}_txt0",
                    "text": cleaned
                })
    else:
        raise ValueError(f"Unsupported extension: {ext}")

    return chunks
