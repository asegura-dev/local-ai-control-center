# Architecture

This chapter describes how LACC is structured and the reasoning behind those
choices. It grows as the implementation does.

## Guiding principles

The design of LACC is guided by a few well-known quality principles. They are
goals that shape decisions, not properties the current code already proves.

- **High cohesion.** Each module aims to have one clear responsibility.
- **Low coupling.** Modules aim to depend on each other as little as possible,
  communicating through explicit contracts rather than shared internals.
- **Explicit over implicit.** Behavior that matters is meant to be declared, not
  assumed: permissions start disabled and are requested per skill, and sensitive
  actions are meant to be shown before they run.
- **Incremental design.** Structure is added when a real need appears, not in
  advance. Flat modules stay flat until a module grows enough to justify a split.

These principles pull against each other in places. Low coupling favors splitting
things apart; incremental design favors keeping them together until a split is
clearly needed. LACC leans toward the simpler structure first and accepts a
little more coupling for a while, rather than building abstractions the code does
not yet require. Some of these boundaries are not yet exercised by real code and
may shift as the project grows.

## Core-first

LACC is built core-first. Application logic is intended to live in the package,
and interfaces consume it. The dependency direction is meant to be one-way:

```text
core logic  ->  CLI / dashboard use it
```

The reverse is not allowed: the core must not depend on the CLI or the
dashboard. This is intended to keep the core testable in isolation and to let
interfaces change without touching business logic.

## Module strategy

Early versions use a small set of flat modules rather than many subpackages.
Subpackages are introduced only when a module grows large enough to justify the
split. This avoids empty folders and premature abstraction.

The package currently exposes its version and a placeholder entry point.
Functional modules such as configuration, workspaces, providers, audit, and
skills are added one at a time in later phases, each with its own tests and
documentation.

## Future direction

As the project matures, the package may be organized into subpackages such as
configuration, workspaces, providers, audit, skills, security, and profiler.
This is direction, not current structure. Folders are created when there is real
code to put in them.