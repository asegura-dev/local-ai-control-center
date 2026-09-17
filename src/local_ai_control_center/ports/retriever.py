"""Abstract port for choosing which passages go into a prompt.

The first component in LACC that discards material on the user's behalf. Every control
before it either refused or reported; this one chooses, which is why the contract requires
saying what was left behind rather than leaving that to an implementation's conscience
(ADR-050).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class Passage(BaseModel):
    """A piece of verified material a retriever can choose, in the port's own vocabulary.

    Not `CollectedClaim`, although a corpus is where these come from. A port depends on
    nothing outside itself, and the reason that rule earns its keep here is that a corpus
    entry carries things retrieval has no business with - what an older version of the
    writer labelled it, what the nearest text was when it failed. What choosing needs is the
    words, where they came from, and where to look.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    """The quotation: what will be sent, and what was already checked against its source."""

    source: str
    note: str = ""
    """The paraphrase that came with it. Matched on, never cited."""

    page: int | None = None


class Selection(BaseModel):
    """What a retriever chose, and what it did not.

    ``set_aside`` is not optional and not a detail. A selection that hides its discards
    turns a partial answer into a confident one, which is the shape of every wrong figure
    in this project's record - a model that covered ten of twenty-four documents and named
    none of the fourteen it dropped (ADR-050).
    """

    model_config = ConfigDict(frozen=True)

    chosen: tuple[Passage, ...] = ()
    set_aside: int = 0
    considered: int = 0
    how: str = ""
    """How the choosing was done, in words a reader can weigh."""

    @property
    def sent_everything(self) -> bool:
        """Whether nothing had to be left out, which is the case worth not warning about."""
        return self.set_aside == 0


class Retriever(ABC):
    """Anything that can pick passages for a question.

    Implementations may rank by words, by embeddings, or by something not invented yet. What
    they may not do is return a selection without a count of what it excluded.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identify the retriever, so a run can record which one chose."""

    @abstractmethod
    def select(self, question: str, passages: tuple[Passage, ...], budget_tokens: int) -> Selection:
        """Choose passages for ``question`` that fit ``budget_tokens``.

        The budget is in tokens because that is what runs out. An implementation that
        returned a fixed number of passages would overflow a window on long quotations and
        waste one on short ones.
        """
