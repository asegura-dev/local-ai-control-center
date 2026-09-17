# ADR-051 - A model per kind of work

## Status

Accepted.

## Context

Two models were compared on the same material and turned out to differ in kind rather than
in quality:

| | 14B | 32B |
|---|---|---|
| extraction fidelity, two papers | 95%, 93% | **97%, 96%** |
| verified quotations, two papers | **40, 75** | 33, 78 |
| synthesis: points made | **3, from two documents** | 2, from one |
| synthesis: attribution | source only | **source and page, as given** |
| speed on this hardware | 33 tok/s | 3.2 tok/s |

**The larger model is more faithful to what it is handed; the smaller one is more
productive.** Neither is better. They are differently biased, and the bias that matters
depends on the step: extraction wants coverage, drafting wants a citation that is right.

Running one model for everything therefore takes the worse half of both trades. And the
configuration allows exactly that and nothing else: `model:` is a single string.

Doing it today means keeping two configuration files and remembering which command takes
which, which works and is an invitation to run the wrong one.

## Decision

**A configuration may name a model per skill**, falling back to the one model it already
names.

```yaml
model: qwen2.5:14b
models:
  draft: qwen2.5:32b
  themes: qwen2.5:32b
```

**The routing is a rule the user wrote, never a choice the model makes.** That line is the
whole decision. ADR-045 ruled out letting a model choose what to do next, on doctrine -
PRINCIPLES and VISION say so in as many words - and on a measurement: asked to cover
twenty-four documents a model covered ten and **named none of the fourteen it dropped**. A
table from skill name to model is as inspectable as the retriever's ranking, and a person
reading a configuration can see the whole policy.

**The preview says which model is about to run**, because a run whose model was chosen by a
table is a run whose model the person should be told. The audit records it per run, which it
already does through the provider's name.

**The profiler reports and does not decide.** `lacc profile` knows what the machine holds and
what is installed; it may say that a model does not fit the card and will be ten times
slower, and it may not act on that. A tool that silently picked a different model than the
one a configuration names would make every recorded run ambiguous.

## Consequences

- `Config` gains `models`, a mapping; `_build_provider` consults it by skill name.
- A step that wants fidelity and a step that wants coverage can be different models in one
  pipeline, without two configuration files.
- An unknown skill name in the mapping is a configuration error rather than a silent
  fallback, in keeping with a configuration that refuses unknown fields.

## Trade-off

**A pipeline whose steps ran on different models is harder to reason about**, and a result
that changed will have two places it could have changed in. Mitigated by the audit recording
the model per run, and it is a real cost.

**This makes it easy to believe an orchestration is better before measuring it.** The
arrangement described above is plausible - extract with the productive model, draft with the
faithful one - and plausible is exactly what this project has been wrong about nine times.
The mapping makes the experiment possible; it does not make the hypothesis true, and the
figures at the top of this record are two documents and one run each.
