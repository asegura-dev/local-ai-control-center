"""Reading back a collected corpus, so several can be assembled into one.

`collect` writes Markdown meant for a person. This reads it again, which is a thing to be
uneasy about: re-parsing prose that was generated is how a format becomes load-bearing
without anyone deciding it should be. The uneasiness is answered by a round-trip test - what
the writer produces, this reads back identically - and by re-checking every quotation
against its source rather than trusting the label that was written beside it.

That last part is not defensiveness. Corpora written before v1.2.0 carry a label that
conflated "in the document, page unknown" with "not in the document", which is the error
ADR-042 exists to correct. Re-checking makes an old corpus tell the truth without re-running
a model over it.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

_SECTION = re.compile(r"^## (.+)$")
_QUOTED = re.compile(r"^(?:- )?> (.+)$")
"""A quoted line, with or without the bullet an assembled corpus uses to mark a subject.

The bullet was added to the writer and broke the reader, which the round-trip test did not
catch because it only ever round-tripped an unmarked corpus. Two hundred and sixty-five
quotations were silently unreadable - the exact failure this module's docstring is uneasy
about, arriving by the exact route it predicted."""
_VERDICT = re.compile(r"^(p\. \d+|page unknown) - (.+)$")
_NEAREST = "Closest text in the source: "
_UNCOLLECTED = "**Not collected.**"


class CollectedClaim(BaseModel):
    """One claim as a corpus recorded it: the document, the quotation, the paraphrase."""

    model_config = ConfigDict(frozen=True)

    document: str
    quote: str
    claim: str = ""
    page: int | None = None
    recorded_verdict: str = ""
    """What the corpus said when it was written. Kept for comparison, never for deciding.

    A corpus written before v1.2.0 says `**NOT IN THE DOCUMENT**` for quotations that are in
    their document and could not be placed on a page. Re-checking is what decides; this only
    lets a reader see that the two disagree.
    """

    nearest: str = ""


def parse_corpus(text: str) -> tuple[CollectedClaim, ...]:
    """Read back what `collect` wrote.

    Documents that could not be collected contribute nothing: their section names a failure
    rather than a claim, and carrying an empty entry forward would put a document into an
    assembled corpus that has nothing in it.
    """
    claims: list[CollectedClaim] = []
    document = ""
    quote = verdict = ""
    page: int | None = None
    expecting_claim = False

    def flush(paraphrase: str) -> None:
        nonlocal quote, verdict, page, expecting_claim
        if quote:
            claims.append(
                CollectedClaim(
                    document=document,
                    quote=quote,
                    claim=paraphrase,
                    page=page,
                    recorded_verdict=verdict,
                )
            )
        quote = verdict = ""
        page = None
        expecting_claim = False

    for raw in text.splitlines():
        line = raw.strip()
        section = _SECTION.match(line)
        if section:
            flush("")
            document = section.group(1)
            continue
        if line.startswith(_UNCOLLECTED):
            continue
        quoted = _QUOTED.match(line)
        if quoted:
            flush("")
            quote = quoted.group(1).strip()
            continue
        outcome = _VERDICT.match(line)
        if outcome and quote:
            where, verdict = outcome.group(1), outcome.group(2).strip()
            page = int(where.removeprefix("p. ")) if where.startswith("p. ") else None
            expecting_claim = True
            continue
        if line.startswith(_NEAREST):
            # The writer puts this after the paraphrase, by which point the claim is
            # already closed. It belongs to the one just finished.
            if claims:
                claims[-1] = claims[-1].model_copy(
                    update={"nearest": line.removeprefix(_NEAREST).strip()}
                )
            continue
        if expecting_claim and line:
            flush(line)
    flush("")
    return tuple(claims)


def about(claims: tuple[CollectedClaim, ...], words: tuple[str, ...]) -> frozenset[str]:
    """The quotations that mention any of ``words``, folded the way containment folds.

    Returns which ones match rather than the matches themselves, so a caller can **mark**
    without removing. Nothing here decides what is relevant: the words come from the person
    whose subject it is, and a quotation can be about a subject without naming it. That was
    measured - pages chosen because they mentioned a term produced claims about adjuvant
    chemotherapy, and choosing by section heading did no better (ADR-046).
    """
    wanted = tuple(_folded(word) for word in words if word.strip())
    if not wanted:
        return frozenset()
    return frozenset(c.quote for c in claims if any(w in _folded(c.quote) for w in wanted))


def _folded(text: str) -> str:
    """Letters and digits only, lower case. Extraction spaces glyphs, not only words."""
    return "".join(character for character in text.lower() if character.isalnum())
