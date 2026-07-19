# ADR-007 - Execution preview: describing an action before it runs

- **Status:** Accepted - implemented (v0.6.0)
- **Date:** 2026-07-19
- **Context:** The control core is complete: configuration, workspace boundary,
  permissions, a provider port, and an audit log. What is still missing is the
  moment the whole design exists for - showing the user what would happen before it
  happens. Skills, which will be the usual source of such actions, do not exist
  yet. This ADR decides what a preview describes and, deliberately, what it must
  not know about.

## Decision

### 1. A preview describes an intended action, not a skill

The preview module knows nothing about skills. It takes an `IntendedAction`: a
description of what is about to happen (a name, a human-readable summary, the
capabilities it requires, and optional target paths) and produces an
`ExecutionPreview` reporting whether it would be allowed and why not.

This keeps the dependency direction right. Skills will be the most volatile part of
the system - each new skill, each new kind of skill - while "describe an intended
action" is stable. The stable module must not depend on the volatile one. It also
means anything describable this way can be previewed: a skill, a chain of skills, a
direct command-line action, without changing this module.

### 2. A preview decides nothing and executes nothing

Building a preview has no side effects: it does not write, does not call a
provider, does not create anything. It answers a question and returns a report. The
decision to proceed belongs to whoever is driving the run.

This is why ADR-004 made `check` return a result instead of raising: the preview
path needs to inspect a denial without failing, and report precisely which
capabilities are missing.

### 3. What a preview reports

An `ExecutionPreview` carries the action being previewed, whether it would be
allowed, the capabilities that are missing (empty when allowed), and any target
paths that fall outside the workspace boundary. It renders to a short, readable
block of text intended to be shown to a person before they confirm.

Both denial reasons are reported together rather than stopping at the first. A user
deciding whether to proceed benefits from seeing everything wrong at once, not one
problem at a time.

### 4. Path targets are checked against the boundary

When an action declares target paths, the preview resolves each through the
workspace boundary (ADR-003) and reports any that escape. Checking at preview time
means containment violations surface before execution rather than during it.

## Trade-off

Keeping the preview ignorant of skills means it cannot show skill-specific detail -
it reports what any action declares about itself, and nothing richer. A
skill-aware preview could say more. That was rejected because the cost is
structural: it would invert the dependency between the stable and the volatile part
of the system, and would tie previewing to a single kind of thing being previewed.
Actions can always declare more about themselves; the module does not need to know
what they are.

Reporting all denial reasons at once costs a little more work than failing fast at
the first problem. It is accepted because a preview exists to inform a human
decision, and a partial list of problems leads to fixing them one round trip at a
time.

## Consequences

- Skills, when they arrive, produce an `IntendedAction` rather than being known to
  the preview module.
- Nothing in the preview path can accidentally execute or modify state.
- The core gains a seventh functional module, `preview`. Chapter 1 and the CHANGELOG
  are updated in this same phase.