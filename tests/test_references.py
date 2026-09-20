"""Reading the reference list a document already carries (ADR-064)."""

from __future__ import annotations

from local_ai_control_center.core.references import (
    Reference,
    reference_section,
    references_in,
    without_truncations,
)

NL = chr(10)


def _paper(body: str, heading: str = "## References") -> str:
    return "# A paper" + NL * 2 + "Some prose." + NL * 2 + heading + NL * 2 + body


def test_a_numbered_list_becomes_one_entry_each() -> None:
    """The numbering is the structure this relies on, rather than a model's willingness."""
    found = references_in(
        _paper(
            "1. Torre LA, Siegel RL. Global cancer. Cancer Epidemiol. 2016; 25:16-27."
            + NL
            + "2. Maurer T. Diagnostic efficacy. J Urol. 2016;195:1436-43."
            + NL
            + "3. Hofman MS. Prostate cancer. Lancet. 2020;395:1208-16."
        )
    )
    assert len(found) == 3
    assert found[0].text.startswith("1. Torre")
    assert found[2].year == 2020


def test_a_reference_wrapped_across_lines_is_still_one_entry() -> None:
    """A page breaks a reference wherever the column ends; an entry is not a line."""
    found = references_in(
        _paper(
            "1. Torre LA, Siegel RL, Ward EM. Global Cancer Inci -"
            + NL
            + "dence and Mortality Rates. Cancer Epidemiol."
            + NL
            + "2016; 25:16-27."
            + NL
            + "2. Maurer T. Diagnostic efficacy. J Urol. 2016."
            + NL
            + "3. Hofman MS. Lancet. 2020."
        )
    )
    assert len(found) == 3
    assert "Mortality Rates" in found[0].text


def test_a_doi_broken_by_the_typesetter_is_recovered() -> None:
    """`10. 1158/ 1055- 9965` is what extraction produces, and it is a real DOI.

    Recovered by the folding written for quotation checking, unchanged (ADR-035, ADR-044).
    """
    found = references_in(
        _paper(
            "1. Torre LA. Global cancer. 2016. https:// doi. org/ 10. 1158/ 1055- 9965"
            + NL
            + "2. Maurer T. J Urol. 2016."
            + NL
            + "3. Hofman MS. Lancet. 2020."
        )
    )
    assert found[0].doi.startswith("10.1158/1055-9965")


def test_a_doi_never_runs_into_the_reference_after_it() -> None:
    """The defect the first measurement found, and the reason entries are folded alone.

    Folding the whole section removes newlines with every other space, so a DOI at the end
    of one entry swallowed the next entry's number and first author. Every DOI came out
    distinct and the count of shared works was zero where the answer is eight (ADR-064).
    """
    found = references_in(
        _paper(
            "1. Torre LA. 2016. https://doi.org/10.1158/1055-9965.epi-15-0578"
            + NL
            + "2. Sung H. Global statistics. CA Cancer J Clin. 2021."
            + NL
            + "3. Hofman MS. Lancet. 2020."
        )
    )
    assert found[0].doi == "10.1158/1055-9965.epi-15-0578", "no tail from reference two"
    assert "sungh" not in found[0].doi


def test_a_truncated_doi_is_dropped_when_the_whole_one_is_present() -> None:
    """`10.2967/jnumed` is the broken half of `10.2967/jnumed.118.224055`.

    Decided by prefix rather than by a length nobody can justify.
    """
    kept = without_truncations(
        frozenset({"10.2967/jnumed", "10.2967/jnumed.118.224055", "10.1016/j.eururo.2015"})
    )
    assert kept == {"10.2967/jnumed.118.224055", "10.1016/j.eururo.2015"}


def test_nothing_is_invented_when_there_is_no_list() -> None:
    """A document that reports zero references is one to look at.

    Two of 24 real papers print author-year bibliographies with no numbering. They yield
    nothing here, visibly, rather than being guessed at.
    """
    assert (
        references_in(_paper("Baro J, Sempau J. PENELOPE. Nucl Instrum. 1995. 100, 31-46.")) == ()
    )
    assert references_in("# A paper" + NL * 2 + "No bibliography at all.") == ()


def test_a_run_of_two_numbers_is_not_a_bibliography() -> None:
    """Prose contains numbered lists. Three entries is what distinguishes them."""
    assert references_in(_paper("1. First point." + NL + "2. Second point.")) == ()


def test_the_last_heading_wins() -> None:
    """A paper says the word in its prose; the bibliography is at the end."""
    text = (
        "# A paper"
        + NL * 2
        + "We give references to the guideline throughout."
        + NL * 2
        + "## References"
        + NL * 2
        + "1. Torre LA. 2016."
        + NL
        + "2. Maurer T. 2016."
        + NL
        + "3. Hofman MS. 2020."
    )
    assert reference_section(text).strip().startswith("1. Torre")


def test_a_reference_is_frozen() -> None:
    """Like every model in the core."""
    import pytest
    from pydantic import ValidationError

    entry = Reference(text="1. Torre LA. 2016.")
    with pytest.raises(ValidationError):
        entry.text = "something else"  # type: ignore[misc]
