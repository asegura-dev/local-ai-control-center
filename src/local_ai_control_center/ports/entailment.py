"""Abstract port for judging whether a quotation supports the reading given of it.

**This is the one check here that is a judgement rather than a measurement**, and the port
says so where an implementer will see it. Every other control in this project compares
strings, walks a hash chain or resolves a path: exact, cheap, opinionless. This one asks a
model about meaning, and can be wrong in both directions (ADR-053).

It exists because the gap it covers stopped being theoretical. A quotation about choline
PET/CT was verified, and the paragraph above it attributed choline's figures to PSMA. Every
mechanical control passed it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict

Verdict = Literal["follows", "contradicts", "neither", "undecided"]
"""What a judge can say about a reading.

``undecided`` is not a fourth kind of answer about the text - it is the judge failing, and it
is a value rather than an exception so that one unanswerable pair costs one pair rather than
a corpus.
"""


class Judgement(BaseModel):
    """What a judge concluded about one claim and the words it rests on."""

    model_config = ConfigDict(frozen=True)

    verdict: Verdict
    detail: str = ""
    """Why, in the judge's words, for a person deciding whether to believe it."""

    asked: str = ""
    """Exactly what the judge put to whatever answered it.

    So a trail can record the digest of what was sent, which is otherwise the one thing
    about these calls that varies and is not written down: the quotation and the claim are
    recorded by the caller, and a change to the judge's own wording would leave no trace at
    all. A judgement that cannot say what it was asked is a weaker record than the rest of
    this project keeps (ADR-059).

    Empty is allowed, for a judge that does not compose a prompt - a model run locally
    against a pair of sentences has nothing of this shape to report.
    """

    @property
    def supported(self) -> bool:
        """Whether the reading was judged to follow.

        False for `undecided`, deliberately: a judge that could not answer has not said the
        reading is fine, and treating silence as approval is how a check becomes decoration.
        """
        return self.verdict == "follows"

    @property
    def worth_a_look(self) -> bool:
        """Whether a person should read this one before citing it."""
        return self.verdict in ("contradicts", "neither")


class Judge(ABC):
    """Anything that can say whether a quotation supports a claim made from it.

    Implementations may prompt a general model, run a purpose-built entailment model, or do
    something not invented yet. What they may not do is present the answer as the same kind
    of fact the quotation check produces.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identify the judge, so a run can record who judged."""

    @abstractmethod
    def judge(self, claim: str, quotation: str) -> Judgement:
        """Say whether ``quotation`` supports ``claim``.

        Never raises for an answer it could not get: an unreachable engine or an unparseable
        reply is `undecided`, because this runs over hundreds of claims and one failure must
        not end the traverse.
        """
