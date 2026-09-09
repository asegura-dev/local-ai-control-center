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
from pydantic import BaseModel, ConfigDict, Field, field_validator

AuditLevel = Literal["standard", "full"]
"""How much detail the audit trail records. A closed set, not a free string."""

AuditFailurePolicy = Literal["abort", "continue"]
"""What to do when an audit record cannot be written."""

MAX_INPUT_BYTES_DEFAULT = 32 * 1024 * 1024
"""32 MiB: large enough that an ordinary research document never meets it, small enough
that meeting it says something rather than merely being a nuisance."""


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
    model: str = Field(
        default="",
        description=(
            "The Ollama model a real provider should use (for example, "
            "'qwen2.5:3b'). Empty by default: naming a model is required to run "
            "against a real engine, so an empty value is a clear configuration "
            "error rather than a guessed default. See installed models with "
            "'lacc profile'."
        ),
    )
    context_tokens: int | None = Field(
        default=None,
        description=(
            "The context window to run the model with, in tokens. Unset by default, "
            "because a guessed window is worse than none: too small refuses work that "
            "would have run, too large cannot be allocated. When set, LACC asks the "
            "engine for exactly this window and refuses a prompt estimated to exceed it "
            "rather than letting the engine truncate silently. See 'lacc profile' for "
            "what each installed model supports. A larger window costs memory."
        ),
    )
    max_input_bytes: int = Field(
        default=MAX_INPUT_BYTES_DEFAULT,
        description=(
            "The largest file LACC will read or convert, in bytes. A document is read "
            "into memory whole, so this is a ceiling about the machine rather than "
            "about the model: whether the text then fits the model's context is a "
            "different question with a different answer. Over the ceiling the run is "
            "refused, naming the file, its size and the limit."
        ),
    )
    output_language: str = Field(
        default="English",
        description=(
            "The language the model is asked to answer in. Defaults to English: "
            "small local models follow instructions and write more reliably in it "
            "than in languages they saw less of during training. Never empty - a "
            "blank language is a clear error, not a silent fallback to whatever "
            "the model happens to choose."
        ),
    )

    @field_validator("context_tokens")
    @classmethod
    def _require_a_usable_window(cls, value: int | None) -> int | None:
        """Reject a window that cannot hold anything.

        ``None`` means unknown, which is a state LACC handles by saying so. Zero or a
        negative number is not a smaller window, it is a broken one.
        """
        if value is not None and value <= 0:
            raise ValueError("context_tokens must be a positive number of tokens")
        return value

    @field_validator("max_input_bytes")
    @classmethod
    def _require_a_positive_ceiling(cls, value: int) -> int:
        """Reject a ceiling that is not a real ceiling.

        Zero or a negative value would refuse every file, which is not a limit but a
        way of turning LACC off by configuration accident.
        """
        if value <= 0:
            raise ValueError("max_input_bytes must be a positive number of bytes")
        return value

    @field_validator("output_language")
    @classmethod
    def _require_a_language(cls, value: str) -> str:
        """Reject a blank language, and normalize the surrounding whitespace.

        Checked once here at the boundary, so everything downstream can put the
        value straight into a prompt without re-validating it.
        """
        language = value.strip()
        if not language:
            raise ValueError("output_language must name a language, for example: English")
        return language


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
