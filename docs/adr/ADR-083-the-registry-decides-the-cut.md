# ADR-083 - The registry decides the cut

## Status

Accepted. The repair for a defect ADR-064 named and did not fix.

## Context

Of 212 DOIs parsed from a bibliography, **40 resolved to nothing**. None was a work that does
not exist. Classified:

| | | |
|---|---|---|
| 3 | the DOI printed twice, run together | `10.1007/s00259-016-3346-0` **`10.1007/s00259-016-3346-0`** |
| 8 | the next entry's number and author | `...-2298-2` **`.17afsharoromieha`** |
| 9 | a word run on | `...-05473-2` **`.publisher`** |
| 20 | genuinely truncated | `10.1016/j.euo.2021` |

The first three groups have something **stuck to them**. The fourth is missing information.

## Decision

**Where there is evidence of contamination, offer a cut and let the registry decide.**

`shortened` proposes cuts - before a second DOI prefix, before a run-on tail - and `resolve`
tries them only when the full string resolved to nothing. A cut is accepted only if the
registry holds it. **Nothing here guesses what the DOI is; it asks.**

**A merely truncated DOI offers no cuts, deliberately.** Cutting one further can only produce
a *different* work, and **a wrong DOI in a bibliography is worse than a missing one** - the
first is a citation somebody will follow to the wrong paper, the second is a gap they can see.

## What it recovered

| | |
|---|---|
| resolved before | 172 of 212 |
| resolved after | **188** |
| recovered by a cut the registry confirmed | **16** |
| left, all genuinely truncated | 24 |

The estimate before building was "up to 20". Sixteen is under it, which is the side to be
wrong on.

## Trade-off

**It costs a request per cut**, on top of the one that failed. Bounded to the DOIs that
failed and to the two or three cuts a contaminated string offers, and only ever for strings
that showed evidence.

**A cut could in principle find a real but different work.** The evidence conditions make it
unlikely rather than impossible: `10.1007/x.17smith` cut to `10.1007/x` is the same prefix and
one entry's worth of tail. The registry confirming it is not proof that the cut was the right
one - only that the cut is *a* work. That is the weakest link here and it is stated rather
than hidden.
