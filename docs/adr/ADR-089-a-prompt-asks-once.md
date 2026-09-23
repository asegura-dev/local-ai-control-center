# ADR-089 - A prompt asks once

## Status

Accepted. A measurement, not a design: `--in-passes` already existed and this record is about
what it turns out to be *for*.

## Context

`--in-passes` was built for documents too large for the context window (ADR-045). A document
that fits was read whole, because reading it in passes would be doing in five requests what
one request can do.

That premise was never checked. Checking it took one document and four minutes.

## What was measured

Six documents, all of which **fit the window**, collected both ways against the same model:

| document | tokens | read whole | read in passes |
|---|---|---|---|
| `eau-6.3-treatment-by-stage.md` | 19,315 | **18** of 18 | **103** of 119 |
| `[3] jnumed.119.234187.md` | 17,796 | **9** | **58** of 61 |
| `[22] diagnostics-13-03013.md` | 18,150 | **11** | **53** of 55 |
| `[21] j.crad.2020.06.031.md` | 14,411 | **7** | **49** of 55 |
| `[10] s00259-016-3573-4.md` | 14,080 | **5** | **45** of 48 |
| `[4] jnumed.118.215434.full.md` | 13,921 | **9** | **44** of 45 |
| | | **59** | **352** |

**Six times as many verified quotations, from documents that did not need passes at all.**

The reason is not subtle once it is stated: **the number of quotations a model returns is a
property of the prompt, not of the document.** Asked once about nineteen thousand tokens, it
answers with about twenty quotations. Asked five times about four thousand tokens each, it
answers with about twenty each time. The document was never the constraint.

And the quotations that arrive are different in kind, not only in number. Of the 103 from the
guideline section, **26 are about nodal disease against 4** from the single pass - because a
pass that sees four pages has no room to summarise and quotes what is in front of it.

## And what it costs, stated

**Passes invent more.** The one document with both figures is clear:

| | quotations produced | not in the document |
|---|---|---|
| read whole | 18 | **0** |
| read in passes | 119 | **16 (13%)** |

Across all five re-read papers, 15 of 264 were not found - about **6%**, against the project's
long-standing one-in-five. Either way the check catches them and they are marked; what this
records is that a higher yield is not a free lunch, and anyone quoting *"103 quotations"*
without *"of 119"* would be repeating this project's most frequent defect.

**It costs five requests instead of one**, which on a 14B model is minutes rather than
seconds.

## Decision

**`--in-passes` is not only for documents that do not fit. It is how a document is read when
you want what is in it rather than a summary of it**, and the guidance says so.

Nothing in the code changes. What changes is `docs/guides/asking-a-corpus-and-writing-from-it.md`
and the command's own help, which both described passes as the remedy for a document that was
refused.

**`--pages-per-pass` is chosen by tokens, not by pages.** A page of a journal article is about
1,300 tokens and a page of a two-column preprint about 320, so the same "3" means very
different things. The figure that mattered here was **three to four thousand tokens per
pass** - twelve pages of one document, three of another.

## Consequences

- The corpus went from **880 citable to 1,129** by re-reading five papers already collected.
- Two of this project's own measured figures are now known to be floors rather than ceilings:
  any document collected in a single pass is holding more than it gave.
- `lacc status` cannot see this. A document *has* quotations, so nothing is outstanding - and
  the stage is settled while five papers hold four fifths of what they say. That is a real
  limit of counting what exists rather than what is missing, and it has no fix here.

## Trade-off

**This makes a slow command slower for everyone**, and the yield is worth it only when the
document is worth it. A methods paper read in passes is a good trade; a fact sheet is not.

**The invention rate is higher and is reported as a rate**, which invites the reading that
passes are *less* reliable. They are not less reliable: every quotation is checked the same
way and the ones that fail are marked the same way. What is higher is the number of attempts.

**And a threshold nobody set is now load-bearing.** "Three to four thousand tokens per pass"
came out of two documents, not an experiment. It is written down as what was used, not as
what is right.
