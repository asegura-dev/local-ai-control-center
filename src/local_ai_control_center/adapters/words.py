"""Choosing passages by the words a question uses. No model, no network (ADR-050).

Deterministic and explainable, which is the whole argument for it being first. An embedding
model may rank better; nobody here has measured that it does, and until somebody has, the
implementation whose reasoning a person can read is the one that ships.

The ranking is ordinary: how many of the question's words a passage uses, how rare each word
is across the corpus, and a mild preference for shorter passages so a long quotation cannot
win by sheer surface area. Nothing here is novel and nothing here needs to be.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from local_ai_control_center.core.budget import estimate_tokens
from local_ai_control_center.ports.retriever import Passage, Retriever, Selection

_WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
"""Runs of three or more letters. Digits are left out deliberately: a question about
sensitivity should not be drawn to every passage mentioning a page number."""

_TOO_COMMON = frozenset(
    [
        "the",
        "and",
        "for",
        "that",
        "with",
        "this",
        "from",
        "were",
        "was",
        "are",
        "has",
        "have",
        "been",
        "not",
        "but",
        "which",
        "they",
        "their",
        "los",
        "las",
        "una",
        "para",
        "que",
        "con",
        "del",
        "por",
        "como",
        "este",
        "esta",
        "sobre",
        "entre",
        "cuando",
        "donde",
    ]
)
"""Words carried by everything, in the two languages this project is written and used in.

Short and unclever. A longer list is a tuning exercise, and the rarity weighting below
already demotes anything that appears everywhere.
"""


def _words(text: str) -> list[str]:
    """The words of a piece of text, folded the way everything here folds them."""
    return [word for word in _WORD.findall(text.lower()) if word not in _TOO_COMMON]


class WordRetriever(Retriever):
    """Rank passages by the question's words, and say how many were left out."""

    @property
    def name(self) -> str:
        """Identify this retriever in a record."""
        return "words"

    def select(self, question: str, passages: tuple[Passage, ...], budget_tokens: int) -> Selection:
        """Choose the passages whose words best match the question, up to the budget.

        A passage matching none of the question's words is never chosen, even when the
        budget would allow it. Filling a prompt to the brim with material that has nothing
        to do with the question is how a model is given permission to invent a connection.
        """
        asked = _words(question)
        if not asked or not passages:
            return Selection(considered=len(passages), set_aside=len(passages), how=self.name)

        rarity = _rarity(passages)
        scored = [
            (score, index, passage)
            for index, passage in enumerate(passages)
            if (score := _score(passage, asked, rarity)) > 0
        ]
        # Index breaks ties, so the order a corpus was assembled in decides rather than
        # whatever order the sort happens to produce. A selection that changed between two
        # identical runs would make the audit's record of it worthless.
        scored.sort(key=lambda entry: (-entry[0], entry[1]))

        chosen: list[Passage] = []
        used = 0
        for _, _, passage in scored:
            cost = estimate_tokens(passage.text) + estimate_tokens(passage.note)
            if used + cost > budget_tokens:
                continue
            chosen.append(passage)
            used += cost

        return Selection(
            chosen=tuple(chosen),
            set_aside=len(passages) - len(chosen),
            considered=len(passages),
            how=f"{self.name}: {len(asked)} words from the question, {len(scored)} passages "
            f"matched at least one",
        )


def _rarity(passages: tuple[Passage, ...]) -> dict[str, float]:
    """How unusual each word is across the corpus, as an inverse document frequency.

    A word every passage carries tells you nothing about which passage to read; a word two
    passages carry tells you a great deal. This is the oldest idea in retrieval and it is
    here because it is cheap and because anybody can check it.
    """
    seen: Counter[str] = Counter()
    for passage in passages:
        seen.update(set(_words(passage.text + " " + passage.note)))
    total = len(passages)
    return {word: math.log(1 + total / count) for word, count in seen.items()}


def _score(passage: Passage, asked: list[str], rarity: dict[str, float]) -> float:
    """How well one passage answers to the question's words.

    Divided by the square root of its length: a long quotation carries more words and would
    otherwise win by size rather than by fit.
    """
    carried = Counter(_words(passage.text + " " + passage.note))
    if not carried:
        return 0.0
    hit = sum(rarity.get(word, 0.0) for word in set(asked) if word in carried)
    return hit / math.sqrt(sum(carried.values()))
