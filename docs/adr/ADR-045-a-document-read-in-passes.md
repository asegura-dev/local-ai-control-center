# ADR-045 - A document read in passes

## Status

Accepted. Sets the scope of v2.

## Context

v1.0 refuses a document that does not fit the window, and says so in the corpus. That is
correct and it is not enough: on the bibliography this project is built for, **eight of
twenty-four documents were refused**, and they are the central ones - nnU-Net, the EAU
guidelines, the NCCN article. A tool for writing from sources that cannot read the sources
that matter most has a hole where its purpose is.

The roadmap listed six things for v2 - library-scale work, splitting documents, conversation
across turns, letting the model choose what to do next, prompts as data, an interface beyond
the CLI. That is a list of phrases rather than a plan, and two of its entries are not safe to
build without deciding something first:

- **"Letting the model choose what to do next"** contradicts PRINCIPLES and VISION, which say
  in as many words that this never becomes an autonomous agent. It is out of v2, and it does
  not enter a later version without an ADR that says what "choose" is allowed to mean.
- **"Holding a conversation across turns"** makes a prompt depend on earlier runs, at which
  point a run's audit record no longer explains that run's output. The trail is v1's
  promise. Out of v2.

**Splitting a document is not a second goal beside library-scale work. It is the mechanism.**
Counting them separately made the plan look twice its size.

## Decision

**v2 is one thing: a document too large for the window can be read in passes, and the result
says that it was.** Everything else named above is out.

**Passes are whole pages, with one page of overlap.** `pages_in` already splits a source on
the `<!-- page N -->` markers ingestion preserves. Overlap is not a refinement: a passage
running across a page break is the case ADR-042 exists for, and without overlap this project
would cut exactly the quotations it taught itself to find.

**A pass is what the model sees. The whole document stays what the check compares against.**
`check_claim(claim, source)` keeps receiving the entire document, so a quotation is verified
and a page located against the real thing rather than against the fragment that produced it.
This is the load-bearing line of the decision: chunking changes the model's view and changes
nothing about the promise v1.0 shipped.

**Claims repeated across overlapping passes are merged on the normalized quotation**, using
the same folding the check uses, so that an overlap costs a little work and never a duplicate.

**Reading in passes is asked for, never substituted.** Without the flag, an oversized document
is still refused exactly as in v1.0; the refusal message names the flag. A document of 355,000
tokens becomes ninety provider calls and the better part of a day, and turning that on
silently - for a user who asked to read one file - would be this project deciding something
expensive on their behalf. Explicit over implicit.

**The preview states the cost before the confirmation, and one confirmation covers the run.**
How many passes, and an estimate from measured throughput. Confirming per pass would make a
long run unusable and would teach the user to stop reading the question.

**The answer and the audit both record that the document was read in passes, and how many.**
A model that never held the whole document cannot speak for the whole document, and a reader
who does not know that will assume it did.

## Consequences

- `extract_claims` becomes usable on the eight documents the corpus is missing, which is the
  measurable outcome this is judged on.
- `collect` reports passes beside the counts, so a corpus says how each document was read.
- The refusal path stays, and gains a sentence.
- Two roadmap entries are closed as out of scope rather than left to drift.

## Trade-off

**The model's view becomes local, and nothing warns when that matters.** A claim resting on
two distant parts of a paper - a method in section 2 and a limitation in section 7 - will not
be found by a reader who sees neither together. Passes buy coverage of the text and spend the
document's coherence, and no count of passes tells anyone which claims were lost.

Overlapping by one page means a claim can be produced twice and merged on its quotation.
Merging on the quotation, rather than on the claim, means two genuinely different claims
supported by the same sentence collapse into one. Accepted: the quotation is what carries
authority here, and the alternative is a corpus with duplicates in it.

A run of ninety provider calls behind one confirmation is a larger thing to approve than this
project has asked anyone to approve before. Mitigated by putting the number and the time in
the preview, and not by asking ninety times.

**This does not make the library readable, only its documents.** The corpus assembled from a
real bibliography is itself around thirty thousand tokens and exceeds the same window.
Synthesis across sources needs selection rather than traversal, it is a different mechanism,
and saying so here is what keeps v2 from quietly becoming v2 through v5.
