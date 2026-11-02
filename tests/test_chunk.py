from insight.ingest.chunk import chunk_block, split_table, split_text
from insight.ingest.extract import Block


def words(text: str) -> int:
    return len(text.split())


def test_short_text_is_unchanged() -> None:
    assert split_text("one two", 5, words) == ["one two"]


def test_splits_at_lines_first() -> None:
    assert split_text("a b\nc d\ne f", 4, words) == ["a b\nc d", "e f"]


def test_long_line_splits_at_words() -> None:
    assert split_text("a b c d e", 2, words) == ["a b", "c d", "e"]


def test_unbreakable_text_splits_by_characters() -> None:
    def characters(text: str) -> int:
        return len(text)

    assert split_text("abcdefgh", 4, characters) == ["abcd", "efgh"]


def test_every_word_survives_splitting() -> None:
    text = "\n".join(f"line{i} word{i} more{i}" for i in range(50))
    pieces = split_text(text, 7, words)
    assert all(words(p) <= 7 for p in pieces)
    assert " ".join(pieces).split() == text.split()


def test_table_split_repeats_header() -> None:
    rows = "\n".join(f"| r{i} | {i} |" for i in range(20))
    table = f"| Name | Value |\n| --- | --- |\n{rows}"
    pieces = split_table(table, 50, words)
    assert len(pieces) > 1
    assert all(p.startswith("| Name | Value |\n| --- | --- |\n") for p in pieces)
    assert sum(p.count("| r") for p in pieces) == 20


def test_chart_title_stays_in_repeated_header() -> None:
    rows = "\n".join(f"| q{i} | {i} |" for i in range(20))
    chart = f"Sales\n| Name | Value |\n| --- | --- |\n{rows}"
    pieces = split_table(chart, 50, words)
    assert len(pieces) > 1
    assert all(p.startswith("Sales\n| Name") for p in pieces)


def test_title_prefix_only_changes_embedding_text() -> None:
    draft = chunk_block(Block("table", "| a |"), "Q3 revenue", 100, words, True)[0]
    assert draft.text == "| a |"
    assert draft.embedding_text == "Q3 revenue\n| a |"


def test_title_is_not_repeated_when_block_starts_with_it() -> None:
    draft = chunk_block(Block("text", "Q3 revenue"), "Q3 revenue", 100, words, True)[0]
    assert draft.embedding_text == "Q3 revenue"


def test_title_prefix_can_be_disabled() -> None:
    draft = chunk_block(Block("text", "body"), "Q3 revenue", 100, words, False)[0]
    assert draft.embedding_text == "body"


def test_title_tokens_reduce_the_chunk_limit() -> None:
    drafts = chunk_block(Block("text", " ".join("x" * 100)), "T " * 10, 50, words, True)
    assert all(words(d.embedding_text) <= 50 for d in drafts)
