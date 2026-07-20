"""The execution cycle: the one place that knows how a run proceeds.

`run_action` drives an intended action through the whole system in order (ADR-008):
preview, refuse or ask, execute, record. Callers describe what they want done; the
cycle knows how. Human confirmation is supplied as a function rather than performed
here, so the core never contains interface code.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.audit import AuditLog
from local_ai_control_center.config import Config
from local_ai_control_center.permissions import Permissions
from local_ai_control_center.preview import (
    ExecutionPreview,
    IntendedAction,
    preview_action,
)
from local_ai_control_center.provider import Completion, Provider
from local_ai_control_center.workspace import Workspace

Outcome = Literal["completed", "refused", "declined"]
"""How a run ended: it ran, it was not allowed, or the human said no."""

ConfirmationFn = Callable[[ExecutionPreview], bool]
"""Given a preview, decide whether to proceed. Supplied by the caller."""


class RunResult(BaseModel):
    """What happened during a run.

    Distinguishes "it ran and here is the answer" from "it was not allowed" and
    "the user declined", so a caller need not inspect exceptions to tell them apart.
    """

    model_config = ConfigDict(frozen=True)

    preview: ExecutionPreview
    outcome: Outcome
    completion: Completion | None = None

    @property
    def executed(self) -> bool:
        """Whether the action actually ran."""
        return self.outcome == "completed"


def run_action(
    action: IntendedAction,
    prompt: str,
    permissions: Permissions,
    config: Config,
    workspace: Workspace,
    provider: Provider,
    audit: AuditLog,
    run_id: str,
    confirm: ConfirmationFn,
) -> RunResult:
    """Run ``action`` through the whole system, in order.

    Previews the action; if it would not be allowed, records the refusal and stops
    without asking anyone. Otherwise asks ``confirm``; a decline is recorded and
    nothing runs. On approval, calls the provider and records the result.
    """
    audit.record(run_id, "run_started", f"Starting {action.name}", {"action": action.name})

    preview = preview_action(action, permissions, config, workspace)

    if not preview.allowed:
        audit.record(
            run_id,
            "run_refused",
            f"Refused {action.name}",
            {
                "action": action.name,
                "missing": list(preview.missing_capabilities),
                "out_of_bounds": [str(path) for path in preview.out_of_bounds],
            },
        )
        return RunResult(preview=preview, outcome="refused")

    audit.record(
        run_id,
        "permission_granted",
        f"Permitted {action.name}",
        {"action": action.name, "required": sorted(action.required)},
    )

    if not confirm(preview):
        audit.record(
            run_id,
            "confirmation_declined",
            f"Declined {action.name}",
            {"action": action.name},
        )
        return RunResult(preview=preview, outcome="declined")

    completion = provider.complete(prompt)

    audit.record(
        run_id,
        "provider_called",
        f"Called {completion.provider} for {action.name}",
        {
            "action": action.name,
            "provider": completion.provider,
            "prompt": prompt,
            "completion": completion.text,
        },
    )
    audit.record(run_id, "run_finished", f"Finished {action.name}", {"action": action.name})

    return RunResult(preview=preview, outcome="completed", completion=completion)
