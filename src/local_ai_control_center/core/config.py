"""Core configuration: a validated contract for how LACC is allowed to run.

The configuration is a frozen Pydantic model validated once at construction and
trusted thereafter (ADR-001). It can be built with defaults in code or loaded
from a YAML file (ADR-002). Safe-by-default: an absent field takes its default,
so network access is off unless explicitly enabled.
"""

from __future__ import annotations

import ipaddress
import os
import re
import urllib.parse
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

AuditLevel = Literal["standard", "full"]
"""How much detail the audit trail records. A closed set, not a free string."""

AuditFailurePolicy = Literal["abort", "continue"]
"""What to do when an audit record cannot be written."""

_ENVIRONMENT_VARIABLE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
"""What a name in a `*_env` field has to look like: a variable name, not a value.

**Upper case is required, and that is the point rather than fussiness.** Checking only
the shape of an identifier is not enough: `tk_f0yn7rfgs48l94eq41y5u7ddh2irw` is a
perfectly valid identifier, so a token pasted into `token_env` passes a shape check
while being exactly the thing this field exists to keep out of files. The upper-case
convention is the only thing that reliably separates the name of a variable from the
value of one, so LACC requires it and says so when it refuses (ADR-030).

The cost is a lower-case environment variable being refused. That is rare, the message
explains it, and renaming a variable is cheaper than a leaked token.
"""

_NAMES_A_VALUE = (
    "`{field}` names an environment variable; it does not hold the value. Got {value!r}, "
    "which is not the name of one - they are written in upper case, like `{suggestion}`. "
    "Put that name here and the value in your environment. Nothing secret belongs in a "
    "configuration file: a token written into one is a token in every backup and every "
    "copy of that folder."
)

MAX_INPUT_BYTES_DEFAULT = 32 * 1024 * 1024
"""32 MiB: large enough that an ordinary research document never meets it, small enough
that meeting it says something rather than merely being a nuisance."""


class NtfySettings(BaseModel):
    """How to reach an ntfy server, without holding its secrets.

    Every secret is named rather than written: the value comes from the environment
    variable this points at. A token in a configuration file is a token in a backup
    (ADR-027).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    server_url_env: str = "NTFY_SERVER"
    topic_env: str = "NTFY_TOPIC"
    token_env: str = "NTFY_TOKEN"

    @field_validator("server_url_env", "topic_env", "token_env")
    @classmethod
    def _must_name_a_variable(cls, value: str, info: ValidationInfo) -> str:
        """Refuse a value written where the name of a variable belongs.

        The first person to follow the setup guide wrote the server URL, the topic and a
        live token straight into these fields. Nothing complained: LACC looked for
        variables with those literal names, found none, and said it was unconfigured. A
        silence that follows a plausible misreading is a design problem, not a user error
        - and the misreading put a secret into a file, which is the exact thing naming
        the variable exists to prevent.
        """
        field = info.field_name or "field"
        if not _ENVIRONMENT_VARIABLE.match(value):
            raise ValueError(
                _NAMES_A_VALUE.format(
                    field=field,
                    value=value,
                    suggestion=f"NTFY_{field.removesuffix('_env').upper()}",
                )
            )
        return value

    priority: int = 3
    tags: tuple[str, ...] = ()


class NotifierSettings(BaseModel):
    """Where LACC may say that a run finished. Nothing is enabled by default."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ntfy: NtfySettings = Field(default_factory=NtfySettings)


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
    workspace_in_repository: bool = Field(
        default=False,
        description=(
            "Acknowledge that the workspace sits inside a git working tree. False by "
            "default, and LACC refuses to run in that case: private material one "
            "'git add -A' away from being published is not a risk a warning covers. "
            "LACC cannot tell whether the path is ignored - answering that means running "
            "git, which it does not do - so it refuses what it can see and leaves the "
            "judgement to you. Setting this to true says you have checked."
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
    engine_host: str = Field(
        default="",
        description=(
            "Where the model runs, when it is not on this machine. Empty means loopback. "
            "A host that is not loopback is reached only when network_access also permits "
            "it, and only because this names it: an environment variable can never widen "
            "what LACC contacts."
        ),
    )
    notifier: NotifierSettings = Field(
        default_factory=NotifierSettings,
        description=(
            "Where LACC says that a long run finished. Off by default, and it never "
            "carries document content: which skill ran, how it ended, how long it took."
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

    @property
    def remote_engine(self) -> str:
        """The configured engine address when it is not this machine, else empty.

        Reports; it does not judge. Whether reaching that host is permitted is
        ``network_access``, and refusing an unpermitted one stays the provider's job. This
        exists so the preview can tell a person their documents are about to leave the
        machine, before they confirm (ADR-028).

        One definition of "not this machine", used both by the code that discloses it and
        by the code that enforces it.
        """
        named = self.engine_host.strip()
        if not named:
            return ""
        host = normalized_host(named)
        hostname = urllib.parse.urlparse(host).hostname
        if hostname is None or is_loopback(hostname):
            return ""
        return host


def normalized_host(host: str) -> str:
    """Return ``host`` with a scheme, so it can be parsed the same way every time."""
    return host if host.startswith("http") else f"http://{host}"


def is_loopback(hostname: str) -> bool:
    """Whether ``hostname`` names this machine, by literal address or by `localhost`."""
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


DOTENV_FILENAME = ".env"
"""Read from the configuration's own directory, and nowhere else (ADR-030)."""


def parse_dotenv(text: str) -> dict[str, str]:
    """Read `KEY=value` lines, ignoring comments, blanks and an optional `export`.

    Its own parser rather than a dependency: the format is twenty lines of code, and the
    alternative is a package present in every environment LACC runs in for the sake of it.

    A malformed line is skipped rather than raising. The file exists to supply credentials,
    and failing the whole run over a stray line would be a worse outcome than the one
    missing variable that follows - which announces itself clearly when it is looked up.
    """
    found: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        stripped = stripped.removeprefix("export ").lstrip()
        name, separator, value = stripped.partition("=")
        name = name.strip()
        if not separator or not _ENVIRONMENT_VARIABLE.match(name):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        found[name] = value
    return found


def load_dotenv(directory: str | Path) -> tuple[str, ...]:
    """Load ``directory/.env`` into the environment, and report the names it set.

    A variable already present is never overwritten, so a shell, a server or a CI job
    keeps the last word and the file only fills what is missing (ADR-030).

    Returns the names set, never the values: a caller may want to say that credentials
    were found, and no caller should print them to a terminal that scrolls into a log.
    A missing or unreadable file is not an error - it means there was nothing to add.
    """
    path = Path(directory) / DOTENV_FILENAME
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ()

    added = []
    for name, value in parse_dotenv(text).items():
        if name not in os.environ:
            os.environ[name] = value
            added.append(name)
    return tuple(added)


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
