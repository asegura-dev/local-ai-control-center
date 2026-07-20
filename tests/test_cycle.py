"""Integration tests for the execution cycle.

Unlike the other test modules, these exercise configuration, workspace,
permissions, provider, preview, and audit together rather than in isolation.
"""

from __future__ import annotations

import json
from pathlib import Path

from local_ai_control_center.audit import AuditLog
from local_ai_control_center.config import Config
from local_ai_control_center.cycle import ExecutionPreview, RunResult, run_action
from local_ai_control_center.permissions import Permissions
from local_ai_control_center.preview import IntendedAction
from local_ai_control_center.provider import MockProvider
from local_ai_control_center.workspace import Workspace


def _accept(_preview: ExecutionPreview) -> bool:
    return True


def _decline(_preview: ExecutionPreview) -> bool:
    return False


def _run(
    tmp_path: Path,
    action: IntendedAction,
    permissions: Permissions,
    confirm: object = _accept,
    **config_kwargs: object,
) -> tuple[RunResult, AuditLog]:
    workspace = Workspace.ensure(tmp_path)
    config = Config(workspace_root=tmp_path, **config_kwargs)  # type: ignore[arg-type]
    audit = AuditLog(workspace, config)
    result = run_action(
        action,
        "the prompt",
        permissions,
        config,
        workspace,
        MockProvider({"the prompt": "the answer"}),
        audit,
        "run-1",
        confirm,  # type: ignore[arg-type]
    )
    return result, audit


def _events(audit: AuditLog) -> list[dict[str, object]]:
    text = audit.path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def _kinds(audit: AuditLog) -> list[object]:
    return [event["kind"] for event in _events(audit)]


def test_allowed_and_confirmed_action_runs(tmp_path: Path) -> None:
    """An action that is permitted and confirmed executes and returns a completion."""
    action = IntendedAction(
        name="summarize",
        summary="Summarize something",
        required=frozenset({"read_files"}),
    )
    result, _ = _run(tmp_path, action, Permissions(read_files=True))
    assert result.outcome == "completed"
    assert result.executed is True
    assert result.completion is not None
    assert result.completion.text == "the answer"


def test_completed_run_records_the_full_sequence(tmp_path: Path) -> None:
    """A successful run leaves the expected trail of events."""
    action = IntendedAction(name="summarize", summary="Summarize", required=frozenset())
    _, audit = _run(tmp_path, action, Permissions())
    assert _kinds(audit) == [
        "run_started",
        "permission_granted",
        "provider_called",
        "run_finished",
    ]


def test_missing_capability_refuses_before_asking(tmp_path: Path) -> None:
    """A refused preview stops the run without calling the confirmation function."""

    def _explode(_preview: ExecutionPreview) -> bool:
        raise AssertionError("confirmation must not be requested for a refused action")

    action = IntendedAction(
        name="write-report",
        summary="Write a report",
        required=frozenset({"write_files"}),
    )
    result, audit = _run(tmp_path, action, Permissions(), confirm=_explode)
    assert result.outcome == "refused"
    assert result.executed is False
    assert result.completion is None
    assert _kinds(audit) == ["run_started", "run_refused"]


def test_refusal_records_what_was_missing(tmp_path: Path) -> None:
    """The refusal event names the missing capability."""
    action = IntendedAction(
        name="write-report",
        summary="Write a report",
        required=frozenset({"write_files"}),
    )
    _, audit = _run(tmp_path, action, Permissions())
    refusal = _events(audit)[-1]
    assert refusal["detail"] == {
        "action": "write-report",
        "missing": ["write_files"],
        "out_of_bounds": [],
    }


def test_target_outside_the_workspace_is_refused(tmp_path: Path) -> None:
    """Boundary violations stop the run, integrating workspace with the cycle."""
    outside = tmp_path / "elsewhere.txt"
    workspace_root = tmp_path / "ws"
    action = IntendedAction(name="read", summary="Read a file", targets=(outside,))
    result, _ = _run(workspace_root, action, Permissions())
    assert result.outcome == "refused"


def test_declining_stops_the_run_and_is_recorded(tmp_path: Path) -> None:
    """A declined confirmation executes nothing and leaves a record."""
    action = IntendedAction(name="summarize", summary="Summarize", required=frozenset())
    result, audit = _run(tmp_path, action, Permissions(), confirm=_decline)
    assert result.outcome == "declined"
    assert result.completion is None
    assert _kinds(audit) == ["run_started", "permission_granted", "confirmation_declined"]


def test_configuration_ceiling_refuses_the_run(tmp_path: Path) -> None:
    """A capability the configuration forbids refuses the run end to end."""
    action = IntendedAction(
        name="fetch",
        summary="Fetch something",
        required=frozenset({"network"}),
    )
    result, _ = _run(tmp_path, action, Permissions(network=True), network_access=False)
    assert result.outcome == "refused"


def test_configuration_ceiling_lifted_allows_the_run(tmp_path: Path) -> None:
    """With the configuration allowing it, the same action runs."""
    action = IntendedAction(
        name="fetch",
        summary="Fetch something",
        required=frozenset({"network"}),
    )
    result, _ = _run(tmp_path, action, Permissions(network=True), network_access=True)
    assert result.outcome == "completed"


def test_standard_audit_level_omits_prompt_and_completion(tmp_path: Path) -> None:
    """By default the trail records that a provider was called, not what was said."""
    action = IntendedAction(name="summarize", summary="Summarize", required=frozenset())
    _, audit = _run(tmp_path, action, Permissions())
    call = next(event for event in _events(audit) if event["kind"] == "provider_called")
    detail = call["detail"]
    assert isinstance(detail, dict)
    assert "prompt" not in detail
    assert "completion" not in detail
    assert detail["provider"] == "mock"


def test_full_audit_level_records_prompt_and_completion(tmp_path: Path) -> None:
    """Under `full`, the content is recorded as an explicit opt-in."""
    action = IntendedAction(name="summarize", summary="Summarize", required=frozenset())
    _, audit = _run(tmp_path, action, Permissions(), audit_level="full")
    call = next(event for event in _events(audit) if event["kind"] == "provider_called")
    detail = call["detail"]
    assert isinstance(detail, dict)
    assert detail["prompt"] == "the prompt"
    assert detail["completion"] == "the answer"


def test_every_event_carries_the_run_id(tmp_path: Path) -> None:
    """The whole trail is tied to one execution."""
    action = IntendedAction(name="summarize", summary="Summarize", required=frozenset())
    _, audit = _run(tmp_path, action, Permissions())
    assert {event["run_id"] for event in _events(audit)} == {"run-1"}
