"""Finding the part of a document a question is about (ADR-079).

`sections` lists what a document numbers; this ranks that list against a question, so a
guideline of 154 sections can be opened at the one that answers it rather than at the top.

**Nothing new is retrieved.** The ranking is the same `Retriever` a corpus is searched with,
pointed at a document's own outline instead of at quotations - which is why a word ranking
already works here, and why naming an embedding model makes it work across languages for the
same reason it does everywhere else (ADR-061).
"""

from __future__ import annotations

from local_ai_control_center.core.budget import estimate_tokens
from local_ai_control_center.core.sections import Section, summaries_in
from local_ai_control_center.ports.retriever import Outgoing, Passage, Retriever


def _openings(summaries: tuple[tuple[Section, str], ...]) -> tuple[Passage, ...]:
    """Each section as the passage a ranking reads: its number, and its title and opening."""
    return tuple(Passage(text=summary, source=section.number) for section, summary in summaries)


def sections_would_send(text: str, retriever: Retriever) -> Outgoing | None:
    """What ranking this document's sections would send to an engine, before it does.

    The openings `ranked` would rank, counted and not sent. A ranking by meaning keeps no
    store for a document, so every opening goes every time (ADR-106).
    """
    summaries = summaries_in(text)
    return retriever.would_send(_openings(summaries)) if summaries else None


def ranked(text: str, question: str, retriever: Retriever) -> tuple[Section, ...]:
    """The document's sections, the ones a question is most about first.

    Returns every section rather than a chosen few: which of them to read is the reader's
    decision, and a list that hid the rest would be deciding it for them. A document that
    numbers nothing returns nothing, as it does everywhere else.
    """
    summaries = summaries_in(text)
    if not summaries:
        return ()
    passages = _openings(summaries)
    # A budget large enough for all of them: the ranking is what is wanted, not a selection,
    # and a section dropped for space would be one the reader never sees.
    whole = sum(estimate_tokens(passage.text) for passage in passages) + len(passages)
    order = [passage.source for passage in retriever.select(question, passages, whole).chosen]
    by_number = {section.number: section for section, _ in summaries}
    first = [by_number[number] for number in order if number in by_number]
    rest = [section for section, _ in summaries if section.number not in set(order)]
    return tuple(first + rest)
