"""A BibTeX file written from what a registry said, and nothing else (ADR-102).

No network and no model anywhere here. The answers are the ones `resolve` keeps beside what it
writes, and every test below is about one of three promises: a field the registry did not hold
is named and never filled, a key somebody cites is never handed out again, and nothing a third
party deposited can reach a LaTeX document as an instruction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from local_ai_control_center.adapters.crossref import answers_in, work_from
from local_ai_control_center.cli import app
from local_ai_control_center.features.bibtex import Held, as_bibtex, bibtex, held_in, key_base
from local_ai_control_center.ports.registry import Work

NOTHING = Held(keys=frozenset(), dois=frozenset())


def _work(**fields: object) -> Work:
    """One answer as `resolve` keeps it today, with only what a test cares about changed."""
    base: dict[str, object] = {
        "doi": "10.1007/s00259-016-3573-4",
        "title": "F-18 labelled PSMA-1007",
        "authors": ("Giesel, Frederik L.", "Hadaschik, B."),
        "container": "European Journal of Nuclear Medicine and Molecular Imaging",
        "year": 2016,
        "kind": "journal-article",
        "volume": "44",
        "issue": "4",
        "pages": "678-688",
        "fetched_on": "2026-09-28",
    }
    base.update(fields)
    return Work.model_validate(base)


def test_a_key_is_the_first_family_name_and_the_year() -> None:
    assert key_base(_work()) == "giesel2016"
    assert key_base(_work(authors=("Schäfer, M.",))) == "schafer2016"
    assert key_base(_work(authors=("Maier-Hein, Lena",))) == "maierhein2016"
    assert key_base(_work(authors=("van den Hoff, Jörg",))) == "vandenhoff2016"


def test_a_work_without_author_or_year_still_gets_a_key_it_can_be_found_by() -> None:
    assert key_base(_work(authors=(), title="The Metrics of a Thing")) == "metrics2016"
    assert key_base(_work(authors=(), title="")) == "anon2016"
    assert key_base(_work(year=None)) == "gieselnd"


def test_a_key_already_cited_is_never_handed_out_again() -> None:
    """The reason the file somebody cites from is read at all.

    `giesel2016` is taken, in another case, by an entry with no DOI - which is exactly the entry
    a comparison by DOI would miss.
    """
    held = held_in("@misc{Giesel2016,\n  title = {Something else},\n}\n")
    written = bibtex([_work()], held)
    assert written.entries == (("giesel2016a", "10.1007/s00259-016-3573-4"),)


def test_two_new_works_that_would_share_a_key_each_get_their_own() -> None:
    first = _work(doi="10.1000/a")
    second = _work(doi="10.1000/b", title="Another paper that year")
    written = bibtex([second, first], NOTHING)
    assert written.entries == (("giesel2016", "10.1000/a"), ("giesel2016a", "10.1000/b"))


def test_a_work_the_cited_file_already_holds_is_left_out() -> None:
    """Found as Crossref writes it: the whole entry on one line, `DOI=` in capitals."""
    crossref_style = (
        " @article{giesel2016, title={F-18 labelled PSMA-1007}, "
        "DOI={10.1007/S00259-016-3573-4}, year={2016} }\n"
    )
    written = bibtex([_work(), _work(doi="10.1000/new")], held_in(crossref_style))
    assert written.already == ("10.1007/s00259-016-3573-4",)
    assert [doi for _, doi in written.entries] == ["10.1000/new"]


def test_nothing_a_third_party_deposited_reaches_latex_as_an_instruction() -> None:
    """A title is a publisher's text, and a LaTeX document executes what it is given.

    The braces become commands rather than escaped braces because BibTeX counts every brace to
    find where a field ends: an escaped one still opens a field that never closes.
    """
    entry = as_bibtex(_work(title=r"\input{/etc/passwd} & 100% of $x_1$ ~ ^#"), "k")
    title = next(line for line in entry.splitlines() if line.lstrip().startswith("title"))
    value = title.split("=", 1)[1].strip().removeprefix("{").removesuffix("},")
    assert r"\input{" not in value
    assert r"\textbackslash{}input\textbraceleft{}/etc/passwd\textbraceright{}" in value
    assert r"\& 100\% of \$x\_1\$ \~{} \^{}\#" in value
    assert value.count("{") == value.count("}")


def test_a_name_in_a_title_keeps_its_capitals_whatever_the_style() -> None:
    """Found by rendering the file through pandoc: `3D U-Net` came out as `3D u-Net`."""
    entry = as_bibtex(_work(title="3D U-Net: Learning Dense Segmentation in PET/CT"), "k")
    assert "title = {{3D} {U-Net:} Learning Dense Segmentation in {PET/CT}}," in entry


def test_the_registry_s_name_for_a_kind_cannot_open_an_entry_from_a_comment() -> None:
    """Outside an entry BibTeX does not honour `%`: an `@` there starts one."""
    entry = as_bibtex(_work(kind="x @preamble{evil}"), "k")
    comments = [line for line in entry.splitlines() if line.startswith("%")]
    assert comments
    assert not any("@" in line or "{" in line for line in comments)
    assert entry.count("@") == 1


def test_what_the_registry_did_not_hold_is_named_above_the_entry() -> None:
    entry = as_bibtex(_work(pages="", issue=""), "k")
    assert "% Not in the registry record: issue, pages." in entry
    assert "pages =" not in entry
    assert "number =" not in entry
    assert "volume = {44}" in entry


def test_what_was_never_read_is_not_called_missing() -> None:
    """An answer kept before volume, issue and pages were read holds none of them.

    Calling them absent from the registry record would be false - the record has them, they
    were not read. The entry says which of the two it is.
    """
    older = _work(volume=None, issue=None, pages=None, fetched_on="2026-09-24")
    entry = as_bibtex(older, "k")
    assert "Not in the registry record" not in entry
    assert "Received on 2026-09-24, before volume, issue and pages were read." in entry
    assert bibtex([older], NOTHING).unread == 1


def test_a_kind_this_does_not_know_is_written_as_misc_and_says_so() -> None:
    entry = as_bibtex(_work(kind="posted-content", container="medRxiv"), "k")
    assert entry.splitlines()[0].startswith("% The registry calls this posted-content")
    assert "@misc{k," in entry
    assert "howpublished = {medRxiv}" in entry


def test_an_organisation_stays_one_author() -> None:
    entry = as_bibtex(_work(authors=("Giesel, F.", "PSMA Working Group")), "k")
    assert "author = {Giesel, F. and {PSMA Working Group}}," in entry


def test_a_doi_that_would_break_the_file_is_left_out_and_named() -> None:
    written = bibtex([_work(doi="10.1000/a}b")], NOTHING)
    assert written.entries == ()
    assert written.unwritable == ("10.1000/a}b",)


def test_the_same_doi_twice_is_one_entry_and_the_newest_answer() -> None:
    older = _work(volume=None, issue=None, pages=None, fetched_on="2026-09-24")
    written = bibtex([older, _work()], NOTHING)
    assert len(written.entries) == 1
    assert written.unread == 0


def test_where_in_the_journal_is_read_and_bounded() -> None:
    record = {
        "title": ["A title"],
        "type": "journal-article",
        "volume": "395",
        "issue": "10231",
        "page": "1208-1216" + "9" * 500,
    }
    work = work_from(record, "10.1000/x", "2026-09-28")
    assert work.volume == "395"
    assert work.issue == "10231"
    assert work.pages is not None
    assert work.pages.startswith("1208-1216")
    assert len(work.pages) <= 40


def test_a_record_without_them_says_empty_not_unread() -> None:
    work = work_from({"title": ["A title"]}, "10.1000/x", "2026-09-28")
    assert (work.volume, work.issue, work.pages) == ("", "", "")


def test_kept_answers_are_read_as_kept(tmp_path: Path) -> None:
    kept = tmp_path / "b.registry.json"
    kept.write_text(json.dumps({"10.1000/x": _work().model_dump(), "10.1000/gone": {}}))
    answers = answers_in(kept)
    assert answers["10.1000/gone"] is None
    assert answers["10.1000/x"] == _work()


@pytest.mark.parametrize("content", ["[]", '{"10.1000/x": "a string"}', "not json"])
def test_a_file_that_is_not_kept_answers_is_refused(tmp_path: Path, content: str) -> None:
    kept = tmp_path / "b.registry.json"
    kept.write_text(content)
    with pytest.raises(ValueError, match="kept registry answers"):
        answers_in(kept)


runner = CliRunner()


def _said(output: str) -> str:
    """What the command printed, with the terminal's line wrapping undone."""
    return " ".join(output.split())


def _workspace(tmp_path: Path) -> Path:
    """A workspace holding one file of kept answers, and a configuration with no network."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    answers = {"10.1007/s00259-016-3573-4": _work().model_dump(), "10.1000/gone": {}}
    (workspace / "b.registry.json").write_text(json.dumps(answers), encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}\n", encoding="utf-8")
    return config


def test_bib_writes_from_kept_answers_with_the_network_off(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    result = runner.invoke(app, ["bib", "b.registry.json", "--into", "r.bib", "-c", str(config)])
    assert result.exit_code == 0, result.stdout
    written = (tmp_path / "ws" / "r.bib").read_text(encoding="utf-8")
    assert "@article{giesel2016," in written
    assert "pages = {678-688}," in written
    assert "1 DOIs the registry holds nothing for" in _said(result.stdout)


def test_bib_never_replaces_a_file(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    (tmp_path / "ws" / "r.bib").write_text("mine", encoding="utf-8")
    result = runner.invoke(app, ["bib", "b.registry.json", "--into", "r.bib", "-c", str(config)])
    assert result.exit_code == 1
    assert "LACC writes its results only to new files" in _said(result.stdout)
    assert (tmp_path / "ws" / "r.bib").read_text(encoding="utf-8") == "mine"


def test_bib_writes_only_bib(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    result = runner.invoke(app, ["bib", "b.registry.json", "--into", "r.md", "-c", str(config)])
    assert result.exit_code == 1
    assert not (tmp_path / "ws" / "r.md").exists()


def test_bib_adding_to_a_file_outside_the_workspace_says_what_to_do(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    result = runner.invoke(
        app,
        ["bib", "b.registry.json", "--into", "r.bib", "--adding-to", "refs.bib", "-c", str(config)],
    )
    assert result.exit_code == 1
    said = _said(result.stdout)
    assert "Copy the .bib you cite from into the workspace" in said
    # It said "LACC reads nothing outside it" after ADR-111 made that false (ADR-117).
    assert "reads nothing outside" not in said and "a bibliography is not one" in said
    assert not (tmp_path / "ws" / "r.bib").exists()


def test_bib_adding_to_writes_only_what_is_new(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    (tmp_path / "ws" / "refs.bib").write_text(
        "@article{giesel2016, doi = {10.1007/s00259-016-3573-4}}\n", encoding="utf-8"
    )
    result = runner.invoke(
        app,
        ["bib", "b.registry.json", "--into", "r.bib", "--adding-to", "refs.bib", "-c", str(config)],
    )
    assert result.exit_code == 0, result.stdout
    assert "Nothing new to write" in _said(result.stdout)
    assert "1 left out" in _said(result.stdout)
    assert not (tmp_path / "ws" / "r.bib").exists()
