"""Judging a reading by asking the engine that is already configured (ADR-053).

No new dependency. This project installs with seven packages, and a deep-learning stack to
check paraphrases would cost everyone who never uses it. A purpose-built entailment model is
likely better and stays possible behind the same port; it is not first because the
measurement that would justify the dependency has not been taken.

The answer is constrained by a schema, so the model can only emit one of three labels
(ADR-052). That does not make it right - it makes it parseable.
"""

from __future__ import annotations

import json
from typing import Any

from local_ai_control_center.ports.entailment import Judge, Judgement
from local_ai_control_center.ports.provider import Provider

_VERDICTS = ("follows", "contradicts", "neither")

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(_VERDICTS)},
        "why": {"type": "string"},
    },
    "required": ["verdict", "why"],
}

_ASKED = """You are checking one thing only: whether a sentence taken from a document
supports a reading somebody made of it.

THE SENTENCE FROM THE DOCUMENT:
{quotation}

THE READING:
{claim}

Answer `follows` only if the reading is supported by that sentence alone. Answer
`contradicts` if the sentence says otherwise. Answer `neither` if the sentence is about
something else, names a different subject, or simply does not settle it - a reading that may
well be true but is not established by these words is `neither`, not `follows`.

Judge the sentence in front of you. Do not use anything you know about the subject."""


class AskingJudge(Judge):
    """Ask the configured engine whether a quotation supports a claim.

    A model judging a model. The port says so and so does this: what comes back is an
    opinion produced deterministically, not a fact produced mechanically.
    """

    def __init__(self, provider: Provider) -> None:
        """Judge with whatever provider the run was given."""
        self._provider = provider

    @property
    def name(self) -> str:
        """Identify this judge, and the model behind it, in a record."""
        return f"asking:{self._provider.name}"

    def judge(self, claim: str, quotation: str) -> Judgement:
        """Say whether the quotation supports the claim, or that it could not tell.

        An unreachable engine, an unparseable reply or a label nobody asked for all become
        `undecided`. This runs over hundreds of claims, and one failure must cost one claim.
        """
        if not claim.strip() or not quotation.strip():
            return Judgement(verdict="undecided", detail="Nothing to judge.")
        try:
            answer = self._provider.complete(
                _ASKED.format(quotation=quotation.strip(), claim=claim.strip()), 0.0, _SCHEMA
            )
        except Exception as error:  # noqa: BLE001 - one claim, not the traverse (ADR-053)
            return Judgement(verdict="undecided", detail=f"The judge could not answer: {error}")

        try:
            said = json.loads(answer.text.strip())
        except ValueError:
            return Judgement(verdict="undecided", detail="The judge did not answer in shape.")
        verdict = str(said.get("verdict", "")).strip().lower()
        if verdict not in _VERDICTS:
            return Judgement(verdict="undecided", detail=f"Unknown verdict: {verdict!r}")
        return Judgement(verdict=verdict, detail=str(said.get("why", "")).strip())  # type: ignore[arg-type]
