"""Execution preview: describing an intended action before it runs.

A preview answers "what would happen, and would it be allowed?" without doing
anything (ADR-007). It knows nothing about skills: it takes an `IntendedAction`
that describes itself, so anything describable this way can be previewed. Building
a preview has no side effects.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from local_ai_control_center.config import Config
from local_ai_control_center.permissions import Capability, Permissions, check
from local_ai_control_center.workspace import Workspace


class IntendedAction(BaseModel):
    """A description of something about to happen.

    Produced by whatever is driving the run - a skill, a chain, a command-line
    action. The preview module only needs the action to describe itself.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Short identifier of the action.")
    summary: str = Field(description="Human-readable description of what it does.")
    required: frozenset[Capability] = Field(
        default_factory=frozenset,
        description="Capabilities the action needs to run.",
    )
    targets: tuple[Path, ...] = Field(
        default=(),
        description="Paths the action intends to touch, if any.",
    )


class ExecutionPreview(BaseModel):
    """The result of previewing an action: what would happen, and whether it may.

    Frozen and side-effect free. Reports every reason a run would be refused, not
    just the first, so a person deciding whether to proceed sees the whole picture.
    """

    model_config = ConfigDict(frozen=True)

    action: IntendedAction
    allowed: bool
    missing_capabilities: tuple[Capability, ...] = ()
    out_of_bounds: tuple[Path, ...] = ()

    def render(self) -> str:
        """Return a short readable block intended to be shown before confirming."""
        lines = [
            f"Action:  {self.action.name}",
            f"Summary: {self.action.summary}",
        ]
        if self.action.required:
            lines.append(f"Requires: {', '.join(sorted(self.action.required))}")
        if self.action.targets:
            lines.append(f"Targets: {', '.join(str(path) for path in self.action.targets)}")
        if self.allowed:
            lines.append("Status:  would run")
        else:
            lines.append("Status:  would be refused")
            if self.missing_capabilities:
                lines.append(f"  Missing capabilities: {', '.join(self.missing_capabilities)}")
            if self.out_of_bounds:
                outside = ", ".join(str(path) for path in self.out_of_bounds)
                lines.append(f"  Outside the workspace: {outside}")
        return "\n".join(lines)


def preview_action(
    action: IntendedAction,
    permissions: Permissions,
    config: Config,
    workspace: Workspace,
) -> ExecutionPreview:
    """Report whether ``action`` would be allowed, and why not.

    Has no side effects: nothing is written, no provider is called, nothing is
    created. Both kinds of refusal - missing capabilities and paths escaping the
    workspace - are reported together.
    """
    permission_result = check(action.required, permissions, config)
    out_of_bounds = tuple(target for target in action.targets if not workspace.is_within(target))
    return ExecutionPreview(
        action=action,
        allowed=permission_result.allowed and not out_of_bounds,
        missing_capabilities=permission_result.missing,
        out_of_bounds=out_of_bounds,
    )
