"""Reading a draft against a corpus: what is judged, and how it is reported (ADR-068).

The splitting is tested hardest, because it is the part that can fail silently. A paragraph
that is never extracted is never judged, and nothing in the output says it was skipped -
which is the shape of defect this project has found seven times by using the tool.
"""

from __future__ import annotations

from local_ai_control_center.features.review import (
    Finding,
    Paragraph,
    concluded,
    paragraphs_in,
    report,
)
from local_ai_control_center.ports.entailment import Judgement

DRAFT = """# A heading, which asserts nothing

PSMA PET/CT is more sensitive than conventional imaging for nodal staging in high-risk
prostate cancer, and its adoption has changed how these patients are assessed.

## Another heading

| a | table |
|---|---|
| is | skipped |

- a list item that is long enough to be a paragraph if it were prose at all

> a block quotation is somebody else's sentence and is not judged here either

Short one.

```python
# code with a blank line in it

still_code = True
```

The second real paragraph, which is long enough to assert something and should be found
after the fenced block above it.
"""


def test_only_prose_long_enough_to_assert_something_is_read() -> None:
    found = paragraphs_in(DRAFT)
    assert len(found) == 2
    assert found[0].text.startswith("PSMA PET/CT is more sensitive")
    assert found[1].text.startswith("The second real paragraph")


def test_a_fenced_block_does_not_become_paragraphs() -> None:
    """A fence can contain blank lines, so splitting on those first would judge code."""
    assert not any("still_code" in p.text for p in paragraphs_in(DRAFT))
    assert not any("import" in p.text for p in paragraphs_in("```\nimport os\n\nx = 1\n```\n"))


def test_a_paragraph_knows_which_line_it_starts_on() -> None:
    """The number is how a person finds it again. Off by one is useless."""
    found = paragraphs_in("# h\n\nthis paragraph has quite enough words in it to be read here\n")
    assert found[0].line == 3
    later = paragraphs_in("\n\n\nthis paragraph has quite enough words in it to be read here\n")
    assert later[0].line == 4


def test_a_short_claim_is_still_a_claim() -> None:
    """The strongest sentences in a draft are usually the shortest ones."""
    assert len(paragraphs_in("PSMA PET/CT is more sensitive than CT for nodal staging.\n")) == 1


def test_a_wrapped_paragraph_is_read_as_one_thing() -> None:
    """Prose wraps across lines and a claim can span the break."""
    found = paragraphs_in("one two three four\nfive six seven eight\nnine ten eleven twelve\n")
    assert len(found) == 1
    assert found[0].text == "one two three four five six seven eight nine ten eleven twelve"


def _para() -> Paragraph:
    return Paragraph(text="a paragraph with quite enough words in it to be read", line=3)


def test_a_contradiction_outranks_support() -> None:
    """The most important thing on the page is not the half that agrees with you."""
    judged = [
        ("a.md", "supporting words", Judgement(verdict="follows")),
        ("b.md", "opposing words", Judgement(verdict="contradicts", detail="the figure differs")),
    ]
    finding = concluded(_para(), judged)
    assert finding.verdict == "contradicted"
    assert finding.quote == "opposing words"
    assert finding.document == "b.md"


def test_support_is_reported_with_the_quotation_that_holds_it() -> None:
    judged = [
        ("a.md", "unrelated", Judgement(verdict="neither")),
        ("b.md", "the words that hold it", Judgement(verdict="follows")),
    ]
    finding = concluded(_para(), judged)
    assert finding.verdict == "supported"
    assert finding.quote == "the words that hold it"
    assert not finding.worth_a_look


def test_a_judge_that_could_not_answer_is_not_support() -> None:
    """Treating silence as approval is how a check becomes decoration (ADR-053)."""
    judged = [("a.md", "words", Judgement(verdict="undecided"))]
    assert concluded(_para(), judged).verdict == "nothing"


def test_nothing_found_is_reported_as_uncovered_never_as_wrong() -> None:
    finding = concluded(_para(), [("a.md", "words", Judgement(verdict="neither"))])
    assert finding.verdict == "nothing"
    assert finding.worth_a_look


def test_the_report_says_uncovered_is_not_false_where_it_appears() -> None:
    """The distinction that makes this tool usable rather than corrosive.

    Stated where a reader is looking at the finding, not once in a legend at the top.
    """
    written = report([concluded(_para(), [])], "draft.md", "corpus.md", 0)
    assert "Nothing here says a paragraph is wrong" in written
    assert "Not covered by your corpus" in written
    assert "Only the third is a problem with the writing" in written


def test_contradictions_come_first_in_the_report() -> None:
    """A person reads from the top, so what can put a false claim in a thesis goes there."""
    against = Finding(
        paragraph=_para(), quote="q", document="b.md", verdict="contradicted", detail="d"
    )
    held = Finding(paragraph=_para(), quote="q2", document="a.md", verdict="supported")
    written = report([held, against], "draft.md", "corpus.md", 0)
    assert written.index("your corpus says otherwise") < written.index("Held up by your corpus")


def test_the_counts_in_the_report_match_the_findings() -> None:
    findings = [
        Finding(paragraph=_para(), verdict="supported", quote="q", document="a.md"),
        Finding(paragraph=_para(), verdict="contradicted", quote="q", document="b.md"),
        Finding(paragraph=_para()),
    ]
    written = report(findings, "draft.md", "corpus.md", 0)
    assert "1 are held up by a quotation in it, 1 are contradicted by one, and 1 are not" in written


def test_a_long_paragraph_is_shortened_in_the_report_but_findable() -> None:
    long_one = Paragraph(text="word " * 300, line=42)
    written = report([Finding(paragraph=long_one)], "draft.md", "corpus.md", 0)
    assert "Line 42" in written
    assert "…" in written
