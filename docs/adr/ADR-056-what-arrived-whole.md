# ADR-056 - What arrived whole

## Status

Accepted. It also **corrects a figure this project published in v1.4.0, hours old at the time
of writing**, and reverses the advice that came with it.

## Context

ADR-052 was measured as soon as ADR-055 made it switchable. The result, published in v1.4.0:
enforcing the shape gave **19 quotations asking for the format and 0 enforcing it**, and the
advice was not to turn it on.

**The zero was this project's parser, not the model's answer.** The engine had been stopped at
the token cap mid-string, and `json.loads` returns nothing for a document with one unclosed
brace - so an answer carrying seventy-six complete entries parsed to none of them. The line
format, cut in the same place, yields every complete block before the cut.

That asymmetry was noticed at the time and written down as an argument for keeping the line
parser. **It was actually a defect in the JSON path**, and reading it as a property of JSON
rather than as something to fix is what put a wrong figure in a release.

## Decision

**A shaped answer that will not parse is walked entry by entry, and every entry that arrived
whole is kept.** `json.JSONDecoder.raw_decode` parses one value and reports where it ended, so
the entries are taken in order until one fails.

**Nothing is repaired and nothing is guessed.** The entry that was cut is dropped whole, along
with anything after it. There is no brace-balancing, no trailing-comma fix, no attempt to
complete a string. The recovery has no threshold and no number in it.

**The whole-document path is unchanged.** A document that parses is parsed as one, exactly as
before; recovery runs only after `json.loads` has refused.

**Recovering nothing still falls back to lines.** Enforcement improves a path that works and
does not replace it, and that holds for this too (ADR-052).

**Truncation is still reported.** It is audited as `answer_truncated` and the CLI says so,
independently of parsing. Recovering entries must not make a cut answer look complete, and it
does not: the two are separate paths and always were.

## The corrected measurement

Same runs, same recorded answers, re-parsed. Deduplication applied as a real run applies it
(ADR-054), because that is the number a person actually receives.

| | asked for the format | shape enforced |
|---|---|---|
| claims returned | 19 | **76** |
| after deduplication | 16 | **35** |
| **found in the document** | **15** | **32** |
| rate | 93% | **91%** |
| the four runs took | 5 min | 24 min |

**More than twice the verified quotations, at the same fidelity.** The advice published in
v1.4.0 - do not turn it on - was backwards.

**And the schema does not degrade the answer; running on does.** Taking the enforced answer in
order:

| first N entries | found in the document |
|---|---|
| 19 | 17 (89%) |
| **30** | **28 (93%)** |
| 50 | 35 (70%) |
| 76 | 35 (46%) |

Through entry thirty it matches the line format's fidelity while producing far more. From
roughly entry fifty onward it produces **nothing** - the last entries are the same table
caption repeated, which is why `without_repeats` collapses seventy-six to thirty-five.

So the real defect is the one the first measurement also found and named correctly: **the
answer never ends.** The grammar admits another array element at every point, and the model
spends most of twenty-four minutes restating a caption. That is worth fixing and it is not
this record.

## Consequences

- The enforced path becomes usable, and on this skill and model it is the better one.
- `enforce_shape` still ships off for everything. "Better here" is one document, one model,
  one skill; the default is not changed on that.
- A cut answer now yields partial work in both formats, so the two are comparable at last -
  which is the only reason the corrected figures above mean anything.

## Trade-off

**A partial answer is easier to mistake for a whole one.** The mitigation is that truncation
was already audited and reported, and this changes neither. It is a real cost: before, a
truncated shaped answer was conspicuous because it produced nothing.

**More claims at the same rate still means more wrong claims in absolute terms.** Thirty-two
verified out of thirty-five is three that are not, against one of sixteen. Every one of them
is marked, which is what the check is for, and a person reads more marks.

## What this says about the project's own record

The v1.4.0 figure was wrong in the direction that made the tool look decisive - *the schema
loses the answer, do not use it* - and the check that would have caught it was the one always
prescribed here: **ask what the check could not see.** The zero was not a measurement of the
model. It was the parser's blind spot, reported as a property of the world, which is the exact
shape of six earlier corrections in `docs/04-measurements.md`.

One further thing is worth naming. The published claim *"content quality did not degrade"* was
based on reading the **first entry** of the enforced answer and finding it identical. It was
identical. Entry sixty was a repeated caption. **Checking the first item and concluding about
the set** is how that sentence got written, and it is a smaller, faster version of the same
mistake.
