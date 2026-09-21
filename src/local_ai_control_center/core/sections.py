"""The sections a document numbers for itself (ADR-076).

A PDF does not say what a heading is - a heading there is text in a larger font, and nothing
survives extraction to distinguish it from a sentence. Measured: seven of eight papers carry
no Markdown heading at all.

What does survive is **numbering**, where the author used it. This reads that and nothing
else: no font, no length of line, no position on a page, and no model.

**Detected, never written in.** The workspace holds hundreds of quotations checked against
these files as they are. Inserting `##` to mark a heading would put every one of those checks
at risk to gain a convenience that is available without it.

Four rules were tried and the count fell each time: **16, 18, 10, 6 of 24 documents**. The
second went *up* and was the worst - it added consecutive numbering, which every numbered
list has, so it counted author affiliations and bibliographies. The last two conditions came
from running this on the real guideline and reading the output (ADR-076).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

_NUMBERED = re.compile(r"^\s{0,3}(\d{1,2}(?:\.\d{1,2}){0,2})\.\s+(\S.*?)\s*$")
"""`1. Introduction` or `2.1. Image acquisition`, with the dot after the number required.

That dot is the whole of the difference between a section and any other numbered line. An
affiliation and a reference entry are written without it.
"""

_ENDS_IN_A_PAGE = re.compile(r"\s\d{1,3}\s*$")
"""What a table-of-contents entry carries and a heading does not: `1. INTRODUCTION      11`.

Excluded by that number rather than by position in the file, so a contents page at the end,
or a document with none, needs no special case.
"""

_LONGEST_TITLE = 9
"""Words. A section is named, not written - past this it is a sentence that starts with a
number, which in these documents is usually a numbered finding or a figure caption."""


def _pattern_under(top: str) -> re.Pattern[str]:
    """The shape of a subsection of ``top``, where the parent's number is the anchor.

    **Inside a confirmed section the dot is not needed**, because the prefix does the work it
    was doing: a `5.1` between section 5 and section 6 is a subsection of 5 whatever
    punctuation follows. The EAU guideline writes `5.1 Screening` and `5.1.4 P opulation-based
    screening` with no dot, and its subsections were invisible until this existed (ADR-076).

    Built rather than formatted: a format string collides with the repetition braces the
    pattern needs, which is how `{0,3}` became a `KeyError`.
    """
    return re.compile(r"^\s{0,3}(" + re.escape(top) + r"(?:\.\d{1,2}){1,2})\.?\s*(.*?)\s*$")


_ENOUGH_SECTIONS = 3
"""Below this a run of numbered lines is a list in the prose rather than a structure."""

_SHORTEST_SECTION = 10
"""Lines a first-level section must have before the next one starts.

A section has a body; a bibliography entry has three lines and a recommendation has one. The
EAU guideline's real sections are hundreds of lines apart and its reference list - which is
numbered `10. Haas, G.P` **with the dot**, so the dot alone does not exclude it - runs four
lines an entry. Found by running this on that document and reading the output.

Ten rather than twenty, measured: twenty also held, and cost a paper whose sections are real
(`1. Introduction`, `2. AI basic Terminology`). Five gained only an appendix whose numbering
restarts, which is a section of something but not of the document (ADR-076).
"""


class Section(BaseModel):
    """One numbered section, as the document itself labelled it."""

    model_config = ConfigDict(frozen=True)

    number: str
    """`3` or `3.2`, exactly as printed."""

    title: str
    """The title as extraction left it. `EPIDEMIOL OGY` is what the PDF gives, and repairing
    it here would mean editing what the document says (ADR-036)."""

    line: int
    """Where it starts, so a person can find it in their own editor."""

    @property
    def depth(self) -> int:
        """How deep it sits: 1 for `3`, 2 for `3.2`."""
        return self.number.count(".") + 1

    @property
    def top(self) -> str:
        """The first-level number this belongs under."""
        return self.number.split(".")[0]


def _candidates(text: str) -> list[Section]:
    """Every line shaped like a numbered heading, before the structural rules apply."""
    found: list[Section] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        match = _NUMBERED.match(raw)
        if not match:
            continue
        label, title = match.group(1), match.group(2)
        if _ENDS_IN_A_PAGE.search(title):
            continue
        if len(title) < 3 or len(title.split()) > _LONGEST_TITLE or not title[0].isupper():
            continue
        found.append(Section(number=label, title=title, line=number))
    return found


def sections_in(text: str) -> tuple[Section, ...]:
    """The sections a document numbers, or nothing when its numbering is not a structure.

    First-level numbers must run 1, 2, 3 without gaps and reach at least three, which is what
    separates a document's own outline from a list that happens to be numbered. A document
    that yields nothing is a document to look at rather than a silent gap - the same stance
    reference parsing takes (ADR-064).
    """
    found = _candidates(text)
    lines = text.count(chr(10)) + 1

    # First level: 1, 2, 3 with no gaps, each taken once and in the order they appear, and
    # each with enough of a body to be a section. Without the order, a `1.` far below the
    # `5.` was accepted as the first section; without the body, every entry of a numbered
    # bibliography was (ADR-076).
    tops: list[Section] = []
    wanted = 1
    for entry in found:
        if entry.depth == 1 and entry.number == str(wanted):
            tops.append(entry)
            wanted += 1
    kept: list[Section] = []
    for position, entry in enumerate(tops):
        ends_at = tops[position + 1].line if position + 1 < len(tops) else lines
        if ends_at - entry.line >= _SHORTEST_SECTION:
            kept.append(entry)
        else:
            break
    if len(kept) < _ENOUGH_SECTIONS:
        return ()

    # A subsection belongs to the section it sits inside, found by position rather than by
    # its number alone - a `2.1` appearing after section 5 is not filed under section 2.
    every = text.splitlines()
    inside: list[Section] = []
    for position, top in enumerate(kept):
        ends_at = kept[position + 1].line if position + 1 < len(kept) else lines
        inside.append(top)
        inside.extend(_under(top, every, ends_at))
    return tuple(sorted(inside, key=lambda s: s.line))


def _under(top: Section, lines: list[str], ends_at: int) -> list[Section]:
    """The subsections of one confirmed section, between it and the next.

    A title on the following line is taken from there. Guidelines print the number alone and
    the name beneath it, and a subsection with no name is still a place in the document.
    """
    pattern = _pattern_under(top.number)
    found: list[Section] = []
    for number in range(top.line, min(ends_at, len(lines) + 1)):
        match = pattern.match(lines[number - 1])
        if not match:
            continue
        label, title = match.group(1), match.group(2)
        if not title:
            following = next(
                (
                    lines[n].strip()
                    for n in range(number, min(number + 2, len(lines)))
                    if lines[n].strip()
                ),
                "",
            )
            title = following if len(following.split()) <= _LONGEST_TITLE else ""
        if title and (len(title.split()) > _LONGEST_TITLE or not title[0].isupper()):
            continue
        if _ENDS_IN_A_PAGE.search(title):
            continue
        found.append(Section(number=label, title=title, line=number))
    return found


def section_of(text: str, number: str) -> str:
    """The text of one section, from its heading to the next at the same depth or shallower.

    Returns empty when the document does not number that section. A caller asking for `6.3`
    gets `6.3` and everything nested under it, which is what somebody reading a guideline one
    part at a time means by a section.
    """
    found = sections_in(text)
    lines = text.splitlines()
    start = next((s for s in found if s.number == number), None)
    if start is None:
        return ""
    after = [
        s
        for s in found
        if s.line > start.line and (s.depth <= start.depth or not s.number.startswith(f"{number}."))
    ]
    ends_at = after[0].line - 1 if after else len(lines)
    return chr(10).join(lines[start.line - 1 : ends_at]).strip() + chr(10)
