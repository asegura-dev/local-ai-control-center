"""Abstract port for asking what a work is, given its identifier (ADR-067).

Separate from every other port because it is a different question asked of a different
endpoint, and the only one whose endpoint is not the user's own machine or their own
network. A `Provider` is asked to write something; a `Registry` is asked to **recall**
something it already holds, and the difference is the whole point.

The measured reason this exists: asked for the journal a paper appeared in, with an explicit
instruction to say "not available" when it did not know, a 14B invented twelve journal names
out of twenty-four (ADR-047). A DOI resolves against a record somebody deposited. A journal
name recalled by a model resolves against nothing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class RegistryError(Exception):
    """Raised when the registry could not be reached or did not answer usefully.

    Distinct from a work the registry does not hold, which is an answer: `about` returns
    ``None`` for that. Reaching nothing and being told "no such work" are different facts
    and a bibliography that confused them would be wrong in a way nobody could see.
    """


class Work(BaseModel):
    """What a registry says a work is. Every field is what was deposited, never a guess.

    Frozen, and deliberately small. There is no abstract here: it is the one long free-text
    field a registry returns, it is the obvious carrier for an injection, and a bibliography
    does not need it. Refusing the field removes the vector rather than sanitising it
    (ADR-067).
    """

    model_config = ConfigDict(frozen=True)

    doi: str
    title: str = ""
    authors: tuple[str, ...] = ()
    container: str = ""
    """The journal, book or proceedings the work appeared in - the field a model invented."""

    year: int | None = None
    kind: str = ""
    """What the registry calls it: journal-article, posted-content, book-chapter."""

    fetched_on: str = ""
    """The date this was received, as YYYY-MM-DD.

    Carried because staleness is this project's most frequent defect: twelve wrong figures,
    several of them true sentences that had aged (ADR-042). A field with a date can be
    questioned; a field without one reads as current forever.
    """

    @property
    def says_anything(self) -> bool:
        """Whether the registry returned anything beyond the identifier it was given."""
        return bool(self.title or self.authors or self.container or self.year)


class Registry(ABC):
    """Anything that can say what a work is, given a DOI."""

    @abstractmethod
    def about(self, doi: str) -> Work | None:
        """What the registry holds for ``doi``, or ``None`` if it holds nothing.

        Raises `RegistryError` when the registry could not be reached at all. A caller
        resolving many identifiers needs to tell "this work is unknown" from "the network
        is down", because the first is a fact to record and the second is a run to retry.
        """
