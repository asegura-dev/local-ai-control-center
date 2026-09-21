"""Turning selected passages into what a question is asked against (ADR-066).

Two pure functions that used to live in the view. Neither prints, and what they decide is
what a person then reads: which passages become the material of a prompt, and which ones are
offered beside a flagged reading as things that might carry it.

**Candidates, never support** is the discipline both of them keep. LACC ranks sentences; it
does not decide that any of them establishes anything.
"""

from __future__ import annotations

from local_ai_control_center.core.budget import estimate_tokens
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
