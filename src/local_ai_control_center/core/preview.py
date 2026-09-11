"""Execution preview: describing an intended action before it runs.

A preview answers "what would happen, and would it be allowed?" without doing
anything (ADR-007). It knows nothing about skills: it takes an `IntendedAction`
that describes itself, so anything describable this way can be previewed. Building
a preview has no side effects.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from local_ai_control_center.core.config import Config
from local_ai_control_center.core.permissions import Capability, Permissions, check
from local_ai_control_center.core.workspace import Workspace


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
        description="Paths the action intends to read, if any.",
    )
    writes: tuple[Path, ...] = Field(
        default=(),
        description=(
            "Paths the action intends to write, if any. Separate from targets because "
            "the two are not interchangeable: everything here is checked against the "
            "boundary and shown before confirming, and none of it is read - a file "
            "about to be created cannot be."
        ),
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
    sends_to: str = ""
    """Where the contents read would be sent, when that is not this machine.

    Empty for a run that contacts nothing, or an engine on this machine. Absence carries
    meaning here: no destination shown means nothing leaves the computer (ADR-028).
    """

    def render(self) -> str:
        """Return a short readable block intended to be shown before confirming."""
        lines = [
            f"Action:  {self.action.name}",
            f"Summary: {self.action.summary}",
        ]
        if self.action.required:
            lines.append(f"Requires: {', '.join(sorted(self.action.required))}")
        if self.action.targets:
            lines.append(f"Reads:   {', '.join(str(path) for path in self.action.targets)}")
        if self.action.writes:
            lines.append(f"Writes:  {', '.join(str(path) for path in self.action.writes)}")
        if self.sends_to:
            lines.append(f"Sends:   the contents read above, to {self.sends_to}")
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
    sends_to: str = "",
) -> ExecutionPreview:
    """Report whether ``action`` would be allowed, and why not.

    Has no side effects: nothing is written, no provider is called, nothing is
    created. Both kinds of refusal - missing capabilities and paths escaping the
    workspace - are reported together.

    ``sends_to`` is passed by the caller rather than derived here, because whether a run
    contacts an engine at all is something only the caller knows: converting a document
    never does. Inferring it from the action's capabilities would be a guess, and it would
    be wrong (ADR-028).
    """
    permission_result = check(action.required, permissions, config)
    touched = action.targets + action.writes
    out_of_bounds = tuple(path for path in touched if not workspace.is_within(path))
    return ExecutionPreview(
        action=action,
        allowed=permission_result.allowed and not out_of_bounds,
        missing_capabilities=permission_result.missing,
        out_of_bounds=out_of_bounds,
        sends_to=sends_to,
    )
