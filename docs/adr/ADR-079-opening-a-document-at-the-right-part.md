# ADR-079 - Opening a document at the right part

## Status

Accepted. Nothing new was built: two things that existed were pointed at each other.

## Context

`lacc sections` finds what a document numbers - 154 of them in the EAU guideline - and
`--take` pulls one out. Both require knowing **which one you want**, and a list of 154
fragments, several with titles extraction left cut in half (`5.2.4 Imag`, `5.1.1 Pr`), is not
a thing to read down.

The question a person actually has is *"where does this guideline talk about nodal staging?"*,
and answering it meant scrolling.

Meanwhile `Retriever` has ranked passages against a question since ADR-061, over a corpus of
quotations. A document's own outline is a set of passages too.

## Decision

**Rank the sections a document numbers against a question, with the retriever already
configured.** No new port, no new model, no new concept.

**A section is represented by its title *and* the opening of its body.** This is the part that
makes it work. Ranking titles alone would be ranking fragments - `Imag`, `Pr`, `N-st` - and
would fail exactly on the documents that need this most, because the ones with the worst
extraction are the ones too large to read. Twenty-five lines is enough for a section to say
what it is about.

**A summary stops at the next section**, never at a line count alone. A section shorter than
the window must not borrow its neighbour's words, or the ranking credits it with what the next
one says.

**Every section is returned, in order.** Not the best few. Which to read is the reader's
decision, and a list that showed only the top would be making it for them - the same stance
`--about` on a corpus takes, where nothing is removed and everything is marked (ADR-046).

## What it does, measured on the real guideline

Asked *"lymph node metastasis detection and nodal staging"* of 154 sections:

| | |
|---|---|
| 1 | 4.5 Recommendations for classification and staging systems |
| 2 | **5.8 Diagnosis - Clinical Staging** |
| 3 | 4.4 Prognostic relevance of stratification |
| 4 | **5.8.2 N-staging** |

**The section that answers the question is fourth, and a closely related one is second.** That
is the honest description: it takes 154 down to a handful with the right one among them. It is
not "it finds the section", and saying so would be the kind of claim this project keeps having
to correct.

Taking 5.8.2 out gives **3,561 tokens of 348,276** - the thresholds for nodal size on CT and
MRI, which is the passage this bibliography exists to reach.

It works with the word ranking alone. Naming an embedding model makes it work across
languages, for the same reason it does everywhere else.

## Consequences

- `lacc sections <doc> --about "<question>"` orders them, and `--take` still does the taking.
- `core/sections.py` gains `summaries_in`, pure.
- `features/navigate.py` holds the ranking, which reaches for `core` and a port and nothing
  else.

## Trade-off

**The ranking is over an opening, not over a section.** A section whose subject only appears
in its last paragraph ranks badly, and there is no way to tell from the output that this
happened. Reading the whole of every section would be accurate and would mean holding a
348,000-token document in memory to answer one question.

**It cannot say a document does not discuss something.** Every section is returned in some
order, so the list always looks like an answer. A guideline with nothing about nodal staging
would still put four sections at the top.

**And it ranks what the extraction produced.** A heading cut to `Imag` contributes its body
and not its name, which is the mitigation and not a fix.
