# ADR-123 - What the thesis's corpus showed the checker

## Status

Accepted on 1 October 2026. Three defects found by building the thesis's corpus on the same
day, all measured before anything was changed. Decided by the user ahead of the notes per
reference, which will be built on this corpus.

## Context

The thesis's 65 references gave 4,844 quotations, and `lacc corpus` found 4,395 of them in
their documents. Three things in that work were not as they should be.

- **The checker refused faithful quotations for their citation marks.** Two documents stood
  out: `chen22.md` had 51 of 103 quotations not found, and `lecun.md` 33 of 100. Each refused
  quotation was compared, with the checker's own `nearest_text` and normalisation, against
  the nearest sentence of its document.
  - Most of them were near-verbatim: 30 and 26, against 6 and 2 that the documents do not
    contain. Across the corpus, 164 of the 449 refused quotations are 90% or more alike to
    their document.
  - Among what separates them, the largest single kind is bracketed citation marks the model
    left out: `[7], [8]`, `[9]-[11]`.
  - **Measured:** dropping numbered marks in brackets on both sides verifies 52 of the 449,
    and stops none of the 4,395 from verifying. Dropping parenthesised lists as well gives
    three more.
  - Ligatures, guessed first, were not a cause: `casefold()` already turns `ﬁ` into `fi`.
- **Two papers were filed as topics lists.** `status` counted 63 documents of 65, because
  `dkd.md` and `liu19.md` were taken for topics lists. A topics list is recognised by a line
  opening with `!`, and both papers have one in their opening.
  - In `dkd.md` it is a formula the extraction garbled: `!"#$$%&#"'(=*!'(+,−./`.
  - In `liu19.md` it is a `!` alone on its line, which the rule `^!\s*\S` matched anyway,
    because `\s` crosses the line break and the next line supplied the `\S`.
- **`collect` asked "Read 1 documents and write corpus-lckd.md?"** when it was run for the
  65th reference.

## Decision

1. **A numbered citation mark in brackets is not part of the sentence.** The checker's
   normalisation drops `[7]`, `[7], [8]`, `[9]-[11]` and `[3, 5]` on both sides, after folding
   dashes, so `[12–14]` is covered too.
   - Parentheses are left alone, because `(3)` can be content, and they were worth three
     quotations.
   - A number in the sentence itself is untouched: `0.846` changed to `0.864` still fails.
   - The seeded corpus of ADR-044 passes unchanged. In it, every real quotation is found and
     every planted fabrication refused, with no error allowed in either direction.
2. **A converted document is never a topics list.**
   - A file opening with ingestion's page marker, `<!-- page 1 -->`, is a document; a person
     writing a topics list never opens it that way.
   - The control mark is recognised only when it is followed on its own line: `^![ \t]*\S`.
3. **`collect` asks about one document in the singular**, through `counted`.

## Consequences

- **Rebuilt without a model.** `lacc corpus` re-checked all 4,844 quotations into
  `citas-v2.md`:
  - **4,447 are in their documents, up from 4,395, and 397 are not**, exactly the 52 the
    measurement predicted;
  - it took 197 seconds;
  - `status` now counts 65 documents.
- Tests:
  - `tests/test_grounding.py`:
    - a quotation without `[7], [8]` and `[9]-[11]` is found;
    - a changed figure still fails, while a different bracketed number does not;
    - a number in parentheses is kept.
  - `tests/test_kinds.py`: a converted paper with a garbled formula, or a lone `!`, is a
    document; a lone mark is not a control.
  - `tests/test_cli.py`: `Read 1 document`.
- `tests/test_seeded_corpus.py` passes unchanged: no planted fabrication became a quotation.
  ADR-044's other measurement, 231 quotations each mutated by a word or a digit, was not
  re-run for this change.

## Trade-off

**A bracketed number that is content is now ignored.** A paper that writes a value in square
brackets, `[95]`, would have that number dropped from both sides, and a quotation that changed
it would pass. No such case was found in the 4,844, and parentheses were left out of the rule
for this reason.

**The other causes stay.** Of the 164 near-verbatim refusals, the rest have other causes:
- quotations the model cut with `...`;
- a table's caption that falls mid-sentence;
- a symbol the extraction broke, so the PDF gives `6` where it prints `±` and the model
  restores it;
- a citation number glued to a word, as in `models71`.

Each would need a rule of its own, and each rule is a way to forgive a real change, so none
is taken here without its own measurement.
