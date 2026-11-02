from pathlib import Path

import pytest
from fixtures import make_pdf, make_pptx

from insight.ingest.pipeline import InvalidDocument, clean_filename, file_sha256, validate_file
from insight.store.db import render_schema


def test_accepts_real_files(tmp_path: Path) -> None:
    validate_file(make_pptx(tmp_path / "a.pptx"), 10)
    validate_file(make_pdf(tmp_path / "a.pdf"), 10)


@pytest.mark.parametrize("name", ["notes.txt", "old.ppt", "noextension"])
def test_rejects_other_extensions(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_text("content")
    with pytest.raises(InvalidDocument, match="Unsupported"):
        validate_file(path, 10)


@pytest.mark.parametrize("name", ["fake.pdf", "fake.pptx"])
def test_rejects_content_that_does_not_match_extension(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_text("not a real document")
    with pytest.raises(InvalidDocument, match="isn't"):
        validate_file(path, 10)


def test_rejects_oversized_files(tmp_path: Path) -> None:
    path = tmp_path / "big.pdf"
    path.write_bytes(b"%PDF-" + b"0" * (1024 * 1024))
    with pytest.raises(InvalidDocument, match="larger"):
        validate_file(path, 1)


def test_clean_filename_drops_directories_and_control_characters() -> None:
    assert clean_filename("../../etc/pass\nwd.pdf") == "passwd.pdf"
    assert clean_filename("\n") == "unnamed"


def test_sha256_depends_on_content_only(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(b"same")
    second.write_bytes(b"same")
    assert file_sha256(first) == file_sha256(second)


def test_schema_uses_configured_dim() -> None:
    schema = render_schema(384)
    assert "vector(384)" in schema
    assert "{{" not in schema
