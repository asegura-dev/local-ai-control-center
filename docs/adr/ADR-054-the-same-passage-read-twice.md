# ADR-054 - The same passage read twice

## Status

Accepted. It also records a piece that was planned and **not** built, and the measurement
that stopped it.

## Context

Reading a document in passes offers the overlapping page to the model twice (ADR-045), so
`without_repeats` drops a quotation whose words have already appeared. It compares for
equality after folding, and equality is not the shape a repeat actually takes.

The corpus shows what it takes instead. `isensee2020` contributed two quotations, one wholly
inside the other: the second pass quoted the proposal, and it also quoted the sentence before
it. Two entries, one passage. The Globocan fact sheet did the same with a table - three rows,
then five. Equality saw nothing to merge in either.

The plan called for approximate deduplication next - MinHash over the corpus, on the stated
grounds that *"the corpus has near-duplicates between documents"*. That claim had never been
checked. It is now, over all 654 quotations of the real bibliography, across its 26 documents.

| | |
|---|---|
| near-duplicates **between** documents | **0** |
| identical after folding | 3 |
| one quotation inside another, and not caught by equality | 3 |
| every pair at Jaccard >= 0.3 | 12 |
| exact Jaccard over all 213,531 pairs | **133 ms** |

## Decision

**`without_repeats` drops a quotation wholly inside another, and keeps the longer.** Exact
substring after the same folding containment already uses - no threshold, no new module, no
dependency. The longer quotation is a superset of the shorter, so nothing that was verified
is lost by preferring it, and the surviving order is the document's rather than the order the
dropping happened in.

It is called with one document's claims, so this never reaches across documents - where the
same sentence in two papers is a fact about the literature and not a repeat.

**MinHash is not built, and neither is any similarity threshold.** Two reasons, and the
second is the one that matters.

**It solves a cost that is not there.** MinHash exists to avoid the quadratic blowup of
comparing everything with everything. Here the whole quadratic comparison, exact, takes 133
milliseconds. An approximation of a 133-millisecond answer is a worse answer at no saving,
and it would only begin to pay somewhere around a hundred times this corpus.

**And a threshold here would be wrong in the direction that costs the most.** The two most
alike quotations in the corpus that are not identical agree on 0.86 of their wording:

> *"**Apalutamide** is a category 1, preferred option for patients with M0 CRPC if PSADT is
> #10 months."*
>
> *"**Darolutamide** is a category 1, preferred option for patients with M0 CRPC if PSADT is
> #10 months."*

Two different drugs. One word apart, and that word is the entire content. Every conventional
near-duplicate threshold - 0.8 is the usual one in corpus deduplication - merges these and
silently deletes a treatment option from a corpus meant to be cited. **The highest-similarity
non-identical pair in this corpus is a pair that must be kept**, which is not an argument for
tuning the threshold higher. It is an argument that similarity is the wrong question when the
content lives in the words that differ.

## Consequences

- Passes stop producing two entries for one passage, which is what they were producing.
  Over the corpus this drops six quotations of 654 where equality dropped three.
- The corpus gains no new module and no new dependency.
- Duplication of *fact* rather than of *wording* - the same statistic in two papers worded
  differently - is untouched by this and will stay untouched until there are embeddings to
  see it. It is not a threshold problem, so a threshold was never going to find it.

## Trade-off

**Two different readings of one passage collapse into one.** The shorter quotation's
paraphrase is lost with it. `without_repeats` already made that trade for equality and the
reason is unchanged: the quotation carries the authority, and a corpus holding one passage
twice is worse than a reading lost.

**A short quotation that genuinely stands alone is dropped if it happens to sit inside a
longer one.** Real, and there is no way to tell it apart from a repeat by looking at the
text. Containment within a single document is the whole of the mitigation.

**Nothing here was measured on a corpus large enough to be general.** 654 quotations from 26
documents is what exists. The figures above describe it and are not a rate. If a corpus ever
does turn out to hold near-duplicates across documents, this record says what was measured
and when, and MinHash is still there to be built.
