"""Abstract port for turning text into a vector that can be compared with another.

Separate from `Provider` because it is a different question asked of a different endpoint:
`Provider` asks a model to write something, and nothing about generation says what an
embedding is. A model that can do one cannot be assumed to do the other.

What this makes possible is choosing passages by **meaning** rather than by shared rare
words. Measured on the real corpus: a question asked in Spanish against quotations written in
English returned two relevant passages of 654 by word ranking, and eight of the first eight
by this (ADR-061).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingError(Exception):
    """Raised when text could not be turned into vectors at all.

    Unlike a judgement that could not be made (ADR-053), there is no useful partial answer
    here: a selection built on some of the corpus, silently, would choose from whatever
    happened to embed. The caller is told and decides.
    """


class Embedder(ABC):
    """Anything that can turn texts into vectors of the same length.

    Implementations may call a local engine, load a model in-process, or do something not
    invented yet. What they must not do is return vectors of differing lengths, or vectors
    from a different model than the one they name - both make a stored set of vectors
    silently incomparable with a new one.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identify the embedder **and the model**, so a stored set can be matched to it.

        Vectors made by one model mean nothing against another's. This name is what a
        vector file records and checks, so a changed model recomputes rather than compares
        across an incompatible space and returns confident nonsense.
        """

    @abstractmethod
    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Return one vector per text, in the same order.

        Takes many rather than one because the cost is dominated by the round trip: the
        corpus embeds in 48 seconds in batches and would take far longer one at a time.

        Raises `EmbeddingError` rather than returning fewer vectors than texts. A caller
        cannot line up a short answer with its input, and a silently short one would
        mis-attribute every vector after the gap.
        """
