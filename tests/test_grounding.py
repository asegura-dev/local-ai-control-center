"""Tests for grounding: parsing claims, and checking quotations against the source."""

from __future__ import annotations

from local_ai_control_center.grounding import (
    Claim,
    check_answer,
    check_claim,
    pages_in,
    parse_claims,
)

_SOURCE = """<!-- page 1 -->

The study analysed 240 cases between 2019 and 2023 across three hospitals.

<!-- page 2 -->

Mortality fell by twelve per cent under the proposed protocol.
"""


def _answer(claim: str, quote: str, page: str) -> str:
    return f"CLAIM: {claim}\nQUOTE: {quote}\nPAGE: {page}"


def test_a_well_formed_block_parses() -> None:
    """The format a small model is asked for is read back as a claim."""
    claims = parse_claims(_answer("Three hospitals took part.", "across three hospitals", "1"))
    assert claims == (
        Claim(claim="Three hospitals took part.", quote="across three hospitals", page=1),
    )


def test_several_blocks_parse() -> None:
    """One block per claim, separated by a blank line."""
    text = _answer("First.", "quote one", "1") + "\n\n" + _answer("Second.", "quote two", "2")
    assert len(parse_claims(text)) == 2


def test_a_block_without_a_quotation_is_dropped() -> None:
    """There is nothing to check, so there is nothing to report as checked."""
    assert parse_claims("CLAIM: something asserted\nPAGE: 3") == ()


def test_surrounding_quotation_marks_are_not_part_of_the_quotation() -> None:
    """A model that wraps the quote in marks has still quoted the same words."""
    claims = parse_claims(_answer("A claim.", '"across three hospitals"', "1"))
    assert claims[0].quote == "across three hospitals"


def test_a_missing_page_is_recorded_as_unknown_not_as_zero() -> None:
    """Unknown is a state; zero would be a wrong answer."""
    assert parse_claims("CLAIM: a claim\nQUOTE: some words")[0].page is None


def test_a_real_quotation_on_its_real_page_verifies() -> None:
    """The ordinary case: the model quoted the document and said where."""
    checked = check_claim(Claim(claim="c", quote="across three hospitals", page=1), _SOURCE)
    assert checked.verdict == "verified"
    assert checked.holds is True


def test_an_invented_quotation_is_reported_as_not_found() -> None:
    """The failure this module exists for: words the document never contained.

    A prompt asking a model not to fabricate is a request. This is the check.
    """
    invented = Claim(claim="The sample was 500 patients.", quote="the sample was 500", page=1)
    checked = check_claim(invented, _SOURCE)
    assert checked.verdict == "not_found"
    assert checked.holds is False


def test_the_page_reported_is_the_one_found_not_the_one_claimed() -> None:
    """A model that misplaces a passage it quoted correctly no longer produces a bad page.

    On a real paper this failed often and independently of everything else: page 4 for a
    sentence on page 1. LACC locates the quotation anyway while verifying it, so it stops
    asking a model something it can answer itself (ADR-031).
    """
    checked = check_claim(Claim(claim="c", quote="Mortality fell by twelve", page=1), _SOURCE)
    assert checked.verdict == "verified"
    assert checked.found_on_page == 2


def test_the_model_being_wrong_about_the_page_is_still_recorded() -> None:
    """Out of the answer, into the audit: it measures fidelity, so it is not thrown away."""
    checked = check_claim(Claim(claim="c", quote="Mortality fell by twelve", page=1), _SOURCE)
    assert checked.page_disagreed is True


def test_a_model_that_placed_the_page_correctly_does_not_register_disagreement() -> None:
    """The ordinary case, so the signal counts what it says it counts."""
    checked = check_claim(Claim(claim="c", quote="Mortality fell by twelve", page=2), _SOURCE)
    assert checked.page_disagreed is False


def test_a_claim_with_no_page_disagrees_with_nothing() -> None:
    """Silence is not a wrong answer, and must not be counted as one."""
    checked = check_claim(Claim(claim="c", quote="Mortality fell by twelve"), _SOURCE)
    assert checked.verdict == "verified"
    assert checked.found_on_page == 2
    assert checked.page_disagreed is False


def test_layout_differences_do_not_hide_a_real_quotation() -> None:
    """Extracted text wraps differently than a model repeats it; that is not fabrication."""
    spaced = Claim(claim="c", quote="across   THREE\n  hospitals", page=1)
    assert check_claim(spaced, _SOURCE).verdict == "verified"


def test_a_near_miss_is_not_accepted() -> None:
    """Deliberately not fuzzy: a quotation that only nearly appears is not a quotation.

    "four hospitals" for "three hospitals" is exactly the error that must not pass.
    """
    near = Claim(claim="c", quote="across four hospitals", page=1)
    assert check_claim(near, _SOURCE).verdict == "not_found"


def test_a_source_without_page_markers_yields_a_quotation_with_no_page() -> None:
    """Unable to say is not the same as wrong, and is not reported as wrong.

    Anything LACC did not ingest has no markers, so the quotation still verifies as text
    and the page is simply unavailable.
    """
    plain = "The study analysed 240 cases across three hospitals."
    checked = check_claim(Claim(claim="c", quote="three hospitals", page=1), plain)
    assert checked.verdict == "page_unknown"
    assert checked.found_on_page is None


def test_pages_are_split_on_the_markers_ingestion_writes() -> None:
    """Page checking works because ingestion kept the boundaries (ADR-016)."""
    pages = pages_in(_SOURCE)
    assert [number for number, _ in pages] == [1, 2]
    assert "three hospitals" in pages[0][1]


def test_an_answer_is_checked_claim_by_claim() -> None:
    """A fabricated claim among real ones is the case that matters, and it is caught."""
    answer = "\n\n".join(
        [
            _answer("Real.", "across three hospitals", "1"),
            _answer("Invented.", "funded by the ministry of health", "2"),
        ]
    )
    checked = check_answer(answer, _SOURCE)
    assert [item.verdict for item in checked] == ["verified", "not_found"]
