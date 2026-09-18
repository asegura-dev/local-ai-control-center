"""Grounding: checking that a quotation appears in the document it claims to come from.

The one control in LACC that does not ask a model to behave (ADR-026). Every prompt that
says "add nothing the document does not contain" is a request; this is a check. A quotation
either appears in the source or it does not, and that is decided here by comparing strings,
with no model involved in deciding whether the model told the truth.

Everything in this module is a pure function over text.
"""

from __future__ import annotations

import difflib
import json
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
    def found(self) -> bool:
        """Whether the quotation is in the document at all.

        The question that decides whether something can be cited. A quotation spanning a
        page break is real and has no single page, and counting it beside a fabrication
        reports the tool's limit as the model's dishonesty - which is what a corpus of 237
        quotations showed: 72 unplaceable, and **zero** not in their document (ADR-042).
        """
        return self.verdict in ("verified", "page_unknown")

    @property
    def holds(self) -> bool:
        """Whether the quotation was found and its page could be named."""
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


def _complete_entries_in(text: str) -> list[object] | None:
    """Every entry of a shaped answer that arrived whole, from a document cut short.

    A truncated JSON answer parses to nothing at all: one unclosed brace and the whole
    document is lost, where a truncated line-oriented answer yields every complete block
    before the cut. That asymmetry was measured and it is not small - an answer stopped at
    the token cap gave 19 claims as lines and **0** as JSON, four runs out of four (ADR-052).

    So the entries are walked one value at a time with `raw_decode`, which reports where each
    ended. Nothing is repaired and nothing is guessed: the entry that was cut is dropped
    whole, along with anything after it.
    """
    opens = text.find(chr(34) + "entries" + chr(34))
    bracket = text.find("[", opens) if opens >= 0 else -1
    if bracket < 0:
        return None
    decoder = json.JSONDecoder()
    entries: list[object] = []
    at = bracket + 1
    while True:
        while at < len(text) and (text[at].isspace() or text[at] == ","):
            at += 1
        if at >= len(text) or text[at] != "{":
            break
        try:
            entry, at = decoder.raw_decode(text, at)
        except ValueError:
            break
        entries.append(entry)
    return entries or None


def _from_json(text: str, fields: tuple[str, ...], quote_field: str) -> tuple[Claim, ...] | None:
    """Read an answer the engine was made to shape, or return nothing and let lines be tried.

    Returns ``None`` rather than an empty tuple when this is not JSON, so that a model which
    ignored a schema - or a provider that could not enforce one - still gets parsed the way
    it always was. Enforcement improves a path that works; it does not replace it (ADR-052).
    """
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        loaded = json.loads(stripped)
    except ValueError:
        entries = _complete_entries_in(stripped)
        if entries is None:
            return None
    else:
        found = loaded.get("entries") if isinstance(loaded, dict) else None
        if not isinstance(found, list):
            return None
        entries = found

    describes = next((name for name in fields if name != quote_field), fields[0] if fields else "")
    claims: list[Claim] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        said, quoted = (
            str(entry.get(describes, "")).strip(),
            str(entry.get(quote_field, "")).strip(),
        )
        if not said or not quoted:
            continue
        digits = "".join(c for c in str(entry.get("page", "")) if c.isdigit())
        claims.append(
            Claim(
                claim=said,
                quote=quoted.strip("\"'" + chr(0x201C) + chr(0x201D)),
                page=int(digits) if digits else None,
            )
        )
    return tuple(claims)


def parse_claims(
    text: str,
    fields: tuple[str, ...] = ("claim", "quote", "page"),
    quote_field: str = "quote",
) -> tuple[Claim, ...]:
    """Read the claims a model returned, skipping anything malformed.

    Line-oriented rather than JSON, because a small local model follows it far more
    reliably and a malformed block costs one claim instead of the whole answer. A block
    without both a claim and a quotation is dropped: there is nothing to check.

    ``fields`` are the labels to look for, in order, and the first of them starts a new
    block. A skill declared in a file names its own (ADR-048); the defaults are what the
    built-in skills ask for. ``quote_field`` says which label carries the document's own
    words, and it is the only one that gets checked - everything else is the model's prose
    and is returned for a person to read.
    """
    structured = _from_json(text, fields, quote_field)
    if structured is not None:
        return structured

    claims: list[Claim] = []
    current: dict[str, str] = {}
    opens = fields[0] if fields else "claim"
    describes = next((name for name in fields if name != quote_field), opens)

    def flush() -> None:
        if describes in current and quote_field in current:
            raw_page = current.get("page", "")
            digits = "".join(character for character in raw_page if character.isdigit())
            claims.append(
                Claim(
                    claim=current[describes],
                    quote=current[quote_field].strip("\"'“”"),
                    page=int(digits) if digits else None,
                )
            )
        current.clear()

    for line in text.splitlines():
        # Emphasis is stripped before matching. A model asked for `CLAIM:` may write
        # `**CLAIM:**`, and it does - which made a skill that declared it verified
        # quotations verify none of them, and report that it had.
        stripped = line.strip().lstrip("*_#- ")
        lowered = stripped.lower()
        for field in fields:
            if lowered.startswith(f"{field}:") or lowered.startswith(f"{field}**:"):
                _, _, value = stripped.partition(":")
                if field == opens:
                    flush()
                current[field] = value.strip().lstrip("*_ ").strip()
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


def _unspaced(text: str) -> str:
    """Normalize, then drop spacing entirely, to decide whether a quotation is present.

    Kept apart from `_normalized` because it answers a different question. Containment asks
    whether the words are in the document; similarity asks how close two sentences are, and
    difflib needs the gaps to answer that. Only the first uses this.

    Extraction sometimes emits a word as `A c c o r d i n gt o`, spacing driven by glyph
    positions rather than by the text. Under `_normalized` alone such a page defeats every
    quotation taken from it, and a faithful quotation returns `not_found` - which this module
    defines as a fabrication, the thing the check exists for. Measured over the 237
    quotations of a real bibliography: 22 were real and reported as fabrications for this
    reason alone, and 231 quotations mutated by one word or one digit still failed, under
    this folding and the previous one alike (ADR-044).

    Word boundaries go with the spaces, so a short enough quotation could match across one.
    The mutation test does not probe that, and it is the known cost of the change.
    """
    return _WHITESPACE.sub("", _normalized(text))


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


def page_spans(source: str) -> tuple[tuple[int, int, int], ...]:
    """Where each page begins and ends in ``source``, with its marker inside the span.

    The companion to `pages_in`, which returns page *text* and drops the marker. This
    returns offsets instead, so a caller can slice the source and get back something that
    still looks like an ingested document - markers and all. `passes` needs that: a reading
    of part of a document should have the same shape as a reading of all of it.
    """
    markers = list(_PAGE_MARKER.finditer(source))
    if not markers:
        return ()
    spans = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(source)
        spans.append((int(marker.group(1)), marker.start(), end))
    return tuple(spans)


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

    Exact substring after folding case and spacing away. Deliberately not fuzzy: a
    quotation that only nearly appears is not a quotation, and accepting near-misses would
    defeat the check (ADR-026).

    The page is **found here, not taken from the claim**. Locating the quotation is already
    how it gets verified, so the page falls out of work being done anyway - and it is right
    by construction, where a model asked to remember a page is wrong often enough to put a
    bad citation into a thesis (ADR-031). What the model said is kept on the claim, for
    comparison, and never reported as the answer.
    """
    needle = _unspaced(claim.quote)
    # The markers are stripped before the search. They are LACC's own annotation, not the
    # document's words, and a sentence that runs across a page break has one sitting inside
    # it - which made every quotation spanning a page impossible to verify, in every
    # multi-page document (ADR-035).
    if not needle or needle not in _unspaced(_MARKER.sub(" ", source)):
        return CheckedClaim(
            claim=claim, verdict="not_found", nearest=nearest_text(claim.quote, source)
        )

    # Located per page against the raw source, so a quotation spanning a break belongs to
    # no single page and is reported as such rather than attributed to one of them.
    pages = pages_in(source)
    found_on = next((number for number, text in pages if needle in _unspaced(text)), None)
    if found_on is None:
        # A sentence that runs across a break belongs to no single page, which is not the
        # same as belonging to none. Adjacent pairs are searched and the page it *starts*
        # on is reported - the one a reader would turn to.
        found_on = next(
            (
                pages[index][0]
                for index in range(len(pages) - 1)
                if needle in _unspaced(pages[index][1] + " " + pages[index + 1][1])
            ),
            None,
        )
    if found_on is None:
        return CheckedClaim(claim=claim, verdict="page_unknown")
    return CheckedClaim(claim=claim, verdict="verified", found_on_page=found_on)


def without_repeats(claims: tuple[CheckedClaim, ...]) -> tuple[CheckedClaim, ...]:
    """Drop quotations already seen, and those wholly inside one that was, keeping the longer.

    A document read in overlapping passes offers the overlapping page twice, and the same
    passage quoted twice is one quotation (ADR-045). Folded the way containment folds, so a
    difference nobody can see does not become two entries.

    **Containment, not similarity.** The second pass rarely repeats a passage word for word;
    it takes the same sentence with different boundaries, and equality misses that entirely.
    A quotation wholly inside another is the same passage read twice, and the longer one is
    kept because it is a superset of the shorter - nothing verified is lost by preferring it.
    The order of what survives is the document's, not the order the dropping happened in.

    Exact and unthresholded, and that is the whole design. A threshold on similarity would
    be wrong here, and the corpus says so: the two most alike quotations in it that are not
    identical differ by one word - `Apalutamide` against `Darolutamide` - and that word is
    the entire content. Anything willing to merge at 0.86 would merge those (ADR-054).

    Merged on the quotation rather than on the claim. Two different readings of one sentence
    collapse into one, which is the cost: the quotation is what carries authority here, and
    a corpus with the same sentence in it twice is worse than a reading lost.

    Called with the claims of one document, so containment never reaches across documents -
    where the same sentence in two papers is a fact about the literature, not a repeat.
    """
    folded = [_unspaced(checked.claim.quote) for checked in claims]
    # Longest first, so a passage read twice is represented by the fuller reading. The sort
    # is stable, so two identical quotations keep the earlier - the behaviour this had before
    # containment was added, of which equality is now just the tied case.
    longest_first = sorted(range(len(claims)), key=lambda i: -len(folded[i]))
    kept: list[int] = []
    for index in longest_first:
        quotation = folded[index]
        if not quotation or any(quotation in folded[other] for other in kept):
            continue
        kept.append(index)
    return tuple(claims[index] for index in sorted(kept))


def check_answer(
    answer: str,
    source: str,
    fields: tuple[str, ...] = ("claim", "quote", "page"),
    quote_field: str = "quote",
) -> tuple[CheckedClaim, ...]:
    """Parse an answer into claims and check every quotation against ``source``.

    The field names come from the skill, so a declared one is checked by the same code as a
    built-in one. A declaration chooses which label carries the quotation; it cannot choose
    how the checking is done (ADR-048).
    """
    return tuple(check_claim(claim, source) for claim in parse_claims(answer, fields, quote_field))
