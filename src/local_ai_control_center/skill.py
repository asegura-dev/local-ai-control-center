"""Skills: named units of work that produce actions for the cycle to run.

A `Skill` mirrors the provider port (ADR-009): an abstract contract with concrete
implementations. A skill declares its name and required capabilities and implements
`plan`, which turns a request into an action and a prompt without doing anything.
Running a skill hands its plan to the execution cycle, which owns side effects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.audit import AuditLog
from local_ai_control_center.config import Config
from local_ai_control_center.cycle import ConfirmationFn, RunResult, run_action
from local_ai_control_center.permissions import Capability, Permissions
from local_ai_control_center.preview import IntendedAction
from local_ai_control_center.provider import Provider
from local_ai_control_center.workspace import Workspace


class SkillPlan(BaseModel):
    """What a skill intends to do: an action to preview, and a prompt to send.

    Frozen and side-effect free. Produced by `plan`; consumed by the cycle.
    """

    model_config = ConfigDict(frozen=True)

    action: IntendedAction
    prompt: str


class Skill(ABC):
    """Abstract unit of work. Concrete skills declare needs and describe intent."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier of the skill."""

    @property
    @abstractmethod
    def required(self) -> frozenset[Capability]:
        """Capabilities the skill needs to run."""

    @abstractmethod
    def plan(self, request: str) -> SkillPlan:
        """Turn a request into a plan. Pure: reads nothing, calls nothing."""


class SummarizeFileSkill(Skill):
    """Summarize a file inside the workspace. Read-only: one capability, one target.

    Describes reading and summarizing a file; the actual read happens where side
    effects belong, not in `plan`.
    """

    @property
    def name(self) -> str:
        """Identify this skill."""
        return "summarize_file"

    @property
    def required(self) -> frozenset[Capability]:
        """Summarizing a file needs to read it, nothing more."""
        return frozenset({"read_files"})

    def plan(self, request: str) -> SkillPlan:
        """Plan to summarize the file at ``request`` (a path inside the workspace)."""
        action = IntendedAction(
            name=self.name,
            summary=f"Summarize the file at {request}",
            required=self.required,
            targets=(Path(request),),
        )
        prompt = f"Summarize the contents of the file at {request}."
        return SkillPlan(action=action, prompt=prompt)


def run_skill(
    skill: Skill,
    request: str,
    permissions: Permissions,
    config: Config,
    workspace: Workspace,
    provider: Provider,
    audit: AuditLog,
    run_id: str,
    confirm: ConfirmationFn,
) -> RunResult:
    """Plan the skill, then run its plan through the execution cycle.

    Wires a skill to the cycle so callers do not repeat the wiring. The skill only
    describes; the cycle previews, checks, confirms, executes, and records.
    """
    plan = skill.plan(request)
    return run_action(
        plan.action,
        plan.prompt,
        permissions,
        config,
        workspace,
        provider,
        audit,
        run_id,
        confirm,
    )
