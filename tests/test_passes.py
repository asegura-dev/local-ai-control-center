"""Tests for dividing a document into readings that fit the window."""

from __future__ import annotations

from local_ai_control_center.core.budget import estimate_tokens
from local_ai_control_center.core.grounding import Claim, check_claim, page_spans
from local_ai_control_center.core.passes import passes_over

NL = chr(10)


def _document(pages: list[str]) -> str:
    return NL.join(f"<!-- page {n} -->{NL}{NL}{text}" for n, text in enumerate(pages, start=1))


def test_a_document_that_fits_is_read_once() -> None:
    source = _document(["alpha", "beta", "gamma"])
    readings = passes_over(source, budget_tokens=10_000)
    assert len(readings) == 1
    assert (readings[0].first_page, readings[0].last_page) == (1, 3)
    assert readings[0].pages == 3


def test_a_source_without_page_markers_cannot_be_divided() -> None:
    """Anything LACC did not ingest has no honest place to split."""
    assert passes_over("a document with no markers at all", budget_tokens=10) == ()


def test_consecutive_readings_overlap_by_exactly_one_page() -> None:
    source = _document([f"page {n} " + "word " * 200 for n in range(1, 11)])
    readings = passes_over(source, budget_tokens=800)
    assert len(readings) > 2, "this document is meant to need several readings"
    for earlier, later in zip(readings, readings[1:], strict=False):
        assert later.first_page == earlier.last_page


def test_no_page_is_left_out_of_every_reading() -> None:
    """The failure that would matter most: a document reported as read, minus a page."""
    source = _document([f"page {n} " + "word " * 200 for n in range(1, 11)])
    readings = passes_over(source, budget_tokens=800)
    covered = {n for r in readings for n in range(r.first_page, r.last_page + 1)}
    assert covered == {number for number, _, _ in page_spans(source)}


def test_a_reading_keeps_the_page_markers_so_it_looks_like_a_document() -> None:
    source = _document([f"page {n} " + "word " * 200 for n in range(1, 11)])
    for reading in passes_over(source, budget_tokens=800):
        assert reading.text.startswith(f"<!-- page {reading.first_page} -->")
        assert f"<!-- page {reading.last_page} -->" in reading.text


def test_a_page_larger_than_the_budget_is_still_offered_not_dropped() -> None:
    """Silently leaving it out would be this module deciding a page does not count."""
    source = _document(["small", "enormous " * 2000, "small again"])
    readings = passes_over(source, budget_tokens=100)
    covered = {n for r in readings for n in range(r.first_page, r.last_page + 1)}
    assert 2 in covered
    oversized = [r for r in readings if estimate_tokens(r.text) > 100]
    assert oversized, "the caller must be able to see that it does not fit"


def test_a_quotation_spanning_a_page_break_is_whole_inside_some_reading() -> None:
    """The property overlap exists for: ADR-042's case must survive being divided."""
    pages = [f"page {n} " + "word " * 200 for n in range(1, 11)]
    pages[4] = pages[4] + " The sensitivity was"
    pages[5] = "ninety four per cent in that cohort. " + pages[5]
    source = _document(pages)
    quote = "The sensitivity was ninety four per cent in that cohort."

    readings = passes_over(source, budget_tokens=800)
    assert len(readings) > 2
    claim = Claim(claim="c", quote=quote)
    assert any(check_claim(claim, r.text).found for r in readings)


def test_without_room_for_two_pages_there_is_no_overlap_and_the_guarantee_is_gone() -> None:
    """The stated exception, pinned. A page that fills the budget cannot be overlapped."""
    pages = [f"page {n} " + "word " * 200 for n in range(1, 6)]
    pages[2] = pages[2] + " The sensitivity was"
    pages[3] = "ninety four per cent in that cohort. " + pages[3]
    source = _document(pages)

    readings = passes_over(source, budget_tokens=400)
    assert all(r.pages == 1 for r in readings)
    assert [r.first_page for r in readings] == [1, 2, 3, 4, 5], "every page still read"

    claim = Claim(claim="c", quote="The sensitivity was ninety four per cent in that cohort.")
    assert not any(check_claim(claim, r.text).found for r in readings)
    assert check_claim(claim, source).found, "and it is there, in the whole document"
