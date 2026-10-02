"""`lacc repeats`: where a text states the same fact twice, and a model's proposal (ADR-125).

Finding is tested with no engine at all. Proposing is tested against an engine stand-in that
answers what a model might: a wording that brings in a number and drops a citation, one in
another language, a place that is not in the group - each of which the checks must name.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from local_ai_control_center.cli import app
from local_ai_control_center.core.preview import ExecutionPreview, IntendedAction
from local_ai_control_center.core.repetition import Repetition, Stated, repetitions, stated_in
from local_ai_control_center.features.repeats import (
    UNCHANGED,
    chapter_of,
    places_of,
    proposal_from,
    proposal_prompt,
    proposal_schema,
    report_text,
)
from local_ai_control_center.ports.provider import Completion, Provider

runner = CliRunner()

_INTRO = (
    "# Introducción\n"
    "\n"
    "Un estudio previo: un clasificador desde CT alcanzó un AUC de 0.86 a 0.95, frente "
    "a 0.81 de los lectores [12].\n"
)
_BACKGROUND = (
    "# Antecedentes\n"
    "\n"
    "| Referencia | Resultado |\n"
    "|---|---|\n"
    "| Pérez et al. 2020 [12] | AUC de 0.86 a 0.95 contra 0.81 de los lectores. |\n"
)


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    (workspace / "drafts").mkdir(parents=True)
    (workspace / "drafts" / "02_intro.md").write_text(_INTRO, encoding="utf-8")
    (workspace / "drafts" / "03_antecedentes.md").write_text(_BACKGROUND, encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}\n", encoding="utf-8")
    return config


def test_the_same_fact_in_two_chapters_is_shown_with_where_it_is(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    result = runner.invoke(app, ["repeats", "drafts/0*.md", "-c", str(config)])
    assert result.exit_code == 0, result.stdout
    said = " ".join(result.stdout.split())
    assert "1 group, holding 2 sentences of 2 read in 2 files." in said
    assert "02_intro.md:3" in said and "03_antecedentes.md:5" in said
    assert "figures 0.81, 0.86, 0.95" in said
    assert not (tmp_path / "ws" / "audit.jsonl").exists(), "reading alone leaves no record"


def test_a_report_is_written_and_its_run_recorded(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    result = runner.invoke(
        app, ["repeats", "drafts/0*.md", "--into", "repeats.md", "-c", str(config)]
    )
    assert result.exit_code == 0, result.stdout
    written = (tmp_path / "ws" / "repeats.md").read_text(encoding="utf-8")
    assert "## 1 · 2 sentences · figures 0.81, 0.86, 0.95" in written
    assert "> **02_intro.md:3**" in written
    records = [
        json.loads(line)
        for line in (tmp_path / "ws" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    kinds = [record["kind"] for record in records]
    assert kinds == ["run_started", "files_read", "file_written", "run_finished"]
    assert len(records[1]["detail"]["files"]) == 2
    assert records[-1]["detail"]["groups"] == 1


def test_a_report_already_there_is_refused_before_anything_is_read(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    (tmp_path / "ws" / "repeats.md").write_text("mine", encoding="utf-8")
    result = runner.invoke(
        app, ["repeats", "drafts/0*.md", "--into", "repeats.md", "-c", str(config)]
    )
    assert result.exit_code == 1
    assert (tmp_path / "ws" / "repeats.md").read_text(encoding="utf-8") == "mine"
    assert not (tmp_path / "ws" / "audit.jsonl").exists()


def test_a_pdf_is_refused_rather_than_read_as_text(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    (tmp_path / "ws" / "drafts" / "protocolo.pdf").write_bytes(b"%PDF-1.7 not prose")
    result = runner.invoke(app, ["repeats", "drafts/protocolo.pdf", "-c", str(config)])
    assert result.exit_code == 1
    assert "Convert it first" in " ".join(result.stdout.split())


def test_a_file_that_is_not_there_is_named(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    result = runner.invoke(app, ["repeats", "drafts/04_nada.md", "-c", str(config)])
    assert result.exit_code == 1
    assert "Not in the workspace: drafts/04_nada.md" in " ".join(result.stdout.split())


def test_the_preview_says_what_is_sent_when_it_is_not_what_was_read() -> None:
    """Whole chapters are read and only a group's sentences go: "the contents read above"
    would have said more than is so."""
    action = IntendedAction(
        name="repeats",
        summary="Propose",
        targets=(Path("drafts/02_intro.md"),),
        sends="the sentences of each group, 2 sentences in all",
    )
    shown = ExecutionPreview(action=action, allowed=True, sends_to="http://server:11434").render()
    assert "Sends:   the sentences of each group, 2 sentences in all, to http" in shown


_PROPOSED = json.dumps(
    {
        "keep": "03_antecedentes.md:5",
        "others": [
            {
                "at": "02_intro.md:3",
                "reads": "Un estudio previo: un clasificador desde CT alcanzó un AUC de "
                "0.99 (ver antecedentes).",
            }
        ],
    }
)


class _Editor(Provider):
    """Answers every group with one proposal, and keeps the shape it was asked for."""

    def __init__(self, answer: str = _PROPOSED, fails: bool = False) -> None:
        self.answer = answer
        self.fails = fails
        self.schemas: list[dict[str, Any] | None] = []

    @property
    def name(self) -> str:
        return "editor"

    def complete(
        self, prompt: str, temperature: float = 0.0, schema: dict[str, Any] | None = None
    ) -> Completion:
        self.schemas.append(schema)
        if self.fails:
            raise RuntimeError("the engine went away")
        return Completion(text=self.answer, provider="editor")


def _with(editor: _Editor, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    asked_for: list[str] = []

    def built(choice: object, config: object, skill: str = "") -> Provider:
        asked_for.append(skill)
        return editor

    monkeypatch.setattr("local_ai_control_center.cli._build_provider", built)
    return asked_for


_PROPOSE = ["repeats", "drafts/0*.md", "--propose", "--into", "repeats.md"]


def _kinds(tmp_path: Path) -> list[str]:
    lines = (tmp_path / "ws" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["kind"] for line in lines]


def test_propose_needs_somewhere_to_write(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    result = runner.invoke(app, ["repeats", "drafts/0*.md", "--propose", "-c", str(config)])
    assert result.exit_code == 1
    assert "Name where the proposals go with --into." in " ".join(result.stdout.split())
    assert not (tmp_path / "ws" / "audit.jsonl").exists()


def test_a_proposal_is_written_under_its_group_with_what_the_checks_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path)
    editor = _Editor()
    asked_for = _with(editor, monkeypatch)
    result = runner.invoke(app, [*_PROPOSE, "-c", str(config)], input="y\n")
    assert result.exit_code == 0, result.stdout
    assert asked_for == ["edit_repetition"], "the editor is asked for by its own name"
    schema = editor.schemas[0]
    assert schema is not None
    assert schema["properties"]["keep"]["enum"] == ["02_intro.md:3", "03_antecedentes.md:5"]
    written = (tmp_path / "ws" / "repeats.md").read_text(encoding="utf-8")
    assert "**The model's proposal** (editor)" in written
    assert "- keep whole: **03_antecedentes.md:5**" in written
    assert (
        "*Checks: adds 0.99; drops [12]; loses what the group no longer says: frente.*" in written
    ), "a synonym the table uses instead - contra - is shown as lost, to be dismissed at a glance"
    said = " ".join(result.stdout.split())
    assert "1 proposal in the report; the checks found something to look at in 1." in said


def test_the_trail_keeps_digests_and_leaves_the_words_to_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path)
    _with(_Editor(), monkeypatch)
    runner.invoke(app, [*_PROPOSE, "-c", str(config)], input="y\n")
    assert _kinds(tmp_path) == [
        "run_started",
        "files_read",
        "edits_proposed",
        "file_written",
        "run_finished",
    ]
    lines = (tmp_path / "ws" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    proposed = json.loads(lines[2])["detail"]
    assert proposed["rows"][0]["keep"] == "03_antecedentes.md:5"
    assert len(proposed["rows"][0]["asked_sha256"]) == 64
    assert "prompt" not in proposed and "completion" not in proposed, "words only under full"


def test_a_no_sends_nothing_and_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path)
    editor = _Editor()
    _with(editor, monkeypatch)
    result = runner.invoke(app, [*_PROPOSE, "-c", str(config)], input="n\n")
    assert result.exit_code == 0
    assert "Nothing was sent to the engine." in " ".join(result.stdout.split())
    assert editor.schemas == [], "nothing was asked"
    assert not (tmp_path / "ws" / "repeats.md").exists()
    assert _kinds(tmp_path) == ["run_started", "files_read", "confirmation_declined"]


def test_an_engine_that_does_not_answer_costs_its_group_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path)
    _with(_Editor(fails=True), monkeypatch)
    result = runner.invoke(app, [*_PROPOSE, "-c", str(config)], input="y\n")
    assert result.exit_code == 0, result.stdout
    written = (tmp_path / "ws" / "repeats.md").read_text(encoding="utf-8")
    assert "*Not usable as given:* The engine did not answer: the engine went away" in written


def _group() -> Repetition:
    found = stated_in(_INTRO, "02_intro.md") + stated_in(_BACKGROUND, "03_antecedentes.md")
    return repetitions(found)[0]


def test_a_proposal_in_another_language_is_named() -> None:
    answer = json.dumps(
        {
            "keep": "03_antecedentes.md:5",
            "others": [
                {
                    "at": "02_intro.md:3",
                    "reads": "A previous study: a classifier trained on CT alone did well, as "
                    "the background shows [12].",
                }
            ],
        }
    )
    edit = proposal_from(_group(), answer).edits[0]
    assert edit.other_language and not edit.added and not edit.dropped


def test_unchanged_is_a_proposal_and_needs_no_check() -> None:
    answer = json.dumps(
        {"keep": "02_intro.md:3", "others": [{"at": "03_antecedentes.md:5", "reads": "unchanged"}]}
    )
    proposal = proposal_from(_group(), answer)
    assert proposal.edits[0].reads == UNCHANGED
    assert proposal.edits[0].unchanged and not proposal.flagged


def test_an_answer_out_of_shape_is_said_and_never_mended() -> None:
    group = _group()
    assert proposal_from(group, "Keep the table.").problems == (
        "The answer is not in the shape asked.",
    )
    stray = proposal_from(group, json.dumps({"keep": "05_otro.md:1", "others": []}))
    assert stray.keep == "" and "not one of this group's" in stray.problems[0]
    silent = proposal_from(group, json.dumps({"keep": "02_intro.md:3", "others": []}))
    assert silent.problems == ("It says nothing of 03_antecedentes.md:5.",)


_DATASET = Repetition(
    sentences=(
        Stated(
            source="03_antecedentes (2026-10-01).md",
            line=45,
            text="Smith et al. 2024 [29] - Conjunto de 412 estudios de 205 pacientes.",
        ),
        Stated(
            source="08_metodologia (2026-10-01).md",
            line=23,
            text="Estudios y pacientes - 412 estudios de 205 pacientes; edad media de 64 años.",
        ),
    )
)


def _rewriting(reads: str) -> str:
    return json.dumps(
        {
            "keep": "03_antecedentes (2026-10-01).md:45",
            "others": [{"at": "08_metodologia (2026-10-01).md:23", "reads": reads}],
        }
    )


def test_what_a_rewrite_takes_out_that_nothing_else_says_is_named() -> None:
    """The pilot's 14B dropped the mean age; the kept sentence never had it."""
    edit = proposal_from(_DATASET, _rewriting("Estudios y pacientes: véase antecedentes.")).edits[0]
    assert {"64", "edad", "media", "años"} <= set(edit.lost)
    assert "412" not in edit.lost, "the kept sentence still says it"


def test_a_rewrite_that_points_by_file_or_line_is_named() -> None:
    for reads in ("Véase la línea 45.", "Detalles en 03_antecedentes (2026-10-01).md:45."):
        edit = proposal_from(_DATASET, _rewriting(reads)).edits[0]
        assert edit.names_a_place, reads
    plain = proposal_from(_DATASET, _rewriting("Edad media de 64 años; véase antecedentes."))
    assert not plain.edits[0].names_a_place and not plain.edits[0].lost


def test_each_place_carries_its_chapter_in_words() -> None:
    assert chapter_of("03_antecedentes (2026-10-01).md") == "antecedentes"
    assert chapter_of("compacto_04_estado_del_arte (2026-10-01).md") == "estado del arte"
    assert chapter_of("draft.md") == "draft"
    asked = proposal_prompt(_DATASET)
    assert "03_antecedentes (2026-10-01).md:45 (chapter: antecedentes): Smith" in asked
    assert "never write a file name or a line" in asked


def test_two_sentences_of_one_paragraph_get_places_apart() -> None:
    """Joined to a group through a third, they still have to be told apart by the model."""
    group = Repetition(
        sentences=(
            Stated(source="a.md", line=3, text="primera"),
            Stated(source="a.md", line=3, text="segunda"),
            Stated(source="b.md", line=9, text="tercera"),
        )
    )
    assert places_of(group) == ("a.md:3", "a.md:3 (2)", "b.md:9")
    assert proposal_schema(group)["properties"]["keep"]["enum"] == list(places_of(group))


def test_the_report_says_its_rule_and_calls_nothing_a_fault() -> None:
    groups = repetitions(stated_in(_INTRO, "02.md") + stated_in(_BACKGROUND, "03.md"))
    written = report_text(groups, ("02.md", "03.md"), 2)
    assert "A group is a place to look, not a fault" in written
    assert "1 group, holding 2 sentences of 2 read in 2 files:" in written
    assert written.count("> **") == 2
    assert report_text((), ("02.md",), 1).count("Nothing in them is said twice") == 1
