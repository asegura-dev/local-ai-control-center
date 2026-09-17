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

import contextlib
import difflib
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.budget import answer_reserve, estimate_tokens
from local_ai_control_center.core.config import Config
from local_ai_control_center.core.fence import (
    CONTEXT_SLOT,
    content_slot,
    instruction_shapes_in,
    without_markers,
)
from local_ai_control_center.core.grounding import (
    CheckedClaim,
    check_answer,
    without_repeats,
)
from local_ai_control_center.core.passes import PageRangeError, only_pages, passes_over
from local_ai_control_center.core.permissions import Capability, PermissionDenied, Permissions
from local_ai_control_center.core.preview import ExecutionPreview, IntendedAction, preview_action
from local_ai_control_center.core.run import Progress, ProgressFn
from local_ai_control_center.core.skill import Skill
from local_ai_control_center.core.workspace import Workspace
from local_ai_control_center.ports.converter import ConversionError, Converter
from local_ai_control_center.ports.provider import Completion, Provider
from local_ai_control_center.system.audit import AuditLog, digest_of, digest_of_file

Outcome = Literal["completed", "refused", "declined"]
"""How a run ended: it ran, it was not allowed, or the human said no."""

ConfirmationFn = Callable[[ExecutionPreview], bool]
"""Given a preview, decide whether to proceed. Supplied by the caller."""

ApprovalFn = Callable[[str], bool]
"""Given a diff, decide whether the result is worth keeping on disk (ADR-025)."""


_CONVERSION_CAPABILITIES: frozenset[Capability] = frozenset({"read_files", "write_files"})
"""What a conversion does, and therefore what its action has to declare.

Reading the document and writing the result are both effects, and the preview checks
only what an action declares. Guarding one and not the other leaves the unguarded effect
outside everything the human was shown before agreeing to it (ADR-016).
"""


_TOO_LARGE = (
    "{name} is {size:,} bytes, over the {limit:,}-byte ceiling set by max_input_bytes. "
    "LACC reads a document into memory whole, so this ceiling is about the machine, not "
    "about the model. Raise max_input_bytes if the file really is meant to be read."
)


def _oversize(path: Path, limit: int) -> str | None:
    """Return a message if ``path`` is over ``limit``, or ``None`` if it is not.

    A message rather than an exception, because the two entry points translate the same
    fact into different errors. A path that cannot be measured returns ``None``: the read
    or the conversion that follows reports why far better than a guess here would
    (ADR-017).
    """
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size <= limit:
        return None
    return _TOO_LARGE.format(name=path.name, size=size, limit=limit)


WINDOW_TOLERANCE = 8
"""How close the engine's prompt count may come to the window before LACC calls it clipped.

A tolerance around an equality, not a factor scaling a quantity: the engine measured stops
exactly one token short of the window when it truncates, and a few tokens of slack covers
engines that reserve differently. Being wrong here costs a warning about a prompt that
filled the window exactly, which is worth saying anyway (ADR-024).
"""

_PROMPT_TOO_LARGE = (
    "The prompt is an estimated {estimate:,} tokens, over the {budget:,} available: the "
    "context window is {window:,} tokens and {reserve:,} are held back for the answer. "
    "Nothing was sent, because an engine given more than fits does not fail - it drops "
    "what does not fit and answers from the rest. Read it in passes with --in-passes, "
    "which divides it on page boundaries and still checks every quotation against the "
    "whole document. Or use a shorter document, or raise context_tokens if the model "
    "and this machine can hold more."
)


class PromptTooLargeError(Exception):
    """Raised when a prompt would not fit the configured context window.

    Refused rather than trimmed. Truncating is what this exists to prevent, and doing it
    in LACC rather than in the engine would only move the dishonesty closer to home.
    """


class CannotReadInPasses(Exception):
    """Raised when a document cannot be divided into readings that fit.

    Two causes, both worth distinguishing from "it did not fit": no configured window to
    divide against, and no page markers to divide on. Anything LACC did not ingest has no
    pages, and inventing a boundary mid-sentence would cut the quotations this project
    exists to find (ADR-045).
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
    checked_claims: tuple[CheckedClaim, ...] = ()
    """Quotations found in the answer, and whether each one appears in the source.

    Empty unless the skill asked for its output to be checked (ADR-026).
    """

    markers_removed: int = 0
    """Fence markers taken out of the document before it entered the prompt (ADR-038)."""

    passes: int = 1
    """How many readings the document was divided into to fit the window.

    One means it was read whole. More means the model never held all of it at once, and a
    reader who does not know that will assume it did (ADR-045).
    """

    instruction_shapes: tuple[str, ...] = ()
    """Ways the document read like an instruction rather than like a document.

    Carried out to the caller so it can be shown beside the answer, which is when a person
    is deciding whether to trust it. Detection only: a model can obey something no pattern
    catches (ADR-038).
    """

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
    sends_to: str = "",
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

    preview = preview_action(action, permissions, config, workspace, sends_to)

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


def _read_file(path: Path, max_bytes: int) -> str:
    """Return the text of ``path``, translating any failure into a clear message."""
    oversize = _oversize(path, max_bytes)
    if oversize is not None:
        raise ReadError(oversize)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ReadError(f"Cannot read {path}: it is not UTF-8 text.") from error
    except OSError as error:
        raise ReadError(f"Cannot read {path}: {error.strerror or error}.") from error


class ContentsRead(BaseModel):
    """What the cycle read, and what it noticed while reading it."""

    model_config = ConfigDict(frozen=True)

    prompt: str
    paths: tuple[Path, ...] = ()
    contents: str = ""
    markers_removed: int = 0
    """Fence markers found inside a document and taken out before it entered the prompt.

    A document carrying one could end its own fence, after which the rest of it read to
    the model as LACC's instructions. Removing them is the one control here rather than a
    request; the count is kept because it is worth telling someone about (ADR-038).
    """

    instruction_shapes: tuple[str, ...] = ()
    """Ways the document read like an instruction. Detection only - a model can obey
    something no pattern catches, and treating this as prevention would repeat the claim
    ADR-038 exists to correct."""


def _fill_template(
    template: str, action: IntendedAction, workspace: Workspace, max_bytes: int
) -> ContentsRead:
    """Return the prompt with the action's file contents in place, and what was read.

    Reads only when the action declared `read_files`: the preview has already checked
    that declaration against the permissions and every target against the workspace
    boundary, so the read trusts what was verified and only translates failures
    (ADR-014). An action that declared no read gets its template back untouched.

    Fence markers are removed from what was read before it goes anywhere near the prompt.
    That is the order that matters: a document cannot end its own fence if the string that
    would do it is gone by the time the fence is assembled (ADR-038).
    """
    if "read_files" not in action.required or not action.targets:
        return ContentsRead(prompt=template)
    paths = tuple(workspace.resolve_within(target) for target in action.targets)
    raw = [_read_file(path, max_bytes) for path in paths]

    pieces, removed = [], 0
    for piece in raw:
        cleaned, count = without_markers(piece)
        pieces.append(cleaned)
        removed += count

    filled = template
    for index, piece in enumerate(pieces):
        filled = filled.replace(content_slot(index), piece)
    contents = chr(10).join(pieces)
    return ContentsRead(
        prompt=filled,
        paths=paths,
        contents=contents,
        markers_removed=removed,
        instruction_shapes=instruction_shapes_in(contents),
    )


def diff_between(before: str, after: str, after_name: str) -> str:
    """Return a unified diff of ``before`` and ``after``.

    Pure computation on two strings. No version control system is involved and none is
    needed: a diff is a comparison, not a history (ADR-025).
    """
    lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile="before",
        tofile=after_name,
        lineterm="",
    )
    return chr(10).join(lines)


def write_new_file(path: Path, text: str) -> None:
    """Write ``text`` to ``path``, refusing to touch a file that is already there.

    Public because collecting writes its own file outside the cycle, and nothing LACC
    writes should reach disk by a route that does not refuse an existing file (ADR-039).

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


def _standing_context(config: Config, workspace: Workspace) -> tuple[str, bool]:
    """Read the file the configuration names, or report that there was none.

    An absent file is not an error: a project without standing context is the ordinary
    case, and a missing one should not stop work. Read through the workspace boundary like
    anything else, and the markers are stripped from it for the same reason they are
    stripped from a document (ADR-038, ADR-041).
    """
    named = config.context_file.strip()
    if not named:
        return "", False
    try:
        text = workspace.resolve_within(Path(named)).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return "", False
    cleaned, _ = without_markers(text)
    return cleaned.strip(), bool(cleaned.strip())


def _prepare(
    prompt_template: str,
    action: IntendedAction,
    config: Config,
    workspace: Workspace,
    audit: AuditLog,
    run_id: str,
    uses_context: bool,
) -> tuple[ContentsRead, str]:
    """Read what the action points at, assemble the prompt, and record what was noticed.

    Everything between being allowed to run and having something to send. Shared by a
    run and a run in passes, so that reading a document in seventeen readings notices
    the same things about it as reading it in one.
    """
    try:
        read = _fill_template(prompt_template, action, workspace, config.max_input_bytes)
    except ReadError as error:
        audit.record(
            run_id,
            "read_failed",
            f"Could not read for {action.name}",
            {"action": action.name, "error": str(error)},
        )
        raise

    prompt, files_read = read.prompt, read.paths

    # Only when the plan asked for it. A file that reached every prompt because it exists
    # would be the failure ADR-041 exists to prevent, applied by accident.
    context, had_context = _standing_context(config, workspace) if uses_context else ("", False)
    prompt = prompt.replace(CONTEXT_SLOT, context)
    if had_context:
        audit.record(
            run_id,
            "standing_context_used",
            f"{action.name} was given the standing context",
            {"action": action.name, "file": config.context_file},
        )

    # Recorded whether or not anything was found, because "nothing was found" is the claim
    # a reader of the trail needs, and an absent field cannot make it (ADR-038).
    if read.markers_removed:
        audit.record(
            run_id,
            "fence_markers_removed",
            f"Removed {read.markers_removed} fence markers from what {action.name} read",
            {"action": action.name, "markers": read.markers_removed},
        )
    if read.instruction_shapes:
        audit.record(
            run_id,
            "instruction_shapes_seen",
            f"The document read for {action.name} contains text shaped like an instruction",
            {"action": action.name, "shapes": list(read.instruction_shapes)},
        )

    if files_read:
        audit.record(
            run_id,
            "files_read",
            f"Read targets for {action.name}",
            {
                "action": action.name,
                "files": [
                    {"path": str(path), "sha256": digest_of_file(path)} for path in files_read
                ],
            },
        )

    return read, prompt


def _ask(
    prompt: str,
    action: IntendedAction,
    config: Config,
    provider: Provider,
    audit: AuditLog,
    run_id: str,
    temperature: float,
) -> Completion:
    """Measure a prompt, refuse it if it will not fit, send it, and record all three.

    The one place a prompt reaches an engine. A run that reads a document in passes calls
    it once per pass, and each pass is measured and refused on its own terms - which is how
    a page too large to fit is caught rather than quietly truncated (ADR-045).
    """
    estimate = estimate_tokens(prompt)
    audit.record(
        run_id,
        "prompt_measured",
        f"Prompt for {action.name} is an estimated {estimate} tokens",
        {
            "action": action.name,
            "estimated_tokens": estimate,
            "requested_window": config.context_tokens,
        },
    )

    if config.context_tokens is not None:
        reserve = answer_reserve(config.context_tokens)
        budget = config.context_tokens - reserve
        if estimate > budget:
            message = _PROMPT_TOO_LARGE.format(
                estimate=estimate,
                budget=budget,
                window=config.context_tokens,
                reserve=reserve,
            )
            audit.record(
                run_id,
                "prompt_too_large",
                f"Refused to send an oversized prompt for {action.name}",
                {"action": action.name, "estimated_tokens": estimate, "budget": budget},
            )
            raise PromptTooLargeError(message)

    completion = provider.complete(prompt, temperature)

    audit.record(
        run_id,
        "provider_called",
        f"Called {completion.provider} for {action.name}",
        {
            "action": action.name,
            "provider": completion.provider,
            "estimated_tokens": estimate,
            "temperature": temperature,
            "prompt_sha256": digest_of(prompt),
            "completion_sha256": digest_of(completion.text),
            "measured_prompt_tokens": completion.prompt_tokens,
            "measured_answer_tokens": completion.answer_tokens,
            "finish_reason": completion.finish_reason,
            "prompt": prompt,
            "completion": completion.text,
        },
    )
    _record_what_the_engine_reported(completion, estimate, action, config, audit, run_id)
    return completion


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
    destination: Path | None = None,
    approve: ApprovalFn | None = None,
    verify_quotes: bool = False,
    temperature: float = 0.0,
    uses_context: bool = False,
    fields: tuple[str, ...] = ("claim", "quote", "page"),
    quote_field: str = "quote",
) -> RunResult:
    """Run ``action`` through the whole system, in order, and ask a provider.

    Previews, refuses or asks, and records - then, on approval, reads the declared files
    into ``prompt_template``, calls the provider with the filled prompt, and records the
    result. A file that cannot be read is recorded and raised as :class:`ReadError`.
    """
    preview, stopped = _authorize(
        action, permissions, config, workspace, audit, run_id, confirm, config.remote_engine
    )
    if stopped is not None:
        return stopped

    read, prompt = _prepare(prompt_template, action, config, workspace, audit, run_id, uses_context)

    completion = _ask(prompt, action, config, provider, audit, run_id, temperature)
    audit.record(run_id, "run_finished", f"Finished {action.name}", {"action": action.name})

    checked: tuple[CheckedClaim, ...] = ()
    if verify_quotes:
        checked = check_answer(completion.text, read.contents, fields, quote_field)
        held = sum(1 for claim in checked if claim.holds)
        # How often the model misplaced a passage it quoted correctly. It is not shown to
        # the reader, who wants the right page rather than a note about someone else's
        # error - but it measures a model's fidelity, and that belongs here (ADR-031).
        misplaced = sum(1 for claim in checked if claim.page_disagreed)
        audit.record(
            run_id,
            "quotations_checked",
            f"Checked {len(checked)} quotations for {action.name}",
            {
                "action": action.name,
                "quotations": len(checked),
                "verified": held,
                "found_but_unplaced": sum(1 for c in checked if c.found and not c.holds),
                "not_in_the_document": sum(1 for c in checked if not c.found),
                "pages_the_model_got_wrong": misplaced,
            },
        )

    if destination is not None:
        _offer_the_answer(
            completion.text, read.contents, destination, action, workspace, audit, run_id, approve
        )

    return RunResult(
        preview=preview,
        outcome="completed",
        completion=completion,
        checked_claims=checked,
        markers_removed=read.markers_removed,
        instruction_shapes=read.instruction_shapes,
    )


def _offer_the_answer(
    answer: str,
    before: str,
    destination: Path,
    action: IntendedAction,
    workspace: Workspace,
    audit: AuditLog,
    run_id: str,
    approve: ApprovalFn | None,
) -> None:
    """Show what the answer would change, and write it beside the original if approved.

    Never over it (ADR-025). Replacing the original would make the judgement irreversible
    at the moment it is made; writing beside it makes the same judgement reversible by
    doing nothing.
    """
    if "write_files" not in action.required:
        audit.record(
            run_id,
            "permission_denied",
            f"Refused to write for {action.name}",
            {"action": action.name, "missing": ["write_files"]},
        )
        raise PermissionDenied(
            f"{action.name} would write {destination} without declaring write_files."
        )

    resolved = workspace.resolve_within(destination)
    if approve is not None and not approve(diff_between(before, answer, resolved.name)):
        audit.record(
            run_id,
            "revision_declined",
            f"Declined the revision for {action.name}",
            {"action": action.name, "destination": str(resolved)},
        )
        return

    write_new_file(resolved, answer)
    audit.record(
        run_id,
        "revision_written",
        f"Wrote the revision for {action.name}",
        {
            "action": action.name,
            "destination": str(resolved),
            "destination_sha256": digest_of_file(resolved),
            "characters": len(answer),
        },
    )


def _record_what_the_engine_reported(
    completion: Completion,
    estimate: int,
    action: IntendedAction,
    config: Config,
    audit: AuditLog,
    run_id: str,
) -> None:
    """Record the two ways the engine can tell us the answer is not what it looks like.

    Both arrive after the prompt was sent, so neither can gate anything (ADR-020). They
    are recorded, and the caller reports them, because an answer built on a truncated
    document and an answer that stopped mid-thought both look exactly like answers.
    """
    if completion.prompt_tokens is not None and config.context_tokens is not None:
        window = config.context_tokens
        budget = window - answer_reserve(window)
        if completion.prompt_tokens >= window - WINDOW_TOLERANCE:
            audit.record(
                run_id,
                "prompt_was_truncated",
                f"The engine did not read all of the prompt for {action.name}",
                {
                    "action": action.name,
                    "estimated_tokens": estimate,
                    "measured_prompt_tokens": completion.prompt_tokens,
                    "window": window,
                },
            )
        elif completion.prompt_tokens > budget:
            audit.record(
                run_id,
                "ceiling_underestimated",
                f"The prompt for {action.name} was larger than estimated",
                {
                    "action": action.name,
                    "estimated_tokens": estimate,
                    "measured_prompt_tokens": completion.prompt_tokens,
                    "budget": budget,
                },
            )

    if completion.finish_reason == "length":
        audit.record(
            run_id,
            "answer_truncated",
            f"The answer for {action.name} stopped for want of room",
            {"action": action.name, "answer_tokens": completion.answer_tokens},
        )


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
    pages: tuple[int, int] | None = None,
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

    oversize = _oversize(resolved_source, config.max_input_bytes)
    if oversize is not None:
        audit.record(
            run_id,
            "ingestion_failed",
            f"Could not ingest {resolved_source.name}",
            {"action": action.name, "source": str(resolved_source), "error": oversize},
        )
        raise ConversionError(oversize)

    try:
        text = converter.extract_text(resolved_source)
        if pages is not None:
            # After extraction rather than during it: the port has no notion of pages,
            # because a Word document has none, and the markers carry the document's own
            # numbering so a chapter taken from page 40 still cites as page 40 (ADR-046).
            text = only_pages(text, *pages)
        write_new_file(resolved_destination, text)
    except (ConversionError, PageRangeError) as error:
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
            "source_sha256": digest_of_file(resolved_source),
            "destination": str(resolved_destination),
            "destination_sha256": digest_of_file(resolved_destination),
            "characters": len(text),
            "pages_taken": list(pages) if pages else None,
            # Ingestion now edits rather than only transcribing, so what it removed is
            # recorded. An extraction that dropped an implausible amount should be visible
            # afterwards, not only at the time (ADR-036).
            "furniture_dropped": getattr(converter, "furniture_dropped", 0),
        },
    )
    audit.record(run_id, "run_finished", f"Finished {action.name}", {"action": action.name})

    return RunResult(preview=preview, outcome="completed")


def _tell(progress: ProgressFn | None, where: Progress) -> None:
    """Report where a run has got to, if anybody asked to be told.

    Swallows whatever the listener raises. A watcher that fails is a watcher's problem, and
    a run that got half way through a document must not be lost to a broken progress bar.
    """
    if progress is None:
        return
    # The run matters; the report does not. A watcher that raises is a watcher's problem.
    with contextlib.suppress(Exception):
        progress(where)


def run_in_passes(
    action: IntendedAction,
    prompt_template: str,
    permissions: Permissions,
    config: Config,
    workspace: Workspace,
    provider: Provider,
    audit: AuditLog,
    run_id: str,
    confirm: ConfirmationFn,
    verify_quotes: bool = False,
    temperature: float = 0.0,
    uses_context: bool = False,
    pages_per_pass: int | None = None,
    progress: ProgressFn | None = None,
    fields: tuple[str, ...] = ("claim", "quote", "page"),
    quote_field: str = "quote",
) -> RunResult:
    """Read one document in as many passes as the window needs, and answer from all of them.

    The same run as :func:`run_action` up to the point of asking, then asking once per pass.
    What comes back is the readings joined, and **every quotation is checked against the
    whole document** rather than against the pass that produced it - the line ADR-045 draws,
    and the reason v1.0's promise survives being divided.

    One target only. Reading several documents in passes at once is a different question,
    and guessing at it here would put one document's pages into another's prompt.
    """
    if len(action.targets) != 1:
        raise CannotReadInPasses(
            f"{action.name} points at {len(action.targets)} documents. A run in passes reads one."
        )
    if config.context_tokens is None:
        raise CannotReadInPasses(
            "No context window is configured, so there is nothing to divide against. "
            "Set context_tokens to the window the model actually has."
        )

    preview, stopped = _authorize(
        action, permissions, config, workspace, audit, run_id, confirm, config.remote_engine
    )
    if stopped is not None:
        return stopped

    read, prompt = _prepare(prompt_template, action, config, workspace, audit, run_id, uses_context)
    if not read.contents or read.contents not in prompt:
        raise CannotReadInPasses(f"{action.name} read nothing that could be divided.")

    # What the skill wraps around the document has to come out of the budget: the wrapper
    # is sent with every pass, so a pass sized against the raw window would overflow by it.
    around = estimate_tokens(prompt) - estimate_tokens(read.contents)
    budget = config.context_tokens - answer_reserve(config.context_tokens) - around
    readings = passes_over(read.contents, budget, pages_per_pass)
    if not readings:
        raise CannotReadInPasses(
            f"{action.name} points at a document with no page markers, so there is no "
            "honest place to divide it. Ingest it with lacc ingest, which preserves them."
        )

    audit.record(
        run_id,
        "read_in_passes",
        f"Divided the document for {action.name} into {len(readings)} readings",
        {
            "action": action.name,
            "passes": len(readings),
            "pages": [[r.first_page, r.last_page] for r in readings],
            "budget_tokens": budget,
            "pages_per_pass": pages_per_pass,
        },
    )

    _tell(
        progress,
        Progress(
            stage="dividing",
            total=len(readings),
            detail=f"{len(readings)} readings over pages "
            f"{readings[0].first_page} to {readings[-1].last_page}",
        ),
    )

    answers: list[str] = []
    asked = 0
    for number, reading in enumerate(readings, start=1):
        _tell(
            progress,
            Progress(
                stage="asking",
                done=number - 1,
                total=len(readings),
                detail=f"pages {reading.first_page} to {reading.last_page}",
            ),
        )
        completion = _ask(
            prompt.replace(read.contents, reading.text, 1),
            action,
            config,
            provider,
            audit,
            run_id,
            temperature,
        )
        answers.append(completion.text)
        asked += completion.answer_tokens or 0

    joined = Completion(
        text=(chr(10) * 2).join(answers),
        provider=f"{provider.name} x{len(readings)}",
        answer_tokens=asked or None,
        finish_reason="stop",
    )
    audit.record(run_id, "run_finished", f"Finished {action.name}", {"action": action.name})

    checked: tuple[CheckedClaim, ...] = ()
    if verify_quotes:
        _tell(progress, Progress(stage="checking", detail="looking for every quotation"))
        checked = without_repeats(check_answer(joined.text, read.contents, fields, quote_field))
        audit.record(
            run_id,
            "quotations_checked",
            f"Checked {len(checked)} quotations for {action.name}",
            {
                "action": action.name,
                "quotations": len(checked),
                "verified": sum(1 for c in checked if c.holds),
                "found_but_unplaced": sum(1 for c in checked if c.found and not c.holds),
                "not_in_the_document": sum(1 for c in checked if not c.found),
                "pages_the_model_got_wrong": sum(1 for c in checked if c.page_disagreed),
                "passes": len(readings),
            },
        )

    return RunResult(
        preview=preview,
        outcome="completed",
        completion=joined,
        checked_claims=checked,
        markers_removed=read.markers_removed,
        instruction_shapes=read.instruction_shapes,
        passes=len(readings),
    )


def run_skill(
    skill: Skill,
    requests: tuple[str, ...],
    permissions: Permissions,
    config: Config,
    workspace: Workspace,
    provider: Provider,
    audit: AuditLog,
    run_id: str,
    confirm: ConfirmationFn,
    approve: ApprovalFn | None = None,
    in_passes: bool = False,
    pages_per_pass: int | None = None,
    progress: ProgressFn | None = None,
) -> RunResult:
    """Plan the skill, then run its plan through the execution cycle.

    Wires a skill to the cycle so callers do not repeat the wiring. The skill only
    describes; the cycle previews, checks, confirms, executes, and records.

    ``in_passes`` divides a document too large for the window into readings that fit. It is
    asked for rather than substituted: a document of 355,000 tokens becomes ninety calls and
    the better part of a day, which is not a thing to start on someone's behalf (ADR-045).
    """
    plan = skill.plan(requests, config)
    if in_passes or pages_per_pass is not None:
        if plan.destination is not None:
            raise CannotReadInPasses(
                f"{plan.action.name} writes a file, and an answer assembled from several "
                "readings is not a revision of anything. Run it whole."
            )
        return run_in_passes(
            plan.action,
            plan.prompt_template,
            permissions,
            config,
            workspace,
            provider,
            audit,
            run_id,
            confirm,
            plan.verify_quotes,
            plan.temperature,
            plan.uses_context,
            pages_per_pass,
            progress,
            plan.fields,
            plan.quote_field,
        )
    return run_action(
        plan.action,
        plan.prompt_template,
        permissions,
        config,
        workspace,
        provider,
        audit,
        run_id,
        confirm,
        plan.destination,
        approve,
        plan.verify_quotes,
        plan.temperature,
        plan.uses_context,
        plan.fields,
        plan.quote_field,
    )
