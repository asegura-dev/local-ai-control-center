"""Turning selected passages into what a question is asked against (ADR-066).

Two pure functions that used to live in the view. Neither prints, and what they decide is
what a person then reads: which passages become the material of a prompt, and which ones are
offered beside a flagged reading as things that might carry it.

**Candidates, never support** is the discipline both of them keep. LACC ranks sentences; it
does not decide that any of them establishes anything.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.budget import answer_reserve, estimate_tokens
from local_ai_control_center.core.config import Config
from local_ai_control_center.core.corpus import parse_corpus
from local_ai_control_center.core.grounding import CheckedClaim
from local_ai_control_center.ports.retriever import Passage, Retriever, Selection


def as_material(selection: Selection) -> str:
    """Render the chosen passages as the text that goes into the prompt."""
    blocks = []
    for passage in selection.chosen:
        where = f"{passage.source}, p. {passage.page}" if passage.page else passage.source
        blocks.append(f"[{where}]{chr(10)}{passage.text}")
    return (chr(10) * 2).join(blocks)


def might_support(
    claim: str, quoted: str, passages: tuple[Passage, ...], retriever: Retriever
) -> tuple[Passage, ...]:
    """Passages from what was sent that might support ``claim``, best first (ADR-063).

    **Candidates, never support.** LACC has ranked some sentences against the words of a
    reading; it has not decided that any of them establishes it. The same discipline
    `nearest_text` follows when a quotation is not found: report the match, and say plainly
    that it is not a reconstruction of what the model meant (ADR-034).

    The one already quoted is left out - a writer told to cite something knows about the
    sentence they cited.
    """
    # Deduplicated on the words, not only against the quotation. A corpus holds the same
    # sentence more than once - `without_repeats` drops repeats within one answer, not
    # across the documents a selection draws from - and two candidates that are one
    # sentence twice is half a tool. Found on the first real use (ADR-063).
    seen = {quoted.strip()}
    others: list[Passage] = []
    for passage in passages:
        words = passage.text.strip()
        if words in seen:
            continue
        seen.add(words)
        others.append(passage)
    if not others:
        return ()
    # A budget large enough for everything: what is wanted here is the ranking, not a
    # selection, and a passage dropped for space would be one the writer never sees.
    whole = sum(estimate_tokens(passage.text) for passage in others) + len(others)
    return retriever.select(claim, tuple(others), whole).chosen[:2]


# --- a question prepared before it is sent (ADR-085) ----------------------------------------


class Prepared(BaseModel):
    """What a question would send, worked out without sending the prompt.

    The window has no y/n defaulting to no, so this object *is* the confirmation: the control
    that sends does not exist until this has been drawn. Everything a person needs to decide
    with is a field here, including the reason when there is nothing to decide (ADR-085).
    """

    model_config = ConfigDict(frozen=True)

    question: str
    corpus: str = ""
    material: str = ""
    """The passages as they would arrive in the prompt. Not drawn - it is what is sent."""

    chosen: tuple[Passage, ...] = ()
    """The passages themselves, for a caller that needs more than their rendering.

    `ask --judge` offers candidates from them beside a reading it flags, which is why they
    are carried rather than only counted.
    """

    selected: int = 0
    considered: int = 0
    set_aside: int = 0
    how: str = ""
    """Which ranking chose them, in the retriever's own words."""

    model: str = ""
    reaches: str = ""
    tokens: int = 0
    """The material alone, estimated. The instruction around it is counted separately."""

    refusal: str = ""
    """Why this cannot be sent, in a sentence, or empty."""

    @property
    def sendable(self) -> bool:
        """Whether there is anything to send. The button is drawn only when this is true."""
        return not self.refusal and self.selected > 0


class Reading(BaseModel):
    """One claim from an answer, and whether its quotation was in what the model was shown."""

    model_config = ConfigDict(frozen=True)

    claim: str
    quote: str
    found: bool
    nearest: str = ""


class Asked(BaseModel):
    """What came back, including the four ways nothing did.

    A failure is a result with a sentence in it rather than an exception crossing a thread
    boundary into a widget. The window draws this in the place a good answer would go.
    """

    model_config = ConfigDict(frozen=True)

    prepared: Prepared
    answer: str = ""
    readings: tuple[Reading, ...] = ()
    seconds: float = 0.0
    failure: str = ""

    @property
    def worked(self) -> bool:
        return not self.failure and bool(self.answer)

    @property
    def invented(self) -> int:
        """Quotations the answer carried that are not in the passages it was given."""
        return sum(1 for reading in self.readings if not reading.found)


def readings_from(checked: tuple[CheckedClaim, ...]) -> tuple[Reading, ...]:
    """The checked claims as this project's own contract, not the grounding module's.

    The same reason `EngineSeen` exists: what crosses into a view is a type the view's layer
    may name, so a section never handles something from deeper in (ADR-066, ADR-077).
    """
    return tuple(
        Reading(
            claim=one.claim.claim,
            quote=one.claim.quote,
            found=one.found,
            nearest=one.nearest,
        )
        for one in checked
    )


def prepare(
    question: str,
    corpus: str,
    text: str,
    config: Config,
    retriever: Retriever,
) -> Prepared:
    """Read a corpus, rank it against a question, and report what would be sent.

    **The prompt is not sent here.** What this does cost, when an embedding model is
    configured, is embedding the question itself - one small call to the host already named,
    with the material staying on this machine. That is said in the preview rather than left
    for somebody to discover, because a window that reached the network without saying so
    would break the only rule this project has about reaching anywhere.
    """
    asked = question.strip()
    if not asked:
        return Prepared(question="", corpus=corpus, refusal="Type a question first.")
    if config.context_tokens is None:
        return Prepared(
            question=asked,
            corpus=corpus,
            refusal=(
                "No context window is configured, so there is no budget to select against. "
                "Set context_tokens to the window the model actually has."
            ),
        )

    # Only what was found in its document is eligible, which is the same rule `lacc ask`
    # keeps: retrieving over unverified text and checking afterwards would verify what the
    # model echoed rather than what it was shown.
    collected = [c for c in parse_corpus(text) if "NOT IN THE DOCUMENT" not in c.recorded_verdict]
    if not collected:
        return Prepared(
            question=asked,
            corpus=corpus,
            refusal=f"{corpus} holds no quotation that was found in its own document.",
        )

    passages = tuple(
        Passage(text=c.quote, source=c.document, note=c.claim, page=c.page) for c in collected
    )
    budget = (config.context_tokens - answer_reserve(config.context_tokens)) // 2
    try:
        selection = retriever.select(asked, passages, budget)
    except Exception as error:  # noqa: BLE001 - a ranking may fail for any reason
        # A ranking that cannot be made becomes a sentence on the screen. The alternative is
        # an exception raised on a worker thread, which a window reports by not repainting.
        return Prepared(question=asked, corpus=corpus, refusal=str(error))

    material = as_material(selection)
    reaches = config.engine_host if config.network_access else "this machine only"
    if not selection.chosen:
        return Prepared(
            question=asked,
            corpus=corpus,
            considered=selection.considered,
            how=selection.how,
            model=config.model,
            reaches=reaches,
            refusal=(
                f"Nothing in those {selection.considered} passages matches that question. "
                "The word ranking does not cross languages: a question in Spanish will not "
                "find quotations in English unless an embedding model is configured."
            ),
        )
    return Prepared(
        question=asked,
        corpus=corpus,
        material=material,
        chosen=selection.chosen,
        selected=len(selection.chosen),
        considered=selection.considered,
        set_aside=selection.set_aside,
        how=selection.how,
        model=config.model,
        reaches=reaches,
        tokens=estimate_tokens(material),
    )
