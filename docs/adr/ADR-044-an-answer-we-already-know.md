# ADR-044 - An answer we already know

## Status

Accepted.

## Context

Every number this project has published about its own detection was measured against real
papers, where nobody knew the correct answer. That is the condition under which six
measurements in a row were wrong in the same direction.

| What was reported | What it was |
|---|---|
| The model is inconsistent | Temperature was never sent; the engine sampled at 0.8 |
| A third of quotations do not verify | A third could not be placed on a page (ADR-042) |
| The model fabricated two quotations | The PDF held `sensi- tivity` across a line break (ADR-034) |
| The model extracts few claims | The format was restated 9,000 tokens from generation (ADR-037) |
| The corpus covers the bibliography | Seven documents were refused for size and never named |
| Zero fabrications in an answer | The check looked at numbers, surnames and years, and not at the journal, where seven of ten attributions came from outside the material |

Every one of these flattered the tool. That is not luck. When the truth is unknown, a
check's own limit and the thing it detects produce the same output, and nothing inside the
check can tell them apart.

The live example is `_normalized`. A PDF whose extraction reads `A c c o r d i n gt o` -
letter spacing, not a line break - defeats the four foldings it applies. A faithful
quotation from such a document is returned `not_found`, which this project's own vocabulary
defines as "the words are not there - a fabrication, the thing the check exists for". The
defect ships today, and every corpus rate measured on such a paper is wrong by however many
of its pages were extracted that way.

What is missing is not another check. It is one document where the answer is known before
the question is asked.

## Decision

**A fixture corpus whose ground truth this project controls.** Documents written here, with
a recorded set of quotations that are genuinely present and a recorded set that are not.

**The assertion is exact, in both directions.** The seeded fabrications are found, and
nothing else is. A check that flags a real quotation fails this test as hard as one that
misses a fake, because reporting a limit as a catch is the failure in the table above.
"Catches most" is not an outcome this test has.

**The seeds are the defects already observed, not invented ones.** Each row of the table
above becomes a case, plus the ones ADR-031 through ADR-036 found: a quotation spanning a
page break, letter-spaced extraction, typographic look-alikes, a hyphen the typesetter
inserted, page furniture, a source with no page markers at all. The letter-spacing row
fails on the code as it stands, and is committed failing-first rather than after the fix, so
the record shows the test found it.

**Ground truth is data beside the fixture, not assertions inside a test.** What is real and
what is seeded must be readable without reading the test that consumes it, because a person
auditing this needs to grade the grader.

**The rate v1 publishes is the one this test produces**, over `CheckedClaim.found`. Rates
measured on real bibliographies remain in the record as observations of a run, and stop
being stated as the accuracy of the detector. They were never that.

**What the fixture cannot reach is written down.** It cannot tell whether a *claim* is true -
only whether its quotation is real, which is the boundary ADR-026 drew and this does not
move. And it measures the detector against the fabrications we thought of.

## Consequences

- `tests/fixtures/` gains the corpus and its truth file; `tests/test_grounding.py` gains the
  suite that reads both.
- One test fails on merge, deliberately, and `_normalized` is the change that turns it green.
- Any later edit to `_normalized`, `check_claim` or `pages_in` is measured against a fixed
  corpus, so a folding rule that quietly swallows a real difference fails instead of
  improving the numbers.
- The README and the guides state a measured rate with the corpus it was measured on, rather
  than a figure carried over from a run on real papers.

## Trade-off

A corpus of our own making measures the detector against our own model of the problem, and
flatters it exactly where imagination stops. Accepted: the alternative in place today
measures it against nothing gradeable at all.

Writing ground truth by hand makes a person the oracle, and a person can be wrong. Accepted,
because a wrong oracle can be read and corrected, and an unknown answer cannot be either.

A fixture drifts. Documents written to exercise a check stop resembling the documents the
check meets, and the suite goes green on a problem that has moved. Mitigated by seeding only
from defects that were actually observed, and by adding a row each time a new one is - which
is a discipline rather than a mechanism, and is what is available.

The uncomfortable part belongs in the record, as it did in ADR-042, because the count has
gone up since: six measurements, one direction, every one of them kinder to this project than
the truth. A check that is only ever run where nobody can grade it will report its own blind
spots as findings, indefinitely, and sound precise doing it.
