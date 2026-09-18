# ADR-057 - The prompt and the grammar disagreed

## Status

Accepted.

## Context

ADR-052 lets the engine enforce a skill's output shape. ADR-055 made it reachable. ADR-056
fixed the parser that was throwing the result away. What none of them touched is the prompt.

**It was byte-identical whether or not a schema was sent.** The audit records it: the same
`prompt_sha256` under both conditions, and that prompt says

> Use this format, and nothing else:
>
> CLAIM: what the document asserts
> QUOTE: the exact words from the document
> PAGE: the page number

and ends, after the document, by seeding `CLAIM: ...`. With the schema on, the grammar
**forbids** every one of those characters. The model was instructed to produce a format it was
physically prevented from producing.

That is very likely why the enforced run never stopped. A model's sense of *done* is tied to
the shape it was asked for; told to write labelled blocks and prevented from writing them, it
had nothing that said the answer was finished. It ran to the token cap - 8,192 tokens - and
spent the last third repeating one table caption.

**And a second defect was found looking for the first.** `assess_source` sets
`verify_quotes=True`, which was the test for whether a shape could be enforced (ADR-055). Its
answer is not a list of blocks: it is three headings of prose - what is new, what overlaps,
what contradicts - **and then** a list of blocks. Forcing that into `{"entries": [...]}`
deletes the part a reader reads. Nobody had enforced it, because until ADR-055 nobody could.

## Decision

**A skill asks for the shape the engine will enforce, and never for a different one.** One
helper builds both forms from the same field labels, so the two cannot drift: labelled lines
when nothing is enforced, a described JSON object when something is. The restatement after the
document changes with it, because stating a format thousands of tokens before generation cost
two thirds of the claims (ADR-037) and that reason does not care which format it is.

**The enforced form asks the model to close the array.** There is no structural way to bound
it that does not invent a number - `maxItems` needs one - so this is an instruction, and this
project's own measurement says instruction is the weaker of the two. It is named as the weaker
half rather than relied on, and whether it helps is measured, not assumed.

**Whether a shape may be enforced is decided by `answer_is_entries_only`, not by
`verify_quotes`.** A skill declares that its whole answer is the blocks. `extract_claims`,
`ask_corpus` and every declared skill say so; `assess_source` does not, so naming it in
`enforce_shape` is inert. This replaces the test ADR-055 chose, which conflated *checks its
quotations* with *has nothing else in its answer*.

**The unenforced prompt does not change, byte for byte.** Verified against the audit: the same
`prompt_sha256` as before this record, the same answer digest, the same nineteen quotations.
A fix for a path nobody uses by default must not disturb the path everybody does.

## Consequences

- The enforced and unenforced prompts are built from one description of the fields, so a field
  added to a skill reaches both.
- `assess_source` cannot be shape-enforced, and says so in a test rather than in a comment.
- ADR-055's `verify_quotes` condition is superseded.

## Trade-off

**Two prompts to reason about where there was one.** Both come from the same labels, which is
the mitigation, and a skill author still writes neither.

**"Close the array when you are done" is a request, and requests get negotiated here.** The
project's most-cited measurement is that structure is obeyed where instruction is not. Asking
is what is available; the alternative is a number nobody can justify. If it does not work, the
honest options are a bounded array with the number argued for, or leaving the cap to do it and
relying on the recovery in ADR-056.

**It changes a prompt, and prompts are measured things here.** The unenforced one is unchanged
and that is checked. The enforced one is new, was never good, and is measured below.

## Measured

Same skill, same paper, same 14B at temperature zero, four measured runs each with a warm-up.
Every measured run within a condition was byte-identical. Deduplication applied as ADR-058
now applies it.

| | lines | schema, prompt contradicting it | schema, prompt agreeing |
|---|---|---|---|
| **why it stopped** | `stop` | **`length` - the cap** | **`stop`** |
| answer tokens | 1,621 | 8,192, unfinished | **2,006** |
| one run took | 58 s | 290 s | **73 s** |
| claims returned | 19 | 76 | 20 |
| after deduplication | 16 | 35 | **20 - no repeats at all** |
| found in the document | 15 | **32** | 18 |
| rate | 93% | 91% | 90% |

**The contradiction was the cause of the non-termination, and removing it fixed that
completely.** The answer ends by itself, in a quarter of the tokens and a quarter of the time.
Nothing else about the run changed.

**It did not make the enforced path better at finding quotations, and the record should not
claim it did.** Eighteen verified against the line format's fifteen is a modest gain, the rate
is three points lower, and a run costs a quarter more time. What did change markedly is
repetition: twenty claims survived deduplication out of twenty, where the line format lost
three of nineteen.

**And the broken configuration still returns the most verified quotations - thirty-two.** Not
because breaking it helped, but because a model that cannot stop keeps extracting, and a good
deal of what it extracted was real until it began repeating a table caption around the
fiftieth entry. Buying thirteen more verified quotations with four times the wall clock and an
answer that has to be salvaged is not a trade to take, and **how exhaustive to be is a
separate question from whether the prompt should contradict the grammar.** ADR-046 already
poses the first one properly, with passes.

**A caveat this measurement produced by accident.** The warm-up answer differed from the four
that followed it - a different digest, 2,030 tokens against 2,006, and nineteen verified
rather than eighteen. At temperature zero, on a freshly loaded model. Determinism here holds
*within a warmed engine* and is not guaranteed across a load, which is what the warm-up in
`lacc measure` exists for and is the first time it has visibly earned its place. A single run
compared against another single run can differ for this reason alone.
