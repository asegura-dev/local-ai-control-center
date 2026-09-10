# ADR-031 - The page is found, not asked for

## Status

Accepted.

## Context

`extract_claims` asks a model for three things: a claim, a verbatim quotation, and the page
the quotation came from. The quotation is then checked against the source, and the page is
checked too - if the quotation appears somewhere other than the page claimed, the result is
marked *wrong page*.

The first run against a real paper showed that page attribution fails often and
independently of everything else. Page 4 for a sentence on page 1; page 3 for a sentence on
page 5. The quotations were real; the pages were invented. In a citation that is its own
kind of wrong, and it is the sort of error that survives review because the quotation
checks out when someone looks.

The uncomfortable part is that LACC already knows the answer. `check_claim` locates the
quotation in order to verify it - `found_on_page` is computed on the way past, and it is
correct by construction because it comes from searching the text rather than from a model
recalling where it read something. So the system asks a model a question it can answer
itself, gets a wrong answer often enough to matter, and reports the wrong answer next to
the right one.

## Decision

**When a quotation is found, the page LACC located it on is the page reported.** What the
model said about the page stops being an output.

The verdicts become:

- **verified** - the quotation is in the source, and LACC located the page it is on.
- **page unknown** - the quotation is in the source, but no page can be given: either the
  document has no markers, or the quotation spans a boundary and sits in no single page.
- **not found** - the words are not in the document.

**`wrong page` disappears as a verdict**, because the situation it described - a real
quotation with a bad page - no longer produces a bad page.

**The model is still asked for the page, and the disagreement is recorded in the audit.**
Dropping the question would save a line of prompt and lose a free measurement: how often a
model misplaces a quotation it copied correctly is a fidelity signal, and the audit is
where signals belong. It stays out of the answer the user reads, because a person checking
citations wants the right page rather than a note about someone else's error.

**The prompt is not changed.** The format a model is asked for stays exactly as it was.
This decision is being made while extraction quality is also under investigation, and
changing two things at once makes neither measurable.

## Consequences

- `CheckedClaim` reports the located page; the model's page is kept for comparison only.
- A new audit detail records how many claims placed a correctly-quoted passage on the wrong
  page, so model fidelity remains measurable.
- One of the two failure classes seen on a real paper stops existing rather than being
  reported more clearly.
- The CLI shows one page per claim, and it is right whenever the quotation was found.
- A quotation appearing on more than one page reports the first, which is a limit worth
  naming rather than a decision worth agonising over.

## Trade-off

A signal disappears from the user's view: they no longer learn that the model misattributed
a page. Accepted, because the signal was only ever useful for judging the model, the audit
keeps it for exactly that, and the person reading the output is trying to cite a document
rather than grade a model.

This narrows what the grounding check *catches* while improving what the system *reports*.
That is worth being explicit about: the check has one job less to do, not because the
failure was solved but because the question was withdrawn. A model that cannot be trusted
with page numbers is still a model that cannot be trusted with page numbers - LACC simply
stops relying on it for something it can determine itself.
