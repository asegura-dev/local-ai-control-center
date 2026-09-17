"""The grounding check, graded against answers known before it ran (ADR-044).

Every other figure this project has published was measured against real papers where nobody
knew the correct answer, which is the condition that produced nine wrong ones. Here the
answer is written down first, by a person, in `fixtures/seeded/truth.yaml`.

The assertion is exact in both directions. A check that flags a real quotation fails as hard
as one that misses a seeded fabrication, because reporting its own limit as a catch is the
failure the whole corpus exists to catch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from local_ai_control_center.core.grounding import Claim, check_claim

_SEEDED = Path(__file__).parent / "fixtures" / "seeded"


def _truth() -> list[dict[str, Any]]:
    loaded = yaml.safe_load((_SEEDED / "truth.yaml").read_text(encoding="utf-8"))
    return list(loaded["documents"])


def _cases() -> list[tuple[str, dict[str, Any]]]:
    return [
        (document["file"], quotation)
        for document in _truth()
        for quotation in document["quotations"]
    ]


def _identify(case: tuple[str, dict[str, Any]]) -> str:
    name, quotation = case
    return f"{name}:{'real' if quotation['real'] else 'seeded'}:{quotation['seed'][:40]}"


@pytest.mark.parametrize("case", _cases(), ids=_identify)
def test_each_quotation_is_found_exactly_when_it_is_real(case: tuple[str, dict[str, Any]]) -> None:
    name, quotation = case
    source = (_SEEDED / name).read_text(encoding="utf-8")
    checked = check_claim(Claim(claim="graded", quote=quotation["quote"]), source)

    assert checked.found is quotation["real"], f"{name}: {quotation['seed']}" + (
        "  - a real quotation was reported as not in the document"
        if quotation["real"]
        else "  - a seeded fabrication was reported as found"
    )


@pytest.mark.parametrize("case", _cases(), ids=_identify)
def test_a_page_is_named_whenever_the_document_has_pages(
    case: tuple[str, dict[str, Any]],
) -> None:
    """`found` and `holds` are different questions, and the fixture records which is which."""
    name, quotation = case
    if not quotation["real"]:
        return
    source = (_SEEDED / name).read_text(encoding="utf-8")
    checked = check_claim(Claim(claim="graded", quote=quotation["quote"]), source)

    if quotation.get("placeable", True):
        assert checked.holds, f"{name}: {quotation['seed']} - no page was named"
        assert checked.found_on_page == quotation["page"]
    else:
        assert checked.found and not checked.holds
        assert checked.verdict == "page_unknown"


def test_the_corpus_grades_the_check_and_the_totals_are_exact() -> None:
    """The headline this project may quote: measured where the answer was known first."""
    real = seeded = caught = flagged = 0
    for name, quotation in _cases():
        source = (_SEEDED / name).read_text(encoding="utf-8")
        found = check_claim(Claim(claim="graded", quote=quotation["quote"]), source).found
        if quotation["real"]:
            real += 1
            flagged += not found
        else:
            seeded += 1
            caught += not found

    assert (real, seeded) == (6, 6), "the corpus changed; update this and say so"
    assert caught == seeded, f"{seeded - caught} of {seeded} seeded fabrications were missed"
    assert flagged == 0, f"{flagged} of {real} real quotations were reported as fabrications"


def test_the_corpus_does_not_claim_to_grade_what_it_cannot() -> None:
    """The boundary ADR-026 drew, restated where somebody reading the numbers will see it.

    Every quotation here is graded on whether its words are in the document. None of them is
    graded on whether what it says is true, because nothing in this project can do that.
    """
    text = (_SEEDED / "truth.yaml").read_text(encoding="utf-8")
    assert "page furniture" in text, "the fixture must say what it leaves to other tests"
