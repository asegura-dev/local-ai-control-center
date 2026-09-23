"""Choosing passages by meaning, and fusing that with choosing by words (ADR-061).

Word ranking finds a rare term - a tracer name, a cohort size - and cannot see that *nodal
staging* and *lymph node involvement* are one subject. Dense ranking sees the subject and
smooths the rare term away. Neither is the better one, which is why the fused retriever here
holds both and why the word retriever is not removed.

**This ranks by similarity in a space nobody can inspect**, so it is a judgement in the sense
ADR-053 means, not a measurement. What protects the answer is unchanged: every passage it can
choose was already checked against the document it names, and every selection still says how
much it set aside.
"""

from __future__ import annotations

import math
from pathlib import Path

from local_ai_control_center.adapters.vectors import key_for, remember, remembered
from local_ai_control_center.core.budget import estimate_tokens
from local_ai_control_center.ports.embedder import Embedder
from local_ai_control_center.ports.retriever import Passage, Retriever, Selection

_FUSION_CONSTANT = 60
"""The `k` of Reciprocal Rank Fusion, from the paper that published it.

A number taken rather than fitted. Blending two rankings with a weight would mean choosing
that weight, and this project has a rule about numbers invented until the examples look
right (ADR-034). RRF needs no weight: each ranking contributes the inverse of its position,
and `k` only flattens how sharply the top of a list counts.
"""


def _unit(vector: tuple[float, ...]) -> tuple[float, ...]:
    """Scale to length one, so a dot product is a cosine. A zero vector stays zero."""
    length = math.sqrt(sum(value * value for value in vector))
    return tuple(value / length for value in vector) if length else vector


class DenseRetriever(Retriever):
    """Rank passages by how close their meaning is to the question's."""

    def __init__(self, embedder: Embedder, cache: Path | None = None) -> None:
        """Embed with ``embedder``, remembering vectors in ``cache`` when one is given."""
        self._embedder = embedder
        self._cache = cache

    @property
    def name(self) -> str:
        """Name the embedder too: two runs with different models chose differently."""
        return f"meaning ({self._embedder.name})"

    def select(self, question: str, passages: tuple[Passage, ...], budget_tokens: int) -> Selection:
        """Choose the passages closest in meaning to ``question`` that fit the budget."""
        if not passages or budget_tokens <= 0:
            return Selection(considered=len(passages), set_aside=len(passages), how=self.name)
        ranked = self._ranked(question, passages)
        return _fill(ranked, passages, budget_tokens, self.name)

    def _ranked(self, question: str, passages: tuple[Passage, ...]) -> list[int]:
        """Passage indices, closest first."""
        vectors = self.vectors_for(passages)
        asked = _unit(self._embedder.embed((question,))[0])
        scored = [
            (sum(a * b for a, b in zip(asked, vectors[index], strict=False)), index)
            for index in range(len(passages))
        ]
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [index for _, index in scored]

    def vectors_for(self, passages: tuple[Passage, ...]) -> list[tuple[float, ...]]:
        """The unit vector of every passage, embedding only what is not already known.

        Public because a second caller needs exactly this and would otherwise write it
        again: `lacc coverage` compares topics against the same vectors this ranks with, and
        a second copy of "compute what is missing, reuse the rest, rewrite the whole cache"
        is a second thing to keep true (ADR-088).
        """
        known = remembered(self._cache, self._embedder.name) if self._cache else {}
        keys = [key_for(passage.text) for passage in passages]
        missing = tuple(
            passage.text for passage, key in zip(passages, keys, strict=True) if key not in known
        )
        if missing:
            fresh = self._embedder.embed(missing)
            for text, vector in zip(missing, fresh, strict=True):
                known[key_for(text)] = _unit(vector)
            if self._cache:
                # Everything known, not only the new: the file describes one set of texts,
                # and writing only the additions would lose the rest.
                remember(self._cache, self._embedder.name, known)
        return [known[key] for key in keys]


class FusedRetriever(Retriever):
    """Combine two rankings by Reciprocal Rank Fusion, with no weight to choose."""

    def __init__(self, first: Retriever, second: Retriever) -> None:
        """Fuse ``first`` and ``second``. Order affects nothing: RRF is symmetric."""
        self._first = first
        self._second = second

    @property
    def name(self) -> str:
        """Name both, because what a fusion chose is not explained by either alone."""
        return f"{self._first.name} + {self._second.name}, fused by rank"

    def select(self, question: str, passages: tuple[Passage, ...], budget_tokens: int) -> Selection:
        """Rank by both, sum the inverse positions, and fill the budget from the top.

        Each retriever is asked for its ranking of **everything** rather than of what fits:
        a passage ranked eleventh by one and first by the other should surface, and it
        cannot if the first one already dropped it for space.
        """
        if not passages or budget_tokens <= 0:
            return Selection(considered=len(passages), set_aside=len(passages), how=self.name)

        whole = sum(estimate_tokens(passage.text) for passage in passages) + len(passages)
        scores: dict[int, float] = {}
        for retriever in (self._first, self._second):
            chosen = retriever.select(question, passages, whole).chosen
            place = {passage.text: rank for rank, passage in enumerate(chosen)}
            for index, passage in enumerate(passages):
                rank = place.get(passage.text)
                if rank is not None:
                    scores[index] = scores.get(index, 0.0) + 1.0 / (_FUSION_CONSTANT + rank + 1)

        ranked = sorted(scores, key=lambda index: (-scores[index], index))
        return _fill(ranked, passages, budget_tokens, self.name)


def _fill(
    ranked: list[int], passages: tuple[Passage, ...], budget_tokens: int, how: str
) -> Selection:
    """Take from ``ranked`` in order while the budget lasts, **and stay in that order**.

    Ranked order, not the corpus's. `WordRetriever` returns its choices best-first and two
    things depend on it: a model reads a prompt from the top, and `FusedRetriever` reads
    each ranking's positions out of `chosen`. An earlier version of this sorted by corpus
    index - so the fusion was combining the word ranking with the order the corpus happened
    to be assembled in, which is no ranking at all (ADR-061).

    Skips a passage too large rather than stopping, so one long quotation does not end the
    selection while shorter ones behind it would have fit. What is left out is counted,
    which the port requires of every implementation (ADR-050).
    """
    taken: list[int] = []
    spent = 0
    for index in ranked:
        cost = estimate_tokens(passages[index].text) + 1
        if spent + cost > budget_tokens:
            continue
        taken.append(index)
        spent += cost
    return Selection(
        chosen=tuple(passages[index] for index in taken),
        set_aside=len(passages) - len(taken),
        considered=len(passages),
        how=how,
    )
