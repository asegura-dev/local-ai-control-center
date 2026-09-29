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
from local_ai_control_center.ports.retriever import Outgoing, Passage, Retriever


def rendered(passages: tuple[Passage, ...]) -> str:
    """Render passages as the text that goes into a prompt.

    One renderer, because a thread sends passages a selection did not choose and rendering
    them a second way would be a second thing to keep true (ADR-091).
    """
    blocks = []
    for passage in passages:
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


class Ranked(BaseModel):
    """What a ranking by meaning sent to the engine, and whether it came back (ADR-108)."""

    model_config = ConfigDict(frozen=True)

    sent: Outgoing
    failed: str = ""
    """What the engine said when the ranking did not come back, or empty."""


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

    established: int = 0
    """How many of the selected passages a thread had already established (ADR-091).

    Zero for a question asked on its own. Shown, because an answer resting mostly on what
    earlier turns established is an answer about the thread rather than about the corpus.
    """

    set_aside: int = 0
    how: str = ""
    """Which ranking chose them, in the retriever's own words."""

    model: str = ""
    reaches: str = ""
    tokens: int = 0
    """The material alone, estimated. The instruction around it is counted separately."""

    refusal: str = ""
    """Why this cannot be sent, in a sentence, or empty."""

    awaiting: Outgoing | None = None
    """What ranking would send to an engine, waiting for somebody to agree to it (ADR-106).

    Set only when nothing was ranked for that reason. Nothing has left the machine, and this
    is the preview: what would go, to which model, reaching where.
    """

    ranked: Ranked | None = None
    """What the ranking sent to an engine, set whenever it reached one (ADR-108).

    Whether it came back or not, so the terminal and the window record the same thing from
    the same value rather than each working out afterwards whether a ranking happened.
    """

    @property
    def sendable(self) -> bool:
        """Whether there is anything to send. The button is drawn only when this is true."""
        return not self.refusal and self.selected > 0

    @property
    def asks(self) -> str:
        """The sentence somebody agrees to before the ranking sends anything, or empty."""
        return ranking_would_send(self.awaiting, self.reaches) if self.awaiting else ""


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


def reaching(config: Config) -> str:
    """Where a call to the configured engine goes, in the words a preview uses."""
    return config.engine_host if config.network_access else "this machine only"


def ranking_would_send(
    outgoing: Outgoing,
    reaches: str,
    sends: str = "your question",
    one: str = "quotation never embedded before",
    many: str = "quotations never embedded before",
) -> str:
    """What ranking by meaning would send, as the sentence somebody agrees to (ADR-106).

    One wording for the terminal and the window, so the two cannot describe the same sending
    two ways. ``sends`` is what goes every time; ``one`` and ``many`` name the passages that
    go with it, when some have no stored vector.
    """
    count = outgoing.unembedded
    more = f" and {count} {one if count == 1 else many}" if count else ""
    return f"Ranking by meaning sends {sends}{more} to {outgoing.model}, reaching {reaches}."


def before_preparing(config: Config) -> str:
    """What pressing Prepare sends, said beside it before it is pressed (ADR-106).

    The line is the preview and the press is the agreement - to the question alone. Anything
    beyond it is shown after the press, and sent only by a second one.
    """
    if not config.embedding_model:
        return (
            "Prepare ranks the corpus by the words you use, on this machine: nothing leaves it "
            "until you press the button that appears after."
        )
    return (
        f"Prepare sends your question to {config.embedding_model}, reaching "
        f"{reaching(config)}, to rank the corpus by meaning as well as by words. The prompt "
        "goes only with the button that appears after."
    )


def prepare(
    question: str,
    corpus: str,
    text: str,
    config: Config,
    retriever: Retriever,
    carried: tuple[Passage, ...] = (),
    agreed: int | None = None,
) -> Prepared:
    """Read a corpus, rank it against a question, and report what would be sent.

    **The prompt is not sent here, and the ranking sends only what was agreed.** Ranking by
    meaning embeds the question and every quotation with no stored vector yet - on a corpus's
    first question, all of them. ``agreed`` is how far somebody has allowed that: ``None``
    for nothing, ``0`` for the question alone, a number for the question and up to that many
    quotations. When the ranking would send more, nothing is ranked, and the result says what
    it would send and waits (ADR-106). Ranking by words needs no agreement: it never leaves
    this machine.
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
    reaches = reaching(config)
    outgoing = retriever.would_send(passages)
    if outgoing is not None and (agreed is None or outgoing.unembedded > agreed):
        # Nothing is ranked, so nothing is sent. What the ranking would send is the preview
        # somebody agrees to first - and agreeing to fewer quotations than there now are is
        # not agreeing to these (ADR-106).
        return Prepared(
            question=asked,
            corpus=corpus,
            considered=len(passages),
            model=config.model,
            reaches=reaches,
            awaiting=outgoing,
        )
    budget = (config.context_tokens - answer_reserve(config.context_tokens)) // 2
    ranked = Ranked(sent=outgoing) if outgoing is not None else None
    try:
        selection = retriever.select(asked, passages, budget)
    except Exception as error:  # noqa: BLE001 - a ranking may fail for any reason
        # A ranking that cannot be made becomes a sentence on the screen. The alternative is
        # an exception raised on a worker thread, which a window reports by not repainting.
        # What it tried to send is kept: it reached for the engine, and that is recorded.
        failed = Ranked(sent=outgoing, failed=str(error)) if outgoing is not None else None
        return Prepared(question=asked, corpus=corpus, refusal=str(error), ranked=failed)

    # What a thread already established goes in front of what the ranking chose for this
    # question, and the budget runs out on the new material rather than on what a previous
    # turn already stood on. Empty for a question asked on its own (ADR-091).
    kept = {passage.text.strip() for passage in carried}
    chosen = (*carried, *(p for p in selection.chosen if p.text.strip() not in kept))
    material = rendered(chosen)
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
            ranked=ranked,
        )
    return Prepared(
        question=asked,
        corpus=corpus,
        material=material,
        chosen=chosen,
        selected=len(chosen),
        established=len(carried),
        considered=selection.considered,
        set_aside=selection.set_aside,
        how=selection.how,
        model=config.model,
        reaches=reaches,
        tokens=estimate_tokens(material),
        ranked=ranked,
    )
