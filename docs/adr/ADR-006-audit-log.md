# ADR-006 - Audit log: append-only records, privacy by default, and failure policy

- **Status:** Accepted - implemented (v0.5.0)
- **Date:** 2026-07-19
- **Context:** LACC promises that what it does can be traced afterwards. ADR-002
  introduced a `run_id` to identify an execution, but nothing records anything yet.
  This ADR defines what an audit record contains, where it is written, how much
  detail it captures, and what happens when writing fails - the last of which is a
  question about what the tool owes the user when it cannot keep its promise.

## Decision

### 1. Append-only JSON Lines inside the workspace

Audit records are written as JSON Lines: one JSON object per line, appended, never
rewritten. The format is readable by both a program and a person, survives partial
writes (a truncated last line does not corrupt earlier records), and needs no
database.

The log lives inside the workspace, and its path is resolved through the workspace
boundary (ADR-003). The audit trail is subject to the same containment as anything
else LACC touches.

### 2. A minimal event contract

An `AuditEvent` records: the UTC timestamp, the `run_id` grouping the execution, an
event kind, a short message, and an optional detail mapping. Event kinds are a
closed set covering what exists today - run start and end, permission decisions,
and provider calls - and grow as real events appear.

### 3. `audit_level` decides detail, and privacy is the default

The existing `audit_level` field gains behavior:

- **`standard`** (default) records events and their metadata: which capabilities
  were requested, whether they were granted, which provider was called. It does
  **not** record prompt or completion text.
- **`full`** records the same, plus prompt and completion content.

Prompts can contain whatever the user was working on. Writing that to disk by
default would contradict the local-first, privacy-first stance: the safe value is
the default, and capturing content is a deliberate opt-in - the same shape as
`network_access`.

### 4. Write failure is configurable, and defaults to refusing to proceed

A new configuration field, `audit_failure_policy`, decides what happens when a
record cannot be written:

- **`abort`** (default): the failure is raised. If the execution cannot be
  recorded, it does not proceed. The consequence is that a full disk or a
  permission error stops LACC - the tool becomes less robust, deliberately.
- **`continue`**: the failure is swallowed and execution proceeds unrecorded. The
  consequence is that the tool keeps working when logging breaks, at the cost of a
  gap in the audit trail precisely when something is going wrong.

Each option states its consequence in the field description, so the choice is
informed rather than a bare toggle. The default is `abort` because for a tool whose
promise is traceability, an unrecorded execution is worse than no execution; but
the user, not the tool, decides which risk they prefer to carry.

## Trade-off

Defaulting to `abort` makes LACC fragile in exactly the situations where a more
forgiving tool would keep running. That fragility is the point: silent gaps in an
audit trail are indistinguishable from an audit trail that was never trustworthy.
The alternative - always continuing - was rejected as a default because it makes
the promise conditional without telling anyone. Making it configurable, with the
consequences written into the option itself, keeps the safe default while
respecting that some users legitimately need the other trade.

Recording metadata but not content by default means an operator reading a
`standard` log can see that a provider was called but not what was asked. That is a
real loss of forensic detail, accepted because the alternative - writing user
content to disk unless someone remembered to turn it off - is the kind of default
that betrays a privacy-first tool.

## Consequences

- Every later phase records what it does through the audit module rather than
  inventing its own logging.
- The configuration gains `audit_failure_policy`; `audit_level` gains meaning.
- The audit log is contained by the workspace boundary like any other path.
- The core gains a sixth functional module, `audit`. Chapter 1 and the CHANGELOG
  are updated in this same phase.