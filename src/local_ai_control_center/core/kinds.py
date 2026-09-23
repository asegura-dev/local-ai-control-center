"""What a file in a workspace is, decided once (ADR-090).

A workspace holds papers somebody brought, corpora and bibliographies and reports this
program wrote, sections taken out of documents, and the list of topics a coverage run is
asked about. Telling them apart is one decision, and it was being made in two places - one
for `lacc status` and one for the window - which had already drifted nine files apart by the
time anybody counted.

**It decides what a file *is*, never what to do with it.** Grouping bibliographies, reviews
and coverage reports under "written by LACC" is a presentation decision and belongs to
whoever is drawing. Excluding the standing context file is a configuration decision and
belongs to whoever read the configuration.

Recognition is by how a file opens, which is a guess dressed as a fact: a paper whose first
line reads `# Bibliography` is filed wrong. Every recogniser here makes that trade, and errs
toward counting less rather than claiming more.
"""

from __future__ import annotations

import re
from pathlib import Path

CORPUS_MARKS = ("# Collected quotations", "# Claims collected by")
"""How a corpus opens. Two, because `collect` and `corpus` write different first lines."""

BIBLIOGRAPHY_MARK = "# Bibliography"
REVIEW_MARK = "# Review of"
COVERAGE_MARK = "# How far the nearest quotation is"

WRITTEN_BY_LACC = frozenset({"bibliography", "review", "coverage"})
"""The kinds this program produced rather than read.

Offered as a set because more than one caller groups them, and a second copy of the grouping
is how the decision above came to be made twice (ADR-090).
"""

_SAMPLE = 200
"""How much is read for the checks that look at the first line."""

_ENOUGH_FOR_A_LIST = 8_000
"""How much is read when every cheap check has missed.

Only reached by a file that is not a corpus, a bibliography, a review, a coverage report or
an extract, so it is read once, to look for a control marker a person writes at the end of a
short list. Anything with nothing of the sort this far in is a document.
"""

_SECTION_OPENING = re.compile(r"^\s{0,3}\d{1,2}(?:\.\d{1,2}){0,2}\.?(?:\s|$)")
"""How a file written by `sections --take` opens: with the number of the section it is.

Counted apart from the documents somebody brought, because it is neither - it came out of
one of them. The first reading of this counted six documents "with no quotation" of which
three were extracted sections and one was a page of the user's own notes (ADR-080).
"""

_A_CONTROL_TOPIC = re.compile(r"(?m)^!\s*\S")
"""How a topics file is recognised: a line marked as the control.

Not a heading, because a topics list has none worth requiring. The control marker is the one
thing `coverage` **refuses to run without** (ADR-088), so every usable topics file carries
one, and a line opening with `!` is not markdown for anything else.

Looked for anywhere in the opening rather than on the first line, because a person writes the
control **last** - it is the odd one out, and that is where an odd one out goes.
"""


def kind_of(path: Path) -> str:
    """What ``path`` announces itself to be.

    `other` for anything that is not Markdown this project reads, and for a file that cannot
    be opened - an unreadable file is not a document with no quotations in it.
    """
    if path.suffix != ".md":
        return "other"
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            more = handle.read(_ENOUGH_FOR_A_LIST)
    except OSError:
        return "other"

    opening = more[:_SAMPLE]
    if opening.startswith(CORPUS_MARKS):
        return "corpus"
    if opening.startswith(BIBLIOGRAPHY_MARK):
        return "bibliography"
    if opening.startswith(REVIEW_MARK):
        return "review"
    if opening.startswith(COVERAGE_MARK):
        return "coverage"
    first = opening.splitlines()[0] if opening.splitlines() else ""
    if _SECTION_OPENING.match(first):
        return "extract"
    if _A_CONTROL_TOPIC.search(more):
        return "topics"
    return "document"
