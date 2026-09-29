"""Bringing a draft into the workspace, one named file at a time (ADR-111).

The one place LACC reads outside the workspace, so what it decides is kept here, small and
pure: whether a file may be brought, what its copy is called, and what the note beside it says.
Where copies live is `core.drafts`, which the stages read too. The command that asks and copies
is in `cli.py`; nothing here prints.

**One file, named.** Never a folder, never a pattern, never a second file: the exception to the
boundary is exactly as wide as one path somebody typed and confirmed.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict

BRINGABLE = frozenset({".md", ".txt", ".docx", ".pdf"})
"""What LACC can read once it is here: Markdown and text as they are, PDF and `.docx` through
`ingest`."""

MOST_BYTES = 20 * 1024 * 1024
"""A draft, not a library. A thesis chapter is kilobytes; a PDF of one, a few megabytes."""


class Brought(BaseModel):
    """What a copy remembers about its original."""

    model_config = ConfigDict(frozen=True)

    source: str
    """The path that was read, as it was resolved - where to look for a newer version."""

    brought_on: str
    sha256: str


def refusal(source: Path, inside: bool, size: int | None) -> str:
    """Why ``source`` cannot be brought, in a sentence, or empty when it can.

    ``inside`` is whether it already resolves inside the workspace, and ``size`` its size in
    bytes - ``None`` when it is not a file at all. Decided before anything of it is read but
    that: the preview is drawn from what this allows.
    """
    if inside:
        return f"{source.name} is already in the workspace. Use it where it is."
    if size is None:
        return f"{source} is not a file. One file is brought at a time, never a folder."
    if source.suffix.lower() not in BRINGABLE:
        kinds = ", ".join(sorted(BRINGABLE))
        return f"{source.name} is a kind of file LACC cannot read here. It takes {kinds}."
    if size > MOST_BYTES:
        return (
            f"{source.name} is {size / 1_048_576:.0f} MB. A draft is brought one at a time and "
            f"under {MOST_BYTES // 1_048_576} MB; this looks like something else."
        )
    return ""


def copy_name(source: Path, taken: set[str], day: date) -> str:
    """What the copy is called: the file's name and the day, and a number when that is taken.

    A snapshot never replaces an earlier one. Bringing the same chapter twice in a day keeps
    both, the second numbered after the date.
    """
    stem, suffix = source.stem, source.suffix
    base = f"{stem} ({day.isoformat()})"
    candidate = f"{base}{suffix}"
    number = 2
    while candidate in taken:
        candidate = f"{base} {number}{suffix}"
        number += 1
    return candidate


def noted(source: Path, day: date, sha256: str) -> str:
    """The note that sits beside a copy, as the text written there."""
    note = Brought(source=str(source), brought_on=day.isoformat(), sha256=sha256)
    return json.dumps(note.model_dump(), indent=2, ensure_ascii=False) + "\n"
