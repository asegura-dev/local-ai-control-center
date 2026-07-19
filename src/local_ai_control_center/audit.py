"""Audit: an append-only record of what LACC did.

Records are JSON Lines inside the workspace, resolved through the workspace
boundary (ADR-006). Detail follows the configured `audit_level`: metadata always,
prompt and completion content only under `full`. When a record cannot be written,
`audit_failure_policy` decides whether execution stops or proceeds unrecorded.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from local_ai_control_center.config import Config
from local_ai_control_center.workspace import Workspace

EventKind = Literal[
    "run_started",
    "run_finished",
    "permission_granted",
    "permission_denied",
    "provider_called",
]
"""The closed set of events recorded today. It grows as real events appear."""

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
        )
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
        except OSError as error:
            if self._config.audit_failure_policy == "abort":
                raise AuditWriteError(f"Could not write audit record: {error}") from error
            return None
        return event

    def _filter_detail(self, detail: dict[str, Any]) -> dict[str, Any]:
        """Drop content fields unless the configured level is ``full``.

        Prompts and completions can contain whatever the user was working on, so
        they are recorded only when explicitly opted into.
        """
        if self._config.audit_level == "full":
            return dict(detail)
        return {key: value for key, value in detail.items() if key not in _CONTENT_KEYS}


_CONTENT_KEYS = frozenset({"prompt", "completion"})
"""Detail keys treated as user content, omitted unless the level is ``full``."""
