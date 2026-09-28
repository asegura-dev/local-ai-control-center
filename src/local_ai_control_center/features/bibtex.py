"""A bibliography a LaTeX document can cite from, written from what a registry said (ADR-102).

Pure: works in, BibTeX out. It keeps the rule `bibliography` keeps, in another format: every
field is what the registry held, and a field it did not hold is named above the entry rather
than filled in. Nothing here is generated.

Two more rules belong to BibTeX. **A key is never changed once somebody cites it**: keys are
derived from the first author's family name and the year, and a file the person already cites
from is read so that no key in it is given again. And **every field is escaped**: the text is a
third party's, and a LaTeX document executes what it is given, so a brace or a backslash in a
deposited title is written as a character and never as a command.
"""

from __future__ import annotations

import itertools
import re
import string
import unicodedata
from collections.abc import Iterable, Iterator

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.ports.registry import Work

TYPES = {
    "journal-article": "article",
    "proceedings-article": "inproceedings",
    "book-chapter": "incollection",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
}
"""What a registry calls a work, and the BibTeX type that prints it.

Anything else is written as `misc`, the one type every style accepts, and the entry says what
the registry called it.
"""

_CONTAINER = {
    "article": "journal",
    "inproceedings": "booktitle",
    "incollection": "booktitle",
    "book": "series",
    "misc": "howpublished",
}
"""The field the container goes in, which depends on what the work is."""

_EXPECTED = {
    "article": ("volume", "issue", "pages"),
    "inproceedings": ("pages",),
    "incollection": ("pages",),
}
"""The types whose container and locators a style prints, so their absence is worth naming."""

_LOCATORS = (("volume", "volume"), ("issue", "number"), ("pages", "pages"))
"""Where in the container a work is, by its name in a `Work` and its name in BibTeX."""

_SPECIAL = {
    "\\": r"\textbackslash{}",
    "{": r"\textbraceleft{}",
    "}": r"\textbraceright{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "^": r"\^{}",
    "~": r"\~{}",
}
"""Every character LaTeX would read as an instruction, written as the character instead.

The braces become commands rather than `\\{` because BibTeX counts every brace, escaped or
not, to find where a field ends: one stray `{` in a title would swallow the rest of the file.
"""

_ENTRY = re.compile(r"@\s*(\w+)\s*\{\s*([^,\s{}]+)\s*,")
_DOI_FIELD = re.compile(r"\bdoi\s*=\s*[{\"]\s*(10\.[^}\"\s]+)", re.IGNORECASE)
_NOT_ENTRIES = frozenset({"comment", "string", "preamble"})

_WRITABLE_DOI = re.compile(r"10\.[^\s{}\\]+")
"""A DOI that survives as BibTeX: nothing that would open or close a field or begin a command."""


class Held(BaseModel):
    """What a bibliography somebody already cites from holds: its keys and its DOIs.

    Both lower-cased. A key differing only in case from one in use would be a second name for
    a thing that has one, and a DOI is the same DOI in any case.
    """

    model_config = ConfigDict(frozen=True)

    keys: frozenset[str]
    dois: frozenset[str]


class Written(BaseModel):
    """A BibTeX file, and an account of what went into it and what did not."""

    model_config = ConfigDict(frozen=True)

    text: str
    entries: tuple[tuple[str, str], ...]
    """Each key written, with the DOI it names."""

    already: tuple[str, ...]
    """DOIs left out because the file named as already cited holds them."""

    unwritable: tuple[str, ...]
    """DOIs that could not be written without breaking the file."""

    unread: int
    """Entries whose volume, issue and pages were never read, because the answer predates it."""


def held_in(text: str) -> Held:
    """The keys and DOIs a BibTeX file holds, read by pattern and nothing more.

    Tolerant of the forms found in the wild - Crossref writes a whole entry on one line with
    `DOI={...}`, others one field per line - because a key missed here is a key that could be
    handed out twice.
    """
    found = list(_ENTRY.finditer(text))
    keys: set[str] = set()
    dois: set[str] = set()
    for number, entry in enumerate(found):
        if entry.group(1).lower() in _NOT_ENTRIES:
            continue
        keys.add(entry.group(2).lower())
        end = found[number + 1].start() if number + 1 < len(found) else len(text)
        doi = _DOI_FIELD.search(text, entry.end(), end)
        if doi:
            dois.add(doi.group(1).lower())
    return Held(keys=frozenset(keys), dois=frozenset(dois))


def _plain(text: str) -> str:
    """Lower-case ASCII letters only: `Schäfer` gives `schafer`, `Maier-Hein` `maierhein`."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z]", "", folded.lower())


def key_base(work: Work) -> str:
    """The first author's family name and the year: `giesel2016`.

    Without an author, the first word of four letters or more in the title, which passes over
    `The` and `A`; without either, `anon`. Without a year, `nd`, which is what a style prints
    for a work with no date. Derived from the record, never chosen.
    """
    name = _plain(work.authors[0].split(",")[0]) if work.authors else ""
    if not name:
        words = (_plain(word) for word in work.title.split())
        name = next((word for word in words if len(word) > 3), "")
    return f"{name or 'anon'}{work.year or 'nd'}"


def _suffixes() -> Iterator[str]:
    return itertools.chain(string.ascii_lowercase, (str(n) for n in itertools.count(27)))


def unique_key(base: str, taken: set[str]) -> str:
    """``base`` if nobody uses it, otherwise the first free `base` + a, b, c..."""
    if base not in taken:
        return base
    return next(base + suffix for suffix in _suffixes() if base + suffix not in taken)


def _escaped(text: str) -> str:
    return "".join(_SPECIAL.get(character, character) for character in text)


def _kept_as_written(title: str) -> str:
    """A title with each word whose capitals belong to it kept as the registry wrote it.

    A style that re-cases titles lower-cases every word it is not told to keep, and pandoc -
    which makes the Word preview - did it to `3D U-Net`, and printed `3D u-Net`. A word with a
    capital after its first character - an acronym, `U-Net`, `PET/CT`, `68Ga` - goes inside
    braces, which every style reads as "leave this alone". `High-Risk` is kept too, which costs
    a style that wants `high-risk`; a name corrupted in a thesis costs more.
    """
    words = []
    for word in title.split(" "):
        written = _escaped(word)
        words.append("{" + written + "}" if any(c.isupper() for c in word[1:]) else written)
    return " ".join(words)


def _name(name: str) -> str:
    """One author as BibTeX reads names: `Family, Given` as it is, anything else kept whole.

    A name without a comma and with a space - an organisation - would otherwise be split into
    given and family names; a name containing " and " would be read as two people.
    """
    written = _escaped(name)
    if " and " in name.lower() or ("," not in name and " " in name):
        return "{" + written + "}"
    return written


def _locators_read(work: Work) -> bool:
    """Whether this answer was received after volume, issue and pages began to be read.

    They are read together or not at all, so one of them answers for the three.
    """
    return work.pages is not None


def _notes(work: Work, kind: str) -> list[str]:
    """What is worth saying above an entry: its gaps, and anything written differently.

    The notes are comments outside any entry, where BibTeX reads an `@` as the start of one,
    so the one piece of registry text in them is reduced to what a type name is made of.
    """
    notes = []
    if kind == "misc" and work.kind:
        called = re.sub(r"[^a-z0-9-]", "", work.kind.lower())
        notes.append(f"The registry calls this {called}; written as misc, which any style takes.")
    gaps = [field for field in ("title", "authors", "year") if not getattr(work, field)]
    if kind in _EXPECTED and not work.container:
        gaps.append(_CONTAINER[kind])
    if _locators_read(work):
        gaps += [field for field in _EXPECTED.get(kind, ()) if not getattr(work, field)]
    if gaps:
        notes.append(f"Not in the registry record: {', '.join(gaps)}.")
    if not _locators_read(work):
        received = f" on {work.fetched_on}" if work.fetched_on else ""
        notes.append(f"Received{received}, before volume, issue and pages were read.")
    return notes


def as_bibtex(work: Work, key: str) -> str:
    """One work as one BibTeX entry, its notes above it as comments."""
    kind = TYPES.get(work.kind, "misc")
    fields: list[tuple[str, str]] = []
    if work.authors:
        fields.append(("author", " and ".join(_name(author) for author in work.authors)))
    if work.title:
        fields.append(("title", _kept_as_written(work.title)))
    if work.container:
        fields.append((_CONTAINER[kind], _escaped(work.container)))
    if work.year:
        fields.append(("year", str(work.year)))
    for attribute, shown in _LOCATORS:
        value = getattr(work, attribute)
        if value:
            fields.append((shown, _escaped(value)))
    fields.append(("doi", work.doi))
    lines = [f"% {note}" for note in _notes(work, kind)]
    lines.append(f"@{kind}{{{key},")
    lines += [f"  {name} = {{{value}}}," for name, value in fields]
    lines.append("}")
    return chr(10).join(lines)


def _newest(works: Iterable[Work]) -> list[Work]:
    """One answer per DOI: the most recently received, which was read with the most fields."""
    kept: dict[str, Work] = {}
    for work in works:
        doi = work.doi.strip().lower()
        if doi not in kept or work.fetched_on > kept[doi].fetched_on:
            kept[doi] = work.model_copy(update={"doi": doi})
    return list(kept.values())


def bibtex(works: Iterable[Work], held: Held) -> Written:
    """The whole file, and what was left out of it and why.

    Keys are handed out in order of the key they would want and then of DOI, so the same
    answers give the same file. That is stable only against a file that is named: a key is
    kept across runs by passing the file that cites it, never by hoping the order holds.
    """
    taken = set(held.keys)
    already: list[str] = []
    unwritable: list[str] = []
    pending: list[tuple[str, Work]] = []
    for work in _newest(works):
        if work.doi in held.dois:
            already.append(work.doi)
        elif not _WRITABLE_DOI.fullmatch(work.doi):
            unwritable.append(work.doi)
        else:
            pending.append((key_base(work), work))

    entries: list[tuple[str, Work]] = []
    for base, work in sorted(pending, key=lambda item: (item[0], item[1].doi)):
        key = unique_key(base, taken)
        taken.add(key)
        entries.append((key, work))
    entries.sort(key=lambda item: item[0])

    received = sorted({work.fetched_on for _, work in entries if work.fetched_on})
    dated = f"Received {', '.join(received)}." if received else "No date of receipt."
    header = [
        "% Written by lacc bib from what a registry answered. Nothing in it was generated.",
        f"% {dated} A record can change after that date.",
        "% A field the record did not hold is named above its entry, never filled in.",
        "% Keys are the first author's family name and the year. Once you cite one, keep it.",
    ]
    if any(not _locators_read(work) for _, work in entries):
        header.append(
            "% Where an entry was received before volume, issue and pages were read, it says so;"
            " resolving it again into a new file reads them."
        )
    body = [as_bibtex(work, key) for key, work in entries]
    return Written(
        text=chr(10).join(header) + chr(10) * 2 + (chr(10) * 2).join(body) + chr(10),
        entries=tuple((key, work.doi) for key, work in entries),
        already=tuple(sorted(already)),
        unwritable=tuple(sorted(unwritable)),
        unread=sum(1 for _, work in entries if not _locators_read(work)),
    )
