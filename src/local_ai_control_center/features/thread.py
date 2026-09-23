"""A thread of questions over one corpus (ADR-091).

It looks like a conversation and is deliberately not one. **A conversation puts the model's
previous answer into the next prompt**, and that single move breaks the only guarantee this
program makes: if one turn invents a quotation and the next is handed that answer, the
invention is now in what was sent, so it **verifies**. The check does not fail - it confirms.
Measured here, a 14B model puts an unfindable quotation into about one answer in five.

So what carries between turns is **what was checked**, never what was said:

- the passages a turn's answer quoted **and that were found** in what it was shown
- the questions, kept for a person to read, and put in no prompt

Nothing is guessed. A follow-up like *"and the specificity?"* means nothing to a retriever, so
the person writes a whole question; the thread is what saves them re-reading, not re-typing.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.ports.retriever import Passage


class Turn(BaseModel):
    """One question and what came back, as the thread keeps it."""

    model_config = ConfigDict(frozen=True)

    question: str
    answer: str = ""
    failure: str = ""
    seconds: float = 0.0
    selected: int = 0
    considered: int = 0
    established: tuple[Passage, ...] = ()
    """The passages this turn quoted **and that were found** in what it was shown.

    The whole of what this turn contributes to the ones after it. The answer's prose is kept
    to be read and is never sent anywhere again.
    """

    invented: int = 0
    """Quotations the answer carried that were not in what it was shown."""

    @property
    def worked(self) -> bool:
        return not self.failure and bool(self.answer)


class Thread(BaseModel):
    """A sequence of questions over one corpus, and what each established."""

    model_config = ConfigDict(frozen=True)

    corpus: str
    turns: tuple[Turn, ...] = ()

    @property
    def carried(self) -> tuple[Passage, ...]:
        """Every passage established so far, in the order it was established.

        Deduplicated on the words: the same sentence can be quoted by two turns, and sending
        it twice would spend a budget that admits about a fifth of a corpus on a repeat.
        """
        seen: set[str] = set()
        out: list[Passage] = []
        for turn in self.turns:
            for passage in turn.established:
                words = passage.text.strip()
                if words in seen:
                    continue
                seen.add(words)
                out.append(passage)
        return tuple(out)

    @property
    def asked(self) -> tuple[str, ...]:
        """The questions, for a person to read. They go in no prompt (ADR-091)."""
        return tuple(turn.question for turn in self.turns)

    def after(self, turn: Turn) -> Thread:
        """This thread with one more turn on the end. Frozen, so a new one comes back."""
        return self.model_copy(update={"turns": (*self.turns, turn)})


def established_by(sent: tuple[Passage, ...], found_quotes: tuple[str, ...]) -> tuple[Passage, ...]:
    """Which of the passages that were sent an answer actually quoted.

    Takes the quotations that were **found** and nothing else - a slice reaches only `core`
    and `ports`, and the shape of an answer belongs to another slice. The caller passes the
    verified quotations; whatever produced them is not this module's business.

    Matched by the quotation appearing **in** the passage rather than by equality: a model
    quotes a sentence out of a longer passage far more often than a whole one, and requiring
    equality would establish almost nothing.

    A quotation that was not found is simply never passed in. That is the point of the whole
    arrangement - an invention must not become material for the next turn (ADR-091).
    """
    wanted = [quote.strip() for quote in found_quotes if quote.strip()]
    if not wanted:
        return ()
    return tuple(
        passage for passage in sent if any(quote in passage.text.strip() for quote in wanted)
    )
