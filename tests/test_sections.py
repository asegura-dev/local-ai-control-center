"""What a document numbers for itself, and what only looks numbered (ADR-076).

The four rules that were tried are what is tested hardest, because three of them were wrong
and each was wrong in a way that produced plausible output.
"""

from __future__ import annotations

from pathlib import Path

from local_ai_control_center.core.sections import Section, section_of, sections_in


def _paper() -> str:
    """A paper with sections that have bodies, because a real one does.

    The first fixture put its headings four lines apart and the body condition rejected all
    of them - correctly. A fixture no real document resembles tests nothing (ADR-076).

    Each section carries a sentence of its own, so a test can say which one it got.
    """

    def body(marker: str) -> str:
        return (f"{marker} " + "Prose that carries the section. " * 3 + chr(10)) * 12

    return chr(10).join(
        [
            "Some opening prose about the study.",
            "",
            "1. Introduction",
            body("Prostate cancer is common."),
            "2. Materials and methods",
            "",
            "2.1. Image acquisition",
            body("Scans were acquired."),
            "2.2. Data pre-processing",
            body("Everything was resampled."),
            "3. Results",
            body("The model did well."),
            "4. Discussion",
            body("It is promising."),
        ]
    )


PAPER = _paper()


def test_a_document_that_numbers_its_sections_yields_them() -> None:
    found = sections_in(PAPER)
    assert [s.number for s in found] == ["1", "2", "2.1", "2.2", "3", "4"]
    assert [s.title for s in found][:2] == ["Introduction", "Materials and methods"]


def test_a_section_knows_where_it_starts() -> None:
    """The line number is how a person finds it in their own editor."""
    assert sections_in(PAPER)[0].line == 3


def test_a_bibliography_is_not_a_set_of_sections() -> None:
    """The second rule tried counted these, because every numbered list is consecutive.

    The dot is what tells them apart, and this is the case that proved it.
    """
    bibliography = """References

1 Afshar-Oromieh A, Avtzi E, Giesel FL, Holland-Letz T
2 Eiber M, Maurer T, Souvatzoglou M, Beer AJ, Ruffani A
3 Fendler WP, Eiber M, Beheshti M, Bomanji J, Ceci F
4 Perera M, Papa N, Roberts M, Williams M, Udovicich C
"""
    assert sections_in(bibliography) == ()


def test_author_affiliations_are_not_sections() -> None:
    """The other thing the consecutive rule counted, for the same reason."""
    affiliations = """1 Department of Nuclear Medicine, University Hospital Heidelberg
2 Department of Urology, University Hospital Heidelberg
3 Division of Radiopharmaceutical Chemistry, German Cancer Research Centre
"""
    assert sections_in(affiliations) == ()


def test_a_table_of_contents_is_excluded_by_the_page_it_carries() -> None:
    """The first rule tried counted the contents page and called it the document."""
    contents = """CONTENTS

1. INTRODUCTION      11
2. METHODS      14
3. EPIDEMIOLOGY AND AETIOLOGY      17
4. CLASSIFICATION      22
"""
    assert sections_in(contents) == ()


def test_numbering_with_a_gap_is_not_a_structure() -> None:
    """An outline runs 1, 2, 3. A list that starts at 4 is somebody else's numbering."""
    gapped = "1. Introduction\n\n3. Results\n\n7. Discussion\n"
    assert sections_in(gapped) == ()


def test_too_few_to_be_an_outline() -> None:
    assert sections_in("1. Introduction\n\n2. Methods\n") == ()


def test_a_sentence_beginning_with_a_number_is_not_a_heading() -> None:
    """Nine words is a name; more is a sentence that happens to start with a number."""
    body = ("Prose that carries the section. " * 4 + chr(10)) * 12
    prose = chr(10).join(
        [
            "1. Introduction",
            body,
            "2. Methods",
            body,
            "3. Results",
            body,
            "4. The following paragraph explains in some detail why this particular "
            "approach was chosen over the alternatives",
            body,
        ]
    )
    assert [s.number for s in sections_in(prose)] == ["1", "2", "3"]


def test_one_section_can_be_taken_out_with_what_is_under_it() -> None:
    """Asking for a section means that section and everything nested in it."""
    taken = section_of(PAPER, "2")
    assert taken.startswith("2. Materials and methods")
    assert "2.1. Image acquisition" in taken
    assert "Everything was resampled." in taken
    assert "3. Results" not in taken


def test_a_subsection_stops_at_its_sibling() -> None:
    taken = section_of(PAPER, "2.1")
    assert "Scans were acquired." in taken
    assert "Everything was resampled." not in taken


def test_asking_for_a_section_that_is_not_there_returns_nothing() -> None:
    assert section_of(PAPER, "9") == ""


def test_depth_and_parent_are_read_from_the_number() -> None:
    section = Section(number="6.3", title="Something", line=1)
    assert section.depth == 2
    assert section.top == "6"


def test_the_real_documents_are_parsed_the_way_the_record_says() -> None:
    """Against the workspace if it is there, which is where the figure in ADR-076 came from."""
    workspace = Path.home() / "lacc-workspace"
    if not workspace.is_dir():
        return
    papers = [p for p in workspace.glob("*.md") if p.name.startswith("[")]
    if not papers:
        return
    with_sections = sum(
        1 for p in papers if sections_in(p.read_text(encoding="utf-8", errors="replace"))
    )
    # The honest figure was six of twenty-four. This asserts the shape rather than the count:
    # documents come and go from a workspace, and a test that pinned it would fail for that
    # rather than for anything being wrong.
    assert 0 < with_sections < len(papers), (
        f"{with_sections} of {len(papers)} - some documents number their sections and some "
        "do not, and both are expected"
    )
