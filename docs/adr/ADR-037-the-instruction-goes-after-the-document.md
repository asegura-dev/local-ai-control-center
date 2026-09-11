# ADR-037 - The instruction goes after the document too

## Status

Accepted.

## Context

Every prompt LACC builds has the same shape: instructions, then the fenced document. For a
short note that is fine. For a seven-page paper it means two hundred tokens of instruction
followed by nine thousand tokens of text, and by the time the model starts writing, the
format it was asked for is nine thousand tokens behind it.

`extract_claims` had an unexplained result throughout the measurement work: three to nine
claims from a seven-page paper, with the engine reporting `finish_reason: stop` and no
truncation. Nothing was cutting the answer short. The models simply stopped.

The audits so far had looked at what LACC does with an answer. This looks at what LACC asks
for, on the same suspicion and with the same method: assume the fault is here until measured
otherwise.

Three runs each against the real paper, at temperature zero:

| Prompt | Claims | Verified |
|---|---|---|
| Instructions before the document only | 8, 9, 9 | 7, 9, 9 |
| **The format repeated after it** | **12, 12, 12** | **12, 12, 12** |

A third of again as many claims, every one of them verified, and identical across runs where
the original varied.

Removing the request for a page - which ADR-031 made LACC compute for itself, so the model's
answer is discarded - was measured at the same time and did **not** help. Worth recording
because it was the more obvious suspect.

## Decision

**A skill may place a closing instruction after the fenced document, and `extract_claims`
does.** It restates the format and asks for every claim the document makes.

**The opening instructions stay.** They are what frames the task before the model reads
anything, and the document fence needs its warning about not following instructions inside
the document *before* that document arrives. This adds a reminder; it does not move the
briefing.

**The model is still asked for a page.** Removing the request was measured and did not help,
and keeping it preserves the fidelity signal recorded in the audit (ADR-031). Nothing is
changed on the strength of it seeming wasteful.

**One change at a time, measured against the same paper.** Two variants were tried, the one
that worked was kept, and the one that did not is written down so nobody tries it again
believing it was never checked.

## Consequences

- `SkillPlan` templates may carry text after the document; `extract_claims` yields about a
  third more claims, all verified, deterministically.
- The prompt is longer by a few dozen tokens against a document of thousands.
- The same shape is available to any skill whose instructions are far from its output, and
  `summarize_file`, `critique_file` and `revise_file` have not been measured for it - so
  they are left alone until they are.

## Trade-off

Repeating an instruction is a prompt technique rather than a property of the system, and
this project has been sceptical of those: a prompt that asks a model to behave is a request,
not a control. Accepted because this is not asking for better behaviour, it is putting a
requirement where the model can still see it - and because it was measured rather than
believed, on a real document, repeatedly.

The gain may not survive a different model or a longer document. The honest position is that
it was measured on one paper with one model, and that `lacc measure` exists precisely so the
next person can check rather than trust this table.

It also means the fence is no longer the last thing in the prompt, which weakens the
already-imperfect boundary against a document that tries to issue instructions: text after
the fence is LACC's, but a document ending with something that looks like a closing
instruction now sits nearer to it. The fence was never a real defence - ADR-016 said so -
and the mitigation stays what it was: the opening warning, and a human reading the answer.
