"""Reading back a collected corpus, and the round trip that makes that safe."""

from __future__ import annotations

from local_ai_control_center.cli import _collected_markdown
from local_ai_control_center.core.corpus import about, parse_corpus
from local_ai_control_center.core.grounding import CheckedClaim, Claim
from local_ai_control_center.core.preview import ExecutionPreview, IntendedAction
from local_ai_control_center.cycle import RunResult


def _result(*checked: CheckedClaim) -> RunResult:
    preview = ExecutionPreview(
        action=IntendedAction(name="extract_claims", summary="s", required=frozenset()),
        allowed=True,
    )
    return RunResult(preview=preview, outcome="completed", checked_claims=checked)


def _checked(quote: str, claim: str, verdict: str, page: int | None = None) -> CheckedClaim:
    return CheckedClaim(claim=Claim(claim=claim, quote=quote), verdict=verdict, found_on_page=page)


def test_what_the_writer_produces_is_read_back_unchanged() -> None:
    """The round trip that answers the unease about re-parsing generated prose."""
    result = _result(
        _checked("a placed quotation", "it was placed", "verified", 7),
        _checked("an unplaceable one", "it is there", "page_unknown"),
        _checked("one that is nowhere", "it is not there", "not_found"),
    )
    written = _collected_markdown("extract_claims", "a-model", [("paper.md", result)])
    read_back = parse_corpus(written)

    assert [c.quote for c in read_back] == [
        "a placed quotation",
        "an unplaceable one",
        "one that is nowhere",
    ]
    assert [c.claim for c in read_back] == ["it was placed", "it is there", "it is not there"]
    assert [c.page for c in read_back] == [7, None, None]
    assert all(c.document == "paper.md" for c in read_back)


def test_several_documents_keep_their_claims_apart() -> None:
    first = _result(_checked("from the first", "a", "verified", 1))
    second = _result(_checked("from the second", "b", "verified", 2))
    written = _collected_markdown("extract_claims", "m", [("one.md", first), ("two.md", second)])
    read_back = parse_corpus(written)
    assert [(c.document, c.quote) for c in read_back] == [
        ("one.md", "from the first"),
        ("two.md", "from the second"),
    ]


def test_a_document_that_was_not_collected_contributes_nothing() -> None:
    """Its section names a failure, not a claim, and an empty entry would be a lie."""
    good = _result(_checked("a real one", "a", "verified", 1))
    written = _collected_markdown(
        "extract_claims", "m", [("broken.md", "Cannot reach Ollama."), ("ok.md", good)]
    )
    read_back = parse_corpus(written)
    assert [c.document for c in read_back] == ["ok.md"]


def test_the_old_label_that_conflated_two_outcomes_is_kept_for_comparison() -> None:
    """A corpus written before v1.2.0 called an unplaceable quotation a fabrication."""
    old = (
        "## paper.md"
        + chr(10) * 2
        + "*1 of 2 quotations verified.*"
        + chr(10) * 2
        + "> really in the document"
        + chr(10) * 2
        + "page unknown - **NOT IN THE DOCUMENT**"
        + chr(10) * 2
        + "the paraphrase"
        + chr(10)
    )
    read_back = parse_corpus(old)
    assert len(read_back) == 1
    assert read_back[0].recorded_verdict == "**NOT IN THE DOCUMENT**"
    assert read_back[0].quote == "really in the document"


def test_nearest_text_is_carried_back() -> None:
    result = _result(
        CheckedClaim(
            claim=Claim(claim="c", quote="not there"),
            verdict="not_found",
            nearest="what the document does say",
        )
    )
    written = _collected_markdown("extract_claims", "m", [("paper.md", result)])
    assert parse_corpus(written)[0].nearest == "what the document does say"


def test_marking_a_subject_folds_the_spacing_extraction_invents() -> None:
    result = _result(_checked("The PSM A PET/CT protocol", "c", "verified", 1))
    claims = parse_corpus(_collected_markdown("extract_claims", "m", [("p.md", result)]))
    assert about(claims, ("psma",)) == frozenset({"The PSM A PET/CT protocol"})


def test_marking_with_no_words_marks_nothing() -> None:
    result = _result(_checked("anything at all", "c", "verified", 1))
    claims = parse_corpus(_collected_markdown("extract_claims", "m", [("p.md", result)]))
    assert about(claims, ()) == frozenset()
    assert about(claims, ("  ",)) == frozenset()
