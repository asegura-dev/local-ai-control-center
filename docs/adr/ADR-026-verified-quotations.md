# ADR-026 - Quotations are checked against the document they came from

## Status

Accepted. The page-checking part is superseded by
[ADR-031](ADR-031-the-page-is-found-not-asked-for.md): the page is now found by LACC rather
than taken from the model and checked against it, so the *wrong page* verdict below no
longer exists. Everything about the quotation itself stands.

## Context

For work that gets published, the failure that matters is not a shallow answer. It is an
invented one: a quotation that was never written, attributed to a page that does not
contain it, in prose confident enough that nobody checks.

A prompt can ask a model not to fabricate. It cannot stop it, and every prompt in LACC that
says "add nothing the document does not contain" is a request rather than a control. What
*can* be prevented is fabrication going unnoticed, and that part is mechanical: a quotation
either appears in the source or it does not.

## Decision

A skill `extract_claims` returns what a source asserts, each claim with a verbatim
quotation and the page it came from:

```text
CLAIM: Attention outperforms recurrence on long sequences.
QUOTE: self-attention layers are faster than recurrent layers
PAGE: 6
```

A line-oriented format rather than JSON. A small local model follows it far more reliably,
and a malformed block costs one claim instead of failing the whole answer.

**Every quotation is checked against the source text.** Whitespace is collapsed and case is
folded, then the quotation must appear as an exact substring. There is no fuzzy matching:
a quotation that only nearly appears is not a quotation, and accepting near-misses would
defeat the check it exists to perform.

**The page is checked too.** Ingestion preserves `<!-- page N -->` markers (ADR-016), so
the quotation must appear in the region the claim attributes it to. A real quotation with
the wrong page is reported as that, not as a failure.

Each claim ends up marked *verified*, *not found* or *wrong page*, and nothing is removed.
Deleting an unverified claim would hide what the model did; the point is to show it. The
counts are recorded in the audit.

A skill declares that its output is to be checked, through a flag on its plan. The cycle
runs the check against the contents it already read and records the result. The checking
itself is a pure function with no model involved: what verifies the model is not another
model.

## Consequences

- `lacc run extract_claims <path>` returns claims with quotations, each marked with whether
  it was found in the source and on the page it claims.
- A new module holds the parsing and the checking, both pure and directly testable.
- `SkillPlan` carries a flag for output that should be checked; the cycle honours it.
- A new audit event records how many quotations were checked and how many held.
- The check bounds what can be trusted, and does not extend it: a verified quotation proves
  the text appears in the document, not that the claim built on it is sound. A model can
  quote accurately and reason badly, and this catches only the first.
- Extraction from a document LACC did not ingest has no page markers; pages are then
  reported as unverifiable rather than wrong.

## Trade-off

Exact matching will reject quotations a person would accept - a changed dash, a fixed
typo, an ellipsis. Accepted, and it errs the right way: a false "not found" is visible and
costs a glance, while a false "verified" is the failure this exists to prevent.

Asking a small model for a rigid format costs some claims to malformed output. Accepted:
the format is the simplest one that can be parsed, and a claim lost to bad formatting is
better than a claim invented and believed.
