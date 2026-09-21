"""Turning this project's own documentation into blocks (ADR-070).

The window cannot be tested, so everything it would otherwise decide is here and is. What is
tested hardest is the part that fails silently: a paragraph split into fragments, or a fenced
block cut on its blank lines, both render as something and neither looks wrong until read.
"""

from __future__ import annotations

from pathlib import Path

from local_ai_control_center.features.reading import (
    blocks_in,
    documentation_near,
    pages_in,
    plain,
)


def test_a_heading_keeps_its_depth() -> None:
    blocks = blocks_in("# One\n\n### Three\n")
    assert [(b.kind, b.level, b.text) for b in blocks] == [
        ("heading", 1, "One"),
        ("heading", 3, "Three"),
    ]


def test_a_wrapped_paragraph_stays_one_block() -> None:
    """Every file here wraps its prose. One block per line would be a column of fragments."""
    blocks = blocks_in("a sentence that runs\nacross two lines\n\nand a second one\n")
    assert [b.text for b in blocks] == ["a sentence that runs across two lines", "and a second one"]


def test_fenced_code_survives_its_blank_lines() -> None:
    """A fence can contain blank lines, so splitting on those first would cut code up."""
    blocks = blocks_in("```python\nx = 1\n\ny = 2\n```\n")
    assert [b.kind for b in blocks] == ["code"]
    assert blocks[0].text == "x = 1\n\ny = 2"


def test_an_unclosed_fence_still_yields_its_code() -> None:
    """A truncated document should show what it has rather than nothing."""
    assert [b.kind for b in blocks_in("```\nx = 1\n")] == ["code"]


def test_inline_markup_becomes_the_words_it_wrapped() -> None:
    assert plain("**bold** and *thin* and `code`") == "bold and thin and code"
    assert plain("see [the record](ADR-042.md) for it") == "see the record for it"


def test_a_heading_with_markup_in_it_reads_as_words() -> None:
    assert blocks_in("## The `corpus` command\n")[0].text == "The corpus command"


def test_quotations_and_items_are_their_own_kinds() -> None:
    blocks = blocks_in("> quoted words\n\n- an item\n\n1. a numbered one\n")
    assert [(b.kind, b.text) for b in blocks] == [
        ("quote", "quoted words"),
        ("item", "an item"),
        ("item", "a numbered one"),
    ]


def test_a_table_keeps_its_cells_and_drops_its_ruling() -> None:
    """The alignment row is punctuation, not content, and would render as dashes."""
    blocks = blocks_in("| what | how |\n|---|---|\n| a thing | a way |\n")
    assert [b.text for b in blocks if b.kind == "table"] == ["what   how", "a thing   a way"]


def test_a_rule_is_a_block_rather_than_a_paragraph_of_dashes() -> None:
    assert [b.kind for b in blocks_in("one\n\n---\n\ntwo\n")] == ["text", "rule", "text"]


def test_this_project_finds_its_own_documentation() -> None:
    """The folder is found by walking up, never taken from a setting."""
    import local_ai_control_center

    folder = documentation_near(Path(local_ai_control_center.__file__).parent)
    assert folder is not None
    assert (folder / "adr").is_dir()


def test_every_record_in_this_repository_parses_into_blocks() -> None:
    """The real test: the documents that will actually be opened.

    Run against every Markdown file in `docs/`, because a parser that works on a fixture and
    not on the corpus it was written for is the defect this project has found seven times by
    using the tool instead of testing it.
    """
    import local_ai_control_center

    folder = documentation_near(Path(local_ai_control_center.__file__).parent)
    assert folder is not None
    pages = pages_in(folder)
    assert len(pages) > 50, "the records should be found"
    for page in pages:
        blocks = blocks_in(page.path.read_text(encoding="utf-8", errors="replace"))
        assert blocks, f"{page.path.name} produced nothing"
        assert any(b.kind == "heading" for b in blocks), f"{page.path.name} has no heading"


def test_a_page_is_titled_by_its_own_first_heading() -> None:
    import local_ai_control_center

    folder = documentation_near(Path(local_ai_control_center.__file__).parent)
    assert folder is not None
    titles = {page.title for page in pages_in(folder)}
    assert any("Roadmap" in title for title in titles)
