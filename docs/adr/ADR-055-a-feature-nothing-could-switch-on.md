# ADR-055 - A feature nothing could switch on

## Status

Accepted. It records a defect, its fix, and the second instance of the pattern that produced
it.

## Context

ADR-052 decided that a skill may declare a schema the engine constrains decoding to, and said
it would be *"off by default, and turned on per skill after measuring it."* It was built: the
schema is generated from the fields a skill declares, `Provider.complete` takes one, the
Ollama adapter passes it as `format`, and a provider that cannot enforce one ignores it.

**Nothing in the program could set it.** `enforce_shape` had no command-line flag, no
configuration key, and no field in a skill declaration. Every one of the seven places that
build a `SkillPlan` left it at its default of false, so `output_schema` always returned
`None` and no schema was ever sent. The feature was released, described in the changelog and
cited from a decision record, and was reachable from nothing at all.

Six tests covered it and all six passed, because **they built `SkillPlan` directly**. They
tested the object. The program never builds that object by hand: it calls `plan`, and `plan`
was the part with nothing in it.

**This is the second time.** `ask_corpus` was tested through `ask`, which constructs it
directly, and it was deliberately absent from the skill registry - so `measure --from` failed
on its first real launch with the suite green. Same shape: a test that reaches past the
program's own wiring tests a component, and reports it as a feature.

## Decision

**The configuration names the skills whose shape is enforced**, one per line, empty by
default:

```yaml
enforce_shape:
  - extract_claims
```

Per skill rather than global, because whether constraining helps is a property of the skill
and has to be measured one at a time. It mirrors `models`, which ADR-051 made per-skill for
the same reason.

**Every skill's `plan` sets it from the configuration.** All seven, including the declared
path. `plan` already receives the configuration and is already where a skill decides what it
intends, so nothing new is threaded anywhere.

**A skill that answers in prose gets no schema, by construction.** `output_schema` now
requires `verify_quotes`, which is true exactly for the three skills that return parsed
blocks. Naming `summarize_file` in the configuration sets the flag and still produces no
schema - forcing prose into `{"entries": [...]}` would break the answer it was meant to
improve. This is a structural refusal rather than an omission: there is no list of skills to
keep in step with anything.

**A test asks the question of the whole program, not of this one field.** Every field with
a default, on every model the program builds in code rather than reads from a file, must be
set somewhere in the source. Eighty-seven fields qualify and all of them pass; `enforce_shape`
was the only one that did not, and a third instance now fails the suite rather than shipping.
It guards itself too - a second test feeds it the defect as released and asserts it is
reported - because a check that cannot fail is decoration.

**The test that was missing goes through `plan`.** A skill, a configuration, and the
assertion that the schema arrives - and that without the configuration it does not. It fails
against the code as released, which is the only useful property a regression test has.

## Consequences

- ADR-052's promised measurement becomes possible. It could not be run before this.
- `tests/test_reachable.py` joins `tests/test_layering.py` as a rule the suite enforces
  rather than a habit the author remembers.
- The three block-shaped skills and any declared skill can be enforced; the three prose
  skills cannot, and naming them is inert rather than an error.
- `enforce_shape` remains off for everything by default. Nothing about the measurement is
  prejudged by making it reachable.

## Trade-off

**Naming a prose skill does nothing and does not say so.** The configuration accepts it, the
flag is set, and no schema appears. An error would be louder and would need the configuration
layer to know the skill registry, which the import graph forbids and is right to. The
documentation says it; the program does not.

**Per-skill configuration is another thing to get wrong.** A misspelled skill name is silently
inert, the same way a misspelled key in `models` falls back to the single model. The
alternative - validating names against a registry - is the same layering violation.

## The general lesson, which is not about schemas

**A test that constructs the object under test has not tested that the program can produce
it.** Both instances of this defect were unit tests of a well-made component, passing, beside
a program that never built that component. Coverage of a type is not coverage of a path.

The question that catches it, and that neither suite asked: *what in the program sets this?*
If the answer is "a test", the feature does not exist. Chapter 4 records this as the eleventh
wrong figure, because a feature counted as delivered is a figure like any other.
