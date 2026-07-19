"""Core configuration: a validated contract for how LACC is allowed to run.

The configuration is a frozen Pydantic model validated once at construction and
trusted thereafter (ADR-001). It can be built with defaults in code or loaded
from a YAML file (ADR-002). Safe-by-default: an absent field takes its default,
so network access is off unless explicitly enabled.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

AuditLevel = Literal["standard", "full"]
"""How much detail the audit trail records. A closed set, not a free string."""

AuditFailurePolicy = Literal["abort", "continue"]
"""What to do when an audit record cannot be written."""


class Config(BaseModel):
    """Validated configuration for one LACC run.

    Frozen and strict: once validated it does not change, and an unknown field
    is an error rather than being silently ignored.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    network_access: bool = Field(
        default=False,
        description="Whether LACC may use the network. Off by default (local-first).",
    )
    audit_level: AuditLevel = Field(
        default="standard",
        description="Level of detail recorded by the audit trail.",
    )

    workspace_root: Path = Field(
        description="Base directory LACC treats as its working area.",
    )
    audit_failure_policy: AuditFailurePolicy = Field(
        default="abort",
        description=(
            "What happens when an audit record cannot be written. "
            "'abort' raises, so an execution that cannot be recorded does not "
            "proceed - safer for traceability, but a full disk or permission "
            "error stops LACC. 'continue' proceeds unrecorded - more robust, "
            "at the cost of a gap in the audit trail exactly when something is "
            "going wrong."
        ),
    )


def load_config(path: str | Path) -> Config:
    """Load and validate a :class:`Config` from a YAML file.

    Reads the file at ``path``, parses it as YAML, and validates it against the
    model. A missing file, malformed YAML, an unknown field, or a wrong type each
    fails immediately with a clear error (validation at the boundary, fail-fast).
    """
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Config file must contain a YAML mapping, got {type(data).__name__}: {file_path}"
        )
    return Config(**data)
