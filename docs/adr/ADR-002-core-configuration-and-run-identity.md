# ADR-002 - Core configuration and run identity

- **Status:** Accepted - implemented (v0.1.0)
- **Date:** 2026-07-17
- **Context:** ADR-001 established a core-first package with contracts at the
  boundary but no functional behavior yet. The first functional slice a control
  layer needs is a validated notion of *how it is configured* and *which execution
  is running*. Configuration decides what LACC is allowed to do; the run identity
  ties every future audit record to a specific execution. Both are foundational:
  later modules (permissions, preview, audit) read the configuration and stamp
  their records with the run id.

## Decision

### 1. A validated configuration contract

Configuration is a frozen Pydantic model, `Config`, living in a flat `config`
module. Validation happens once, at construction; thereafter the object is trusted
(the pattern from ADR-001). The initial fields are the minimum that carry real
meaning today:

- `network_access: bool = False` - whether LACC may use the network. Defaults to
  **False**: local-first means the safe, offline value is the default, and network
  access is granted only when explicitly requested.
- `audit_level: Literal["standard", "full"] = "standard"` - how much detail the
  (future) audit trail records. A closed set, not a free string, so an unknown
  level fails at the boundary.
- `workspace_root: Path` - the base directory LACC treats as its working area.

The model forbids unknown fields, so a typo in a config file fails loudly instead
of being silently ignored.

### 2. Loading configuration from YAML

`Config` can be built with defaults in code, or loaded from a YAML file via a
`load_config(path)` function. Loading reads the file, then validates it against the
model. A missing file, malformed YAML, an unknown field, or a wrong type each fails
immediately with a clear error - validation at the boundary, fail-fast.

The safe-by-default rule holds across loading: a field absent from the file takes
its default (so an absent `network_access` is **False**). A file may set
`network_access: true`, and LACC respects it - the user is in control - but silence
never enables it.

### 3. Run identity

Each execution gets a `run_id`: a human-readable, sortable, unique string of the
form `YYYYMMDDThhmmssZ-xxxx` (a UTC timestamp plus a short random suffix), produced
by a `new_run_id()` function in a flat `run` module. The timestamp makes audit logs
readable and ordered at a glance; the random suffix keeps two executions that start
in the same second from colliding.

Run identity lives in its own module, separate from configuration, because the two
answer different questions ("how is LACC set up" vs "which run is this") and the run
id will grow toward the audit system while configuration will not.

### 4. New dependencies

This slice adds two runtime dependencies: **pydantic** (the validated contract) and
**pyyaml** (reading the config file). They move `dependencies` from empty to
holding the project's first real external requirements.

## Trade-off

Depending on Pydantic and PyYAML costs two external libraries and a little
construction-time CPU, versus hand-rolling a config parser and validator. In
exchange we get fail-fast validation, self-documenting field types, free
serialization, and a boundary that makes invalid configuration unrepresentable -
worth far more to a tool whose whole point is controlled, auditable execution.

The alternative - a plain dictionary or a hand-written parser - was rejected: it
pushes validation into scattered runtime checks and loses the "validate once, then
trust" guarantee that ADR-001 builds on.

A second choice: the `run_id` uses a readable timestamp format rather than a raw
UUID. A UUID is simpler and collision-proof, but opaque in a log. Since the run id
exists to serve human-readable auditing, readability wins; the random suffix
recovers the uniqueness a bare timestamp would lack.

## Consequences

- `Config` is the single source of truth other modules read to decide what is
  allowed; `network_access = False` by default anchors the local-first stance.
- Every future audit record can be stamped with a `run_id`, tying actions to a
  specific, time-ordered execution.
- The project now has runtime dependencies; `uv sync` installs pydantic and pyyaml.
- Chapter 1 (architecture) and the CHANGELOG are updated in this same phase to
  reflect the first functional modules.