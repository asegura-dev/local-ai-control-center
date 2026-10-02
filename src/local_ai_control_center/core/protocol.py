"""What a thesis protocol cites, and where, read without a model (ADR-124).

A protocol cites by number - `[19]`, `[2-4]`, `[8, 9]` - and a long and a short version of it
number the same works differently. The master list gives each work its key and its number in
each version, so every sentence that cites a number can be traced to the work it names. That
is arithmetic, not judgement, and nothing here asks anything of anyone.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

Version = Literal["compact", "extended"]
"""The two versions a protocol is kept in: the one delivered, and the technical one."""


class MasterEntry(BaseModel):
    """One work in the master list: its key, its numbers, and its reference as written."""

    model_config = ConfigDict(frozen=True)

    key: str
    compact: int | None = None
    extended: int | None = None
    reference: str = ""
    """The reference exactly as the list writes it. Nothing is parsed out of it but the DOI:
    a title or a year taken from a formatted string would be a guess."""

    doi: str = ""

    def number_in(self, version: Version) -> int | None:
        """The number this work is cited by in ``version``, or None when it is not cited."""
        return self.compact if version == "compact" else self.extended


_ENTRY = re.compile(
    r"^- \*\*(?P<key>[\w-]+)\*\*(?P<where>[^\n]*)\n[ \t]+(?P<reference>\S[^\n]*)", re.M
)
_COMPACT = re.compile(r"compacto\s*\[(\d+)\]")
_EXTENDED = re.compile(r"extenso\s*\[(\d+)\]")
_DOI = re.compile(r"doi:\s*(10\.\S+?)\.?$", re.IGNORECASE)


def master_entries(text: str) -> tuple[MasterEntry, ...]:
    """Every work the master list names, in the order it names them.

    The shape is the list's own: a bullet with the key in bold and where it is cited, then the
    reference on the next line, indented. An entry without that second line has no reference to
    show and is still a key with numbers.
    """
    entries: list[MasterEntry] = []
    for match in _ENTRY.finditer(text):
        where, reference = match.group("where"), match.group("reference").strip()
        compact, extended = _COMPACT.search(where), _EXTENDED.search(where)
        doi = _DOI.search(reference)
        entries.append(
            MasterEntry(
                key=match.group("key"),
                compact=int(compact.group(1)) if compact else None,
                extended=int(extended.group(1)) if extended else None,
                reference=reference,
                doi=doi.group(1) if doi else "",
            )
        )
    return tuple(entries)


CITATION = re.compile(r"\[(\d+(?:\s*[-–]\s*\d+)?(?:\s*,\s*\d+(?:\s*[-–]\s*\d+)?)*)\]")
"""A numbered citation: `[19]`, `[2-4]`, `[8, 9]`, `[15, 28, 29]`, `[44–46]`."""


def numbers_in(marker: str) -> tuple[int, ...]:
    """The numbers a citation names, ranges spelled out: `2-4, 9` is 2, 3, 4 and 9."""
    found: list[int] = []
    for part in marker.split(","):
        bounds = re.split(r"\s*[-–]\s*", part.strip())
        if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
            low, high = int(bounds[0]), int(bounds[1])
            found.extend(range(low, high + 1) if low <= high else (low, high))
        elif bounds[0].isdigit():
            found.append(int(bounds[0]))
    return tuple(found)


class CitingSentence(BaseModel):
    """A sentence of the protocol that cites at least one work, with where it is."""

    model_config = ConfigDict(frozen=True)

    source: str
    """The file it was read from."""

    line: int
    """Where its paragraph or table row starts, so it can be found in that file."""

    text: str
    """As written, citation marks and all."""

    numbers: tuple[int, ...]

    @property
    def without_marks(self) -> str:
        """The sentence with its citation marks taken out - what is put to a judge."""
        return re.sub(r"\s+", " ", CITATION.sub("", self.text)).replace(" .", ".").strip()


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])")
_HEADING = re.compile(r"^\s{0,3}#")
_TABLE_RULE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d{1,2}[.)])\s+")


def _units(text: str) -> list[tuple[int, str]]:
    """Paragraphs, list items and table rows, each with the line it starts on.

    A table row is a unit of its own: the state-of-the-art table says in one row what a work
    contributes, and joining rows would attribute one work's sentence to another. **So is a
    list item.** The protocol's objectives are a list with no blank lines between them, and read
    as one paragraph they became a single "sentence" citing ten works, judged against each of
    them (ADR-124's pilot).
    """
    units: list[tuple[int, str]] = []
    block: list[str] = []
    start = 0
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if _LIST_ITEM.match(line) and block:
            units.append((start, " ".join(block)))
            block = []
        if stripped.startswith("|"):
            if block:
                units.append((start, " ".join(block)))
                block = []
            if not _TABLE_RULE.match(stripped):
                cells = [cell.strip() for cell in stripped.strip("|").split("|")]
                units.append((number, " - ".join(cell for cell in cells if cell)))
            continue
        if not stripped or _HEADING.match(line):
            if block:
                units.append((start, " ".join(block)))
                block = []
            continue
        if not block:
            start = number
        block.append(_LIST_ITEM.sub("", stripped, count=1))
    if block:
        units.append((start, " ".join(block)))
    return units


def citing_sentences(text: str, source: str) -> tuple[CitingSentence, ...]:
    """Every sentence of ``text`` that cites a number, with the numbers it cites.

    Sentences end at a stop followed by a capital, which leaves `et al. 2020` and `p. ej.`
    whole. A sentence that cites several works is returned once and belongs to each of them.
    """
    found: list[CitingSentence] = []
    for line, unit in _units(text):
        for sentence in _SENTENCE_END.split(unit):
            numbers = tuple(
                number
                for match in CITATION.finditer(sentence)
                for number in numbers_in(match.group(1))
            )
            if numbers:
                found.append(
                    CitingSentence(source=source, line=line, text=sentence.strip(), numbers=numbers)
                )
    return tuple(found)


def citing(
    entry: MasterEntry, sentences: tuple[CitingSentence, ...], version: Version
) -> tuple[CitingSentence, ...]:
    """The sentences of one version that cite ``entry``, by its number in that version."""
    number = entry.number_in(version)
    if number is None:
        return ()
    return tuple(sentence for sentence in sentences if number in sentence.numbers)
