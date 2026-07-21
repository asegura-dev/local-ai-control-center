# ADR-011 - Permission sourcing: skills declare, configuration limits

- **Status:** Accepted - implemented (v0.10.0)
- **Date:** 2026-07-21
- **Context:** ADR-010 shipped the CLI with a stopgap it explicitly flagged: it
  grants a fixed `read_files` permission to whatever skill it runs. That hardcoding
  is wrong - it ignores what the skill actually needs and would misgrant for any
  other skill. This ADR decides where a skill's granted permissions come from,
  removing the stopgap before a real provider executes anything.

## Decision

### 1. A skill is granted what it declares, limited by configuration

The pieces already exist. A skill declares what it needs (`Skill.required`,
ADR-009). Configuration already acts as a ceiling (`effective_permissions`,
ADR-004). This decision is the function that joins them: grant a skill exactly the
capabilities it declares, minus any the configuration forbids.

A `grant_for(skill, config)` function returns a `Permissions` that enables the
skill's declared capabilities, then lets the configuration ceiling remove any it
forbids. Nothing is granted that the skill did not ask for; nothing survives that
the configuration vetoes.

### 2. Configuration is a ceiling that removes, not an allowlist that grants

Configuration limits by taking away, not by enumerating what is permitted. Today
the only capability it constrains is `network`, via `network_access`. A capability
the configuration says nothing about is granted if the skill declares it. So a
skill that declares `read_files` gets it; a skill that declares `network` gets it
only if `network_access` is on.

This keeps configuration terse (a single `network_access` flag, not a list of every
allowed capability) and consistent with what already exists. The skill is still
bounded: it can only receive capabilities it explicitly declares, never more.

The stricter alternative - an allowlist where the configuration must permit each
capability and anything unmentioned is denied - is deliberately deferred. It is the
right model for untrusted, third-party skills, and belongs to the decision that
introduces those. For skills authored in this repository, "declare, then remove
what is vetoed" is proportionate: the defense is that a skill asks for only what it
needs, and its code is reviewed.

### 3. The CLI uses grant_for instead of hardcoding

The CLI replaces `Permissions(read_files=True)` with `grant_for(skill, config)`.
Whatever skill is run now receives permissions derived from its own declaration and
the active configuration, not a fixed set.

## Trade-off

Deriving grants from what a skill declares means a skill effectively authorizes
itself, bounded only by the configuration ceiling. For skills written and reviewed
in this repository that is appropriate - the review is the trust boundary. It would
not be safe for skills from untrusted sources, which is why the stricter allowlist
model is named here and left for the decision that admits such skills. Choosing the
lighter model now avoids building an allowlist the project has no untrusted skills
to justify.

## Consequences

- The CLI no longer hardcodes permissions; the stopgap from ADR-010 is removed.
- Adding a skill that needs different capabilities works without touching the CLI:
  the skill declares them, and `grant_for` grants them under the ceiling.
- A future decision admitting untrusted skills will revisit this with an allowlist
  model.
- `grant_for` joins the existing skill and permission modules; no existing code is
  restructured. Chapter 1 and the CHANGELOG are updated in this same phase.