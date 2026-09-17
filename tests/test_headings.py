"""Tests for finding a document's sections so a person can choose one."""

from __future__ import annotations

from local_ai_control_center.core.headings import Heading, headings_in, matching

NL = chr(10)


def _document(pages: list[list[str]]) -> str:
    return NL.join(
        f"<!-- page {n} -->{NL}{NL}" + NL.join(lines) for n, lines in enumerate(pages, start=1)
    )


def test_a_numbered_heading_is_found_with_its_page() -> None:
    source = _document([["Some prose."], ["6.4.4 The role of imaging", "More prose."]])
    found = headings_in(source)
    assert [(h.page, h.number, h.title) for h in found] == [(2, "6.4.4", "The role of imaging")]


def test_a_dosage_is_not_a_section() -> None:
    """Every survivor of the first filter was a figure: `27.4 ng/mL`, `8.9 yr. 10-yr. ASTRO`."""
    source = _document(
        [
            [
                "27.4 ng/mL and 1.8 ng/mL/month, respectively [964].",
                "8.9 yr. 10-yr. ASTRO",
                "0.0001 for 15-yr. results)",
                "13.3 yr.,",
            ]
        ]
    )
    assert headings_in(source) == ()


def test_a_single_level_number_is_not_admitted() -> None:
    """`6 Treatment` cannot be told from a numbered list item or a figure caption."""
    source = _document([["6 Treatment", "6.1 Treatment of something"]])
    assert [h.number for h in headings_in(source)] == ["6.1"]


def test_a_contents_line_is_marked_by_its_trailing_page_number() -> None:
    source = _document([["5.8 Diagnosis - Clinical Staging    46"]])
    found = headings_in(source)
    assert found[0].in_contents


def test_the_earlier_of_two_identical_numbers_is_the_contents() -> None:
    """A table of contents lists every section, so every number appears twice."""
    source = _document([["5.8.3.3 PSMA PET"], ["filler"], ["5.8.3.3 PSMA PET/CT"]])
    found = headings_in(source)
    assert [(h.page, h.in_contents) for h in found] == [(1, True), (3, False)]


def test_depth_comes_from_the_number() -> None:
    source = _document([["6.4 One", "6.4.5.1.2.3 Deep"]])
    depths = {h.number: h.depth for h in headings_in(source)}
    assert depths == {"6.4": 1, "6.4.5.1.2.3": 5}


def test_a_filter_folds_the_spacing_extraction_invents() -> None:
    """`PSMA PET/CT` arrives as `PSM A PET/CT`, and a search for psma found nothing."""
    headings = (Heading(page=50, title="PSM A PET/CT", number="5.8.3.3"),)
    assert matching(headings, ("psma",)) == headings


def test_a_filter_with_no_words_hides_nothing() -> None:
    headings = (Heading(page=1, title="Anything", number="1.1"),)
    assert matching(headings, ()) == headings
    assert matching(headings, ("  ",)) == headings


def test_a_source_without_page_markers_yields_nothing() -> None:
    assert headings_in("6.4.4 A heading with no page around it") == ()
