"""The execution cycle: the one place that knows how a run proceeds.

Every run follows the same order (ADR-008): preview, refuse or ask, act, record. What
differs between runs is what "act" means. `run_action` reads the files an action declares
and asks a provider (ADR-014); `run_conversion` turns a document into text and writes it,
never reaching a provider at all (ADR-016).

The order lives in `_authorize`, which both entry points open with, so the cycle can grow
a second kind of effect without growing a second place that knows the sequence. Callers
describe what they want done; the cycle knows how. Human confirmation is supplied as a
function rather than performed here, so the core never contains interface code.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.audit import AuditLog
from local_ai_control_center.config import Config
from local_ai_control_center.converter import ConversionError, Converter
from local_ai_control_center.permissions import Capability, PermissionDenied, Permissions
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


_CONVERSION_CAPABILITIES: frozenset[Capability] = frozenset({"read_files", "write_files"})
"""What a conversion does, and therefore what its action has to declare.

Reading the document and writing the result are both effects, and the preview checks
only what an action declares. Guarding one and not the other leaves the unguarded effect
outside everything the human was shown before agreeing to it (ADR-016).
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
    A run that produced a file rather than an answer completes with no completion.
    """

    model_config = ConfigDict(frozen=True)

    preview: ExecutionPreview
    outcome: Outcome
    completion: Completion | None = None

    @property
    def executed(self) -> bool:
        """Whether the action actually ran."""
        return self.outcome == "completed"


def _authorize(
    action: IntendedAction,
    permissions: Permissions,
    config: Config,
    workspace: Workspace,
    audit: AuditLog,
    run_id: str,
    confirm: ConfirmationFn,
) -> tuple[ExecutionPreview, RunResult | None]:
    """Run the opening that every kind of run shares, and record what it decides.

    Previews the action; if it would not be allowed, records the refusal and stops
    without asking anyone. Otherwise records the grant and asks ``confirm``; a decline is
    recorded and nothing runs.

    Returns the preview together with the result that ends the run, or ``None`` when the
    run may proceed. Keeping this in one function is what lets the cycle have more than
    one kind of effect without having more than one place that knows the order.
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
        return preview, RunResult(preview=preview, outcome="refused")

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
        return preview, RunResult(preview=preview, outcome="declined")

    return preview, None


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


def _write_new_file(path: Path, text: str) -> None:
    """Write ``text`` to ``path``, refusing to touch a file that is already there.

    Opened for exclusive creation rather than checked first. PRINCIPLES says to attempt
    and translate the failure at a volatile boundary rather than pre-check a state that
    can change, and exclusive creation is also free of the race a check-then-write would
    leave open between them.
    """
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
    except FileExistsError as error:
        raise ConversionError(
            f"{path.name} already exists, and ingestion never overwrites. Move or rename "
            "it, or name a different destination."
        ) from error
    except FileNotFoundError as error:
        raise ConversionError(
            f"Cannot write {path.name}: the folder {path.parent} does not exist."
        ) from error
    except OSError as error:
        raise ConversionError(f"Cannot write {path.name}: {error.strerror or error}.") from error


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
    """Run ``action`` through the whole system, in order, and ask a provider.

    Previews, refuses or asks, and records - then, on approval, reads the declared files
    into ``prompt_template``, calls the provider with the filled prompt, and records the
    result. A file that cannot be read is recorded and raised as :class:`ReadError`.
    """
    preview, stopped = _authorize(action, permissions, config, workspace, audit, run_id, confirm)
    if stopped is not None:
        return stopped

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


def run_conversion(
    action: IntendedAction,
    source: Path,
    destination: Path,
    converter: Converter,
    permissions: Permissions,
    config: Config,
    workspace: Workspace,
    audit: AuditLog,
    run_id: str,
    confirm: ConfirmationFn,
) -> RunResult:
    """Turn ``source`` into text and write it to ``destination``, in the same order.

    The second kind of run: it produces a file rather than an answer, and never reaches a
    provider (ADR-016). Everything before the effects is the sequence every run shares.

    The trail records what was converted and where it went, never the text itself - the
    extracted content is already a file the record names, so repeating it in the audit
    would duplicate the document rather than describe the run. A document that cannot be
    read, a destination that already exists, or a folder that is not there ends the run
    with :class:`ConversionError`, recorded and carrying a message a person can act on.
    """
    preview, stopped = _authorize(action, permissions, config, workspace, audit, run_id, confirm)
    if stopped is not None:
        return stopped

    missing = sorted(_CONVERSION_CAPABILITIES - action.required)
    if missing:
        audit.record(
            run_id,
            "permission_denied",
            f"Refused the effects of {action.name}",
            {"action": action.name, "missing": missing},
        )
        raise PermissionDenied(
            f"{action.name} converts {source} into {destination}, which both reads and "
            f"writes, but the action does not declare {', '.join(missing)}. The preview "
            "checks only the capabilities an action declares, so an effect that was never "
            "declared was never checked - and the human who confirmed the run was never "
            "shown it either."
        )

    resolved_source = workspace.resolve_within(source)
    resolved_destination = workspace.resolve_within(destination)

    try:
        text = converter.extract_text(resolved_source)
        _write_new_file(resolved_destination, text)
    except ConversionError as error:
        audit.record(
            run_id,
            "ingestion_failed",
            f"Could not ingest {resolved_source.name}",
            {"action": action.name, "source": str(resolved_source), "error": str(error)},
        )
        raise

    audit.record(
        run_id,
        "document_converted",
        f"Converted {resolved_source.name} with {converter.name}",
        {
            "action": action.name,
            "converter": converter.name,
            "source": str(resolved_source),
            "destination": str(resolved_destination),
            "characters": len(text),
        },
    )
    audit.record(run_id, "run_finished", f"Finished {action.name}", {"action": action.name})

    return RunResult(preview=preview, outcome="completed")
