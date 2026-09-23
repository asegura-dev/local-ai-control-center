"""How far the nearest quotation is from a topic (ADR-088).

What is tested here is mostly what this **must not** do. Two instruments were measured and
refused before this one, both because they produced a confident wrong answer about somebody's
own bibliography - so these assert that nothing is called a gap, that a control is required,
and that the vectors cannot be lined up wrongly against the passages.
"""

from __future__ import annotations

import math

import pytest

from local_ai_control_center.features.coverage import (
    Reach,
    Topic,
    missing_control,
    reach_of,
    report,
    topics_in,
)
from local_ai_control_center.ports.embedder import Embedder
from local_ai_control_center.ports.retriever import Passage

TOPICS = """# what this thesis has to hold up
sensitivity of PSMA PET for pelvic lymph nodes

radiation dose and biodistribution
! paediatric bone sarcoma
"""


class _Directions(Embedder):
    """An embedder placing each text on one of three axes, by a word it contains.

    Deterministic and offline. What matters is that a topic and the passages meant to be
    near it land on the same axis, so the ordering can be asserted without a real model.
    """

    AXES = {"node": 0, "dose": 1, "sarcoma": 2}

    @property
    def name(self) -> str:
        return "directions"

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        out = []
        for text in texts:
            vector = [0.1, 0.1, 0.1]
            for word, axis in self.AXES.items():
                if word in text.lower():
                    vector[axis] = 1.0
            out.append(tuple(vector))
        return tuple(out)


def _passages() -> tuple[Passage, ...]:
    return (
        Passage(text="the node was positive", source="a.md", page=3),
        Passage(text="another node finding", source="b.md", page=4),
        Passage(text="the effective dose was 4.4 mSv", source="c.md", page=2),
    )


def _vectors(passages: tuple[Passage, ...]) -> tuple[tuple[float, ...], ...]:
    return _Directions().embed(tuple(p.text for p in passages))


# --- reading the topics file ----------------------------------------------------------------


def test_a_comment_and_a_blank_line_are_not_topics() -> None:
    found = topics_in(TOPICS)
    assert [t.said for t in found] == [
        "sensitivity of PSMA PET for pelvic lymph nodes",
        "radiation dose and biodistribution",
        "paediatric bone sarcoma",
    ]


def test_the_marked_line_is_the_control_and_keeps_its_words() -> None:
    control = [t for t in topics_in(TOPICS) if t.control]
    assert len(control) == 1
    assert control[0].said == "paediatric bone sarcoma"


def test_a_file_with_no_control_is_recognised_as_having_none() -> None:
    """Without a floor a similarity has no meaning, and a reader supplies one."""
    assert missing_control(topics_in("just one topic\nand another\n"))
    assert not missing_control(topics_in("a topic\n! the control\n"))


def test_a_marker_with_nothing_after_it_is_not_a_topic() -> None:
    assert topics_in("! \nreal topic\n") == (Topic(said="real topic"),)


# --- what reaches what ----------------------------------------------------------------------


def test_topics_come_back_nearest_first_with_the_control_where_it_falls() -> None:
    passages = _passages()
    found = reach_of(topics_in(TOPICS), passages, _vectors(passages), _Directions())
    assert [one.topic.said for one in found][0].startswith("sensitivity")
    assert found[-1].topic.control
    assert found[0].nearest > found[-1].nearest


def test_the_quotation_that_came_closest_is_carried_with_its_document_and_page() -> None:
    """A number saying a topic is thin is a claim to check; this is how it is checked."""
    passages = _passages()
    found = reach_of(topics_in(TOPICS), passages, _vectors(passages), _Directions())
    dosimetry = next(one for one in found if one.topic.said == "radiation dose and biodistribution")
    assert dosimetry.document == "c.md"
    assert dosimetry.page == 2
    assert "4.4 mSv" in dosimetry.quote


def test_a_topic_nothing_is_near_still_reports_the_nearest_thing_there_is() -> None:
    """Never "nothing found": always how far away the closest quotation is."""
    passages = _passages()
    found = reach_of(
        (Topic(said="sarcoma", control=True),), passages, _vectors(passages), _Directions()
    )
    assert found[0].quote
    assert 0 < found[0].nearest < 1


def test_vectors_that_do_not_line_up_with_the_passages_are_refused(caplog: object) -> None:
    """One missing vector would mis-attribute every quotation after it."""
    passages = _passages()
    with pytest.raises(ValueError, match="mis-attribute"):
        reach_of(topics_in(TOPICS), passages, _vectors(passages)[:2], _Directions())


def test_nothing_at_all_gives_nothing_rather_than_an_answer() -> None:
    assert reach_of((), _passages(), _vectors(_passages()), _Directions()) == ()
    assert reach_of(topics_in(TOPICS), (), (), _Directions()) == ()


# --- what the report may not say ------------------------------------------------------------


def test_the_report_never_calls_anything_a_gap() -> None:
    """The load-bearing one. Two instruments were refused for producing false gaps."""
    passages = _passages()
    found = reach_of(topics_in(TOPICS), passages, _vectors(passages), _Directions())
    written = report(found, "corpus.md", "directions", "2026-09-23").lower()
    assert "not covered" not in written
    assert "missing" not in written.split("cannot say what is missing")[0]
    assert "nothing here is called a gap" in written


def test_the_report_names_the_floor_and_which_topic_set_it() -> None:
    passages = _passages()
    found = reach_of(topics_in(TOPICS), passages, _vectors(passages), _Directions())
    written = report(found, "corpus.md", "directions", "2026-09-23")
    assert "The floor is" in written
    assert "paediatric bone sarcoma" in written


def test_a_report_with_no_control_says_its_numbers_have_no_floor() -> None:
    reaches = (Reach(topic=Topic(said="anything"), nearest=0.7),)
    written = report(reaches, "corpus.md", "directions", "2026-09-23")
    assert "no floor" in written


def test_the_report_names_the_model_and_the_date_it_was_taken() -> None:
    """Change the embedding model and every number moves; a comparison across two is void."""
    passages = _passages()
    found = reach_of(topics_in(TOPICS), passages, _vectors(passages), _Directions())
    written = report(found, "corpus.md", "directions", "2026-09-23")
    assert "directions" in written
    assert "2026-09-23" in written


def test_the_report_says_it_cannot_tell_you_what_is_absent() -> None:
    """LACC knows nothing of the field beyond the documents brought to it."""
    passages = _passages()
    found = reach_of(topics_in(TOPICS), passages, _vectors(passages), _Directions())
    assert "cannot say what is missing" in report(found, "c.md", "d", "2026-09-23")


def test_a_similarity_is_between_nothing_and_one() -> None:
    passages = _passages()
    found = reach_of(topics_in(TOPICS), passages, _vectors(passages), _Directions())
    assert all(0.0 <= one.nearest <= 1.0 + 1e-9 for one in found)
    assert not any(math.isnan(one.nearest) for one in found)
