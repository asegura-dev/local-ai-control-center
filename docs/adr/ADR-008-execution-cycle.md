# ADR-008 - The execution cycle: one place that knows the order

- **Status:** Accepted - implemented (v0.7.0)
- **Date:** 2026-07-20
- **Context:** Eight modules now exist and each works alone, but nothing runs them
  together. Without a cycle, every future caller - each skill, the command line, a
  chain - would have to remember to preview, check permissions, confirm, call the
  provider, and record the result, in the right order. That knowledge belongs in
  one place. This ADR defines the cycle, where human confirmation lives, and what
  gets recorded when a run does not happen.

## Decision

### 1. One function that runs an action through the whole system

`run_action` takes an intended action and the pieces it needs (permissions,
configuration, workspace, provider, audit log) and drives the sequence: preview,
refuse or ask, execute, record. Callers describe *what* they want done; the cycle
knows *how* a run proceeds.

### 2. Confirmation is supplied, not performed

The cycle does not ask the user anything. It receives a **confirmation function** -
given a preview, return whether to proceed - and calls it. The command line will
pass one that prints the preview and reads a reply; a test passes one that always
accepts or always declines; a future interface passes its own.

The core must not know how a human is asked (ADR-001). Putting a terminal prompt
inside the cycle would invert the dependency between the stable core and the
volatile interface. Supplying the function keeps the human-in-the-loop moment
mandatory without deciding what it looks like.

### 3. A refused preview stops the run before anything happens

If the preview reports the action would not be allowed - missing capabilities or
targets outside the workspace - the cycle records the refusal and returns without
calling the confirmation function or the provider. There is no point asking someone
to confirm something that cannot run.

### 4. Declining is recorded, like everything else

When the confirmation function declines, the cycle records a
`confirmation_declined` event and returns without executing. An audit trail that
only holds what was executed is incomplete: knowing that an action was proposed and
refused is information about the system, not noise. If a skill is declined every
time, that says something - either it asks for too much, or the configuration is
wrong.

### 5. The result reports what happened, not just what came back

`RunResult` carries the preview, whether the action ran, the completion if it did,
and the outcome (`completed`, `refused`, `declined`). A caller can tell the
difference between "it ran and here is the answer", "it was not allowed", and "the
user said no" without inspecting exceptions.

## Trade-off

Taking confirmation as a parameter is less convenient than a cycle that just asks:
every caller must supply one, including tests. The alternative - prompting inside
the cycle - was rejected because it would put terminal interaction in the core and
make the cycle unusable from anything that is not a terminal.

Recording declined and refused runs makes the audit log larger and means the log
grows even when nothing executes. That cost is accepted: a trail that omits what
did not happen cannot answer "was this ever attempted?", which is one of the
questions an audit trail exists to answer.

## Consequences

- Skills and the command line call `run_action` rather than orchestrating modules
  themselves.
- The audit event set gains `confirmation_declined`.
- This is where the first integration tests live: the cycle is the first code that
  exercises configuration, workspace, permissions, provider, preview, and audit
  together rather than in isolation.
- The core gains an eighth functional module, `cycle`. Chapter 1 and the CHANGELOG
  are updated in this same phase.