# ADR-035 - What counts as the same text

## Status

Accepted. Refines the matching rule in
[ADR-026](ADR-026-verified-quotations.md), which stands in every other respect.

## Context

ADR-026 decided that a quotation must appear in the source as an exact substring "after
collapsing whitespace and folding case", and that nothing fuzzy is ever accepted. The
reasoning holds. The definition did not.

Auditing LACC against a real paper found three ways a faithful quotation failed, none of
them the model's doing:

**Words the typesetter broke.** The PDF holds `sensi- tivity` and `avail - able` across
line breaks, and ingestion preserved them. A model quoting the sentence correctly could not
match.

**Typographic characters.** The paper is set with en-dashes, non-breaking hyphens and curly
quotes. A model reading `76–90%` writes `76-90%`, because that is what the range means and
what a keyboard has. Sixteen of that paper's hundred and sixty sentences could not be
verified even when quoted perfectly.

**An asymmetry the first fix created.** Rejoining only when whitespace followed the hyphen
fixed `sensi- tivity` and broke `inter- reader` - a real compound the typesetter split at
its own hyphen, so the document normalised to `interreader` while a model writing
`inter-reader` did not.

Each of these was reported as *not in the document*, which reads as the model inventing a
citation. The project spent a session concluding that a model fabricated three of seven
quotations from a scientific paper, and wrote that conclusion down twice. **The fabrications
were LACC's.**

## Decision

**A difference a reader cannot see is representation. A difference a reader can see is
content.** Normalisation removes the first and must never touch the second.

Four transformations, and each one is defended by that line rather than by whether it
improved a number:

- **Case folds.** `Results` and `results` are the same word on the page.
- **Whitespace collapses.** A line break, a double space and a tab are typesetting.
- **A hyphen between letters is removed**, with or without space around it. A typesetter can
  insert one at a line break or leave one out, and the reader sees the same word. The two
  cases cannot be told apart from the text, so both sides are treated alike rather than
  guessed at.
- **Typographic characters fold to the ASCII a model writes.** En-dash, em-dash,
  non-breaking hyphen, minus sign, curly quotes and prime marks.

**Numbers keep their hyphens.** `the 5 - 10 range` is a range, and joining it into `the 50
range` would be a worse error than the one being fixed. The rule is letters on both sides.

**Nothing here loosens the refusal.** A changed word, a changed number, an added clause and
a dropped negation all survive every transformation and still fail. `was 82%` and
`was 76-90%` do not match, which is the case the whole check exists for.

## Consequences

- On the paper this was found with, the 14B model went from four verified quotations out of
  seven to **seven out of seven**, at temperature zero, repeatedly. Every apparent
  fabrication was this project's own defect.
- Ten per cent of that paper's sentences were unquotable before this and are not now.
- The rate of invention reported in v0.28.0 and v0.29.0 was wrong three times over, and each
  correction moved it down as another of LACC's defects was removed.
- One artefact remains and is not addressed here: the journal's running header extracted
  *inside* a sentence, which breaks two of the paper's hundred and sixty sentences. That is
  ingestion writing a document a human would also find wrong, and it belongs in the
  converter rather than in the comparison.

## Trade-off

Every fold widens what counts as the same text, and widening is exactly what ADR-026 warned
against. The protection is that the boundary is stated and is not similarity: each
transformation removes something invisible on the page, and none is justified by a
measurement improving. A fold that made a wrong quotation match would be a fold that crossed
the line, and no rule here can.

Removing hyphens between letters will accept `re-cover` for `recover`, which are different
words. Accepted: the alternative is guessing which hyphens a typesetter inserted, and a
citation check that rejects a correctly-copied sentence is worse than one that accepts a
rare homograph.

There is a harder lesson under this, and it is worth writing down rather than fixing
quietly. **The check that exists to catch a model deceiving you was, for three releases,
reporting this project's own defects as the model's dishonesty.** Nothing in the design
caught that; a feature built for something else did, on a real document. Verification tools
need verifying, and the only thing that did it was running against real material and looking
at what failed.
