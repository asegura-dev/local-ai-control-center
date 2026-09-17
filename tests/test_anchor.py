"""The sidecar that remembers how long a trail was (ADR-049).

ADR-043 tested seven safety claims by running them; the one that failed was records removed
from the end. These tests are the same shape: the trail is actually truncated, actually
edited, and the check has to say which.
"""

from __future__ import annotations

import json
from pathlib import Path

from local_ai_control_center.core.config import Config
from local_ai_control_center.core.workspace import Workspace
from local_ai_control_center.system.audit import ANCHOR_SUFFIX, AuditLog, check_anchor

NL = chr(10)


def _trail(tmp_path: Path, records: int = 4) -> AuditLog:
    workspace = Workspace.ensure(tmp_path)
    audit = AuditLog(workspace, Config(workspace_root=tmp_path))
    for number in range(records):
        audit.record(f"run-{number}", "run_started", f"record {number}", {})
    return audit


def test_an_anchor_is_written_beside_the_trail(tmp_path: Path) -> None:
    audit = _trail(tmp_path)
    anchor = audit.path.with_suffix(ANCHOR_SUFFIX)
    assert anchor.exists()
    remembered = json.loads(anchor.read_text(encoding="utf-8"))
    assert remembered["records"] == 4
    assert len(remembered["head"]) == 64


def test_an_untouched_trail_agrees_with_its_anchor(tmp_path: Path) -> None:
    audit = _trail(tmp_path)
    found = check_anchor(audit.path)
    assert found.present and found.agrees
    assert found.expected_records == found.found_records == 4
    assert not found.head_changed and found.lost == 0


def test_records_removed_from_the_end_are_caught(tmp_path: Path) -> None:
    """The gap ADR-043 measured and no hash chain can close from the file alone."""
    audit = _trail(tmp_path, records=6)
    lines = [line for line in audit.path.read_text(encoding="utf-8").splitlines() if line]
    audit.path.write_text(NL.join(lines[:4]) + NL, encoding="utf-8")

    found = check_anchor(audit.path)
    assert found.present and not found.agrees
    assert found.lost == 2
    assert found.expected_records == 6
    assert found.found_records == 4


def test_a_replaced_last_record_is_told_from_a_removed_one(tmp_path: Path) -> None:
    """Different events, different causes, and one message for both would mislead."""
    audit = _trail(tmp_path, records=5)
    lines = [line for line in audit.path.read_text(encoding="utf-8").splitlines() if line]
    swapped = json.loads(lines[-1])
    swapped["message"] = "something else entirely"
    swapped["digest"] = "0" * 64
    lines[-1] = json.dumps(swapped)
    audit.path.write_text(NL.join(lines) + NL, encoding="utf-8")

    found = check_anchor(audit.path)
    assert not found.agrees
    assert found.lost == 0, "nothing was removed"
    assert found.head_changed


def test_a_trail_written_before_anchors_existed_is_not_an_alarm(tmp_path: Path) -> None:
    """Treating every old trail as tampered with would be an alarm about our own history."""
    audit = _trail(tmp_path)
    audit.path.with_suffix(ANCHOR_SUFFIX).unlink()
    found = check_anchor(audit.path)
    assert not found.present
    assert not found.agrees


def test_the_anchor_keeps_up_as_the_trail_grows(tmp_path: Path) -> None:
    audit = _trail(tmp_path, records=2)
    assert check_anchor(audit.path).expected_records == 2
    audit.record("run-later", "run_finished", "one more", {})
    found = check_anchor(audit.path)
    assert found.agrees and found.expected_records == 3


def test_something_appended_behind_lacc_is_noticed(tmp_path: Path) -> None:
    audit = _trail(tmp_path, records=3)
    with audit.path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"kind": "run_started", "message": "not from LACC"}) + NL)
    found = check_anchor(audit.path)
    assert not found.agrees
    assert found.found_records > found.expected_records


def test_an_anchor_that_cannot_be_written_does_not_fail_the_run(tmp_path: Path) -> None:
    """The record is already written; failing for the note about it trades the wrong way."""
    workspace = Workspace.ensure(tmp_path)
    audit = AuditLog(workspace, Config(workspace_root=tmp_path))
    audit.record("run-1", "run_started", "first", {})
    anchor = audit.path.with_suffix(ANCHOR_SUFFIX)
    anchor.unlink()
    anchor.mkdir()  # a directory where the file should be: writing it must fail

    written = audit.record("run-1", "run_finished", "second", {})
    assert written is not None
    assert "second" in audit.path.read_text(encoding="utf-8")
