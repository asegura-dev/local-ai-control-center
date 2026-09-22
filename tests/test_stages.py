"""Where the work stands, and the three ways the first reading of it was wrong (ADR-080)."""

from __future__ import annotations

from pathlib import Path

from local_ai_control_center.features.stages import stages_in


def _corpus(*documents: str) -> str:
    blocks = ["# Collected quotations", ""]
    for name in documents:
        blocks += [
            f"## {name}",
            "",
            "> a quotation from it",
            "",
            "p. 1 - verified",
            "",
            "a claim",
            "",
        ]
    return "\n".join(blocks)


def _bibliography(resolved: int, unknown: int) -> str:
    lines = ["# Bibliography", "", "## Resolved", ""]
    lines += [
        f"- Author, A. *A title {n}*. A Journal. 2020  <10.1000/{n}>" for n in range(resolved)
    ]
    lines += ["", "## The registry holds nothing for these", ""]
    lines += [f"- `10.1000/broken{n}`" for n in range(unknown)]
    return "\n".join(lines) + "\n"


def test_a_stage_that_has_something_outstanding_is_not_settled(tmp_path: Path) -> None:
    (tmp_path / "paper.md").write_text("Some prose about a study.", encoding="utf-8")
    (tmp_path / "corpus.md").write_text(_corpus("paper.md"), encoding="utf-8")
    work = stages_in(tmp_path)
    by_name = {stage.name: stage for stage in work.stages}
    assert by_name["Documents"].settled
    assert not by_name["Writing"].settled
    assert "nothing of yours" in by_name["Writing"].missing


def test_only_the_entries_under_resolved_are_counted(tmp_path: Path) -> None:
    """Counting every bullet turned 172 into 236, by adding the ones it failed on."""
    (tmp_path / "paper.md").write_text("prose", encoding="utf-8")
    (tmp_path / "bibliografia.md").write_text(_bibliography(172, 40), encoding="utf-8")
    by_name = {stage.name: stage for stage in stages_in(tmp_path).stages}
    assert "172 works resolved" in by_name["Bibliography"].done


def test_a_section_taken_out_of_a_document_is_not_a_document(tmp_path: Path) -> None:
    """The first reading called three extracted sections "documents with no quotation"."""
    (tmp_path / "paper.md").write_text("Some prose about a study.", encoding="utf-8")
    # As `sections --take` leaves it: the number alone, the title on the next line.
    (tmp_path / "part.md").write_text("5.2.4\n Imag\ning\nThe body of it.\n", encoding="utf-8")
    by_name = {stage.name: stage for stage in stages_in(tmp_path).stages}
    assert "1 brought in" in by_name["Documents"].done
    assert "sections taken out" in by_name["Documents"].done


def test_a_document_with_no_quotation_is_named(tmp_path: Path) -> None:
    (tmp_path / "covered.md").write_text("prose", encoding="utf-8")
    (tmp_path / "forgotten.md").write_text("prose", encoding="utf-8")
    (tmp_path / "corpus.md").write_text(_corpus("covered.md"), encoding="utf-8")
    by_name = {stage.name: stage for stage in stages_in(tmp_path).stages}
    assert "forgotten.md" in by_name["Quotations"].missing


def test_the_largest_corpus_is_the_one_reported(tmp_path: Path) -> None:
    """A backup beside the corpus is smaller; the one being worked from is the big one."""
    (tmp_path / "a.md").write_text("prose", encoding="utf-8")
    (tmp_path / "small.md").write_text(_corpus("a.md"), encoding="utf-8")
    (tmp_path / "big.md").write_text(_corpus(*[f"doc{n}.md" for n in range(9)]), encoding="utf-8")
    by_name = {stage.name: stage for stage in stages_in(tmp_path).stages}
    assert "big.md" in by_name["Corpus"].done


def test_an_empty_workspace_says_what_to_run(tmp_path: Path) -> None:
    work = stages_in(tmp_path)
    by_name = {stage.name: stage for stage in work.stages}
    assert "nothing to work from" in by_name["Documents"].missing
    assert work.settled == 0


def test_a_workspace_that_is_not_there_yields_no_stages(tmp_path: Path) -> None:
    assert stages_in(tmp_path / "nowhere").stages == ()
