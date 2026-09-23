"""Which work a document *is*, when nothing in it says so (ADR-087).

A PDF usually carries its DOI in its metadata, and `resolve` reads it there. Two things
measured over a real bibliography of 23 papers put a hole in that:

- **Conversion loses it entirely.** Eleven PDFs carried a DOI; eleven of the Markdown files
  made from them carried none. The corpus is built from those Markdown files.
- **Nine of the twelve silent PDFs print a DOI on their own front pages** - where neither
  the metadata nor LACC was looking.

Reading the printed one is not safe on its own, because a document also prints the DOIs of
what it cites, and **no test tried here separates the two**: over the whole front matter a
cited DOI scored 100% against the registry's title, and at every narrower window a cited one
outranked an owned one. So this module does not decide. It finds the candidates, and records
the one a person established, beside the file and never inside it.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

DOI_BESIDE = ".doi.json"
"""What the file recording an established DOI is called, next to its document.

Beside, never inside. The corpus points at these documents as they are and hundreds of
quotations are checked against them by string comparison; a line written into one would
change a file that all of that rests on (ADR-082).
"""

FRONT = 6000
"""Characters of a document treated as its front matter.

About two pages of a journal article, which is where a DOI is printed if it is printed at
all. Past that it is a reference list.
"""

_DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
_TRAILING = ".,;:)]}"


class Established(BaseModel):
    """A DOI somebody established for a document, and what they were shown when they did.

    The title is kept because a bibliography rebuilt later should rest on what the registry
    actually returned, rather than on somebody's recollection of having checked.
    """

    model_config = ConfigDict(frozen=True)

    doi: str
    title: str = ""
    established: str = ""
    """The date it was written down. A registry record can change after it."""


def printed_dois(text: str, front: int = FRONT) -> tuple[str, ...]:
    """Every distinct DOI the document prints near its front, in the order they appear.

    **Candidates, not an answer.** The document's own and the ones it cites look alike here,
    which is the measured finding this module exists because of.
    """
    found: list[str] = []
    for match in _DOI.findall(text[:front]):
        cleaned = match.rstrip(_TRAILING)
        if cleaned and cleaned not in found:
            found.append(cleaned)
    return tuple(found)


OPENING = 160
"""Characters of a document's opening shown beside what the registry said it is."""


def opening_of(text: str, characters: int = OPENING) -> str:
    """The first real words of a document, to put beside the registry's answer.

    Page markers are left out: they are LACC's own, not the document's, and the point of
    this line is to show what the paper says about itself.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    said = " | ".join(line for line in lines if not line.startswith("<!--"))
    return said[:characters]


def beside(document: Path) -> Path:
    """Where the established DOI for ``document`` is kept."""
    return document.with_suffix(document.suffix + DOI_BESIDE)


def established_for(document: Path) -> Established | None:
    """What was established for this document, or nothing.

    A file that cannot be read or does not hold a DOI is nothing rather than an error: an
    unreadable note about a document must not stop the document being used.
    """
    path = beside(document)
    if not path.exists():
        return None
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(held, dict) or not held.get("doi"):
        return None
    return Established(
        doi=str(held["doi"]),
        title=str(held.get("title", "")),
        established=str(held.get("established", "")),
    )


def establish(document: Path, doi: str, title: str = "", when: str = "") -> Path:
    """Write down the DOI for ``document`` and return where it was written."""
    note = Established(
        doi=doi.strip(),
        title=title.strip(),
        established=when or datetime.now(UTC).date().isoformat(),
    )
    path = beside(document)
    path.write_text(note.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
