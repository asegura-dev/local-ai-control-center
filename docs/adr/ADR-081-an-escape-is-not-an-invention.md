# ADR-081 - An escape is not an invention

## Status

Accepted. The sixth time this project has found a defect of its own being reported as the
model's dishonesty, and it was found the same way as the others: by auditing a real corpus
instead of a fixture.

## Context

A corpus of 881 quotations had **110 marked as no longer in their document**. Nobody had
looked at why. The documents were all still in the workspace, so it was not files going
missing.

One document failed **ten of ten**, which is not what random invention looks like. Its
quotations read:

    1st Breast 31 043 15.0%\n2nd Prostate 26 565 12.8%

That `\n` is two characters - a backslash and an `n` - where the page has a line break. The
model had quoted the table correctly; a JSON escape survived the answer being parsed, and the
check compared a two-character sequence against a newline and called the difference an
invention.

## What was measured, and what it was not

The first reading of this was that it explained the ten-of-ten document and probably much of
the 110. Counting:

| | |
|---|---|
| marked absent | **110 of 881** |
| carrying a literal escape | **8** |
| of those, recoverable | **6** |
| the rest | **102** |

**Eight, not a hundred.** The first impression was out by an order of magnitude, in the
direction that would have made this record sound more important than it is.

**And the other 102 are the model, correctly caught.** Looking at them beside the nearest text
in their document:

    quotation  The organ ratios differ only minimally among the various ligands.
               The average 1 h and 3 ...
    nearest    The average 1 h and 3 h SUV max of 18F-PSMA-1007 in tumor tissue...

Two sentences that are not adjacent in the page, joined into one quotation. That is invention,
the check caught it, and nothing here should change to let it through.

## Decision

**A literal escape is folded to the whitespace it stands for**, as a fifth transformation in
`_normalized`, beside the four that were already there.

It belongs with them by the same test each of those passes: **it removes a difference nobody
can see, and touches no content.** A changed word or a changed number still fails - which is
why the test that asserts `94.7%` quoted as `97.4%` still fails sits next to the one that
added this.

**Transport, not content.** A model answers in JSON; an escape surviving that is a fact about
the pipe, in the same way `sensi- tivity` across a line break is a fact about the page
(ADR-034). Nothing in a paper legitimately reads `\n`.

## Consequences

- Re-assembling the corpus took it from **771 citable to 777**, which is the six predicted.
- `docs/04-measurements.md` gains this as the sixth defect of this project reported as the
  model's.

## Trade-off

**A document that legitimately contains a backslash-n loses it.** Source code in an appendix,
a regular expression in a methods section, a path on Windows. In a medical bibliography that
is nothing; in a corpus of software papers it would be a real loss, and the fold is applied to
both sides of the comparison so such a quotation still matches itself - it is the rarer case
of quoting *about* the escape that this would blur.

**It is one fix among a hundred and two that are not fixes.** The honest summary of this audit
is that the check was right 102 times and wrong 8, and the 102 are the reason the check
exists. Reading this record as "the checking was broken" would be the opposite of what was
measured.
