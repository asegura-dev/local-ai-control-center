"""What was done, read back as runs (ADR-104).

The reader in `features/trail.py` and the writer in `system/audit.py` are held together here:
records are written with the real log and read back with the slice, so a change to one that the
other does not follow fails a test rather than a window. Two writers of the corpus format were
not held together, and drifted (ADR-065).
"""

from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path

from typer.testing import CliRunner

from local_ai_control_center.cli import app
from local_ai_control_center.core.config import Config
from local_ai_control_center.core.workspace import Workspace
from local_ai_control_center.features.trail import (
    ANSWER_SHOWN,
    PROMPT_SHOWN,
    Trail,
    integrity_of,
    trail_of,
)
from local_ai_control_center.system.audit import AuditLog, check_anchor, walk


def _log(tmp_path: Path, level: str = "full") -> AuditLog:
    workspace = Workspace.ensure(tmp_path)
    return AuditLog(workspace, Config(workspace_root=tmp_path, audit_level=level))  # type: ignore[arg-type]


def _read(log: AuditLog) -> Trail:
    walked = walk(log.path)
    said = integrity_of(walked.chain, check_anchor(log.path), str(log.path), walked.exists)
    return trail_of(walked.events, said, str(log.path), walked.vouched, zone=UTC)


def _a_run(log: AuditLog, run: str, *ending: str) -> None:
    log.record(run, "run_started", "Starting extract_claims", {"action": "extract_claims"})
    log.record(
        run,
        "provider_called",
        "Called ollama:qwen2.5:14b for extract_claims",
        {"action": "extract_claims", "prompt": "p" * 5000, "completion": "c" * 9000},
    )
    for kind in ending:
        log.record(run, kind, f"{kind} extract_claims", {"action": "extract_claims"})  # type: ignore[arg-type]


def test_records_become_runs_newest_first(tmp_path: Path) -> None:
    log = _log(tmp_path)
    _a_run(log, "first", "run_finished")
    _a_run(log, "second", "run_finished")
    trail = _read(log)
    assert [run.key for run in trail.runs] == ["second", "first"]
    assert trail.total_runs == 2
    assert trail.records == 6
    assert trail.runs[0].what == "extract_claims"
    assert [step.kind for step in trail.runs[0].steps] == [
        "run_started",
        "provider_called",
        "run_finished",
    ]


def test_how_a_run_ended_is_read_from_what_it_recorded(tmp_path: Path) -> None:
    """Nine of the 250 runs in the thesis's trail recorded no end: a crash, or a window
    closed mid-run. Calling them finished would be the one thing this must not do."""
    log = _log(tmp_path)
    _a_run(log, "done", "run_finished")
    _a_run(log, "too-big", "prompt_too_large")
    _a_run(log, "no", "confirmation_declined")
    _a_run(log, "broke", "read_failed")
    _a_run(log, "unreachable", "run_failed")
    _a_run(log, "cut-short")
    log.record("ping", "notification_sent", "Test notification via ntfy", {"transport": "ntfy"})
    ended = {run.key: (run.ending, run.tone) for run in _read(log).runs}
    assert ended == {
        "done": ("finished", "good"),
        "too-big": ("refused: the prompt did not fit", "warn"),
        "no": ("declined", "plain"),
        "broke": ("failed", "bad"),
        "unreachable": ("failed", "bad"),
        "cut-short": ("no end recorded", "warn"),
        "ping": ("notification sent", "plain"),
    }
    assert next(run for run in _read(log).runs if run.key == "ping").what == "notification"


def test_a_command_outside_the_cycle_reads_as_a_run_like_any_other(tmp_path: Path) -> None:
    """`resolve` opened its run with the first record every run has, and the Audit section
    names it and reads its end with nothing learned but `run_failed` (ADR-107)."""
    log = _log(tmp_path, "standard")
    run = log.opened("resolve")
    log.asked(run, "resolve", "https://api.crossref.org", ("10.1000/one", "10.1000/two"), False)
    log.record(run, "run_finished", "Finished resolve", {"action": "resolve", "resolved": 2})
    read = _read(log).runs[0]
    assert (read.what, read.ending) == ("resolve", "finished")
    facts = dict(read.steps[1].facts)
    assert facts["asked"] == "2"
    assert "dois" not in facts, "the list is a bibliography, kept only under full"


def test_what_was_sent_and_said_is_cut_and_counted(tmp_path: Path) -> None:
    log = _log(tmp_path)
    _a_run(log, "one", "run_finished")
    called = _read(log).runs[0].steps[1]
    answer, prompt = called.content
    assert (answer.name, len(answer.shown), answer.left) == ("answer", ANSWER_SHOWN, 5000)
    assert (prompt.name, len(prompt.shown), prompt.left) == ("prompt", PROMPT_SHOWN, 3500)
    assert answer.digest == "" and "prompt" not in dict(called.facts)


def test_a_run_whose_content_was_not_kept_says_so(tmp_path: Path) -> None:
    """Under `standard` the log drops prompt and answer. The run says it called an engine and
    kept neither, rather than looking like a run that sent nothing."""
    log = _log(tmp_path, level="standard")
    _a_run(log, "one", "run_finished")
    run = _read(log).runs[0]
    assert run.unkept
    assert not any(step.content for step in run.steps)


def test_a_broken_trail_is_still_shown_and_marked_from_the_break_on(tmp_path: Path) -> None:
    """Hiding what follows a break would hide the evidence (ADR-104)."""
    log = _log(tmp_path)
    _a_run(log, "before", "run_finished")
    _a_run(log, "after", "run_finished")
    lines = log.path.read_text(encoding="utf-8").splitlines()
    edited = json.loads(lines[3])
    edited["message"] = "Something else entirely"
    lines[3] = json.dumps(edited)
    log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    trail = _read(log)
    assert trail.integrity[0].lead == "The trail has been altered."
    runs = {run.key: run for run in trail.runs}
    assert runs["before"].vouched
    assert not runs["after"].vouched
    assert [step.vouched for step in runs["after"].steps] == [False, False, False]


def test_an_untouched_trail_holds_and_every_record_is_vouched_for(tmp_path: Path) -> None:
    log = _log(tmp_path)
    _a_run(log, "one", "run_finished")
    walked = walk(log.path)
    assert walked.chain.intact
    assert walked.vouched == (True, True, True)


def test_a_workspace_with_nothing_recorded_has_no_trail_yet(tmp_path: Path) -> None:
    """`lacc verify` used to call it unreadable at record 1 (ADR-104)."""
    log = _log(tmp_path)
    trail = _read(log)
    assert trail.runs == ()
    assert trail.integrity[0].lead == "No trail yet."


def test_only_the_latest_are_listed_and_the_total_is_kept(tmp_path: Path) -> None:
    log = _log(tmp_path)
    for number in range(5):
        _a_run(log, f"run-{number}", "run_finished")
    walked = walk(log.path)
    trail = trail_of(walked.events, (), "here", walked.vouched, zone=UTC, most=2)
    assert trail.total_runs == 5
    assert [run.key for run in trail.runs] == ["run-4", "run-3"]


runner = CliRunner()


def test_verify_says_the_trail_holds_and_what_the_anchor_says(tmp_path: Path) -> None:
    log = _log(tmp_path)
    _a_run(log, "one", "run_finished")
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {tmp_path}\n", encoding="utf-8")
    result = runner.invoke(app, ["verify", "-c", str(config)])
    said = " ".join(result.stdout.split())
    assert result.exit_code == 0, result.stdout
    assert "The trail holds. 3 records in" in said
    assert "The anchor agrees: 3 records" in said
    assert "removed from the end" in said


def test_verify_in_a_workspace_with_no_trail_is_not_a_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}\n", encoding="utf-8")
    result = runner.invoke(app, ["verify", "-c", str(config)])
    assert result.exit_code == 0, result.stdout
    assert "No trail yet." in result.stdout


def test_verify_fails_on_an_altered_trail(tmp_path: Path) -> None:
    log = _log(tmp_path)
    _a_run(log, "one", "run_finished")
    lines = log.path.read_text(encoding="utf-8").splitlines()
    edited = json.loads(lines[0])
    edited["message"] = "Altered"
    lines[0] = json.dumps(edited)
    log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {tmp_path}\n", encoding="utf-8")
    result = runner.invoke(app, ["verify", "-c", str(config)])
    assert result.exit_code == 1
    assert "The trail has been altered." in " ".join(result.stdout.split())
