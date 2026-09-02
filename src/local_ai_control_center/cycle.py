"""The execution cycle: the one place that knows how a run proceeds.

`run_action` drives an intended action through the whole system in order (ADR-008):
preview, refuse or ask, read, execute, record. Callers describe what they want done;
the cycle knows how. Human confirmation is supplied as a function rather than
performed here, so the core never contains interface code. Reading the action's
declared files is a side effect, so it happens here and only after the human has
confirmed (ADR-014).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
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

CONTENT_PLACEHOLDER = "<<file_content>>"
"""Marker a prompt template leaves for the cycle to replace with file contents.

A skill's plan is pure, so it can only leave the hole; filling it is a side
effect's product and belongs to the cycle (ADR-014). A literal marker is replaced,
not formatted, so braces in a path or a file never break the substitution.
"""


class ReadError(Exception):
    """Raised when a file the action declared cannot be read.

    Carries a message already translated into something a person can act on, the
    same posture `ProviderError` takes: a failure at an external, volatile boundary
    is reported clearly, never surfaced as a raw filesystem error (ADR-014).
    """


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


def _read_file(path: Path) -> str:
    """Return the text of ``path``, translating any failure into a clear message."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ReadError(f"Cannot read {path}: it is not UTF-8 text.") from error
    except OSError as error:
        raise ReadError(f"Cannot read {path}: {error.strerror or error}.") from error


def _fill_template(
    template: str, action: IntendedAction, workspace: Workspace
) -> tuple[str, tuple[Path, ...]]:
    """Return the prompt with the action's file contents in place, and what was read.

    Reads only when the action declared `read_files`: the preview has already checked
    that declaration against the permissions and every target against the workspace
    boundary, so the read trusts what was verified and only translates failures
    (ADR-014). An action that declared no read gets its template back untouched.
    """
    if "read_files" not in action.required or not action.targets:
        return template, ()
    paths = tuple(workspace.resolve_within(target) for target in action.targets)
    contents = "\n\n".join(_read_file(path) for path in paths)
    return template.replace(CONTENT_PLACEHOLDER, contents), paths


def run_action(
    action: IntendedAction,
    prompt_template: str,
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
    nothing runs. On approval, reads the declared files into ``prompt_template``,
    calls the provider with the filled prompt, and records the result. A file that
    cannot be read is recorded and raised as :class:`ReadError`.
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

    try:
        prompt, files_read = _fill_template(prompt_template, action, workspace)
    except ReadError as error:
        audit.record(
            run_id,
            "read_failed",
            f"Could not read for {action.name}",
            {"action": action.name, "error": str(error)},
        )
        raise

    if files_read:
        audit.record(
            run_id,
            "files_read",
            f"Read targets for {action.name}",
            {"action": action.name, "files": [str(path) for path in files_read]},
        )

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
