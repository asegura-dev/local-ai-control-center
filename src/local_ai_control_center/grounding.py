"""Grounding: checking that a quotation appears in the document it claims to come from.

The one control in LACC that does not ask a model to behave (ADR-026). Every prompt that
says "add nothing the document does not contain" is a request; this is a check. A quotation
either appears in the source or it does not, and that is decided here by comparing strings,
with no model involved in deciding whether the model told the truth.

Everything in this module is a pure function over text.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

Verdict = Literal["verified", "not_found", "wrong_page", "page_unknown"]
"""What checking one quotation concluded. A closed set, not a free string."""

_PAGE_MARKER = re.compile(r"<!--\s*page\s+(\d+)\s*-->", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")


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
    found_on_page: int | None = None

    @property
    def holds(self) -> bool:
        """Whether the quotation was found where the claim said it would be."""
        return self.verdict == "verified"


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
    """Collapse whitespace and fold case, so layout differences do not hide a match."""
    return _WHITESPACE.sub(" ", text).casefold().strip()


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


def check_claim(claim: Claim, source: str) -> CheckedClaim:
    """Look for ``claim``'s quotation in ``source`` and report what was found.

    Exact substring after normalizing whitespace and case. Deliberately not fuzzy: a
    quotation that only nearly appears is not a quotation, and accepting near-misses would
    defeat the check (ADR-026).
    """
    needle = _normalized(claim.quote)
    if not needle or needle not in _normalized(source):
        return CheckedClaim(claim=claim, verdict="not_found")

    pages = pages_in(source)
    if not pages:
        return CheckedClaim(claim=claim, verdict="page_unknown")

    found_on = next(
        (number for number, text in pages if needle in _normalized(text)),
        None,
    )
    if claim.page is None or found_on is None:
        return CheckedClaim(claim=claim, verdict="page_unknown", found_on_page=found_on)
    if found_on != claim.page:
        return CheckedClaim(claim=claim, verdict="wrong_page", found_on_page=found_on)
    return CheckedClaim(claim=claim, verdict="verified", found_on_page=found_on)


def check_answer(answer: str, source: str) -> tuple[CheckedClaim, ...]:
    """Parse an answer into claims and check every quotation against ``source``."""
    return tuple(check_claim(claim, source) for claim in parse_claims(answer))
