"""Ordering a document's own sections by what a question is about (ADR-079)."""

from __future__ import annotations

from local_ai_control_center.adapters.dense import DenseRetriever, FusedRetriever
from local_ai_control_center.adapters.words import WordRetriever
from local_ai_control_center.core.sections import summaries_in
from local_ai_control_center.features.navigate import ranked, sections_would_send
from local_ai_control_center.ports.embedder import Embedder


class _Recording(Embedder):
    """An embedding engine that answers anything and remembers what it was sent."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, ...]] = []

    @property
    def name(self) -> str:
        return "recording"

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.asked.append(texts)
        return tuple((1.0, 0.0) for _ in texts)


def _guideline() -> str:
    """A document with sections about visibly different things."""

    def body(words: str) -> str:
        return (words + " " + "filler that carries the section. " * 3 + chr(10)) * 12

    return chr(10).join(
        [
            "1. Introduction",
            body("This guideline concerns prostate cancer in general."),
            "2. Screening",
            body("Screening and early detection with PSA testing in asymptomatic men."),
            "3. Staging",
            "",
            "3.1. T-staging",
            body("Local tumour extent assessed by digital rectal examination and MRI."),
            "3.2. N-staging",
            body("Lymph node metastasis detected by nodal size on CT and by PSMA PET."),
            "4. Treatment",
            body("Radical prostatectomy and radiotherapy for localised disease."),
        ]
    )


def test_a_summary_is_the_title_and_the_opening_of_its_body() -> None:
    """A title alone will not do: extraction leaves them cut, like `5.2.4 Imag`."""
    summaries = summaries_in(_guideline())
    numbers = [section.number for section, _ in summaries]
    assert numbers == ["1", "2", "3", "3.1", "3.2", "4"]
    body = dict((s.number, text) for s, text in summaries)
    assert "PSA testing" in body["2"]
    assert body["2"].startswith("2 Screening")


def test_a_summary_does_not_borrow_the_next_sections_words() -> None:
    """A short section must not be credited with what its neighbour says."""
    body = dict((s.number, text) for s, text in summaries_in(_guideline()))
    assert "digital rectal" not in body["3"], "section 3 has no body of its own"
    assert "Lymph node" not in body["3.1"]


def test_the_section_a_question_is_about_comes_near_the_top() -> None:
    order = ranked(_guideline(), "lymph node metastasis and nodal staging", WordRetriever())
    assert [s.number for s in order][:2] == ["3.2", "3"] or order[0].number == "3.2"


def test_a_different_question_gives_a_different_order() -> None:
    """If the order never changed, the ranking would be decoration."""
    nodal = ranked(_guideline(), "lymph node metastasis on CT", WordRetriever())
    screening = ranked(_guideline(), "PSA screening in asymptomatic men", WordRetriever())
    assert nodal[0].number != screening[0].number


def test_every_section_is_returned_not_just_the_best() -> None:
    """Which to read is the reader's decision; a list that hid the rest would make it."""
    order = ranked(_guideline(), "anything at all", WordRetriever())
    assert len(order) == len(summaries_in(_guideline()))


def test_a_document_that_numbers_nothing_ranks_nothing() -> None:
    assert ranked("Just prose, with no numbering at all.", "a question", WordRetriever()) == ()


def test_ranking_sections_by_meaning_says_what_it_would_send_first() -> None:
    """`sections --about` sent every opening, every run, and asked nothing (ADR-106)."""
    engine = _Recording()
    meaning = FusedRetriever(WordRetriever(), DenseRetriever(engine))
    outgoing = sections_would_send(_guideline(), meaning)
    assert engine.asked == [], "counting sent nothing"
    assert outgoing is not None
    assert outgoing.unembedded == len(summaries_in(_guideline())), "no store: every opening"
    assert sections_would_send(_guideline(), WordRetriever()) is None
    assert sections_would_send("Just prose.", meaning) is None
