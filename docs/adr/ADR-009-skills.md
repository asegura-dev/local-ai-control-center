# ADR-009 - Skills: units of work that produce actions

- **Status:** Accepted - implemented (v0.8.0)
- **Date:** 2026-07-20
- **Context:** The execution cycle (ADR-008) can run an `IntendedAction`, but
  nothing produces one - actions are assembled by hand in tests. A skill is what
  produces them for real: a named unit of work that declares the capabilities it
  needs and knows how to turn an input into an action and a prompt. This ADR defines
  the skill contract and a first read-only skill that runs the whole path end to
  end.

## Decision

### 1. A skill is an abstract contract

`Skill` is an abstract base class in a flat `skill` module, mirroring the
`Provider` port (ADR-005) so the project resolves "a contract with concrete
implementations" one way, not two. Each skill declares:

- `name` - a short identifier.
- `required` - the capabilities it needs, as a frozenset.

and implements:

- `plan(request)` - turn a request into an `IntendedAction` describing what it
  would do, and the `prompt` to send the provider.

Declaring capabilities on the skill rather than computing them per run means the
preview and the permission check know what a skill needs before it does anything.

### 2. plan is pure; it decides nothing and touches nothing

`plan` builds a description - an action and a prompt - and returns it. It does not
read files, call the provider, or write anything. The cycle owns side effects and
ordering (ADR-008); a skill only describes what it intends. This keeps a skill
testable in isolation and keeps the dangerous parts in the one place that audits
them.

### 3. A skill is run through the cycle, never on its own

Running a skill means: call `plan` to get the action and prompt, then hand them to
`run_action` (ADR-008), which previews, checks permissions, confirms, executes, and
records. A skill never calls the provider or the audit log itself. A small
`run_skill` helper wires a skill to the cycle so callers do not repeat the wiring.

### 4. The first skill: summarize a file, read-only

`SummarizeFileSkill` reads nothing itself - it declares a `read_files` requirement
and a target path, and builds a prompt asking the provider to summarize the file at
that path. The actual read happens where side effects belong. It targets a path
inside the workspace, so the boundary check applies. It is deliberately the
smallest useful skill: one capability, one target, no writing.

## Trade-off

Making `plan` pure - describing rather than doing - means a skill cannot, for
example, read a file to decide what to do with it before the preview. A skill that
acted while planning could be smarter. That was rejected because it would move side
effects out of the cycle and into skills, scattering the dangerous operations the
audit trail and the boundary exist to contain. Skills describe; the cycle acts.

Keeping the first skill read-only means it cannot demonstrate the write path or a
diff-style preview. That is accepted: writing introduces questions (proposed
content, diffs, destructive operations) that deserve their own decision when a
writing skill actually exists, rather than being guessed at now.

## Consequences

- Skills produce `IntendedAction`s; the cycle runs them. Neither knows how the user
  is asked, nor calls the provider directly except through the cycle.
- A registry of skills is deliberately not built yet: with one skill there is
  nothing to look up. It arrives with the command line, when several skills and a
  way to select one exist.
- The core gains a ninth functional module, `skill`. Chapter 1 and the CHANGELOG
  are updated in this same phase.