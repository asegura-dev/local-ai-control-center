# ADR-004 - Permissions: restrictive by default, with configuration as a ceiling

- **Status:** Accepted - implemented (v0.3.0)
- **Date:** 2026-07-17
- **Context:** ADR-002 and ADR-003 gave LACC a validated configuration and an
  enforced workspace boundary, but nothing yet decides *whether an action is
  allowed at all*. This is the mechanism the project is built around: a skill must
  declare what it needs, and something must grant or deny it. This ADR defines the
  vocabulary of capabilities, the permission contract, and how a decision is made.

## Decision

### 1. A small, closed set of capabilities

Capabilities are a closed set, not free-form strings, so an unknown capability is a
boundary error rather than a silent grant. The initial set is the minimum that
carries real meaning today:

- `read_files` - reading inside the workspace.
- `write_files` - creating or modifying files inside the workspace.
- `network` - any outbound network use.
- `run_commands` - executing external processes.

The set grows only when a real need appears; inventing categories in advance would
be structure without substance.

### 2. Permissions start disabled

`Permissions` is a frozen Pydantic model with one boolean per capability, each
defaulting to **False**. An empty `Permissions()` grants nothing. A skill opts in
to exactly what it needs and nothing more. This is the restrictive-by-default
stance made concrete: silence never grants.

### 3. Configuration is a ceiling, not a suggestion

Configuration constrains permissions rather than sitting beside them. If
`Config.network_access` is `False`, the `network` capability is denied regardless of
what a skill's permissions say. An `effective_permissions(permissions, config)`
function computes the intersection: a capability is available only if the
permissions grant it **and** the configuration allows it.

Without this, the local-first promise would be breakable by a skill granting itself
network access - the configuration would be advice rather than policy. Coupling
points inward (permissions reads configuration; configuration knows nothing of
permissions), consistent with ADR-001.

### 4. Two ways to ask, for two different moments

Checking returns a result rather than raising, because the answer feeds the
execution preview: a caller needs to show *what would be denied and why*, not just
fail. `check(required, granted, config)` returns a `PermissionCheck` holding whether
it was allowed and the sorted list of missing capabilities.

A companion `require(required, granted, config)` raises `PermissionDenied` listing
what is missing. The pair exists so the preview path can inspect a decision safely
while the execution path cannot proceed past a denial by accident - an ignored
return value should never become an unnoticed grant.

## Trade-off

Making configuration a ceiling couples the permission module to the configuration
module, where a fully independent module would be cleaner in isolation. The
alternative - keeping them separate and combining them later in the command-line
layer - was rejected: it would leave a window in which a caller could consult
permissions alone and act on an answer the configuration forbids. A safety
invariant belongs in the core, not in whichever interface remembers to apply it.

Returning a result rather than raising is the more useful shape for previews, but
carries the risk of a caller ignoring it. Providing `require` alongside `check`
recovers the safety without losing the usefulness: the execution path uses the
raising form, the preview path uses the inspecting form.

## Consequences

- Every future skill declares its required capabilities, and nothing runs without a
  check against granted permissions and the configuration ceiling.
- The execution preview can report precisely which capabilities are missing.
- The core gains a fourth functional module, `permissions`. Chapter 1 and the
  CHANGELOG are updated in this same phase.