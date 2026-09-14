# ADR-042 - What "unverified" was actually counting

## Status

Accepted - the decision stands. **Its measurements do not: see Correction, below.**

## Context

A quotation check has three outcomes, and LACC has been reporting two.

`verified` means the quotation is in the document and LACC could name the page.
`not_found` means the words are not there - a fabrication, the thing the check exists for.
`page_unknown` means the quotation **is** in the document and no single page could be
named: the source has no markers, or the passage runs across a break.

Every tally in the project counted `holds`, which is true only for `verified`. So
`page_unknown` was added to the failures, and every report said "did not check out" of
quotations that were genuinely present.

The corpus collected from a real bibliography says how much that mattered:

| | |
|---|---|
| Verified | 165 (69%) |
| **Found, no page determinable** | **72 (30%)** |
| **Not in the document** | **0** |

Two hundred and thirty-seven quotations, every one of them real, reported as 70%. The
"third of quotations that don't verify" named in three releases was a third that LACC could
not place on a page.

This is the fourth time in one session that a limit of this project has been reported as
the model's dishonesty.

## Decision

**`found` and `holds` are different questions, and reports lead with `found`.**

`found` asks whether the quotation is in the document, which is what decides whether
something can be cited. `holds` additionally requires a page, which measures LACC's ability
to place it rather than the model's fidelity.

**Fabrications and unplaceable quotations are reported separately.** Only the first carries
"do not cite without opening the document". The second is a note in passing, because a real
quotation whose page is unavailable is a smaller problem than the wording implied.

**`lacc measure` counts `found`.** Comparing models or prompts should measure the model, and
mixing in LACC's page-location ability is what made a corpus of real quotations look a third
fabricated.

**A quotation spanning a page break is placed on the page it starts on.** Adjacent pages are
searched as a pair when no single page contains it. The first page is the one a reader turns
to, and it removed the `page_unknown` category entirely on the paper this was measured on.

**The audit records all three counts**, so the distinction survives into the trail rather
than living only in a terminal.

## Consequences

- Reported rates rise, and the rise is a correction rather than an improvement: the
  quotations were always real.
- The corpus's true fabrication rate on a real bibliography is **zero of 237**; on a single
  paper measured after this change, one in fourteen.
- `CheckedClaim.found` joins `holds`; `collect`, `measure`, the CLI and the audit all use
  the one that answers the question being asked.

## Trade-off

Searching adjacent pairs will place a quotation on the wrong page if the same words appear
twice across different breaks. Accepted: it is rarer than the problem it fixes, and the page
reported is still one where the words genuinely are.

Two properties where there was one is more to hold in mind, and a future caller will
eventually pick the wrong one. Accepted because the alternative - a single number that
silently mixes the model's fidelity with the tool's page-location - is what produced three
releases of wrong figures. Names that force the question are worth the friction.

The uncomfortable part belongs in the record. This project's own measurements were wrong in
the same direction four times in one session, and every time the error flattered the tool by
making the model look worse. That is not a coincidence: a check that fails closed reports
its own limits as the thing it was built to catch, and nothing inside it can tell the
difference. Only looking at what it rejected could.

## Correction (v0.39.0)

The table above does not reproduce. Re-running the shipped code over the same 237 quotations
from the same bibliography gives different figures, and the published ones are the wrong
ones.

| | This ADR published | Re-measured, v0.38.0 | After the spacing fix |
|---|---|---|---|
| verified | 165 | 167 | **189** |
| found, no page | 72 | 0 | 0 |
| **not in the document** | **0** | **70** | **48** |

Each of the 70 was then tested against the marker-stripped document directly: **none** was
present as written, **22** were present once spacing is folded away, and **48** are absent by
every criterion tried. The 22 are the letter-spacing defect named in ADR-044 and fixed in
this release. The 48 are not a tool limit. Splitting each into sentences and
looking for them individually accounts for four: one whose sentences are all present but not
adjacent, three with some present and some not. **The remaining 44 are absent in any form
tried** - not stitched, not reworded, not there.

So the sentence "every one of them real" is false, and so is "zero of 237". The rate on this
corpus is **48 of 237, about one in five**, and it is the model's, not the tool's.

How the original figure was produced could not be determined from the record, which is its
own finding: a number was published without a way to re-run it. The method for the figures
above is the corpus at `corpus.md`, its source documents, and `check_claim` - re-runnable,
which is the point of ADR-044.

The direction is worth naming. Six measurements in this project had been wrong in the
direction that flattered the tool by making the model look worse. This ADR was the correction
to that pattern, and it overshot in the opposite direction: it reported a model with no
fabrications at all. A project that has learned it is biased one way is not thereby unbiased.

