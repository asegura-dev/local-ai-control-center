"""`lacc repeats`: where a text states the same fact twice, with no model (ADR-125)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from local_ai_control_center.cli import app
from local_ai_control_center.core.repetition import repetitions, stated_in
from local_ai_control_center.features.repeats import report_text

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


def test_the_report_says_its_rule_and_calls_nothing_a_fault() -> None:
    groups = repetitions(stated_in(_INTRO, "02.md") + stated_in(_BACKGROUND, "03.md"))
    written = report_text(groups, ("02.md", "03.md"), 2)
    assert "A group is a place to look, not a fault" in written
    assert "1 group, holding 2 sentences of 2 read in 2 files:" in written
    assert written.count("> **") == 2
    assert report_text((), ("02.md",), 1).count("Nothing in them is said twice") == 1
