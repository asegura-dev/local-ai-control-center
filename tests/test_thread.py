"""A thread of questions, and the one thing it must never carry (ADR-091).

The load-bearing tests here are the negative ones. A conversation puts the model's previous
answer into the next prompt, and if one turn invents a quotation the next turn then **has**
it - so the check confirms the invention instead of catching it. Everything below exists to
make that impossible rather than unlikely.
"""

from __future__ import annotations

from local_ai_control_center.features.thread import Thread, Turn, established_by
from local_ai_control_center.ports.retriever import Passage

SENSITIVITY = Passage(
    text="The sensitivity for pelvic lymph node metastases was 82 per cent.",
    source="psma.md",
    page=4,
)
STAGING = Passage(
    text="Nodal staging with PSMA PET outperformed conventional imaging.",
    source="psma.md",
    page=7,
)
DOSE = Passage(text="The effective dose was 4.4 mSv.", source="dosimetry.md", page=2)


# --- what a turn establishes ----------------------------------------------------------------


def test_a_passage_whose_quotation_was_found_is_established() -> None:
    sent = (SENSITIVITY, DOSE)
    assert established_by(sent, ("sensitivity for pelvic lymph node",)) == (SENSITIVITY,)


def test_nothing_is_established_when_no_quotation_was_found() -> None:
    """The whole point: an invention is never passed in, so it never becomes material."""
    assert established_by((SENSITIVITY, DOSE), ()) == ()


def test_only_the_verified_quotations_establish_their_passages() -> None:
    """The caller passes the found ones. An answer with one of each establishes one."""
    assert established_by((SENSITIVITY, DOSE), ("effective dose was 4.4",)) == (DOSE,)


def test_a_quotation_matching_nothing_that_was_sent_establishes_nothing() -> None:
    assert established_by((SENSITIVITY, DOSE), ("a sentence nobody sent",)) == ()


def test_a_quotation_taken_out_of_a_longer_passage_still_establishes_it() -> None:
    """A model quotes a sentence out of a passage far more often than a whole one."""
    assert established_by((SENSITIVITY,), ("82 per cent",)) == (SENSITIVITY,)


def test_an_empty_quotation_establishes_nothing_rather_than_everything() -> None:
    """`"" in anything` is true, which would establish the whole selection."""
    assert established_by((SENSITIVITY, DOSE), ("", "   ")) == ()


# --- what carries between turns ---------------------------------------------------------


def _thread(*turns: Turn) -> Thread:
    return Thread(corpus="corpus.md", turns=turns)


def test_the_model_s_prose_is_not_among_what_carries() -> None:
    """A `Turn` keeps the answer to be read. `carried` is passages and nothing else."""
    turn = Turn(question="q", answer="prose the model wrote", established=(SENSITIVITY,))
    carried = _thread(turn).carried
    assert carried == (SENSITIVITY,)
    assert all(isinstance(one, Passage) for one in carried)
    assert not any("prose the model wrote" in one.text for one in carried)


def test_the_questions_carry_for_a_person_to_read() -> None:
    thread = _thread(Turn(question="first"), Turn(question="second"))
    assert thread.asked == ("first", "second")


def test_the_same_passage_established_twice_is_carried_once() -> None:
    """A budget that admits a fifth of a corpus should not spend it on a repeat."""
    thread = _thread(
        Turn(question="a", established=(SENSITIVITY, DOSE)),
        Turn(question="b", established=(DOSE, STAGING)),
    )
    assert thread.carried == (SENSITIVITY, DOSE, STAGING)


def test_a_thread_is_frozen_and_a_turn_returns_a_new_one() -> None:
    """Nothing mutates under a window that is drawing it."""
    thread = _thread(Turn(question="a"))
    longer = thread.after(Turn(question="b"))
    assert thread.asked == ("a",)
    assert longer.asked == ("a", "b")


def test_a_turn_that_failed_is_still_a_turn_in_the_thread() -> None:
    """An engine that was not there is part of what happened, not a gap in the record."""
    turn = Turn(question="q", failure="Cannot reach the engine.")
    assert not turn.worked
    assert _thread(turn).asked == ("q",)
    assert _thread(turn).carried == ()
