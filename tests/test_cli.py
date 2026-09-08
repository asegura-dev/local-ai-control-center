"""Tests for the command-line interface.

Uses Typer's CliRunner to invoke commands as a user would, with a temporary
configuration and workspace so nothing real is touched. Confirmation is driven
through stdin. Run tests use the mock provider so they never depend on Ollama.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

from typer.testing import CliRunner

from local_ai_control_center.cli import app

runner = CliRunner()


def _config_file(tmp_path: Path) -> Path:
    """Write a configuration whose workspace already holds the note runs summarize."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "notes.txt").write_text("A short note to summarize.\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}\n", encoding="utf-8")
    return config


def test_help_lists_the_commands() -> None:
    """The top-level help shows run and preview."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "preview" in result.stdout


def test_preview_shows_the_preview_without_running(tmp_path: Path) -> None:
    """preview renders the preview and does not create an audit log."""
    config = _config_file(tmp_path)
    result = runner.invoke(app, ["preview", "summarize_file", "notes.txt", "-c", str(config)])
    assert result.exit_code == 0
    assert "summarize_file" in result.stdout
    assert not (tmp_path / "ws" / "audit.jsonl").exists()


def test_run_declined_by_default(tmp_path: Path) -> None:
    """Pressing Enter at the prompt declines; nothing executes."""
    config = _config_file(tmp_path)
    result = runner.invoke(
        app,
        ["run", "summarize_file", "notes.txt", "-c", str(config), "--provider", "mock"],
        input="\n",
    )
    assert result.exit_code == 0
    assert "Declined" in result.stdout


def test_run_executes_on_yes(tmp_path: Path) -> None:
    """Answering yes runs the skill and shows a result."""
    config = _config_file(tmp_path)
    result = runner.invoke(
        app,
        ["run", "summarize_file", "notes.txt", "-c", str(config), "--provider", "mock"],
        input="y\n",
    )
    assert result.exit_code == 0
    assert "Result" in result.stdout


def test_run_records_to_the_audit_log(tmp_path: Path) -> None:
    """A confirmed run leaves an audit trail in the workspace."""
    config = _config_file(tmp_path)
    runner.invoke(
        app,
        ["run", "summarize_file", "notes.txt", "-c", str(config), "--provider", "mock"],
        input="y\n",
    )
    log = tmp_path / "ws" / "audit.jsonl"
    assert log.exists()
    kinds = [json.loads(line)["kind"] for line in log.read_text(encoding="utf-8").splitlines()]
    assert kinds == [
        "run_started",
        "permission_granted",
        "files_read",
        "provider_called",
        "run_finished",
    ]


def test_run_without_model_fails_clearly(tmp_path: Path) -> None:
    """The default provider (Ollama) needs a configured model; without one, it exits clearly."""
    config = _config_file(tmp_path)
    result = runner.invoke(
        app,
        ["run", "summarize_file", "notes.txt", "-c", str(config)],
        input="y\n",
    )
    assert result.exit_code == 1
    assert "No model configured" in result.stdout


def test_unknown_skill_fails_clearly(tmp_path: Path) -> None:
    """An unknown skill name exits with an error and lists what is available."""
    config = _config_file(tmp_path)
    result = runner.invoke(app, ["run", "nonexistent", "x", "-c", str(config)])
    assert result.exit_code == 1
    assert "Unknown skill" in result.stdout
    assert "summarize_file" in result.stdout


def test_missing_config_fails_clearly(tmp_path: Path) -> None:
    """A missing configuration file exits with a clear error."""
    result = runner.invoke(
        app,
        ["preview", "summarize_file", "notes.txt", "-c", str(tmp_path / "nope.yaml")],
    )
    assert result.exit_code == 1
    assert "Could not load configuration" in result.stdout


def _ingest_config(tmp_path: Path) -> tuple[Path, Path]:
    """A configuration whose workspace holds a real PDF, and the workspace path."""
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    config = tmp_path / "ingest.yaml"
    config.write_text(f"workspace_root: {workspace}\n", encoding="utf-8")
    return config, workspace


def test_ingest_converts_after_confirmation(tmp_path: Path, make_pdf: Callable[..., Path]) -> None:
    """Answering yes writes the extracted text and says where it went."""
    config, workspace = _ingest_config(tmp_path)
    shutil.copy(make_pdf("Attention is all you need"), workspace / "paper.pdf")

    result = runner.invoke(app, ["ingest", "paper.pdf", "-c", str(config)], input="y\n")
    assert result.exit_code == 0
    assert "paper.md" in result.stdout
    assert "Attention is all you need" in (workspace / "paper.md").read_text(encoding="utf-8")


def test_ingest_declined_writes_nothing(tmp_path: Path, make_pdf: Callable[..., Path]) -> None:
    """Pressing Enter declines, and the effects never happen."""
    config, workspace = _ingest_config(tmp_path)
    shutil.copy(make_pdf("Some text"), workspace / "paper.pdf")

    result = runner.invoke(app, ["ingest", "paper.pdf", "-c", str(config)], input="\n")
    assert result.exit_code == 0
    assert "Declined" in result.stdout
    assert not (workspace / "paper.md").exists()


def test_ingest_accepts_an_explicit_destination(
    tmp_path: Path, make_pdf: Callable[..., Path]
) -> None:
    """The destination can be named instead of derived."""
    config, workspace = _ingest_config(tmp_path)
    shutil.copy(make_pdf("Some text"), workspace / "paper.pdf")

    result = runner.invoke(
        app, ["ingest", "paper.pdf", "sources.md", "-c", str(config)], input="y\n"
    )
    assert result.exit_code == 0
    assert (workspace / "sources.md").exists()
    assert not (workspace / "paper.md").exists()


def test_ingest_rejects_an_unsupported_format_before_asking(tmp_path: Path) -> None:
    """An unsupported format exits non-zero without previewing or asking anything."""
    config, workspace = _ingest_config(tmp_path)
    (workspace / "notes.rtf").write_text("x", encoding="utf-8")

    result = runner.invoke(app, ["ingest", "notes.rtf", "-c", str(config)])
    assert result.exit_code == 1
    assert "does not know how to convert" in result.stdout
    assert "Proceed?" not in result.stdout


def test_ingest_will_not_overwrite(tmp_path: Path, make_pdf: Callable[..., Path]) -> None:
    """An existing destination ends the run with a clear message and exit code."""
    config, workspace = _ingest_config(tmp_path)
    shutil.copy(make_pdf("Some text"), workspace / "paper.pdf")
    (workspace / "paper.md").write_text("corrected by hand", encoding="utf-8")

    result = runner.invoke(app, ["ingest", "paper.pdf", "-c", str(config)], input="y\n")
    assert result.exit_code == 1
    assert "already exists" in result.stdout
    assert (workspace / "paper.md").read_text(encoding="utf-8") == "corrected by hand"


def test_refused_run_exits_non_zero(tmp_path: Path, make_pdf: Callable[..., Path]) -> None:
    """A script that checks the exit code must not be told the work succeeded."""
    config, workspace = _ingest_config(tmp_path)
    shutil.copy(make_pdf("Some text"), workspace / "paper.pdf")

    result = runner.invoke(
        app, ["ingest", "paper.pdf", "../escaped.md", "-c", str(config)], input="y\n"
    )
    assert result.exit_code == 1
    assert "Refused" in result.stdout
    assert not (tmp_path / "escaped.md").exists()


def test_declined_run_still_exits_zero(tmp_path: Path, make_pdf: Callable[..., Path]) -> None:
    """Declining is the system working, not a failure, and the exit code says so."""
    config, workspace = _ingest_config(tmp_path)
    shutil.copy(make_pdf("Some text"), workspace / "paper.pdf")

    result = runner.invoke(app, ["ingest", "paper.pdf", "-c", str(config)], input="\n")
    assert result.exit_code == 0


def test_both_skills_are_available(tmp_path: Path) -> None:
    """An unknown name lists what does exist, and both skills are in it."""
    config, _ = _ingest_config(tmp_path)
    result = runner.invoke(app, ["run", "nonexistent", "x", "-c", str(config)])
    assert result.exit_code == 1
    assert "summarize_file" in result.stdout
    assert "critique_file" in result.stdout


def test_critique_previews_as_a_read_only_action(tmp_path: Path) -> None:
    """The preview shows a critique asking for read_files and nothing more."""
    config, workspace = _ingest_config(tmp_path)
    (workspace / "chapter.md").write_text("A claim without support.", encoding="utf-8")

    result = runner.invoke(app, ["preview", "critique_file", "chapter.md", "-c", str(config)])
    assert result.exit_code == 0
    assert "critique_file" in result.stdout
    assert "read_files" in result.stdout
    assert "write_files" not in result.stdout
