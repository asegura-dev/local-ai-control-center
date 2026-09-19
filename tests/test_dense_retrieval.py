"""Choosing by meaning, the cache beside the corpus, and fusing two rankings (ADR-061).

No engine here. A stub embedder returns vectors chosen by hand, so what is tested is this
project's code - the ranking, the cache, the fusion - rather than a model's behaviour.
**Whether meaning beats words is a measurement, not a test**, and it lives in chapter 4 with
its numbers: a stub can be made to prove anything.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from local_ai_control_center.adapters.dense import DenseRetriever, FusedRetriever
from local_ai_control_center.adapters.vectors import SUFFIX, key_for, remember, remembered
from local_ai_control_center.adapters.words import WordRetriever
from local_ai_control_center.core.budget import estimate_tokens
from local_ai_control_center.ports.embedder import Embedder, EmbeddingError
from local_ai_control_center.ports.retriever import Passage


class _Bench(Embedder):
    """An embedder with a fixed table, counting what it was actually asked to embed."""

    def __init__(self, table: dict[str, tuple[float, ...]], name: str = "bench") -> None:
        self._table = table
        self._name = name
        self.asked: list[tuple[str, ...]] = []

    @property
    def name(self) -> str:
        return self._name

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.asked.append(texts)
        missing = [text for text in texts if text not in self._table]
        if missing:
            raise EmbeddingError(f"nothing for {missing[0]!r}")
        return tuple(self._table[text] for text in texts)


_NEAR = "the model segmented the lesions"
_FAR = "the authors thank the department"
_ASKED = "which model found the lesions"

_TABLE = {
    _ASKED: (1.0, 0.0),
    _NEAR: (0.96, 0.28),
    _FAR: (0.0, 1.0),
}
_PASSAGES = (Passage(text=_NEAR, source="a.md"), Passage(text=_FAR, source="b.md"))


def test_the_closest_meaning_is_chosen_first() -> None:
    """What the retriever is for, and the order it comes back in.

    The passages are given **furthest-first** on purpose. An earlier version of this test
    listed them nearest-first and passed against a selection that returned corpus order and
    no ranking at all - which is also what the fusion was reading positions out of.
    """
    reversed_corpus = (_PASSAGES[1], _PASSAGES[0])
    selection = DenseRetriever(_Bench(_TABLE)).select(_ASKED, reversed_corpus, 10_000)
    assert [passage.source for passage in selection.chosen] == ["a.md", "b.md"], (
        "closest first, whatever order the corpus was assembled in"
    )
    assert selection.considered == 2


def test_what_was_left_out_is_counted_here_too() -> None:
    """The port requires it of every implementation, and a new one is where it gets missed."""
    selection = DenseRetriever(_Bench(_TABLE)).select(_ASKED, _PASSAGES, 4)
    assert selection.set_aside == selection.considered - len(selection.chosen)
    assert selection.set_aside > 0


def test_a_passage_too_large_is_skipped_rather_than_ending_the_selection() -> None:
    """One long quotation must not close the door on shorter ones ranked behind it.

    The budget below fits one of the short passages and not two, so what this shows is a
    selection continuing past something it could not take rather than stopping there.
    """
    table = dict(_TABLE)
    huge = "x " * 400
    table[huge] = (0.99, 0.1)
    passages = (Passage(text=huge, source="huge.md"), *_PASSAGES)
    budget = estimate_tokens(_NEAR) + 1
    selection = DenseRetriever(_Bench(table)).select(_ASKED, passages, budget)
    assert [passage.source for passage in selection.chosen] == ["a.md"], (
        "the best-ranked passage does not fit, and the next one still does"
    )
    assert selection.set_aside == 2


def test_nothing_is_embedded_twice(tmp_path: Path) -> None:
    """The cache exists for one measured reason: 48 seconds against 72 milliseconds."""
    cache = tmp_path / ("corpus.md" + SUFFIX)
    bench = _Bench(_TABLE)
    DenseRetriever(bench, cache).select(_ASKED, _PASSAGES, 10_000)
    first = sum(len(batch) for batch in bench.asked)

    again = _Bench(_TABLE)
    DenseRetriever(again, cache).select(_ASKED, _PASSAGES, 10_000)
    embedded_again = [text for batch in again.asked for text in batch if text != _ASKED]

    assert first >= 3, "the passages and the question"
    assert embedded_again == [], "the second run embeds no passage it already knew"


def test_a_corpus_that_grew_embeds_only_what_is_new(tmp_path: Path) -> None:
    """A bibliography gains documents. Re-embedding all of it each time is the cost."""
    cache = tmp_path / ("corpus.md" + SUFFIX)
    DenseRetriever(_Bench(_TABLE), cache).select(_ASKED, _PASSAGES, 10_000)

    fresh = "a third passage nobody has seen"
    table = {**_TABLE, fresh: (0.5, 0.5)}
    bench = _Bench(table)
    DenseRetriever(bench, cache).select(
        _ASKED, (*_PASSAGES, Passage(text=fresh, source="c.md")), 10_000
    )
    embedded = [text for batch in bench.asked for text in batch if text != _ASKED]
    assert embedded == [fresh]


def test_vectors_from_another_model_are_not_compared_with_these(tmp_path: Path) -> None:
    """The one cache failure that must not be quiet.

    A missing or truncated file is answered by computing again. Vectors from a **different
    embedding space** are answered by returning confident nonsense, so the embedder's name
    is part of the file and a mismatch counts as no cache at all (ADR-061).
    """
    cache = tmp_path / ("corpus.md" + SUFFIX)
    remember(cache, "someone-else", {key_for(_NEAR): (0.0, 1.0)})
    assert remembered(cache, "bench") == {}, "a foreign file is ignored, not trusted"

    bench = _Bench(_TABLE)
    DenseRetriever(bench, cache).select(_ASKED, _PASSAGES, 10_000)
    assert any(_NEAR in batch for batch in bench.asked), "it embeds again rather than compare"


@pytest.mark.parametrize(
    "damage",
    [b"", b"not json at all", b'{"embedder": "bench", "dim": 2, "keys": ["a"]}\n\x00\x01'],
)
def test_an_unreadable_cache_is_no_cache_and_not_an_error(tmp_path: Path, damage: bytes) -> None:
    """Every one of these is answered correctly by computing again."""
    cache = tmp_path / ("corpus.md" + SUFFIX)
    cache.write_bytes(damage)
    assert remembered(cache, "bench") == {}


def test_a_cache_that_cannot_be_written_does_not_end_the_run(tmp_path: Path) -> None:
    """The answer is already correct; a cache is not worth failing a run over."""
    unwritable = tmp_path / "missing" / "corpus.md.vectors"
    selection = DenseRetriever(_Bench(_TABLE), unwritable).select(_ASKED, _PASSAGES, 10_000)
    assert selection.chosen, "the selection happened anyway"
    assert not unwritable.exists()


def test_a_vector_survives_the_round_trip(tmp_path: Path) -> None:
    """Stored as float32, so what comes back is close rather than identical."""
    cache = tmp_path / ("corpus.md" + SUFFIX)
    original = (0.1234567, -0.7654321, 0.0)
    remember(cache, "bench", {"k": original})
    returned = remembered(cache, "bench")["k"]
    assert len(returned) == len(original)
    assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(returned, original, strict=True))


def test_fusion_reaches_what_neither_ranking_reaches_alone() -> None:
    """Reciprocal Rank Fusion, with no weight to choose (ADR-061).

    The two rankings are made to disagree completely: one passage carries the question's
    word and means something else, the other means the right thing and shares no word. A
    fusion that simply preferred one of its inputs would be that input renamed, so the test
    is that **both** surface and that the word-only ranking does not reach the second.
    """
    shares_the_word = Passage(text="biopsy of the department archive", source="word.md")
    shares_the_meaning = Passage(text="the network outlined each node", source="meaning.md")
    asked = "biopsy"
    table = {
        asked: (0.0, 1.0),
        shares_the_word.text: (1.0, 0.0),
        shares_the_meaning.text: (0.0, 1.0),
    }
    passages = (shares_the_word, shares_the_meaning)

    by_words = WordRetriever().select(asked, passages, 10_000)
    assert [p.source for p in by_words.chosen] == ["word.md"], "words reach only the word"

    by_meaning = DenseRetriever(_Bench(table)).select(asked, passages, 10_000)
    assert by_meaning.chosen[0].source == "meaning.md"

    fused = FusedRetriever(WordRetriever(), DenseRetriever(_Bench(table))).select(
        asked, passages, 10_000
    )
    assert {p.source for p in fused.chosen} == {"word.md", "meaning.md"}
    assert "fused by rank" in fused.how


def test_an_empty_corpus_is_not_an_error() -> None:
    """The same answer the word retriever gives, and for the same reason."""
    selection = DenseRetriever(_Bench(_TABLE)).select(_ASKED, (), 10_000)
    assert selection.chosen == ()
    assert selection.considered == 0
