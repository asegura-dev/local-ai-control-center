"""What a configuration may be changed to from the window, and what it may not (ADR-094).

**The window may change what LACC does. It may not change what LACC is allowed to do.**

That line falls between two kinds of setting. `model`, `context_tokens`, `engine_host` and
the rest decide how work is done. `network_access` and `workspace_in_repository` are not
settings at all - they are **refusals being lifted**: the first is the ceiling deciding
whether anything may leave this machine, the second overrides a refusal to work inside a git
tree. Each exists because a person should have to write it down deliberately, and a toggle is
not writing it down.

`engine_host` is on the editable side because with the ceiling down it is inert: naming a host
LACC may not reach changes nothing.

**Nothing here writes.** `changed` says what a file would become and `differences` says what
that costs, line by line; putting it on disk is the caller's, so the diff can be shown before
anything happens.
"""

from __future__ import annotations

import difflib
import re

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.config import Config

CHANGEABLE: tuple[tuple[str, str], ...] = (
    ("workspace_root", "the folder every file comes from and goes to"),
    ("model", "which model answers"),
    ("context_tokens", "the window it is asked for - unset means the engine's own 4096"),
    ("embedding_model", "choosing passages by meaning as well as by words. Empty turns it off"),
    ("engine_host", "where the engine is. Inert unless network_access is on"),
    ("registry_url", "where a DOI is resolved. Empty means no registry is reached"),
    ("output_language", "the language an answer is asked for"),
    ("context_file", "the standing context every run carries"),
    (
        "audit_level",
        "standard records what ran; full also records every prompt and every answer. "
        "Lowering it is how a workspace that synchronises stops carrying your prose",
    ),
)
"""The settings the window may change, with what each one decides.

In the order a person reads them: where the work is, what answers it, how much it may hold.
"""

FILE_ONLY: tuple[tuple[str, str], ...] = (
    (
        "network_access",
        "the ceiling. With it off nothing reaches anywhere but this machine, whatever else "
        "any setting says. It is written down deliberately or not at all.",
    ),
    (
        "workspace_in_repository",
        "overrides a refusal to work inside a git repository, where everything LACC writes "
        "is one 'git add -A' from being published.",
    ),
)
"""What the window shows and will not change.

Not settings: refusals being lifted. A toggle is not a deliberate decision, and the whole
weight of these two is that somebody decided (ADR-004, ADR-022).
"""

KEPT = (
    "Only the lines above change. Comments, order and spacing are left exactly as they are, "
    "and a setting you did not touch is not written down."
)


class Wanted(BaseModel):
    """One setting a person typed into the window."""

    model_config = ConfigDict(frozen=True)

    key: str
    value: str
    """As typed. Empty means the setting is left out, which is how a default is restored."""


class Refused(BaseModel):
    """Why a value cannot be used, named rather than silently dropped."""

    model_config = ConfigDict(frozen=True)

    key: str
    why: str


def settings_shown(current: str, config: Config) -> tuple[tuple[str, str, str], ...]:
    """Each changeable setting, **what the file says**, and what it decides.

    From the file, not from the parsed contract. Filling a box with the parsed value makes
    every untouched box a change: `~/lacc-workspace` comes back as a Windows path with
    backslashes, and a setting the file never mentioned comes back as today's default - so
    pressing Check on a form nobody touched proposed rewriting three lines (ADR-094).

    A box left empty is a setting the file does not mention, and the note beside it says
    what happens then.
    """
    import yaml

    try:
        held = yaml.safe_load(current) or {}
    except yaml.YAMLError:
        held = {}
    if not isinstance(held, dict):
        held = {}

    out: list[tuple[str, str, str]] = []
    for key, says in CHANGEABLE:
        value = held.get(key)
        default = getattr(config, key, "")
        note = says
        if value is None and default not in ("", None):
            note = f"{says}. Not in the file; the default is {default}"
        out.append((key, "" if value is None else str(value), note))
    return tuple(out)


_LINE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:(.*)$")


def changed(current: str, wanted: tuple[Wanted, ...]) -> tuple[str, tuple[Refused, ...]]:
    """The file as it would be, and every value that could not be used.

    **Edited line by line, not re-serialised.** Dumping the parsed settings back out was the
    first attempt and it rewrote the whole file: every comment gone, `~/lacc-workspace`
    turned into a Windows path with backslashes, and every default the contract has
    frozen into the file as if somebody had chosen it. A person asked to change one setting
    should get a diff of one setting (ADR-094).

    So only a key whose value **actually differs** is touched, its own line is rewritten in
    place, and everything else - comments, order, spacing - survives byte for byte.

    The result is validated by the contract before it is offered, so a refusal here is the
    same refusal a run would meet rather than a second opinion about what is allowed.
    """
    import yaml

    try:
        held = yaml.safe_load(current) or {}
    except yaml.YAMLError as error:
        return current, (Refused(key="the file", why=f"it could not be read: {error}"),)
    if not isinstance(held, dict):
        return current, (Refused(key="the file", why="it is not a mapping of settings"),)

    allowed = {key for key, _ in CHANGEABLE}
    refused: list[Refused] = []
    real: dict[str, str] = {}
    for one in wanted:
        if one.key not in allowed:
            refused.append(Refused(key=one.key, why="this is not changed from the window"))
            continue
        typed = one.value.strip()
        was = held.get(one.key)
        # Against what the file holds, not against what the contract defaulted to: a
        # setting the file never mentioned is unchanged when the box still shows its default.
        if typed == ("" if was is None else str(was)):
            continue
        real[one.key] = typed

    after = dict(held)
    for key, typed in real.items():
        if not typed:
            after.pop(key, None)
        else:
            after[key] = _as_number(typed) if key == "context_tokens" else typed
    try:
        Config(**after)
    except Exception as error:  # noqa: BLE001 - the contract refuses for its own reasons
        refused.append(Refused(key="the configuration", why=str(error).split(chr(10))[0]))
        return current, tuple(refused)
    if refused:
        return current, tuple(refused)
    return _rewritten(current, real), ()


def _rewritten(current: str, real: dict[str, str]) -> str:
    """The file with only the named keys changed, and every other byte where it was."""
    left = dict(real)
    lines: list[str] = []
    for line in current.splitlines():
        found = _LINE.match(line)
        if found is None or found.group(2) not in left:
            lines.append(line)
            continue
        key = found.group(2)
        typed = left.pop(key)
        if typed:
            lines.append(f"{found.group(1)}{key}: {typed}")
        # An empty value removes the line, which is how a default is restored.
    for key, typed in left.items():
        if typed:
            lines.append(f"{key}: {typed}")
    return chr(10).join(lines) + chr(10)


def _as_number(typed: str) -> object:
    """A context window as a number, or as typed so the contract can refuse it by name."""
    try:
        return int(typed)
    except ValueError:
        return typed


def differences(before: str, after: str, name: str) -> tuple[str, ...]:
    """Every line that would change, as a person reads a diff.

    The confirmation *is* this. There is no extra ceremony for the riskier settings: a ritual
    on some changes teaches people to click through the ritual, and this already says exactly
    what happens (ADR-094).
    """
    lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=f"{name} now",
        tofile=f"{name} after",
        lineterm="",
        n=1,
    )
    return tuple(lines)


def ceiling_of(config: Config) -> tuple[tuple[str, str, str], ...]:
    """The two the window will not change, with their value and why they are not here."""
    return tuple((key, str(getattr(config, key, "")), why) for key, why in FILE_ONLY)
