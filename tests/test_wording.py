"""The small things the terminal said wrong (ADR-120), and what its fixes said wrong (ADR-121).

Each is minor, and each sits in a line a person reads for its numbers or its names: a count
that does not agree with its word, a doubled period, a heading cut where a PDF broke it, a
question cut where a limit fell, and a version nobody could ask for.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from local_ai_control_center import __version__
from local_ai_control_center.cli import app
from local_ai_control_center.core.config import Config
from local_ai_control_center.core.sections import sections_in
from local_ai_control_center.core.skill import AskCorpusSkill
from local_ai_control_center.core.wording import agreeing, counted
from local_ai_control_center.features.bibliography import as_entry
from local_ai_control_center.ports.registry import Work

runner = CliRunner()


def test_a_count_and_its_word_agree() -> None:
    assert counted(1, "section") == "1 section"
    assert counted(2, "section") == "2 sections"
    assert counted(1300, "quotation") == "1,300 quotations"
    assert counted(1, "entry", "entries") == "1 entry"
    assert counted(3, "entry", "entries") == "3 entries"


def test_a_word_after_a_count_agrees_with_it() -> None:
    assert agreeing(1, "was", "were") == "was"
    assert agreeing(0, "was", "were") == "were"
    assert agreeing(2, "its", "their") == "their"


def test_one_settled_stage_has_nothing_outstanding(tmp_path: Path) -> None:
    """`1 of 6 stages have` - the verb agrees with the one."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "paper.md").write_text(
        "A paper nobody has quoted yet." + chr(10), encoding="utf-8"
    )
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}{chr(10)}", encoding="utf-8")
    said = " ".join(runner.invoke(app, ["status", "-c", str(config)]).stdout.split())
    assert "1 of 6 stages has nothing outstanding" in said


def test_an_abbreviation_is_not_given_a_second_period() -> None:
    work = Work(
        doi="10.1000/x",
        title="A title",
        authors=("A", "B", "C", "D"),
        container="J. Nucl. Med.",
        year=2019,
    )
    entry = as_entry(work)
    assert "et al.." not in entry and "Med.." not in entry
    assert entry.startswith("A; B; C et al. *A title*. J. Nucl. Med. 2019")


def test_a_heading_a_pdf_broke_mid_word_is_read_whole() -> None:
    """`5.8.5` / `Recommendat` / `ions for staging of prostate cancer`, from the EAU guideline."""

    def body(marker: str) -> str:
        return (f"{marker} " + "Prose that carries the section. " * 3 + chr(10)) * 12

    text = chr(10).join(
        [
            "1. Introduction",
            body("Opening."),
            "2. Staging",
            body("Staging."),
            "2.1",
            " Recommendat",
            "ions for staging of prostate cancer",
            body("Recommendations."),
            "3. Treatment",
            body("Treatment."),
        ]
    )
    titles = {section.number: section.title for section in sections_in(text)}
    assert titles["2.1"] == "Recommendations for staging of prostate cancer"


def _title_of(*heading: str) -> str:
    """The title read for subsection 2.1, printed as ``heading`` in a three-part document."""

    def body(marker: str) -> str:
        return (f"{marker} " + "Prose that carries the section. " * 3 + chr(10)) * 12

    text = chr(10).join(
        [
            "1. Introduction",
            body("Opening."),
            "2. Staging",
            body("Staging."),
            *heading,
            body("Under."),
            "3. Treatment",
            body("Treatment."),
        ]
    )
    return {section.number: section.title for section in sections_in(text)}["2.1"]


def test_a_heading_broken_after_one_letter_is_read_whole() -> None:
    """Nine of the EAU guideline's headings read `T` (ADR-121)."""
    assert _title_of("2.1", " T", "reatment of locally-advanced PCa") == (
        "Treatment of locally-advanced PCa"
    )


def test_a_heading_broken_on_the_numbers_line_is_read_whole() -> None:
    assert _title_of(
        "2.1 Recommendations f",
        "or the first-line treatment of hormone-sensitive metastatic disease*",
    ) == ("Recommendations for the first-line treatment of hormone-sensitive metastatic disease*")


def test_a_heading_broken_between_words_keeps_the_space() -> None:
    """The first join wrote `Summaryof evidence` and `Repeatbiopsy` (ADR-121)."""
    assert _title_of("2.1", " Summary", " of evidence for epidemiology and aetiology") == (
        "Summary of evidence for epidemiology and aetiology"
    )
    assert _title_of("2.1 The role of", " imaging in PSA-only recurrence") == (
        "The role of imaging in PSA-only recurrence"
    )


def test_a_heading_longer_than_nine_words_is_read_whole_when_broken() -> None:
    """The limit is for what is printed with the number; `Imp` stayed `Imp` (ADR-121)."""
    assert _title_of(
        "2.1", " Imp", "roving quality of life in men who have been diagnosed with PCa"
    ) == ("Improving quality of life in men who have been diagnosed with PCa")


def test_the_question_in_a_preview_is_the_whole_question() -> None:
    """It was cut at sixty characters, and a preview is what is agreed to."""
    question = (
        "¿Cómo se entrena un estudiante de una sola modalidad a partir de un profesor multimodal?"
    )
    config = Config(workspace_root=".", model="qwen2.5:14b")
    summary = AskCorpusSkill().plan((question,), config).action.summary
    assert summary.endswith(question)


def test_the_version_can_be_asked_for() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"lacc {__version__}"
