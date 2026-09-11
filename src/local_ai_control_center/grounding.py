"""Grounding: checking that a quotation appears in the document it claims to come from.

The one control in LACC that does not ask a model to behave (ADR-026). Every prompt that
says "add nothing the document does not contain" is a request; this is a check. A quotation
either appears in the source or it does not, and that is decided here by comparing strings,
with no model involved in deciding whether the model told the truth.

Everything in this module is a pure function over text.
"""

from __future__ import annotations

import difflib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

Verdict = Literal["verified", "not_found", "page_unknown"]
"""What checking one quotation concluded. A closed set, not a free string."""

_PAGE_MARKER = re.compile(r"<!--\s*page\s+(\d+)\s*-->", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_MARKER = re.compile(r"<!--.*?-->", re.DOTALL)
_HYPHEN_BETWEEN_LETTERS = re.compile(r"([^\W\d_])\s*-\s*([^\W\d_])")
"""A hyphen between two letters, with or without space around it, is removed.

Requiring whitespace after it was the obvious rule and it was wrong. It fixed
`sensi- tivity`, and it broke `inter- reader`: that is a real compound the typesetter
happened to split at its own hyphen, so the document normalised to `interreader` while a
model writing `inter-reader` did not - an asymmetry this function created, reported as a
fabrication.

The two cases cannot be told apart from the text, so both sides are treated the same. A
hyphen between letters is representation: a typesetter can insert one at a line break or
leave one out, and a reader sees the same word either way. Numbers keep theirs, because
`the 5 - 10 range` is a range and joining it would be a worse error than the one fixed.
"""

_LOOK_ALIKES = str.maketrans(
    {
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "―": "-",
        "−": "-",
        "‘": "'",
        "’": "'",
        "‛": "'",
        "“": '"',
        "”": '"',
        "‟": '"',
        "′": "'",
        "″": '"',
    }
)
"""Typographic characters folded to the ASCII a model writes when it reproduces them.

A paper is typeset with en-dashes, curly quotes and non-breaking hyphens; a model reading
`76–90%` writes `76-90%`, because that is what the range means and what a keyboard has.
The two are the same text to any reader and different to a substring search, and that
difference was being reported as fabrication. Measured on one paper: sixteen of its
hundred and sixty sentences could not be verified even when quoted perfectly (ADR-035).
"""

_SHORTEST_CANDIDATE = 40
"""Below this a sentence is a heading, a caption or a stray line, not something a
quotation was drawn from."""

_CLOSE_ENOUGH = 0.6
"""`difflib`'s own default. A published number rather than one tuned until the examples
looked right, and a weak suggestion is worse than none (ADR-034)."""


class Claim(BaseModel):
    """One thing a model says a document asserts, with the words it says prove it.

    Frozen. The quotation is what gets checked; the claim itself cannot be, which is the
    boundary of what this module can promise (ADR-026).
    """

    model_config = ConfigDict(frozen=True)

    claim: str
    quote: str
    page: int | None = None


class CheckedClaim(BaseModel):
    """A claim after its quotation was looked for in the source."""

    model_config = ConfigDict(frozen=True)

    claim: Claim
    verdict: Verdict
    nearest: str = ""
    """The closest text actually in the source, when the quotation was not found.

    Empty unless something was close enough to be worth showing. It reports a match, not a
    reconstruction: LACC has compared strings and does not know what the model was reaching
    for (ADR-034).
    """

    found_on_page: int | None = None
    """The page LACC located the quotation on. Correct by construction: it comes from
    searching the text, not from a model recalling where it read something (ADR-031)."""

    @property
    def holds(self) -> bool:
        """Whether the quotation was found in the source."""
        return self.verdict == "verified"

    @property
    def page_disagreed(self) -> bool:
        """Whether the model placed a correctly-quoted passage on the wrong page.

        Not shown to the reader, who wants the right page rather than a note about
        somebody else's error. Recorded in the audit, where a fidelity signal belongs.
        """
        return (
            self.claim.page is not None
            and self.found_on_page is not None
            and self.claim.page != self.found_on_page
        )


def parse_claims(text: str) -> tuple[Claim, ...]:
    """Read the claims a model returned, skipping anything malformed.

    Line-oriented rather than JSON, because a small local model follows it far more
    reliably and a malformed block costs one claim instead of the whole answer. A block
    without both a claim and a quotation is dropped: there is nothing to check.
    """
    claims: list[Claim] = []
    current: dict[str, str] = {}

    def flush() -> None:
        if "claim" in current and "quote" in current:
            raw_page = current.get("page", "")
            digits = "".join(character for character in raw_page if character.isdigit())
            claims.append(
                Claim(
                    claim=current["claim"],
                    quote=current["quote"].strip("\"'“”"),
                    page=int(digits) if digits else None,
                )
            )
        current.clear()

    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        for field in ("claim", "quote", "page"):
            if lowered.startswith(f"{field}:"):
                if field == "claim":
                    flush()
                current[field] = stripped[len(field) + 1 :].strip()
                break
    flush()
    return tuple(claims)


def _normalized(text: str) -> str:
    """Reduce text to what a reader sees, so representation cannot hide a real quotation.

    Four transformations, and every one of them removes a difference nobody can see: curly
    quotes and typographic dashes fold to the ASCII a model writes, words the typesetter
    broke across a line are rejoined, whitespace collapses, and case folds. None of them
    touches content - a changed word or a changed number survives all four and still fails,
    which is the whole point (ADR-035).

    Rejoining was added after a real paper produced two "fabrications" that were nothing of
    the kind. The model had quoted faithfully; the PDF held `sensi- tivity` and
    `avail - able` across line breaks, and LACC's own ingestion preserved them. The check
    was reporting a defect in this project as dishonesty in the model (ADR-034).
    """
    folded = text.translate(_LOOK_ALIKES)
    joined = _HYPHEN_BETWEEN_LETTERS.sub(lambda m: m.group(1) + m.group(2), folded)
    return _WHITESPACE.sub(" ", joined).casefold().strip()


def pages_in(source: str) -> tuple[tuple[int, str], ...]:
    """Split ``source`` into its pages, using the markers ingestion preserved.

    Returns pairs of page number and text. A source with no markers - anything LACC did
    not ingest - yields nothing, and page checking then reports itself as unable rather
    than as failed.
    """
    markers = list(_PAGE_MARKER.finditer(source))
    if not markers:
        return ()
    pages = []
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(source)
        pages.append((int(marker.group(1)), source[start:end]))
    return tuple(pages)


def nearest_text(quote: str, source: str) -> str:
    """Return the sentence in ``source`` most like ``quote``, or empty when none is close.

    For the failure that matters most: a model that takes a real sentence and changes the
    number in it. The structure, the wording and the topic are right, and only the figure -
    the part that would be copied into a table - is false. Verifying already means searching
    the document, so when the search fails the tool has what it needs to say what the
    document does contain, instead of leaving someone to hunt through a PDF for a sentence
    they have just been told is wrong.

    This never softens the refusal. The quotation is still not found; this sits beside that
    verdict as a lead (ADR-026, ADR-034).
    """
    needle = _normalized(quote)
    if not needle:
        return ""
    plain = _MARKER.sub(" ", source)
    candidates = [
        sentence.strip()
        for sentence in _SENTENCE_END.split(plain)
        if len(sentence.strip()) >= _SHORTEST_CANDIDATE
    ]
    if not candidates:
        return ""

    matcher = difflib.SequenceMatcher()
    matcher.set_seq2(needle)
    best, best_ratio = "", _CLOSE_ENOUGH
    for candidate in candidates:
        matcher.set_seq1(_normalized(candidate))
        # quick_ratio is an upper bound and much cheaper; skip anything that cannot win.
        if matcher.quick_ratio() < best_ratio:
            continue
        ratio = matcher.ratio()
        if ratio >= best_ratio:
            best, best_ratio = candidate, ratio
    return _WHITESPACE.sub(" ", best)


def check_claim(claim: Claim, source: str) -> CheckedClaim:
    """Look for ``claim``'s quotation in ``source`` and report what was found.

    Exact substring after normalizing whitespace and case. Deliberately not fuzzy: a
    quotation that only nearly appears is not a quotation, and accepting near-misses would
    defeat the check (ADR-026).

    The page is **found here, not taken from the claim**. Locating the quotation is already
    how it gets verified, so the page falls out of work being done anyway - and it is right
    by construction, where a model asked to remember a page is wrong often enough to put a
    bad citation into a thesis (ADR-031). What the model said is kept on the claim, for
    comparison, and never reported as the answer.
    """
    needle = _normalized(claim.quote)
    # The markers are stripped before the search. They are LACC's own annotation, not the
    # document's words, and a sentence that runs across a page break has one sitting inside
    # it - which made every quotation spanning a page impossible to verify, in every
    # multi-page document (ADR-035).
    if not needle or needle not in _normalized(_MARKER.sub(" ", source)):
        return CheckedClaim(
            claim=claim, verdict="not_found", nearest=nearest_text(claim.quote, source)
        )

    # Located per page against the raw source, so a quotation spanning a break belongs to
    # no single page and is reported as such rather than attributed to one of them.
    found_on = next(
        (number for number, text in pages_in(source) if needle in _normalized(text)),
        None,
    )
    if found_on is None:
        return CheckedClaim(claim=claim, verdict="page_unknown")
    return CheckedClaim(claim=claim, verdict="verified", found_on_page=found_on)


def check_answer(answer: str, source: str) -> tuple[CheckedClaim, ...]:
    """Parse an answer into claims and check every quotation against ``source``."""
    return tuple(check_claim(claim, source) for claim in parse_claims(answer))
