# ADR-074 - What it is about to ask

## Status

Accepted. Cheap, because the thing it shows was built to be pure five years of records ago.

## Context

Almost every measured finding in this project is about the distance between **what somebody
meant to ask** and **what was actually sent**:

| what was believed | what the prompt did |
|---|---|
| "say not available for anything missing" would prevent guessing | twelve invented journal names out of twenty-four (ADR-047) |
| a schema would improve the answer | it delivered the shape and lost the answer (ADR-052) |
| a declared skill asks the question you gave it | the prompt never carried the question at all (ADR-062) |
| a schema changes the prompt | the prompt was byte-identical with and without it |

Every one of those was invisible for exactly as long as nobody looked at the prompt. The last
two were found by printing it.

And the prompt has always been printable. `Skill.plan` is pure and produces the template with
no effects; the cycle fills the hole later (ADR-014). **The most useful thing this project can
show about itself was one function call away and behind nothing.**

## Decision

**A section that shows, for every skill, exactly what would be sent.** The instruction, the
capabilities it would ask you to allow, whether its quotations get checked, the labels it asks
the answer to carry, its temperature, and how many words the asking is before any document is
added.

**The document's place is shown, not left as a marker.**

    ────────  your document is inserted here  ────────

`CONTENT_PLACEHOLDER` is a token nobody would recognise, and leaving it raw makes the single
most important fact about a prompt - that **the document arrives inside it, surrounded by
instructions** - the least visible thing on the page. That framing is what ADR-038 exists to
defend, and a reader deciding whether a document could hijack a run needs to see the shape of
the sandwich.

**Planned against one example filename**, so a template can be read before choosing a file.
The alternative was to show the template with the hole unfilled, which means showing something
that is never sent.

**A skill that cannot be planned says why, in place of its template.** That is worth seeing
rather than hiding: a skill that cannot be planned is a skill that will fail when it is run,
and a list that quietly omitted it would be a list that lies by absence.

**Nothing is run and nothing is sent.** Reading a plan calls no model and reaches no engine.
This is the section of the window whose innocence is easiest to state and hardest to doubt.

## Consequences

- Eight sections in the window, and this is the one that answers *what is it asking?*
- `features/prompts.py` takes the skills as an argument rather than gathering them, because
  gathering them reads files and reports failures, which is the caller's job.
- A test plans every skill the CLI offers. One that stops being plannable fails the gate.

## Trade-off

**It shows the template, not the prompt.** The cycle fills the hole, may divide a document
into passes, and appends its own framing. What is shown is the instruction as the skill wrote
it - which is where every defect above lived, and is not the same as the bytes that leave.

**`lacc preview` already answers a harder version of this question** for a real run with real
files, including what it would cost. This is the cheaper, wider view: all of them at once,
before choosing anything. If a person reads only one, it should be `preview`.
