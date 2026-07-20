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
| 004 | [permissions](adr/ADR-004-permissions.md) | The mechanism the project is built around: a closed set of capabilities, all disabled by default, with the configuration acting as a ceiling that no permission can exceed. `check` reports what is missing for previews; `require` raises on the execution path. |
| 005 | [provider-abstraction](adr/ADR-005-provider-abstraction.md) | An abstract `Provider` port kept deliberately minimal (prompt in, completion out, no generation parameters yet) so the core never depends on an engine, plus a deterministic `MockProvider` that makes every later phase testable offline. |
| 006 | [audit-log](adr/ADR-006-audit-log.md) | Append-only JSON Lines inside the workspace, contained by its boundary. `audit_level` decides detail with privacy as the default (metadata always, content only under `full`), and `audit_failure_policy` decides whether a failed write stops execution, with each option's consequence stated. |
| 007 | [execution-preview](adr/ADR-007-execution-preview.md) | A side-effect-free preview that reports whether an action would be allowed, built on a generic `IntendedAction` so it never depends on skills. Reports every refusal reason at once: missing capabilities and paths escaping the workspace. |
| 008 | [execution-cycle](adr/ADR-008-execution-cycle.md) | The one place that knows the order: `run_action` previews, refuses or asks, executes, and records. Confirmation is supplied as a function so the core holds no interface code. Refused and declined runs are audited, not just completed ones. Home of the first integration tests. |
| 009 | [skills](adr/ADR-009-skills.md) | An abstract `Skill` contract mirroring the provider port: a skill declares its name and capabilities and implements a pure `plan` that describes an action without doing anything. The cycle owns side effects. First skill: read-only file summarization. No registry yet - it arrives with the command line. |
| 010 | [command-line-interface](adr/ADR-010-command-line-interface.md) | The `lacc` command (Typer + Rich, confined to the CLI): `run` previews, confirms (defaulting to no), executes, and records; `preview` shows without doing. Skills resolved by a minimal mapping, no registry yet. Notes a deferred decision: where granted permissions come from. |

## Top-level files

| File | What's in it |
|---|---|
| [README.md](../README.md) (repo root) | The public landing page: what LACC is, its design principles, what it is not, and the current status. |
| [docs/README.md](README.md) | The book's table of contents: the numbered chapters with per-version status, the guiding principle, and the ADR index. |
| [CHANGELOG.md](../CHANGELOG.md) (repo root) | Notable changes, newest first. The "what's new since I last looked" skim. |