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


def test_the_context_file_is_not_a_document_with_no_quotation(tmp_path: Path) -> None:
    """A workspace names it in its own configuration; it is carried, not quoted (ADR-082)."""
    (tmp_path / "paper.md").write_text("prose", encoding="utf-8")
    (tmp_path / "contexto.md").write_text("Standing context for every run.", encoding="utf-8")
    (tmp_path / "corpus.md").write_text(_corpus("paper.md"), encoding="utf-8")
    by_name = {s.name: s for s in stages_in(tmp_path, context_file="contexto.md").stages}
    assert not by_name["Quotations"].missing
    assert "1 brought in" in by_name["Documents"].done


def test_a_document_covered_through_its_extracts_is_covered(tmp_path: Path) -> None:
    """Seven sections of a guideline were collected while the guideline read as pending."""
    import json

    (tmp_path / "guideline.md").write_text("A very long guideline.", encoding="utf-8")
    (tmp_path / "part.md").write_text("5.8\n Staging\nThe body of it.\n", encoding="utf-8")
    (tmp_path / "part.md.from.json").write_text(
        json.dumps({"document": "guideline.md", "section": "5.8"}), encoding="utf-8"
    )
    (tmp_path / "corpus.md").write_text(_corpus("part.md"), encoding="utf-8")
    by_name = {s.name: s for s in stages_in(tmp_path).stages}
    assert not by_name["Quotations"].missing, "the guideline is covered through its extract"


# --- what `coverage` brought into the workspace, and what it reads (ADR-088) ---------------


def test_a_coverage_report_is_not_a_document_nobody_quoted(tmp_path: Path) -> None:
    """Written by LACC, like a bibliography and a review.

    It was counted as a document the day `coverage` shipped, which invented three pending
    items out of the tool's own output - the defect ADR-082 exists to prevent, arriving
    again through a new writer nobody had taught this reader about.
    """
    (tmp_path / "paper.md").write_text("Some prose about a study.", encoding="utf-8")
    (tmp_path / "corpus.md").write_text(_corpus("paper.md"), encoding="utf-8")
    (tmp_path / "cobertura.md").write_text(
        "# How far the nearest quotation is\n\n3 topics against corpus.md.\n", encoding="utf-8"
    )
    quotations = next(s for s in stages_in(tmp_path).stages if s.name == "Quotations")
    assert "cobertura.md" not in quotations.missing
    assert not quotations.missing


def test_a_topics_file_is_not_a_document_to_quote_from(tmp_path: Path) -> None:
    """It is the question, not a source. Recognised by the control marker `coverage` demands."""
    (tmp_path / "paper.md").write_text("Some prose about a study.", encoding="utf-8")
    (tmp_path / "corpus.md").write_text(_corpus("paper.md"), encoding="utf-8")
    (tmp_path / "temas.md").write_text(
        "# what this thesis has to hold up\n\nnodal staging\ndosimetry\n! bone sarcoma\n",
        encoding="utf-8",
    )
    quotations = next(s for s in stages_in(tmp_path).stages if s.name == "Quotations")
    assert not quotations.missing


def test_the_control_marker_is_found_where_a_person_writes_it(tmp_path: Path) -> None:
    """Last. It is the odd one out, and that is where an odd one out goes."""
    (tmp_path / "paper.md").write_text("Some prose.", encoding="utf-8")
    (tmp_path / "corpus.md").write_text(_corpus("paper.md"), encoding="utf-8")
    lines = ["# a long preamble about what this file is for", ""]
    lines += [f"topic number {n} of the thesis" for n in range(60)]
    lines += ["! something well outside this field"]
    (tmp_path / "temas.md").write_text("\n".join(lines), encoding="utf-8")
    quotations = next(s for s in stages_in(tmp_path).stages if s.name == "Quotations")
    assert not quotations.missing


def test_a_list_with_no_control_marker_is_still_a_document(tmp_path: Path) -> None:
    """`coverage` refuses such a file, so nothing else should treat it as one."""
    (tmp_path / "corpus.md").write_text(_corpus("other.md"), encoding="utf-8")
    (tmp_path / "notes.md").write_text("nodal staging\ndosimetry\n", encoding="utf-8")
    quotations = next(s for s in stages_in(tmp_path).stages if s.name == "Quotations")
    assert "notes.md" in quotations.missing
