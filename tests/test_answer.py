from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image

from insight.generate.answer import load_context_image, parse_answer
from insight.generate.prompts import NOT_FOUND, build_user_prompt
from insight.models import RetrievedSlide
from insight.retrieve.dense import dedupe_to_slides


def slide(slide_no: int, score: float = 0.5, slide_id: UUID | None = None) -> RetrievedSlide:
    return RetrievedSlide(
        slide_id=slide_id or uuid4(),
        doc_id=uuid4(),
        filename="deck.pptx",
        slide_no=slide_no,
        title="Title",
        text=f"Text of slide {slide_no}",
        image_path=f"pages/x/{slide_no}.png",
        score=score,
    )


def test_citations_map_to_context_slides_in_first_seen_order() -> None:
    slides = [slide(7), slide(9)]
    answer = parse_answer("Up 12% [S2]. Margin 40% [S1]. Again [S2].", slides)
    assert [c.slide_no for c in answer.citations] == [9, 7]
    assert answer.text == "Up 12% [S2]. Margin 40% [S1]. Again [S2]."
    assert not answer.abstained


def test_citations_outside_the_context_are_dropped() -> None:
    answer = parse_answer("Up 12% [S9]. Down 3% [S1].", [slide(7)])
    assert [c.slide_no for c in answer.citations] == [7]
    assert answer.text == "Up 12%. Down 3% [S1]."


def test_grouped_tags_keep_only_valid_labels() -> None:
    answer = parse_answer("Both [S1, S5; s2].", [slide(1), slide(2)])
    assert [c.slide_no for c in answer.citations] == [1, 2]
    assert answer.text == "Both [S1, S2]."


def test_answer_without_tags_has_no_citations() -> None:
    answer = parse_answer("Revenue was 5.", [slide(1)])
    assert answer.citations == []
    assert not answer.abstained


def test_abstention_is_detected_and_clears_citations() -> None:
    answer = parse_answer(f"{NOT_FOUND.upper()}. [S1]", [slide(1)])
    assert answer.abstained
    assert answer.text == NOT_FOUND
    assert answer.citations == []


def test_dedupe_keeps_best_chunk_per_slide_and_limits_to_k() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    hits = [
        slide(1, 0.9, a),
        slide(1, 0.8, a),
        slide(2, 0.7, b),
        slide(1, 0.6, a),
        slide(3, 0.5, c),
    ]
    result = dedupe_to_slides(hits, top_k=2)
    assert [(s.slide_no, s.score) for s in result] == [(1, 0.9), (2, 0.7)]


def test_prompt_formats() -> None:
    slides = [slide(4)]
    assert "Text of slide 4" in build_user_prompt("Q?", slides, "text")
    assert "(image 1)" not in build_user_prompt("Q?", slides, "text")

    image_only = build_user_prompt("Q?", slides, "image")
    assert "(image 1)" in image_only
    assert "Text of slide 4" not in image_only

    both = build_user_prompt("Q?", slides, "both")
    assert "[S1] deck.pptx, slide 4 (image 1)" in both
    assert "Text of slide 4" in both
    assert both.endswith("Question: Q?")


def test_context_image_is_shrunk_to_max_side(tmp_path: Path) -> None:
    path = tmp_path / "slide.png"
    Image.new("RGB", (2000, 1000), "white").save(path)
    data = load_context_image(path, 500)
    output = tmp_path / "out.png"
    output.write_bytes(data)
    with Image.open(output) as image:
        assert image.size == (500, 250)
