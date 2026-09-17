"""Choosing which passages go into a prompt, and saying what was left out (ADR-050)."""

from __future__ import annotations

from local_ai_control_center.adapters.words import WordRetriever
from local_ai_control_center.ports.retriever import Passage


def _corpus() -> tuple[Passage, ...]:
    return (
        Passage(
            text="The sensitivity for pelvic lymph node metastases was 82 per cent.",
            source="a.md",
            note="detection sensitivity",
            page=4,
        ),
        Passage(
            text="Radiation dosimetry showed an effective dose of 4.4 mSv.",
            source="b.md",
            note="dosimetry",
            page=2,
        ),
        Passage(
            text="Nodal staging with PSMA PET outperformed conventional imaging.",
            source="a.md",
            note="staging comparison",
            page=7,
        ),
        Passage(
            text="The authors thank the department for its support.",
            source="c.md",
            note="acknowledgement",
            page=9,
        ),
    )


def test_the_passages_that_share_the_questions_words_are_chosen() -> None:
    selection = WordRetriever().select("pelvic lymph node sensitivity", _corpus(), 10_000)
    assert selection.chosen[0].page == 4
    assert all("dosimetry" not in p.note for p in selection.chosen)


def test_what_was_left_out_is_always_counted() -> None:
    """A selection that hides its discards turns a partial answer into a confident one."""
    selection = WordRetriever().select("dosimetry", _corpus(), 10_000)
    assert selection.considered == 4
    assert selection.set_aside == 4 - len(selection.chosen)
    assert not selection.sent_everything
    assert selection.how


def test_a_passage_matching_nothing_is_never_sent_however_much_room_there_is() -> None:
    """Filling a prompt with unrelated material invites a model to invent a connection."""
    selection = WordRetriever().select("dosimetry", _corpus(), 1_000_000)
    assert len(selection.chosen) == 1
    assert selection.chosen[0].source == "b.md"
    assert selection.set_aside == 3


def test_the_budget_is_in_tokens_and_is_respected() -> None:
    small = WordRetriever().select("sensitivity nodal staging pelvic", _corpus(), 12)
    large = WordRetriever().select("sensitivity nodal staging pelvic", _corpus(), 10_000)
    assert len(small.chosen) < len(large.chosen)
    assert small.set_aside > large.set_aside


def test_a_question_with_no_usable_words_chooses_nothing_and_says_so() -> None:
    selection = WordRetriever().select("the and for", _corpus(), 10_000)
    assert selection.chosen == ()
    assert selection.set_aside == 4


def test_an_empty_corpus_is_not_an_error() -> None:
    selection = WordRetriever().select("anything", (), 10_000)
    assert selection.chosen == ()
    assert selection.considered == 0


def test_the_same_question_chooses_the_same_passages_twice() -> None:
    """A selection that varied between identical runs would make the audit worthless."""
    first = WordRetriever().select("nodal staging PSMA", _corpus(), 10_000)
    second = WordRetriever().select("nodal staging PSMA", _corpus(), 10_000)
    assert [p.text for p in first.chosen] == [p.text for p in second.chosen]


def test_a_common_word_does_not_decide_the_ranking() -> None:
    """Rarity weighting: a word every passage carries says nothing about which to read."""
    corpus = (
        Passage(text="The study reports the sensitivity of the method.", source="a.md"),
        Passage(text="The study reports the dosimetry of the tracer.", source="b.md"),
    )
    selection = WordRetriever().select("study reports dosimetry", corpus, 10_000)
    assert selection.chosen[0].source == "b.md"


def test_words_alone_do_not_cross_languages() -> None:
    """Measured on a real corpus: quotations in English, a question in Spanish, two hits
    out of 654 and both irrelevant. This is the honest reason to measure embeddings, and
    it is pinned here so a later retriever has something to beat (ADR-050)."""
    english = (
        Passage(text="A convolutional neural network segmented the lesions.", source="a.md"),
        Passage(text="The authors thank the department.", source="b.md"),
    )
    selection = WordRetriever().select("red neuronal convolucional segmentacion", english, 10_000)
    assert selection.chosen == (), "word matching finds nothing across a language boundary"
    assert selection.set_aside == 2
