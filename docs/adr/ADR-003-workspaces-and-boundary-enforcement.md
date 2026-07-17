# ADR-003 - Workspaces and boundary enforcement

- **Status:** Accepted - implemented (v0.2.0)
- **Date:** 2026-07-17
- **Context:** ADR-002 gave the configuration a `workspace_root` field
  only a stored path with no behavior. A control layer needs that path to mean
  something enforceable: a bounded area LACC may operate in, and a guarantee that
  operations cannot escape it. This ADR turns `workspace_root` into a validated
  workspace with an explicit safety boundary.

## Decision

### 1. A validated workspace contract

A workspace is a frozen Pydantic model, `Workspace`, in a flat `workspace` module.
It holds a single `root` path. On construction the root is resolved to an absolute,
symlink-free path, so all later checks compare against a canonical location. The
model is validated once and trusted thereafter (the pattern from ADR-001).

### 2. Explicit creation, never automatic

A workspace may create its root directory, but never as a silent side effect of
existing. Construction does not create anything. Creation is a separate, explicit
operation, `Workspace.ensure(root)`, that creates the directory if missing and
returns the workspace. Plain construction of a workspace whose root does not exist
fails. This keeps the convenience of "create if needed" without violating
restrictive-by-default: nothing touches the filesystem unless the caller asks.

### 3. Boundary enforcement

The core safety operation is `is_within(path)`: given any candidate path, it
decides whether that path resolves to a location inside the workspace root. It
resolves the candidate to an absolute, symlink-free path first, so tricks like
`../../etc` or a symlink pointing outside are caught rather than trusted. A
companion `resolve_within(path)` returns the safe absolute path when it is inside
and raises a clear error when it is not, for callers that need the path itself.

The boundary is the mechanism that lets a misbehaving skill be contained: whatever
it asks to touch is checked against the workspace before anything happens.

### 4. Loading a workspace from configuration

A `workspace_from_config(config)` helper builds a workspace from a `Config`'s
`workspace_root`, connecting the two modules. It uses explicit creation, so loading
a config whose workspace does not yet exist creates it deliberately. The core
(`config`, `run`, `workspace`) stays free of interface concerns; this helper is the
seam where configuration becomes an operational workspace.

## Trade-off

Resolving every candidate path (absolute + symlink resolution) before the boundary
check costs a filesystem call per check, versus a cheap string prefix comparison. A
string comparison is faster but unsafe: `..` segments and symlinks defeat it, which
is exactly the attack a control layer must stop. Correct containment is worth the
cost; the boundary is the whole point of the module.

The alternative - trusting paths and comparing strings - was rejected because it
provides the appearance of a boundary without the guarantee, which is worse than no
boundary at all.

A second choice: the workspace can create its root, but only through an explicit
`ensure`. Making creation automatic on construction was rejected as it would let a
mere object instantiation write to disk, breaking the restrictive-by-default stance
and hiding a side effect behind a constructor.

## Consequences

- Any later module that touches the filesystem is expected to route paths through
  the workspace boundary rather than trusting them.
- `workspace_root` in the configuration now has enforceable meaning, not just a
  stored value.
- The core gains a third functional module, `workspace`, consumed the same way as
  `config` and `run`. Chapter 1 and the CHANGELOG are updated in this same phase.