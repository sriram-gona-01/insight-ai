"""Render documents to one PNG per slide: PPTX -> PDF -> PNG, or PDF -> PNG."""

import subprocess
import tempfile
from pathlib import Path

import pypdfium2

PDF_POINTS_PER_INCH = 72


class RenderError(RuntimeError):
    pass


def convert_pptx_to_pdf(pptx: Path, out_dir: Path, soffice_path: str, timeout: int) -> Path:
    """Convert with headless LibreOffice, using a throwaway profile so runs don't collide."""
    with tempfile.TemporaryDirectory() as profile:
        command = [
            soffice_path,
            f"-env:UserInstallation={Path(profile).as_uri()}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(pptx.resolve()),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError as e:
            raise RenderError(f"LibreOffice not found at '{soffice_path}'") from e
        except subprocess.TimeoutExpired as e:
            raise RenderError(f"LibreOffice timed out after {timeout}s") from e

    pdf = out_dir / f"{pptx.stem}.pdf"
    if result.returncode != 0 or not pdf.exists():
        raise RenderError(f"LibreOffice failed to convert the file: {result.stderr.strip()}")
    return pdf


def render_pdf(pdf: Path, out_dir: Path, dpi: int) -> list[Path]:
    """Write `<n>.png` for each page, numbered from 1, and return the paths in order."""
    out_dir.mkdir(parents=True, exist_ok=True)
    document = pypdfium2.PdfDocument(str(pdf))
    paths: list[Path] = []
    try:
        for number, page in enumerate(document, start=1):
            path = out_dir / f"{number}.png"
            page.render(scale=dpi / PDF_POINTS_PER_INCH).to_pil().save(path)
            paths.append(path)
    finally:
        document.close()
    return paths


def render_document(
    path: Path, out_dir: Path, dpi: int, soffice_path: str, soffice_timeout: int
) -> list[Path]:
    if path.suffix.lower() == ".pdf":
        return render_pdf(path, out_dir, dpi)
    with tempfile.TemporaryDirectory() as tmp:
        pdf = convert_pptx_to_pdf(path, Path(tmp), soffice_path, soffice_timeout)
        return render_pdf(pdf, out_dir, dpi)
