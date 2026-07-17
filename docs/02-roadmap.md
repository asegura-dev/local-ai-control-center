# Chapter 2 - Roadmap: where LACC is and where it is heading

This chapter describes where LACC is today and the direction it is heading.
Nearer versions are described with more confidence; later ones are direction and
are expected to change as the project grows.

## Current state

The project is at an early scaffold stage. The package is installable, exposes
its version, and passes a quality gate of linting, type checking, and a small
test suite. It does not yet contain functional modules.

## Near-term direction (v0.1.x)

The v0.1.x series is intended to build the core foundation, one small module at
a time, each with its own tests and documentation:

- Configuration and run identifiers.
- Workspace contracts, with deterministic boundary checks.
- A provider abstraction and a deterministic mock provider that runs offline.
- An audit log foundation that records executions.
- A command-line workflow that ties these together end to end.
- A first demonstration skill, read-only and low risk, that exercises the whole
  design: permission checks, an execution preview, confirmation, and an audited
  result.

The order above reflects current intent, not a fixed schedule. Steps may be
split, merged, or reordered as real code reveals what each one actually needs.

## Later direction

Beyond v0.1.x, the following are directions under consideration, not commitments:

- A lightweight system profiler.
- A dashboard interface consuming the same core.
- An expanded execution preview and initial support for chaining skills.
- Integration with real local inference backends.

These are described so the overall intent is visible. They are expected to
change, and some may not happen at all.

## What this roadmap is not

This is not a release schedule and carries no dates. It is a statement of
direction meant to keep development focused and honest. Where a feature is not
yet implemented, it is described as intent, not as a guarantee.