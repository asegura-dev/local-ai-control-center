"""Reading a draft against a corpus: what is judged, and how it is reported (ADR-068).

The splitting is tested hardest, because it is the part that can fail silently. A paragraph
that is never extracted is never judged, and nothing in the output says it was skipped -
which is the shape of defect this project has found seven times by using the tool.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from local_ai_control_center.cli import app
from local_ai_control_center.features.review import (
    Finding,
    Paragraph,
    concluded,
    draft_text,
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


def test_a_judge_that_could_not_answer_is_not_support_and_not_uncovered() -> None:
    """Silence is not approval (ADR-053), and it is not a verdict on the corpus either.

    This asserted `nothing` until ADR-115: an engine switched off was reported as a corpus
    that does not hold the paragraph.
    """
    judged = [("a.md", "words", Judgement(verdict="undecided", detail="no answer"))]
    finding = concluded(_para(), judged)
    assert finding.verdict == "undecided"
    assert finding.detail == "no answer"
    assert finding.worth_a_look


def test_one_candidate_left_unjudged_leaves_the_paragraph_unjudged() -> None:
    """What was not judged might have held it: "nothing holds this" is not known."""
    judged = [
        ("a.md", "unrelated", Judgement(verdict="neither")),
        ("b.md", "the one that might", Judgement(verdict="undecided")),
    ]
    assert concluded(_para(), judged).verdict == "undecided"


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
    assert "3 paragraphs read against corpus.md" in written
    assert "1 is held up by a quotation in it, 1 is contradicted by one, and 1 is not" in written


def test_one_paragraph_is_said_in_the_singular() -> None:
    """`1 paragraphs read`, `1 were not judged` (ADR-121)."""
    one = report([Finding(paragraph=_para(), verdict="undecided")], "draft.md", "corpus.md", 0)
    assert "1 paragraph read against" in one and "**1 was not judged**" in one
    two = [Finding(paragraph=_para()), Finding(paragraph=_para())]
    assert "and 2 are not covered by it" in report(two, "draft.md", "corpus.md", 0)


def test_a_long_paragraph_is_shortened_in_the_report_but_findable() -> None:
    long_one = Paragraph(text="word " * 300, line=42)
    written = report([Finding(paragraph=long_one)], "draft.md", "corpus.md", 0)
    assert "Line 42" in written
    assert "…" in written


def test_the_report_names_what_was_not_judged_apart_from_what_is_uncovered() -> None:
    findings = [Finding(paragraph=_para(), verdict="undecided"), Finding(paragraph=_para())]
    written = report(findings, "draft.md", "corpus.md", 0)
    assert "and 1 is not covered by it either way. **1 was not judged**" in written
    assert written.index("Not judged: the engine did not answer") < written.index(
        "Not covered by your corpus"
    )


# --- what can be read as a draft (ADR-115) ---------------------------------------------------


def test_a_document_that_is_not_text_is_sent_to_ingest_first() -> None:
    for name in ("drafts/cap3 (2026-09-29).docx", "notes.PDF"):
        with pytest.raises(ValueError, match="Convert it first") as refused:
            draft_text(name, b"PK\x03\x04 anything")
        assert f'lacc ingest "{name}"' in str(refused.value)


def test_bytes_no_text_file_holds_are_refused() -> None:
    with pytest.raises(ValueError, match="is not text"):
        draft_text("draft.md", b"PK\x03\x04\x00\x00[Content_Types].xml")


def test_text_that_is_not_utf8_is_refused_where_it_breaks() -> None:
    """Replacement marks were sent to the judge as `Dise?o metodol?gico`, without a word."""
    latin1 = "Diseño metodológico".encode("latin-1")
    with pytest.raises(ValueError, match=r"byte 0xf1 at position 4"):
        draft_text("latin1.md", latin1)


def test_utf8_is_read_and_a_byte_order_mark_is_not_part_of_the_draft() -> None:
    assert draft_text("a.md", "Diseño".encode()) == "Diseño"
    assert draft_text("a.md", "Diseño".encode("utf-8-sig")) == "Diseño"


# --- the command ----------------------------------------------------------------------------


def _review_setup(tmp_path: Path, *extra: str) -> Path:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    quote = "The sensitivity for pelvic lymph nodes was 82 per cent."
    (workspace / "paper.md").write_text(quote + chr(10), encoding="utf-8")
    (workspace / "corpus.md").write_text(
        chr(10).join(["## paper.md", "", f"> {quote}", "", "p. 1 - sensitivity", ""]),
        encoding="utf-8",
    )
    (workspace / "draft.md").write_text(
        "The sensitivity for pelvic lymph nodes was high in this cohort of patients." + chr(10),
        encoding="utf-8",
    )
    config = tmp_path / "config.yaml"
    config.write_text(
        chr(10).join([f"workspace_root: {workspace}", *extra]) + chr(10), encoding="utf-8"
    )
    return config


def test_an_engine_that_does_not_answer_is_not_reported_as_uncovered(tmp_path: Path) -> None:
    """The tester's case: the same paragraph read `1 held up` with the engine and `1 not
    covered` without it, exit 0, and not a word about the judge (ADR-115)."""
    config = _review_setup(tmp_path, "model: qwen2.5:14b", "engine_host: http://127.0.0.1:9")
    result = CliRunner().invoke(
        app,
        ["review", "draft.md", "--against", "corpus.md", "--into", "r.md", "-c", str(config)],
        input="y\n",
    )
    said = " ".join(result.stdout.split())
    assert "1 not judged" in said and "0 not covered" in said
    assert "nothing was concluded about it." in said
    assert result.exit_code == 1, "nothing at all was judged"
    reviewed = json.loads((tmp_path / "ws" / "r.findings.json").read_text(encoding="utf-8"))
    assert [finding["verdict"] for finding in reviewed["findings"]] == ["undecided"]


def test_a_configuration_without_a_model_is_refused_before_the_question(tmp_path: Path) -> None:
    """It was a traceback after the yes, with the run left open."""
    config = _review_setup(tmp_path)
    result = CliRunner().invoke(
        app, ["review", "draft.md", "--against", "corpus.md", "-c", str(config)], input="y\n"
    )
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "No model configured" in " ".join(result.stdout.split())
    assert "Read it?" not in result.stdout
    assert not (tmp_path / "ws" / "audit.jsonl").exists()


def test_a_declined_review_says_what_did_not_happen(tmp_path: Path) -> None:
    """`Nothing was read`, after the draft was read to count its paragraphs (ADR-121)."""
    config = _review_setup(tmp_path, "model: qwen2.5:14b")
    result = CliRunner().invoke(
        app, ["review", "draft.md", "--against", "corpus.md", "-c", str(config)], input="n\n"
    )
    said = " ".join(result.stdout.split())
    assert result.exit_code == 0
    assert "Nothing was sent to the engine." in said and "Nothing was read" not in said


def test_a_docx_brought_in_is_not_reviewed_as_text(tmp_path: Path) -> None:
    config = _review_setup(tmp_path)
    (tmp_path / "ws" / "cap3.docx").write_bytes(b"PK\x03\x04\x14\x00 [Content_Types].xml")
    result = CliRunner().invoke(
        app, ["review", "cap3.docx", "--against", "corpus.md", "-c", str(config)], input="y\n"
    )
    assert result.exit_code == 1
    assert 'lacc ingest "cap3.docx"' in " ".join(result.stdout.split())
    assert "Read it?" not in result.stdout
