"""Reading the reference list a document already carries (ADR-064).

**Parsed, never generated.** Reference metadata is exactly the shape of thing a model
produces plausibly and wrongly - asked for a journal name with an instruction to say
*"not available"* when it did not know, a 14B invented twelve of twenty-four (ADR-047). The
reference list is in the file. There is nothing to generate.

Everything here is a pure function over text.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.grounding import _unspaced

_HEADING = re.compile(r"(?im)^#{1,6}\s*(references|bibliography|reference list)\s*$")
_BARE_HEADING = re.compile(r"(?im)^\s*(references|bibliography)\s*$")
"""Two ways a reference section announces itself, tried in that order.

A Markdown heading is the reliable one. A bare line is what survives from a PDF whose
headings carried no structure, and it is tried second because the word also appears in
running prose - *"references to the guideline"* - where a heading cannot.
"""

_NUMBERED = re.compile(r"(?m)^\s*(?:\[\s*\d{1,3}\s*\]|\d{1,3}\.)\s")
"""What starts a reference: `1.` or `[1]` at the beginning of a line.

The numbering is the structure this relies on, and relying on structure rather than on a
model's willingness is the measured lesson this project keeps applying (ADR-052). A
bibliography in author-year style with no numbering yields nothing here, visibly.
"""

_ENOUGH_ENTRIES = 3
"""Below this, a run of numbered lines is a list in the prose rather than a bibliography."""

_DOI = re.compile(r"10\.\d{4,9}/[-._;()/:a-z0-9]{3,60}")
_YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


class Reference(BaseModel):
    """One entry of a reference list, as the document printed it."""

    model_config = ConfigDict(frozen=True)

    text: str
    """The entry as it appears, with the line breaks the page had."""

    doi: str = ""
    """The DOI, recovered through the same folding a quotation goes through, or empty.

    Empty for most of them. Measured on a real bibliography: 226 of 2,360 references carry
    a DOI that survives - about one in eleven - because most journals do not print one
    (ADR-064).
    """

    year: int | None = None


def reference_section(text: str) -> str:
    """The text after the reference heading, or empty when there is no such heading.

    The **last** matching heading wins. A paper mentions the word in its prose and in its
    own section titles, and the bibliography is at the end of the document, so taking the
    last occurrence is what distinguishes the section from a sentence about it.
    """
    matches = list(_HEADING.finditer(text)) or list(_BARE_HEADING.finditer(text))
    return text[matches[-1].end() :] if matches else ""


def _folded(entry: str) -> str:
    """One reference, folded the way a quotation is folded before it is searched for.

    Per entry, **never** over the whole section. `_unspaced` removes newlines along with
    every other space, so folding the section as a whole runs each reference into the next:
    a DOI came out as `10.1158/1055-9965.epi-15-0578.2.sungh`, where `.2.sungh` is the
    following reference's number and first author. Every DOI was then distinct, and the
    count of works cited by more than one paper was zero where the answer is nine (ADR-064).
    """
    return _unspaced(entry)


def references_in(text: str) -> tuple[Reference, ...]:
    """Every entry of the document's reference list, in the order it printed them.

    Returns nothing rather than guessing when there is no heading, or when what follows it
    is not a numbered list. A document that reports zero references is one to look at; a
    document given invented references would be worse than one given none.
    """
    section = reference_section(text)
    if not section:
        return ()
    starts = [match.start() for match in _NUMBERED.finditer(section)]
    if len(starts) < _ENOUGH_ENTRIES:
        return ()

    entries: list[Reference] = []
    for start, end in zip(starts, [*starts[1:], len(section)], strict=True):
        entry = section[start:end].strip()
        if not entry:
            continue
        folded = _folded(entry)
        found = _DOI.search(folded)
        years = [int(year) for year in _YEAR.findall(folded)]
        entries.append(
            Reference(
                text=entry,
                doi=found.group(0).rstrip(".,;:)") if found else "",
                # The last year in an entry: a title may contain one, and the year of
                # publication comes after the journal.
                year=years[-1] if years else None,
            )
        )
    return tuple(entries)


def without_truncations(dois: frozenset[str]) -> frozenset[str]:
    """Drop a DOI that is the broken beginning of a longer one in the same set.

    `10.2967/jnumed` is what is left when the folding ends early; the whole is
    `10.2967/jnumed.118.224055`. Deciding by prefix needs no invented length: a DOI that
    another DOI starts with is that one's truncated half, and the longer one is already
    present to stand for it.
    """
    return frozenset(
        doi for doi in dois if not any(other != doi and other.startswith(doi) for other in dois)
    )
