# ADR-033 - The skill declares its temperature, and it is zero

## Status

Accepted.

## Context

LACC sends the engine one option, `num_ctx`. It has never sent a temperature, so the engine
applies its own default - 0.8 on the version measured, with the model declaring no
parameters of its own.

Temperature 0.8 means sampling from the distribution rather than taking the most likely
token. For `extract_claims`, whose entire job is to copy words out of a document without
altering them, that is the wrong setting in a way that is easy to miss because the output
still looks correct.

Measured on a real paper, same model, same document, three requests each:

| Temperature | Distinct responses out of three |
|---|---|
| 0.8 | 3 |
| 0.0 | 1 |

And five runs of `extract_claims` through LACC verified between 25% and 85% of their
quotations - a sixty-point spread that made every comparison so far meaningless, including
one written into this repository before it was repeated.

There is a second reason, and it is the one that decides this. The audit trail records
`prompt_sha256` and `completion_sha256` for every run. **At a non-zero temperature those
hashes cannot be reproduced.** The trail says something happened and nobody can obtain it
again. For a project meant to be cited in a thesis, a record that cannot be reproduced is
weaker evidence than it appears to be, and reproducibility is not an optimisation here - it
is what makes the record mean anything.

## Decision

**A skill declares the temperature its task requires, and the default is zero.**

`SkillPlan` carries the value; the cycle passes it to the provider alongside the context
window. Every skill LACC ships today takes the default, because every one of them either
copies text or reports on it, and none is improved by variety.

**There is no configuration override.** Temperature is a property of the task rather than a
preference: `extract_claims` needs zero because of what extraction *is*, and a configuration
able to raise it could quietly make a grounded task unreliable while everything appeared to
work. That is the shape of "configuration grants" the project already forbids elsewhere.
A knob can be added when a skill genuinely needs a different value; there is no such skill
today, and an abstraction with no second case does not earn its place.

**Determinism is the point, not accuracy.** Zero does not promise better quotations. It
promises the *same* quotations, which is the prerequisite for measuring anything else -
including whether a larger model helps, which cannot currently be answered because every
number so far is dominated by sampling noise.

## Consequences

- `SkillPlan` gains a temperature; `OllamaProvider` sends it with `num_ctx`.
- Repeated runs of the same skill on the same document become reproducible, and the audit's
  completion hashes become something a reader can check.
- The prompt work deferred until measurement was possible becomes evaluable: a baseline at
  temperature zero is a fixed point rather than a distribution.
- The model comparison invalidated in v0.28.0 can be redone and will mean something.
- The mock provider is unaffected: it was already deterministic, which is why the test suite
  never noticed this.

## Trade-off

Zero can lock a skill into a bad answer. At 0.8 a run that verified 25% of its quotations
might have verified 85% on the next attempt; at zero, a bad result is the result every
time. Accepted, and it is the better failure: a consistently bad answer is a bug that can be
found and fixed, while an intermittently good one is a system nobody can reason about. The
variance was never producing better work - it was producing an occasional lucky run and
hiding the real quality behind it.

Revision may read flatter at zero than it did with some sampling. Accepted for now: the
revision is shown as a diff and approved by a human, and getting the same proposal each time
is worth more than variety in a tool whose purpose is to be checkable. If that turns out to
be wrong, the skill can declare otherwise - which is exactly why the value lives on the
skill.
