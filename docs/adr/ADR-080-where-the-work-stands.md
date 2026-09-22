# ADR-080 - Where the work stands

## Status

Accepted. The record of getting it wrong three times is most of what is worth reading here.

## Context

`tools/measure.py` reports the **project**: layers, tests, records, and the size of the
material. What nothing reported is the **work**: how far a bibliography has got through
converting, collecting, assembling, resolving and reviewing, and what each of those is still
missing.

That question was answered by remembering, which is how *"eight of 24 documents never entered
the window"* survived for days after the number had become two.

## Decision

**`lacc status`: six stages, each with what it produced and what it has not.**

    Documents     30 brought in, 3 sections taken out of them
    Quotations    832 from 27 documents        3 with none
    Corpus        723 citable of 832           109 no longer in their document
    References    21 of 30 parse, 205 DOIs     9 cannot be read
    Bibliography  172 works resolved           33 DOIs unresolved
    Writing       2 drafts reviewed

**A stage reports what is missing, not only what is done.** *"832 quotations"* reads like
success. *"832 quotations, 3 documents with none"* is the same fact with the part that still
needs doing attached, and this project has measured what the first kind of sentence costs.

**Counted from the files, every time.** Nothing stored, nothing estimated, no model called and
nothing sent. The same stance the measurement tool takes and for the same reason: a figure you
can re-take in seconds never has to be trusted.

**A stage with no material is not settled.** With an empty workspace, "References" read *"0 of
0 parse"* and called itself done - a stage reporting success for having no work. Found by the
test that asserted an empty workspace settles nothing.

## What the first three readings got wrong

Each reading was plausible and each flattered. The figure fell every time, which by now is the
expected shape.

**First: 236 works resolved.** `resolve` had said 172. It was counting every bullet in the
bibliography, including the DOIs the registry does **not** hold and the documents that carry
none - the two failure lists, counted as successes. Only the entries under `## Resolved` count
now.

**Second: six documents with no quotation.** Three were sections `sections --take` had written
out of the guideline, one was the user's own notes, one a test fixture. A file LACC extracted
is not a document somebody brought, and it is recognised by how it opens: with the number of
the section it is.

**Third: the extracted sections were still miscounted**, because a section opens `5.2.4` with
nothing after it and the pattern required a space. A carriage return and an end of line are
not the same thing.

After three corrections: 172, and three documents with no quotation of which **one is a real
gap** - the guideline - and two are not documents to collect from.

## Consequences

- `lacc status` answers *where am I* without remembering anything.
- `features/stages.py` is the one place that decides what a stage is and when it is settled.
- The classification of a Markdown file - corpus, bibliography, review, extract, document -
  now has a name for what an extraction produced.

## Trade-off

**A stage is settled or open, and nothing in between.** A corpus missing one document of
thirty reads exactly like one missing twenty-nine. The counts are there to be read, but the
word is binary and a binary word about a gradual thing will mislead somebody.

**It recognises files by how they open.** A document whose first line happens to be a number
is filed as an extract. That is the same trade every recogniser here makes, and it is wrong
in the direction of counting less rather than claiming more.

**And it reports the largest corpus as the one being worked from.** That is true here and is
a guess: somebody whose working corpus is a small focused subset of a larger one will be told
about the larger.
