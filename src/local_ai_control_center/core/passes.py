"""Dividing a document too large for the window into readings that fit.

A pass is what the model sees. The whole document remains what a quotation is checked
against, which is the line ADR-045 draws: splitting changes the model's view and changes
nothing about the promise v1.0 shipped.

Pure. Given a document and a number of tokens, it decides where the readings fall. Nothing
here sends anything anywhere.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .budget import estimate_tokens
from .grounding import page_spans


class Pass(BaseModel):
    """One reading of part of a document, and which pages it covers.

    Frozen. The pages are carried so that a run can say how a document was read, rather
    than leaving a reader to assume the model held all of it at once (ADR-045).
    """

    model_config = ConfigDict(frozen=True)

    text: str
    first_page: int
    last_page: int

    @property
    def pages(self) -> int:
        """How many pages this reading covers."""
        return self.last_page - self.first_page + 1


def passes_over(source: str, budget_tokens: int) -> tuple[Pass, ...]:
    """Divide ``source`` into readings that each fit ``budget_tokens``.

    ``budget_tokens`` is for the document alone. What a skill wraps around it has to be
    subtracted by the caller, which knows the template and this does not.

    **Pages are the unit, and consecutive passes overlap by one - when two pages fit.** A
    passage running across a page break is the case ADR-042 exists for, and splitting on a
    boundary without overlap would cut exactly the quotations this project taught itself to
    find. Overlap costs one page of work per pass and buys the guarantee that any passage
    contained in two adjacent pages is wholly inside at least one reading.

    **That guarantee is lost when a single page fills the budget**, because then overlapping
    would hand the next reading the same page and never advance. Such a document is divided
    without overlap and a passage crossing one of its breaks is in no reading whole. It is a
    corner: the pages of a real paper run 1,400 to 2,000 tokens against a budget of 24,576,
    so a dozen fit. It is written down because a guarantee with an unstated exception is
    worse than no guarantee.

    **A source with no page markers yields nothing.** Anything LACC did not ingest has no
    pages, so there is no honest place to divide it, and saying so is better than inventing
    a boundary mid-sentence.

    **A single page larger than the budget is returned as its own pass anyway**, over
    budget. Dropping it would be this module deciding, silently, that part of a document
    does not count. The caller measures what it is about to send and refuses; that decision
    is not made here.
    """
    if budget_tokens <= 0:
        return ()
    spans = page_spans(source)
    if not spans:
        return ()

    readings: list[Pass] = []
    start = 0
    while start < len(spans):
        used, stop = 0, start
        while stop < len(spans):
            size = estimate_tokens(source[spans[stop][1] : spans[stop][2]])
            if stop > start and used + size > budget_tokens:
                break
            used += size
            stop += 1
        last = stop - 1
        readings.append(
            Pass(
                text=source[spans[start][1] : spans[last][2]],
                first_page=spans[start][0],
                last_page=spans[last][0],
            )
        )
        if stop >= len(spans):
            break
        # Overlap by one page, unless the reading was a single page - then overlapping
        # would hand the next round the same page and never advance.
        start = last if last > start else stop
    return tuple(readings)
