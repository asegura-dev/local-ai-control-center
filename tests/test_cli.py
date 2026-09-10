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

import pytest
from typer.testing import CliRunner

from local_ai_control_center.cli import app
from local_ai_control_center.notifier import Delivery, Notification, Notifier

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
        "prompt_measured",
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


class _CapturingNotifier(Notifier):
    """A notifier that keeps what it was given instead of sending it."""

    def __init__(self, delivered: bool = True) -> None:
        self.delivered = delivered
        self.sent: list[Notification] = []

    @property
    def name(self) -> str:
        return "recorder"

    def send(self, notification: Notification) -> Delivery:
        self.sent.append(notification)
        return Delivery(transport=self.name, delivered=self.delivered, detail="HTTP 200")


def _install_notifier(monkeypatch: pytest.MonkeyPatch, notifier: Notifier | None) -> None:
    """Put ``notifier`` behind the CLI's factory, so no transport is involved."""
    monkeypatch.setattr(
        "local_ai_control_center.cli.notifier_from_config",
        lambda config, post=None: notifier,
    )


def _kinds(tmp_path: Path) -> list[str]:
    log = tmp_path / "ws" / "audit.jsonl"
    return [json.loads(line)["kind"] for line in log.read_text(encoding="utf-8").splitlines()]


def test_notify_test_says_so_when_nothing_is_configured(tmp_path: Path) -> None:
    """The default configuration has no notifier, and the check reports that clearly."""
    config = _config_file(tmp_path)
    result = runner.invoke(app, ["notify", "test", "-c", str(config)])
    assert result.exit_code == 1
    assert "No notifier configured" in result.stdout


def test_notify_test_sends_one_notification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of the command: check the settings before relying on them."""
    config = _config_file(tmp_path)
    notifier = _CapturingNotifier()
    _install_notifier(monkeypatch, notifier)
    result = runner.invoke(app, ["notify", "test", "-c", str(config)])
    assert result.exit_code == 0
    assert len(notifier.sent) == 1
    assert "notification_sent" in _kinds(tmp_path)


def test_notify_test_exits_non_zero_when_nothing_arrived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Usable from a script: a check that cannot deliver does not report success."""
    config = _config_file(tmp_path)
    _install_notifier(monkeypatch, _CapturingNotifier(delivered=False))
    result = runner.invoke(app, ["notify", "test", "-c", str(config)])
    assert result.exit_code == 1
    assert "notification_failed" in _kinds(tmp_path)


def test_a_finished_run_is_announced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The reason the notifier exists: a run that took minutes says it is done."""
    config = _config_file(tmp_path)
    notifier = _CapturingNotifier()
    _install_notifier(monkeypatch, notifier)
    result = runner.invoke(
        app,
        ["run", "summarize_file", "notes.txt", "-c", str(config), "--provider", "mock"],
        input="y\n",
    )
    assert result.exit_code == 0
    assert len(notifier.sent) == 1
    assert "summarize_file" in notifier.sent[0].title
    assert "completed" in notifier.sent[0].title


def test_a_notification_carries_no_document_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rule that matters: the destination is a machine, and it still gets no work.

    The note in the workspace is read, summarized and written about; none of its words,
    nor the answer's, may appear in what leaves the machine (ADR-027).
    """
    config = _config_file(tmp_path)
    notifier = _CapturingNotifier()
    _install_notifier(monkeypatch, notifier)
    runner.invoke(
        app,
        ["run", "summarize_file", "notes.txt", "-c", str(config), "--provider", "mock"],
        input="y\n",
    )
    said = notifier.sent[0].title + notifier.sent[0].body
    assert "A short note to summarize" not in said
    assert "notes.txt" not in said


def test_a_declined_run_is_not_announced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Declining happens with the user present; there is nobody to tell."""
    config = _config_file(tmp_path)
    notifier = _CapturingNotifier()
    _install_notifier(monkeypatch, notifier)
    runner.invoke(
        app,
        ["run", "summarize_file", "notes.txt", "-c", str(config), "--provider", "mock"],
        input="\n",
    )
    assert notifier.sent == []


def test_an_undelivered_notification_does_not_fail_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Best effort, and it is the run that matters: the answer still stands."""
    config = _config_file(tmp_path)
    _install_notifier(monkeypatch, _CapturingNotifier(delivered=False))
    result = runner.invoke(
        app,
        ["run", "summarize_file", "notes.txt", "-c", str(config), "--provider", "mock"],
        input="y\n",
    )
    assert result.exit_code == 0
    assert "Result" in result.stdout
    assert "notification_failed" in _kinds(tmp_path)
