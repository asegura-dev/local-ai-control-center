# ADR-098 - A model that thinks is told whether to

## Status

Accepted. Written with the engine switched off: what is decided here is what could be built
and tested without it, and what still needs the engine is named as such.

## Context

Every model this project has run so far answers at once. The newer ones do not. On 27-sep,
with Ollama 0.34.0 on the machine that runs the models, one sentence was asked of two of
them, first saying nothing about reasoning and then asking for none:

| model | unasked | `think: false` |
|---|---|---|
| qwen3.5:9b | 40.1 s, ~5,000 characters of reasoning | 0.5 s |
| gemma4:12b | 25.0 s, no reasoning reported | 0.5 s |

The gemma4 figure includes loading the model, so it is not all reasoning. The qwen3.5
figure is: the engine returned five thousand characters in a field of its own before the
one sentence that was asked for.

**The reasoning arrives in a separate field, and LACC reads only the answer.** So nothing
breaks: a quotation check, a format, a parsed block all see the same text they would have
seen. What changes is the time. A run that took seconds takes a minute, and nothing in the
audit says where the minute went.

**Asked for none, both models also answered worse in one measured way.** The sentence asked
what knowledge distillation is. Without reasoning, both answered with the everyday meaning -
an expert passing experience on - rather than the machine-learning one. In a skill the
passage carries its own context, so this may matter less; it is recorded because it is the
trade and not only the saving.

## Decision

- **A setting, `thinking`, true, false or unset.** True asks the engine to reason, false
  asks it not to, and either is sent explicitly with every request.
- **Unset sends nothing**, which is what every run did before the setting existed. It stays
  the default because one thing has not been measured: whether this engine accepts
  `think: false` for a model that cannot reason at all, such as qwen2.5. If it does, false
  can become the default in a later record; until then, a configuration that names a model
  which thinks says so.
- **The engine check sends it too.** Asking whether a model answers must not take forty
  seconds because the model decided to reason about the word *ready*.
- **How much the engine reasoned is recorded** in the audit, as a count of characters, for
  every call that reports it. The reasoning itself is neither read nor kept: it is not an
  answer and nothing checks it. The count is where the time went.
- **The window's configuration form offers it**, beside the model it qualifies. It decides
  how work is done, not what is allowed, so it is on the editable side of ADR-094's line. A
  file that says `false` shows as `False`, and an untouched form does not propose rewriting
  the line because of it - the defect ADR-094 found in its own form, tested here again.

## Consequences

Tested without the engine, by capturing the request each setting produces and by feeding
the adapter a response that carries a reasoning field and one that does not. Not yet run
against the engine: whether `think: false` is accepted for qwen2.5, and the time the
setting saves inside a real skill.

## Trade-off

**Unset keeps a default that is slow for the newest models.** Somebody who names qwen3.5
and does not write `thinking: false` gets the forty seconds. Choosing false as the default
without knowing whether the engine refuses it for older models would trade a slow run for a
failed one on the models every existing configuration names.

**Asking for no reasoning may cost understanding**, as the definition above shows. The
setting is per configuration rather than per skill, so the choice is made once for all of
them; a skill that needs the reasoning and one that needs the speed cannot yet differ.
