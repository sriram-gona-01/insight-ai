from pathlib import Path

from fixtures import make_pdf, make_pptx

from insight.ingest.extract import extract_pdf, extract_pptx, to_markdown_table


def test_to_markdown_table_escapes_and_pads() -> None:
    assert to_markdown_table([["a|b", None], ["multi\nline"]]) == (
        "| a\\|b |  |\n| --- | --- |\n| multi line |  |"
    )


def test_pptx_text_and_notes(tmp_path: Path) -> None:
    slide = extract_pptx(make_pptx(tmp_path / "d.pptx"))[0]
    assert slide.slide_no == 1
    assert slide.title == "Acme overview"
    kinds = {b.kind: b.text for b in slide.blocks}
    assert "Mention the new Tulsa plant" == kinds["notes"]
    assert [b.text for b in slide.blocks if b.kind == "text"] == [
        "Acme overview",
        "Revenue grew in every region",
    ]


def test_pptx_table_becomes_markdown(tmp_path: Path) -> None:
    slide = extract_pptx(make_pptx(tmp_path / "d.pptx"))[1]
    table = next(b for b in slide.blocks if b.kind == "table")
    assert table.text == "| Segment | Margin |\n| --- | --- |\n| Cloud | 41% |"


def test_pptx_chart_keeps_series_names_and_values(tmp_path: Path) -> None:
    slide = extract_pptx(make_pptx(tmp_path / "d.pptx"))[2]
    chart = next(b for b in slide.blocks if b.kind == "chart")
    assert "| Category | Revenue | Cost |\n| --- | --- | --- |" in chart.text
    assert "| Q1 | 10.5 | 4 |" in chart.text
    assert "| Q2 | 12 | 5 |" in chart.text


def test_pptx_skips_hidden_slides_and_numbers_visible_ones(tmp_path: Path) -> None:
    slides = extract_pptx(make_pptx(tmp_path / "d.pptx"))
    assert [s.slide_no for s in slides] == [1, 2, 3]
    assert all("Hidden" not in s.text for s in slides)


def test_pdf_table_text_is_not_duplicated(tmp_path: Path) -> None:
    page = extract_pdf(make_pdf(tmp_path / "d.pdf"))[0]
    assert page.title == "Acme financial summary"
    text = next(b for b in page.blocks if b.kind == "text").text
    table = next(b for b in page.blocks if b.kind == "table").text
    assert "Operating income improved" in text
    assert "77" not in text
    assert "| 2024 | 77 |" in table


def test_pdf_lone_box_is_not_a_table(tmp_path: Path) -> None:
    page = extract_pdf(make_pdf(tmp_path / "d.pdf"))[1]
    assert [b.kind for b in page.blocks] == ["text"]
    assert "Text inside a box" in page.blocks[0].text
