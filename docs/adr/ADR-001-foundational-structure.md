# ADR-001 - Foundational structure

- **Status:** Accepted - implemented (v0.0.1)
- **Date:** 2026-07-17
- **Context:** LACC begins as an empty project. Before writing any functional
  code, we must decide the shape it grows into: how the package is laid out, which
  direction dependencies point, how modules are organized as they multiply, and
  what base tooling enforces quality. These choices are load-bearing - every later
  decision assumes them - so they are recorded here as the first decision.

## Decision

### 1. Core-first dependency direction

Application logic lives in the installable package (`src/local_ai_control_center`).
Interfaces (a future CLI, a possible dashboard) consume that logic; the logic never
depends on them. Dependencies point one way, inward toward the core.

This mirrors the ports-and-adapters style used in related projects: a
dependency-free core of contracts and logic, with unstable edges (interfaces,
external engines) depending on it, never the reverse. It keeps the core testable
in isolation and lets interfaces change without touching business logic.

### 2. The `src/` package layout

The project uses a `src/` layout with an installable package, created with `uv init
--package`. Code lives under `src/local_ai_control_center/`; tests live under
`tests/`. The package is installed in editable mode during development.

The `src/` layout is chosen over a flat top-level package because it prevents
accidental imports of the not-yet-installed package during testing, forcing tests
to run against the installed artifact - the same thing users get.

### 3. Flat modules until a split is justified

Early versions use a small set of flat modules inside the package rather than many
subpackages. A subpackage is introduced only when a module grows large enough to
justify the split. This avoids empty folders and premature abstraction.

As the project matures it may grow toward a layered structure similar to related
projects (a `contracts` core of validated models, a `ports` layer of abstract
interfaces, and consumer layers around them). That is direction, not current
structure; those folders are created when there is real code to fill them.

### 4. Base stack

- **uv** for environment and dependency management, and for the package build
  (`uv_build` backend).
- **Pydantic** for validated contracts at every boundary (adopted as functional
  modules arrive; the pattern is: validate once at the edge, then trust the object).
- **A quality gate** of `ruff` (lint + format), `mypy` (strict type checking), and
  `pytest` (tests), run before every commit.
- **Python 3.11+**, MIT licensed.

## Trade-off

This structure costs more than a single-file script: a package to install, a
composition seam between core and interfaces, and the discipline of a quality gate
on even trivial code. For a throwaway script this would be over-engineering. For a
tool meant to grow into permission control, previews, and auditing - where
correctness and trust are the whole point - the structure pays for itself the first
time a change would otherwise ripple through untyped, untested code.

The alternative - starting flat and unstructured, adding rigor later - was rejected
because retrofitting a quality gate and a core/interface split onto existing code is
far more expensive than adopting them while the project is empty.

## Consequences

- Every later ADR assumes this core-first, contract-at-the-boundary foundation.
- Adding functional behavior means adding a flat module with its own tests and
  documentation, consumed through the core - not reaching across layers.
- The quality gate must stay green as a condition of every phase being done, and
  documentation is updated in the same phase as the code it describes.