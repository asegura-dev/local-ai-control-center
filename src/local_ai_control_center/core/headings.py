"""Finding the sections of a document, so a person can choose one.

Choosing which part of a long document to read is the step before reading it, and it is the
step a model must not take. A model asked which sections are relevant would omit silently,
which is measured behaviour: asked to cover 24 documents it covered 10 and named none of the
fourteen it dropped. A selection whose misses are invisible is worse than no selection
(ADR-045, ADR-046).

So this is pattern matching over text and nothing else. What it cannot find, it does not
guess at, and the caller is told which method produced the list.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from .grounding import pages_in

_NUMBERED = re.compile(r"^(\d+(?:\.\d+)+)\s+(\S.*)$")
"""A section number followed by a title: `6.4.4.1.6 Whole-body and axial MRI`.

Multi-level only. A bare `6 Treatment` is indistinguishable from a numbered list item, a
figure caption or a dosage, and admitting it filled the list with things that were none of
those.
"""

_TRAILING_PAGE = re.compile(r"\s{2,}\d{1,4}\s*$")
"""A title ending in whitespace and a number is a line from the table of contents.

The contents of a 251-page guideline are themselves several pages of things that look
exactly like headings. They are marked rather than dropped: a reader scanning for a section
is well served by its contents entry, and badly served by being unable to tell one from the
section itself.
"""

_TITLE_OPENS = re.compile(r"^[A-Z\u00c0-\u00de]")
"""A heading begins with a capital. A measurement continues in prose and does not.

Measured against a 251-page guideline, this one rule removed every survivor of the
previous filter: `8.9 yr. 10-yr. ASTRO`, `0.0001 for 15-yr. results)`, `27.4 ng/mL`.
Extraction sometimes breaks a word across a heading's start, so this loses a few real
ones. That trade is deliberate: a list padded with dosages is not a list anybody reads.
"""

_FIRST_PART = re.compile(r"^([1-9]\d?)\.")
"""The first component of a section number: at least one, at most two digits.

`0.0001` and `0.2` are not section one of anything.
"""

_LONGEST_TITLE = 90
"""Characters past which a line is a sentence that began with a number."""


class Heading(BaseModel):
    """One section of a document, and the page it starts on."""

    model_config = ConfigDict(frozen=True)

    page: int
    title: str
    number: str = ""
    """The document's own section number, when it numbers them."""

    in_contents: bool = False
    """Whether this looks like a line from the table of contents rather than the section."""

    depth_hint: int = 0
    """Nesting given by the document itself, when a PDF's own outline supplies it."""

    @property
    def depth(self) -> int:
        """How deep the section sits: from its number, or from what the document said."""
        return self.number.count(".") if self.number else self.depth_hint


def headings_in(source: str) -> tuple[Heading, ...]:
    """Find the numbered headings of an ingested document, with the page each starts on.

    Needs the `<!-- page N -->` markers ingestion preserves, because a heading without a
    page is not something anyone can act on.

    **Numbered headings only.** Guidelines, standards and theses number their sections;
    journal articles usually do not, and for those a PDF's embedded outline is the right
    source and this is the wrong one. Guessing at unnumbered headings by typography is not
    attempted: the text extraction has already thrown away the typography.
    """
    found: list[Heading] = []
    for number, text in pages_in(source):
        for line in text.splitlines():
            stripped = line.strip()
            if len(stripped) > _LONGEST_TITLE:
                continue
            match = _NUMBERED.match(stripped)
            if not match:
                continue
            section, title = match.group(1), match.group(2).strip()
            if not _FIRST_PART.match(section):
                continue
            if not _TITLE_OPENS.match(title) or len(title) < 3:
                continue
            contents = bool(_TRAILING_PAGE.search(title))
            found.append(
                Heading(
                    page=number,
                    title=_TRAILING_PAGE.sub("", title).strip(),
                    number=section,
                    in_contents=contents,
                )
            )
    return _contents_marked(tuple(found))


def _contents_marked(found: tuple[Heading, ...]) -> tuple[Heading, ...]:
    """Mark the earlier of two headings sharing a section number as the contents entry.

    A table of contents lists every section, so every number in it appears twice - once on
    page four and once where the section is. The trailing page number usually gives the
    first away, and when extraction swallows it, being first does.
    """
    last_page = {h.number: h.page for h in found}
    return tuple(
        h.model_copy(update={"in_contents": True})
        if h.number and h.page < last_page[h.number] and not h.in_contents
        else h
        for h in found
    )


def matching(headings: tuple[Heading, ...], words: tuple[str, ...]) -> tuple[Heading, ...]:
    """Headings whose title contains any of ``words``, case-insensitively.

    A filter over titles, not over content. It cannot tell you which section *discusses* a
    subject - only which one is *named* for it. That difference was measured the expensive
    way: pages picked because they mentioned a term produced quotations about adjuvant
    chemotherapy, because mentioning is not being about.
    """
    lowered = tuple(_folded(word) for word in words if word.strip())
    if not lowered:
        return headings
    return tuple(h for h in headings if any(word in _folded(h.title) for word in lowered))


def _folded(text: str) -> str:
    """Letters and digits only, lower case, for comparing a title to a word.

    Extraction spaces glyphs rather than words often enough that `PSMA PET/CT` arrives as
    `PSM A PET/CT`, and a search for "psma" then finds nothing. The same defect cost
    twenty-two quotations before it was found in the grounding check (ADR-046); it is the
    same defect here, and folding is the same answer.
    """
    return "".join(c for c in text.lower() if c.isalnum())


class DocumentMetadata(BaseModel):
    """What a file says about itself, and nothing more.

    Named for what it is rather than "the metadata", because a publisher's tooling wrote it
    and nothing here verifies it. Every field defaults to empty, and empty means the file
    did not say - never that LACC could not be bothered to guess (ADR-047).
    """

    model_config = ConfigDict(frozen=True)

    title: str = ""
    authors: tuple[str, ...] = ()
    doi: str = ""
    date: str = ""

    @property
    def missing(self) -> tuple[str, ...]:
        """The fields this file does not carry, named so a reader can go and find them."""
        absent = []
        if not self.title:
            absent.append("title")
        if not self.authors:
            absent.append("authors")
        if not self.doi:
            absent.append("DOI")
        if not self.date:
            absent.append("date")
        return tuple(absent)

    @property
    def says_anything(self) -> bool:
        """Whether the file carried any of it."""
        return bool(self.title or self.authors or self.doi or self.date)


_DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "doi:", "DOI:")


def normalized_doi(given: str) -> str:
    """Strip the ways a DOI is written down to the DOI itself.

    Observed in one bibliography: bare, `doi:`-prefixed, and as a doi.org URL. A citation
    manager wants the identifier, and three spellings of it are three identifiers to anyone
    comparing strings.
    """
    doi = given.strip()
    for prefix in _DOI_PREFIXES:
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix) :].strip()
            break
    return doi if doi.startswith("10.") else ""
