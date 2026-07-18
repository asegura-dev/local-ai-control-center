# Documentation index - what is in each file

The reference for finding the right doc **without opening it**. One line per file:
what it contains. For the reading order and status, see [README.md](README.md).

## Chapters - the book (`docs/NN-*.md`)

| # | File | What's in it |
|---|---|---|
| 00 | [00-introduction](00-introduction.md) | What LACC is and is **not**: a local-first orchestration and control layer for private, auditable AI-assisted workflows - not an autonomous agent, not a model runtime. The guiding trade-off (control and honesty over capability) and a map of the book. |
| 01 | [01-architecture](01-architecture.md) | The core-first design: logic lives in the package and interfaces consume it; dependencies point one way. Flat modules until a split is justified. The guiding quality principles (cohesion, coupling, explicit over implicit, incremental design) and their honest tensions. |
| 02 | [02-roadmap](02-roadmap.md) | What is done (scaffold, config and run identity, workspaces), the phases still needed to complete the control core, the group that produces the first end-to-end run, and what v1.0 would mean. Direction, not a schedule. |
| 03 | [03-development](03-development.md) | How to set up the project (uv, the requirements), the quality gate (ruff, mypy, pytest), and the documentation discipline: docs are updated in the same phase as the code they describe. |

## Decisions - ADRs (`docs/adr/`)

| ADR | File | The decision |
|---|---|---|
| 001 | [foundational-structure](adr/ADR-001-foundational-structure.md) | Core-first dependency direction, the `src/` package layout, flat modules until a split is justified, and the base stack (uv, Pydantic contracts at the boundary, the quality gate of ruff/mypy/pytest). The decision every later one assumes. |
| 002 | [core-configuration-and-run-identity](adr/ADR-002-core-configuration-and-run-identity.md) | The first functional slice: a validated `Config` contract (network off by default, audit level, workspace root) loadable from YAML, and a human-readable time-ordered `run_id`. Adds pydantic and pyyaml. |
| 003 | [workspaces-and-boundary-enforcement](adr/ADR-003-workspaces-and-boundary-enforcement.md) | Turns `workspace_root` into an enforced boundary: a validated `Workspace` that resolves `..` and symlinks before checking containment (`is_within`, `resolve_within`), with explicit root creation (`ensure`) and a `workspace_from_config` seam. |

## Top-level files

| File | What's in it |
|---|---|
| [README.md](../README.md) (repo root) | The public landing page: what LACC is, its design principles, what it is not, and the current status. |
| [docs/README.md](README.md) | The book's table of contents: the numbered chapters with per-version status, the guiding principle, and the ADR index. |
| [CHANGELOG.md](../CHANGELOG.md) (repo root) | Notable changes, newest first. The "what's new since I last looked" skim. |