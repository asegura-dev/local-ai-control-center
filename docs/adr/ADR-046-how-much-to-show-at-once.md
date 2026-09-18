# ADR-046 - How much to show at once

## Status

Accepted.

## Context

ADR-045 built reading in passes for documents too large for the window. The measurement
that followed says the feature was aimed at the wrong problem.

Three documents that **fit comfortably** were read twice against the same engine, the same
model, the same window of 32,768 tokens and the same temperature - once whole, once in
passes of about three pages:

| | whole | in small passes |
|---|---|---|
| quotations | 59 | **232** |
| **verified quotations** | **45** | **207** |
| wall clock | 6.9 min | 13.2 min |

**Four and a half times the verified quotations for twice the time.** Per document the
density went 2.17 → 12.25, 2.56 → 4.00 and 1.00 → 4.90 quotations per page. The direction
was the same in all three.

The confound has to be named, because more passes are more generation budget: seventeen
calls against three. Per *call*, the whole document extracts as much or more - 26 against
18.4 on the first document. The effect is only visible in the right unit. **Per page
examined**, a reading of three pages yields about 2.8 times what a reading of twelve does.
That is attention, not budget: the same page, seen with fewer neighbours, gives up more.

Fidelity moved in both directions - 53% → 88%, 91% → 97%, 100% → 85%. More output carries
more fabrication in absolute terms, and the check is what separates them. In aggregate it
rose, 76% → 89%.

A second thing surfaced while measuring. **`_GENERATE_TIMEOUT_SECONDS` is a fixed 300**, and
(it is `_MINIMUM_GENERATE_TIMEOUT` now, and a floor rather than a ceiling - this paragraph
describes what was there before this record changed it)
passes on ordinary documents were observed taking 252 seconds. A generation that exceeds it
is reported as `Cannot reach Ollama` - a network fault, for something that is not one. The
fault classification added days earlier would call it a timeout and send someone to check a
firewall, which is a precise wrong answer in place of an imprecise one.

## Decision

**How much of a document to show at once is a setting, not a consequence of what fits.**
`--in-passes` keeps filling the budget by default, which is what a document too large needs.
`--pages-per-pass N` asks for readings of a stated size, which is what a document that fits
benefits from.

**It stays opt-in and the default does not change.** Four and a half times the quotations at
twice the cost is a good trade and it is not everyone's trade, and a flag that silently
quadruples the calls a run makes would be this project spending someone's evening for them.

**The measured numbers go in the guides, with their confound.** "More claims" without "and
2.8 times more per page examined, and roughly the same per call" is the kind of figure this
project has had to correct six times.

**The generation timeout is derived from the window rather than fixed.** The window bounds
the answer through `answer_reserve`; a conservative floor on tokens per second turns that
into a time. A number unrelated to the work being asked for is a number that will be wrong
in both directions.

**A timeout on `/api/generate` does not say what a timeout on `/api/tags` says.** One
follows a prompt of twenty thousand tokens that the engine is still working on; the other
follows a question about what models exist. The first reports slowness and names the prompt
size; the second reports unreachability. Merging them is what produced `Cannot reach Ollama`
for an engine that was reachable and busy.

## Consequences

- `passes_over` already takes a budget, so pass size needs no new mechanism in the core -
  only a way to say it at the command line and carry it through the cycle.
- Runs get slower and more numerous when the option is used. The preview says how many.
- `lacc collect --pages-per-pass` makes a bibliography cost hours rather than half an hour,
  and yields a corpus several times larger.
- The oversized-document path is unchanged; this is about documents that fit.

## Trade-off

**The gain is bought with compute, and the accounting should stay visible.** Per call the
model does not do better on a small pass - it does better per page, and the extra pages come
from asking again. Someone reading only "4.6x" will size a machine on the wrong number.

**More extracted claims means more fabricated ones in absolute terms.** On one of the three
documents the verified share fell from 100% to 85%: ten real quotations became forty-two
real ones and seven that are not in the paper. The check catches them and the corpus marks
them, and a reader who skims past the marks is worse off than before.

**Three documents are not a measurement of the general case.** This project wrote down, in
its own roadmap, that one run per configuration distinguishes nothing and that four are a
measurement. Three documents each run twice is better than the one-run comparison that got
recorded as a finding and was noise - and it is not enough to claim a rate. It is enough to
claim a direction, which is all this decision needs.

**Deriving the timeout from the window trades one wrong number for a less wrong one.** It
still has no idea how fast the engine is, or whether something else is using it - both
observed, in the run that produced these numbers.
