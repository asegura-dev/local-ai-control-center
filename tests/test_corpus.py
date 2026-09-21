"""Reading back a collected corpus, and the round trip that makes that safe."""

from __future__ import annotations

from pathlib import Path

from local_ai_control_center.core.corpus import CollectedClaim, about, parse_corpus
from local_ai_control_center.core.grounding import CheckedClaim, Claim
from local_ai_control_center.core.preview import ExecutionPreview, IntendedAction
from local_ai_control_center.cycle import RunResult
from local_ai_control_center.features.corpus import assembled, collected_markdown


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
    written = collected_markdown("extract_claims", "a-model", [("paper.md", result)])
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
    written = collected_markdown("extract_claims", "m", [("one.md", first), ("two.md", second)])
    read_back = parse_corpus(written)
    assert [(c.document, c.quote) for c in read_back] == [
        ("one.md", "from the first"),
        ("two.md", "from the second"),
    ]


def test_a_document_that_was_not_collected_contributes_nothing() -> None:
    """Its section names a failure, not a claim, and an empty entry would be a lie."""
    good = _result(_checked("a real one", "a", "verified", 1))
    written = collected_markdown(
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
    written = collected_markdown("extract_claims", "m", [("paper.md", result)])
    assert parse_corpus(written)[0].nearest == "what the document does say"


def test_marking_a_subject_folds_the_spacing_extraction_invents() -> None:
    result = _result(_checked("The PSM A PET/CT protocol", "c", "verified", 1))
    claims = parse_corpus(collected_markdown("extract_claims", "m", [("p.md", result)]))
    assert about(claims, ("psma",)) == frozenset({"The PSM A PET/CT protocol"})


def test_marking_with_no_words_marks_nothing() -> None:
    result = _result(_checked("anything at all", "c", "verified", 1))
    claims = parse_corpus(collected_markdown("extract_claims", "m", [("p.md", result)]))
    assert about(claims, ()) == frozenset()
    assert about(claims, ("  ",)) == frozenset()


def test_a_marked_quotation_is_still_readable(tmp_path: Path) -> None:
    """The bullet an assembled corpus uses to mark a subject broke the reader.

    The round trip passed throughout, because it only ever round-tripped a corpus with no
    marks in it. Two hundred and sixty-five quotations were silently unreadable.
    """
    marked = (
        "## paper.md"
        + chr(10) * 2
        + "### Citable"
        + chr(10) * 2
        + "- > a marked quotation"
        + chr(10) * 2
        + "p. 3 - the paraphrase"
        + chr(10) * 2
        + "> an unmarked one"
        + chr(10) * 2
        + "p. 4 - another paraphrase"
        + chr(10)
    )
    read_back = parse_corpus(marked)
    assert [c.quote for c in read_back] == ["a marked quotation", "an unmarked one"]
    assert [c.page for c in read_back] == [3, 4]


def _assemble(claims: list[CollectedClaim]) -> str:
    """Run the corpus assembler over claims, re-checking nothing."""
    return assembled([(claim, True) for claim in claims], frozenset(), [Path("a.md")])


def test_the_other_writer_is_read_back_unchanged_too() -> None:
    """There were two writers and the round trip covered one of them (ADR-065)."""
    written = _assemble(
        [
            CollectedClaim(
                document="paper.md",
                quote="a placed quotation",
                claim="it was placed",
                page=7,
            )
        ]
    )
    read_back = parse_corpus(written)
    assert [c.quote for c in read_back] == ["a placed quotation"]
    assert [c.claim for c in read_back] == ["it was placed"]
    assert [c.page for c in read_back] == [7]


def test_assembling_twice_keeps_what_each_quotation_was_taken_to_mean() -> None:
    """The loss only appears on the second pass, which is why once was not enough.

    `assembled` put the paraphrase on the page line, where `parse_corpus` matched it as a
    verdict - and a recorded verdict is correctly never carried forward (ADR-042). So the
    first assembly looked right and the second silently stripped every paraphrase in the
    corpus, while reporting the same counts it always had (ADR-065).

    Found on a real corpus by noticing the result was 35 KB smaller with 178 more
    quotations. Nothing else would have shown it.
    """
    start = [
        CollectedClaim(
            document="paper.md", quote="a placed quotation", claim="it was placed", page=7
        ),
        CollectedClaim(
            document="paper.md", quote="an unplaceable one", claim="it is there", page=None
        ),
    ]
    once = parse_corpus(_assemble(start))
    twice = parse_corpus(_assemble(list(once)))

    assert [c.claim for c in once] == ["it was placed", "it is there"]
    assert [c.claim for c in twice] == ["it was placed", "it is there"], (
        "the paraphrase survives a second assembly"
    )
    assert [c.quote for c in twice] == ["a placed quotation", "an unplaceable one"]
    assert [c.page for c in twice] == [7, None]


def test_both_writers_say_the_same_thing_about_a_placed_quotation() -> None:
    """One format, written by both, is what closes the round trip."""
    by_collect = collected_markdown(
        "extract_claims", "a-model", [("paper.md", _result(_checked("q", "c", "verified", 7)))]
    )
    by_corpus = _assemble([CollectedClaim(document="paper.md", quote="q", claim="c", page=7)])
    assert "p. 7 - verified" in by_collect
    assert "p. 7 - verified" in by_corpus
