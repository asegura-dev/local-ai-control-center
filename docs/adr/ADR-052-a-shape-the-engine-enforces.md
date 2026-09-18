# ADR-052 - A shape the engine enforces

## Status

Accepted.

## Context

This project's most transferable finding is that **structure is obeyed and instruction is
negotiated**. Asked to cover twenty-four documents a model covered ten; given the same
request as a skeleton with twenty-four slots it returned twenty-three. Told in the same
prompt, explicitly, not to use its own knowledge, it invented twelve journal names anyway.
The fence behaved identically: the instruction not to obey a document was ignored, and
removing the markers worked.

Every skill still **asks** for its format in prose - `CLAIM:`, `QUOTE:`, `PAGE:` - and then
parses whatever arrives. That has already cost something: a skill that declared it verified
quotations verified none of them, because the model wrote `**CLAIM:**` in bold and the parser
matched neither. The fix was to make the parser more forgiving, which is the weaker half of
the pattern this project keeps rediscovering.

Ollama accepts a JSON schema and constrains decoding to it. The shape stops being a request.

## Decision

**A skill may declare a schema, and the engine enforces it.** `Provider.complete` takes an
optional schema; the Ollama adapter passes it as `format`; a provider that cannot enforce one
ignores it rather than pretending.

**The schema is generated from the fields a skill already declares.** `DeclaredSkill` names
its fields and which one carries the quotation, so nothing new is authored. A built-in skill
gets one the same way, from its `fields`.

**A provider that ignores the schema must still produce parseable output**, so the
line-oriented parser stays. Enforcement is an improvement on a path that already works, never
a replacement that only works on one engine. The mock provider enforces nothing, and the
suite has to pass against it.

**Whether this degrades the writing is measured, not assumed.** Constrained decoding can
fight the way a model wants to compose, and a format that arrives perfectly with worse
content inside it would be a loss reported as a win. The same skill runs with and without a
schema and the verified-quotation counts are compared before it becomes the default.

## Consequences

- `Provider.complete` gains an optional parameter; three implementations, one of which uses
  it.
- Answers become JSON rather than labelled lines when a schema is used, so `parse_claims`
  gains a JSON path beside the line-oriented one.
- A malformed block stops costing a claim, because malformed blocks stop happening.

## Trade-off

**Constraining the shape may cost content quality, and the direction is unknown until
measured.** A model steered token by token into a schema has less room to say what it was
going to say. This project has been wrong nine times about improvements that sounded
obviously good, and this ADR is written before the measurement rather than after it, which
means it may have to be corrected like the others.

**Two output paths - JSON and lines - is more to maintain than one**, and the second exists
for engines and providers that cannot constrain. Accepted: a control that only works on one
engine is a control this project cannot claim to have.

**It makes a model's failure quieter.** Today a model that ignores the format produces
visible nonsense and zero claims; under a schema it produces well-formed fields that may be
empty or wrong. Well-formed and wrong is harder to notice than malformed and wrong, and that
is worth watching for rather than assuming away.

## Measured (v1.4.0), and **corrected in v1.4.1** - read ADR-056 first

**The figures in this section are wrong and are kept as published.** The zero below was this
project's parser refusing a truncated document, not the model failing to answer: the same
answer carries seventy-six complete entries, and re-parsed it gives **32 verified quotations
against the line format's 15, at the same fidelity**. The advice this section ends with is
backwards. ADR-056 has the corrected table and how the mistake was made.

What survives from below: the answer never ends, and it costs 24 minutes against 5.

## Measured (v1.4.0)

This record said constraining might cost content quality and had to be measured. It was, as
soon as ADR-055 made it possible to switch on at all. `extract_claims`, one paper, qwen2.5:14b
at temperature zero, a 16,613-token prompt. Four measured runs in each condition, each
preceded by its own warm-up. Every run within a condition returned a byte-identical answer, so
the spread is zero and the comparison is between two numbers rather than two distributions.

| | asked for the format | shape enforced |
|---|---|---|
| answer tokens | 1,621 | **8,192, and not finished** |
| why it stopped | `stop` | `length` - the cap |
| quotations parsed | **19** | **0** |
| found in the document | **18 of 19 (94%)** | **none to check** |
| the four runs took | 5 min | 24 min |

**Content quality is not what failed.** The constrained answer is well-formed JSON with
exactly the declared fields, and its first entry carries the same claim and the same quotation
as the unconstrained one, word for word. The fear this record named did not happen.

*(True of the first entry, which is all that was checked before writing it. Through entry
thirty the fidelity holds at 93%; by entry sixty the model is repeating a table caption.
Checking the first item and concluding about the set - ADR-056.)*

**What failed is that the answer never ended.** Unconstrained, the model wrote 1,621 tokens
and stopped. Constrained, it was still listing entries at 8,192 and was cut mid-string. The
grammar admits another array element at every point, so nothing pushes the model toward
closing the array, and the same content costs five times the tokens in JSON before that even
matters.

**And a truncated JSON answer is worth nothing, where a truncated line-oriented answer is
worth almost everything.** Cut in half, the line format yields every complete block before the
cut. Cut in half, the JSON yields zero - one unclosed brace and the whole document is
unparseable. The parser fell back to lines, found no `CLAIM:`, and returned nothing.

**So the line format is kept for a better reason than this record gave.** It was kept for
engines that cannot enforce a schema. The measurement says it is also the format that
degrades gracefully, and the enforced one is the brittle one.

*(This is the sentence that cost the figure. The asymmetry is real; reading it as a property
of JSON rather than as a defect to fix is what published a zero. `raw_decode` recovers every
entry that arrived whole, and the brittleness was the parser's - ADR-056.)*

**`enforce_shape` stays off, and for `extract_claims` on a 14B the honest advice is not to
turn it on.** *(Wrong. See ADR-056: with the parser fixed it is the better of the two on this
skill and model. `enforce_shape` does stay off by default, for a different reason - one
document is not a licence to change a default.)* The decision to make it per-skill and measured rather than global was right, and
this is the first skill it was measured on. Whether a schema with a bounded array, or a
parser that recovers complete entries from truncated JSON, changes the answer is open and not
yet measured - the second is the more principled of the two, because it needs no number.

**One document, one model, one skill.** Determinism within a condition is not generality
across them: this says what happened here, and a different model may well close its array.
