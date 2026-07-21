"""Tests for the skill contract and the summarize-file demonstration skill."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_ai_control_center.audit import AuditLog
from local_ai_control_center.config import Config
from local_ai_control_center.permissions import Capability, Permissions
from local_ai_control_center.preview import ExecutionPreview, IntendedAction
from local_ai_control_center.provider import MockProvider
from local_ai_control_center.skill import (
    Skill,
    SkillPlan,
    SummarizeFileSkill,
    grant_for,
    run_skill,
)
from local_ai_control_center.workspace import Workspace


def _accept(_preview: ExecutionPreview) -> bool:
    return True


def test_skill_cannot_be_instantiated() -> None:
    """The abstract contract cannot be used directly."""
    with pytest.raises(TypeError):
        Skill()  # type: ignore[abstract]


def test_summarize_declares_read_files() -> None:
    """The summarize skill needs exactly the read_files capability."""
    skill = SummarizeFileSkill()
    assert skill.name == "summarize_file"
    assert skill.required == frozenset({"read_files"})


def test_plan_produces_an_action_and_prompt() -> None:
    """plan returns a plan describing the file to summarize."""
    plan = SummarizeFileSkill().plan("notes.txt")
    assert isinstance(plan, SkillPlan)
    assert plan.action.name == "summarize_file"
    assert plan.action.required == frozenset({"read_files"})
    assert plan.action.targets == (Path("notes.txt"),)
    assert "notes.txt" in plan.prompt


def test_plan_has_no_side_effects(tmp_path: Path) -> None:
    """Planning touches nothing: it neither reads nor writes."""
    before = set(tmp_path.iterdir())
    SummarizeFileSkill().plan(str(tmp_path / "any.txt"))
    assert set(tmp_path.iterdir()) == before


def test_run_skill_executes_through_the_cycle(tmp_path: Path) -> None:
    """A permitted skill runs end to end and returns a completion."""
    workspace = Workspace.ensure(tmp_path)
    config = Config(workspace_root=tmp_path)
    audit = AuditLog(workspace, config)
    target = tmp_path / "notes.txt"
    result = run_skill(
        SummarizeFileSkill(),
        str(target),
        Permissions(read_files=True),
        config,
        workspace,
        MockProvider(),
        audit,
        "run-1",
        _accept,
    )
    assert result.outcome == "completed"
    assert result.completion is not None


def test_run_skill_refused_without_permission(tmp_path: Path) -> None:
    """Without read_files, the skill is refused before running."""
    workspace = Workspace.ensure(tmp_path)
    config = Config(workspace_root=tmp_path)
    audit = AuditLog(workspace, config)
    result = run_skill(
        SummarizeFileSkill(),
        str(tmp_path / "notes.txt"),
        Permissions(),
        config,
        workspace,
        MockProvider(),
        audit,
        "run-1",
        _accept,
    )
    assert result.outcome == "refused"
    assert result.completion is None


def test_run_skill_refused_for_file_outside_workspace(tmp_path: Path) -> None:
    """A target outside the workspace is refused by the boundary."""
    workspace_root = tmp_path / "ws"
    workspace = Workspace.ensure(workspace_root)
    config = Config(workspace_root=workspace_root)
    audit = AuditLog(workspace, config)
    outside = tmp_path / "elsewhere.txt"
    result = run_skill(
        SummarizeFileSkill(),
        str(outside),
        Permissions(read_files=True),
        config,
        workspace,
        MockProvider(),
        audit,
        "run-1",
        _accept,
    )
    assert result.outcome == "refused"


def test_run_skill_records_the_run(tmp_path: Path) -> None:
    """A completed skill run leaves an audit trail tied to the run id."""
    workspace = Workspace.ensure(tmp_path)
    config = Config(workspace_root=tmp_path)
    audit = AuditLog(workspace, config)
    run_skill(
        SummarizeFileSkill(),
        str(tmp_path / "notes.txt"),
        Permissions(read_files=True),
        config,
        workspace,
        MockProvider(),
        audit,
        "run-1",
        _accept,
    )
    events = [json.loads(line) for line in audit.path.read_text(encoding="utf-8").splitlines()]
    kinds = [event["kind"] for event in events]
    assert kinds == ["run_started", "permission_granted", "provider_called", "run_finished"]
    assert {event["run_id"] for event in events} == {"run-1"}


def _config(*, network_access: bool = False) -> Config:
    return Config(workspace_root=Path("/tmp/lacc"), network_access=network_access)


def test_grant_for_gives_the_skill_what_it_declares() -> None:
    """A skill is granted exactly the capabilities it declares."""
    granted = grant_for(SummarizeFileSkill(), _config())
    assert granted.granted() == frozenset({"read_files"})


def test_grant_for_does_not_grant_undeclared_capabilities() -> None:
    """Capabilities the skill did not declare stay disabled."""
    granted = grant_for(SummarizeFileSkill(), _config())
    assert granted.write_files is False
    assert granted.network is False
    assert granted.run_commands is False


def test_grant_for_respects_the_network_ceiling() -> None:
    """A declared network capability is removed when the configuration forbids it."""

    class NetworkSkill(Skill):
        @property
        def name(self) -> str:
            return "needs_network"

        @property
        def required(self) -> frozenset[Capability]:
            return frozenset({"network"})

        def plan(self, request: str) -> SkillPlan:
            action = IntendedAction(name=self.name, summary="x", required=self.required)
            return SkillPlan(action=action, prompt="x")

    denied = grant_for(NetworkSkill(), _config(network_access=False))
    assert denied.network is False

    allowed = grant_for(NetworkSkill(), _config(network_access=True))
    assert allowed.network is True
