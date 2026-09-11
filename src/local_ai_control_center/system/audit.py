"""Audit: an append-only record of what LACC did.

Records are JSON Lines inside the workspace, resolved through the workspace
boundary (ADR-006). Detail follows the configured `audit_level`: metadata always,
prompt and completion content only under `full`. When a record cannot be written,
`audit_failure_policy` decides whether execution stops or proceeds unrecorded.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from local_ai_control_center.core.config import Config
from local_ai_control_center.core.workspace import Workspace

EventKind = Literal[
    "run_started",
    "run_finished",
    "run_refused",
    "confirmation_declined",
    "permission_granted",
    "permission_denied",
    "files_read",
    "document_converted",
    "revision_written",
    "revision_declined",
    "ingestion_failed",
    "read_failed",
    "prompt_measured",
    "prompt_too_large",
    "provider_called",
    "quotations_checked",
    "prompt_was_truncated",
    "ceiling_underestimated",
    "answer_truncated",
    "fence_markers_removed",
    "instruction_shapes_seen",
    "standing_context_used",
    "notification_sent",
    "notification_failed",
]
"""The closed set of events recorded today. It grows as real events appear."""

GENESIS_DIGEST = "0" * 64
"""What the first record folds in, since there is no record before it."""


def digest_of(text: str) -> str:
    """Return the SHA-256 of ``text``, as hex.

    A digest identifies without exposing: it cannot be read back into the thing it
    describes, and it is exactly enough to say whether two things are the same one
    (ADR-023).
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_of_file(path: Path) -> str | None:
    """Return the SHA-256 of the file at ``path``, or ``None`` if it cannot be read.

    Unreadable means unknown. A record that says nothing about a file is honest; one
    that says the wrong thing is not.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


AUDIT_FILENAME = "audit.jsonl"
"""Default log filename inside the workspace."""


class AuditWriteError(Exception):
    """Raised when a record cannot be written and the policy is to abort."""


class AuditEvent(BaseModel):
    """A single audited event.

    Frozen: a record is written once and never revised.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: str
    run_id: str
    kind: EventKind
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)
    previous: str = GENESIS_DIGEST
    """Digest of the record before this one, or the genesis value for the first."""

    digest: str = ""
    """This record's own digest, over its content and the one before it (ADR-023).

    Filled when the record is written. Any later edit changes it, and every record after
    it, so silent tampering becomes detectable and locatable rather than invisible.
    """

    def chained(self, previous: str) -> AuditEvent:
        """Return this record linked to ``previous``, with its own digest computed."""
        linked = self.model_copy(update={"previous": previous, "digest": ""})
        return linked.model_copy(update={"digest": digest_of(linked.model_dump_json())})


class AuditLog:
    """Appends audit events to a JSON Lines file inside a workspace."""

    def __init__(
        self, workspace: Workspace, config: Config, filename: str = AUDIT_FILENAME
    ) -> None:
        """Bind the log to a workspace and configuration.

        The path is resolved through the workspace boundary, so the audit trail is
        contained like anything else LACC touches.
        """
        self._path = workspace.resolve_within(filename)
        self._config = config
        self._previous: str | None = None

    @property
    def path(self) -> Path:
        """The resolved path of the log file."""
        return self._path

    def record(
        self,
        run_id: str,
        kind: EventKind,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent | None:
        """Append an event to the log.

        Returns the written event, or ``None`` when writing failed and the policy
        allows continuing. Raises :class:`AuditWriteError` when the policy is to
        abort.
        """
        event = AuditEvent(
            timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            run_id=run_id,
            kind=kind,
            message=message,
            detail=self._filter_detail(detail or {}),
        ).chained(self._head_digest())
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
        except OSError as error:
            if self._config.audit_failure_policy == "abort":
                raise AuditWriteError(f"Could not write audit record: {error}") from error
            return None
        self._previous = event.digest
        return event

    def _head_digest(self) -> str:
        """The digest the next record links to: the last one written, or genesis.

        Read from the file the first time, so a chain survives LACC being closed and
        reopened; kept in memory afterwards. A trail that started a fresh chain on every
        launch would be a chain in name only.
        """
        if self._previous is not None:
            return self._previous
        self._previous = _last_digest(self._path)
        return self._previous

    def _filter_detail(self, detail: dict[str, Any]) -> dict[str, Any]:
        """Drop content fields unless the configured level is ``full``.

        Prompts and completions can contain whatever the user was working on, so
        they are recorded only when explicitly opted into.
        """
        if self._config.audit_level == "full":
            return dict(detail)
        return {key: value for key, value in detail.items() if key not in _CONTENT_KEYS}


def _last_digest(path: Path) -> str:
    """The digest of the last record in ``path``, or genesis when there is none."""
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    except OSError:
        return GENESIS_DIGEST
    for line in reversed(lines):
        try:
            recorded = AuditEvent.model_validate_json(line)
        except ValueError:
            continue
        return recorded.digest or GENESIS_DIGEST
    return GENESIS_DIGEST


class ChainCheck(BaseModel):
    """What walking an audit trail's hash chain found.

    ``intact`` is True only when every record that carries a digest links correctly to
    the one before it. Records written before the chain existed are counted as
    unverifiable rather than broken: a trail cannot vouch for what predates the
    mechanism, and saying so is honest where an alarm would not be (ADR-023).
    """

    model_config = ConfigDict(frozen=True)

    intact: bool
    records: int
    first_seen: str = ""
    last_seen: str = ""
    """When the trail starts and ends.

    The only signal a person has against records removed from the end, which no hash chain
    can detect from the file alone: a trail whose last record predates your last run is a
    trail that lost something (ADR-043).
    """

    unverifiable: int = 0
    broken_at: int | None = None
    unreadable_at: int | None = None


def verify_chain(path: Path) -> ChainCheck:
    """Walk the trail at ``path`` and report whether its chain holds, and where it does not.

    Detects modification by anything that does not know the file is a chain. It does not
    detect a deliberate rewrite: whatever can write the file can recompute every digest
    from the point it changed. That limit is the claim's boundary, not a gap in it
    (ADR-023).
    """
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    except OSError:
        return ChainCheck(intact=False, records=0, unreadable_at=1)

    previous = GENESIS_DIGEST
    unverifiable = 0
    stamps: list[str] = []
    for position, line in enumerate(lines, start=1):
        try:
            recorded = AuditEvent.model_validate_json(line)
            stamps.append(recorded.timestamp)
        except ValueError:
            return ChainCheck(intact=False, records=len(lines), unreadable_at=position)
        if not recorded.digest:
            unverifiable += 1
            continue
        expected = recorded.model_copy(update={"digest": ""})
        recomputed = digest_of(expected.model_dump_json())
        if recorded.previous != previous or recomputed != recorded.digest:
            return ChainCheck(
                intact=False,
                records=len(lines),
                unverifiable=unverifiable,
                broken_at=position,
            )
        previous = recorded.digest
    return ChainCheck(
        intact=True,
        records=len(lines),
        unverifiable=unverifiable,
        first_seen=stamps[0] if stamps else "",
        last_seen=stamps[-1] if stamps else "",
    )


_CONTENT_KEYS = frozenset({"prompt", "completion"})
"""Detail keys treated as user content, omitted unless the level is ``full``."""
