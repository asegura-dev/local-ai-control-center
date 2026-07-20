"""Tests for the command-line interface.

Uses Typer's CliRunner to invoke commands as a user would, with a temporary
configuration and workspace so nothing real is touched. Confirmation is driven
through stdin.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from local_ai_control_center.cli import app

runner = CliRunner()


def _config_file(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
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
        ["run", "summarize_file", "notes.txt", "-c", str(config)],
        input="\n",
    )
    assert result.exit_code == 0
    assert "Declined" in result.stdout


def test_run_executes_on_yes(tmp_path: Path) -> None:
    """Answering yes runs the skill and shows a result."""
    config = _config_file(tmp_path)
    result = runner.invoke(
        app,
        ["run", "summarize_file", "notes.txt", "-c", str(config)],
        input="y\n",
    )
    assert result.exit_code == 0
    assert "Result" in result.stdout


def test_run_records_to_the_audit_log(tmp_path: Path) -> None:
    """A confirmed run leaves an audit trail in the workspace."""
    config = _config_file(tmp_path)
    runner.invoke(
        app,
        ["run", "summarize_file", "notes.txt", "-c", str(config)],
        input="y\n",
    )
    log = tmp_path / "ws" / "audit.jsonl"
    assert log.exists()
    kinds = [json.loads(line)["kind"] for line in log.read_text(encoding="utf-8").splitlines()]
    assert kinds == ["run_started", "permission_granted", "provider_called", "run_finished"]


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
