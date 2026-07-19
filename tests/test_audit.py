"""Tests for the audit log: record format, privacy levels, and failure policy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from local_ai_control_center.audit import AUDIT_FILENAME, AuditLog, AuditWriteError
from local_ai_control_center.config import Config
from local_ai_control_center.workspace import Workspace


def _log(tmp_path: Path, **config_kwargs: object) -> AuditLog:
    workspace = Workspace.ensure(tmp_path)
    config = Config(workspace_root=tmp_path, **config_kwargs)  # type: ignore[arg-type]
    return AuditLog(workspace, config)


def _lines(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def test_log_path_is_inside_the_workspace(tmp_path: Path) -> None:
    """The log resolves to a path within the workspace."""
    log = _log(tmp_path)
    assert log.path == (tmp_path / AUDIT_FILENAME).resolve()


def test_record_writes_one_json_line(tmp_path: Path) -> None:
    """A recorded event becomes exactly one JSON line."""
    log = _log(tmp_path)
    log.record("run-1", "run_started", "started")
    records = _lines(log.path)
    assert len(records) == 1
    assert records[0]["run_id"] == "run-1"
    assert records[0]["kind"] == "run_started"
    assert records[0]["message"] == "started"


def test_records_append_never_overwrite(tmp_path: Path) -> None:
    """Successive records accumulate; earlier lines are preserved."""
    log = _log(tmp_path)
    log.record("run-1", "run_started", "first")
    log.record("run-1", "run_finished", "second")
    records = _lines(log.path)
    assert [record["message"] for record in records] == ["first", "second"]


def test_record_returns_the_written_event(tmp_path: Path) -> None:
    """A successful record returns the event it wrote."""
    event = _log(tmp_path).record("run-1", "provider_called", "called")
    assert event is not None
    assert event.kind == "provider_called"


def test_timestamp_is_utc_formatted(tmp_path: Path) -> None:
    """The timestamp is an ISO-like UTC string."""
    event = _log(tmp_path).record("run-1", "run_started", "started")
    assert event is not None
    assert event.timestamp.endswith("Z")


def test_standard_level_omits_content(tmp_path: Path) -> None:
    """Under the default level, prompt and completion are not written."""
    log = _log(tmp_path)
    log.record(
        "run-1",
        "provider_called",
        "called",
        {"prompt": "secret question", "completion": "secret answer", "provider": "mock"},
    )
    detail = _lines(log.path)[0]["detail"]
    assert detail == {"provider": "mock"}


def test_full_level_records_content(tmp_path: Path) -> None:
    """Under `full`, content is recorded as an explicit opt-in."""
    log = _log(tmp_path, audit_level="full")
    log.record(
        "run-1",
        "provider_called",
        "called",
        {"prompt": "the question", "completion": "the answer"},
    )
    detail = _lines(log.path)[0]["detail"]
    assert detail == {"prompt": "the question", "completion": "the answer"}


def test_standard_level_keeps_non_content_detail(tmp_path: Path) -> None:
    """Metadata survives the content filter."""
    log = _log(tmp_path)
    log.record("run-1", "permission_denied", "denied", {"missing": ["write_files"]})
    assert _lines(log.path)[0]["detail"] == {"missing": ["write_files"]}


def test_abort_policy_raises_on_write_failure(tmp_path: Path) -> None:
    """With the default policy, a write failure stops execution."""
    log = _log(tmp_path)
    log.path.mkdir()  # a directory where the file should be: writing will fail
    with pytest.raises(AuditWriteError):
        log.record("run-1", "run_started", "started")


def test_continue_policy_returns_none_on_write_failure(tmp_path: Path) -> None:
    """With `continue`, a write failure is swallowed and reported as None."""
    log = _log(tmp_path, audit_failure_policy="continue")
    log.path.mkdir()
    assert log.record("run-1", "run_started", "started") is None


def test_event_is_frozen(tmp_path: Path) -> None:
    """A written event cannot be revised."""
    event = _log(tmp_path).record("run-1", "run_started", "started")
    assert event is not None
    with pytest.raises(ValidationError):
        event.message = "tampered"  # type: ignore[misc]
