"""Asking Crossref what a work is, and remembering the answer (ADR-067).

**The first destination in this project that is not the user's own machine or their own
network.** What leaves is a DOI: no document, no quotation, no corpus, no question, no
filename, and no text the user wrote.

Two things here are refusals rather than features. No contact address is sent, although
Crossref offers a faster queue to clients that supply one - that address is the user's, and
trading their personal data for throughput is not a decision this module makes on their
behalf. And no abstract is read, although Crossref often returns one: it is the single long
free-text field in the answer, it is the obvious carrier for an injection, and a bibliography
does not need it.

Everything that does come back is treated as hostile text: control characters removed, every
field bounded, and none of it ever put in front of a model.
"""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from local_ai_control_center.ports.registry import Registry, RegistryError, Work

TIMEOUT = 20.0
"""Seconds to wait for one answer. A registry that is slow is not a registry that is down."""

MOST_BYTES = 2_000_000
"""How much of an answer is read before giving up on it.

A record for one work is a few kilobytes. Reading an unbounded stream from a third party is
the one thing in this module that a timeout does not already bound - a slow answer stops, an
endless one does not (ADR-078)."""

_LONGEST_TITLE = 500
_LONGEST_NAME = 120
_LONGEST_CONTAINER = 300
_MOST_AUTHORS = 60
"""Bounds on what is accepted from a third party, so a field cannot become a payload."""

_EARLIEST_YEAR = 1500
_LATEST_YEAR = 2100


_TAG = re.compile(r"<[^>]{1,40}>")
"""Markup a publisher deposited inside a title: `<sup>68</sup> Ga-Labeled`.

Removed rather than rendered. A bibliography is read as text and in a terminal, and the tag
is noise in both - while `68 Ga-Labeled` is what the title says. Bounded in length so that a
stray `<` in a chemical name cannot swallow the rest of the line.
"""


def _clean(value: object, longest: int) -> str:
    """One field from the registry, as text that can be safely written into a file.

    Control characters go, including the ones that would let a line rewrite what is above
    it in a terminal. Length is bounded because nothing legitimate here is long, and a bound
    is a thing that holds whatever arrives.

    **Whitespace becomes a space rather than nothing**, which is not a detail. Dropping it
    outright turned a title broken across two lines into one with the words run together -
    `here` and `still` became `herestill` - the same class of damage `_normalized` exists to
    undo when a typesetter splits a word at a line break (ADR-035).
    """
    if not isinstance(value, str):
        return ""
    # Crossref hands back what the publisher deposited, which is XML: `Pathology &amp;
    # Oncology Research` and `<sup>68</sup> Ga-Labeled`. Found by reading the first real
    # bibliography this produced (ADR-067).
    unwrapped = html.unescape(_TAG.sub("", value))
    kept = "".join(" " if c.isspace() else c if c.isprintable() else "" for c in unwrapped)
    return " ".join(kept.split())[:longest]


def _year_from(issued: object) -> int | None:
    """The year in Crossref's `date-parts`, or nothing if it is not a plausible year."""
    if not isinstance(issued, dict):
        return None
    parts = issued.get("date-parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list) or not parts[0]:
        return None
    first = parts[0][0]
    if not isinstance(first, int) or not _EARLIEST_YEAR <= first <= _LATEST_YEAR:
        return None
    return first


def _authors_from(listed: object) -> tuple[str, ...]:
    """The author names, as the registry spells them, bounded in count and in length."""
    if not isinstance(listed, list):
        return ()
    names = []
    for entry in listed[:_MOST_AUTHORS]:
        if not isinstance(entry, dict):
            continue
        family = _clean(entry.get("family"), _LONGEST_NAME)
        given = _clean(entry.get("given"), _LONGEST_NAME)
        whole = f"{family}, {given}" if family and given else family or given
        if whole:
            names.append(whole)
    return tuple(names)


def _first_of(value: object, longest: int) -> str:
    """Crossref returns titles and journal names as lists. Take the first, bounded."""
    if isinstance(value, list):
        return _clean(value[0], longest) if value else ""
    return _clean(value, longest)


def work_from(message: dict[str, Any], doi: str, fetched_on: str) -> Work:
    """Build a `Work` from one Crossref record, reading only the fields decided on.

    A pure function over the parsed answer, so what this project accepts from a third party
    can be tested without a network (ADR-067). Anything not named here is not read, which
    includes the abstract.
    """
    return Work(
        doi=doi,
        title=_first_of(message.get("title"), _LONGEST_TITLE),
        authors=_authors_from(message.get("author")),
        container=_first_of(message.get("container-title"), _LONGEST_CONTAINER),
        year=_year_from(message.get("issued")),
        kind=_clean(message.get("type"), 60),
        fetched_on=fetched_on,
    )


class CrossrefRegistry(Registry):
    """Crossref over HTTP, reached at the address written in the configuration."""

    def __init__(self, url: str, mailto: str = "", timeout: float = TIMEOUT) -> None:
        self._url = url.rstrip("/")
        self._mailto = mailto.strip()
        self._timeout = timeout

    def about(self, doi: str) -> Work | None:
        """Ask the registry about one DOI.

        Returns ``None`` when the registry answers that it holds nothing, and raises when it
        could not be reached. A bibliography that confused the two would record "unknown"
        for a work that is perfectly well known, on a day the network was down.
        """
        wanted = doi.strip().lower()
        if not wanted:
            return None
        # Quoted, because a DOI is a third party's string and this is building a URL with
        # it. `safe` keeps the one separator a DOI legitimately contains.
        address = f"{self._url}/works/{urllib.parse.quote(wanted, safe='/')}"
        if self._mailto:
            # Only ever the address the user wrote in their own configuration file.
            address = f"{address}?mailto={urllib.parse.quote(self._mailto)}"
        request = urllib.request.Request(  # noqa: S310 - the scheme is checked on the way in
            address,
            headers={"Accept": "application/json", "User-Agent": "local-ai-control-center"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                body = response.read(MOST_BYTES + 1)
                if len(body) > MOST_BYTES:
                    raise RegistryError(
                        f"{self._url} answered with more than {MOST_BYTES:,} bytes "
                        f"for {doi}, which no record of one work is."
                    )
                payload = json.loads(body.decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise RegistryError(f"{self._url} answered {error.code} for {doi}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RegistryError(f"could not reach {self._url}: {error}") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RegistryError(f"{self._url} did not answer with JSON") from error

        message = payload.get("message") if isinstance(payload, dict) else None
        if not isinstance(message, dict):
            return None
        return work_from(message, wanted, datetime.now(UTC).strftime("%Y-%m-%d"))


class RememberedRegistry(Registry):
    """Another registry, with its answers kept on disk so nothing is asked twice.

    The cache is not an optimisation. A thesis has to be re-buildable, and a bibliography
    assembled from this is assembled from what was **actually received, on a date**, rather
    than from whatever the registry says next year. It also bounds what leaves: a DOI
    already answered is never sent again (ADR-067).
    """

    def __init__(self, behind: Registry, remembered: Path) -> None:
        self._behind = behind
        self._path = remembered
        self._known: dict[str, dict[str, Any]] = {}
        if remembered.exists():
            try:
                loaded = json.loads(remembered.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._known = {k: v for k, v in loaded.items() if isinstance(v, dict)}
            except (json.JSONDecodeError, OSError):
                # A damaged cache is re-asked, never guessed at. It is a memory of answers,
                # not a source, so losing it costs requests and nothing else.
                self._known = {}

    def holds(self, doi: str) -> bool:
        """Whether this DOI has already been answered, without asking anything."""
        return doi.strip().lower() in self._known

    def about(self, doi: str) -> Work | None:
        wanted = doi.strip().lower()
        if wanted in self._known:
            remembered = self._known[wanted]
            return Work(**remembered) if remembered else None
        answer = self._behind.about(wanted)
        self._known[wanted] = answer.model_dump() if answer else {}
        return answer

    def write(self) -> None:
        """Keep what was learned. Called once, after a run, never per answer."""
        self._path.write_text(json.dumps(self._known, indent=2, sort_keys=True), encoding="utf-8")
