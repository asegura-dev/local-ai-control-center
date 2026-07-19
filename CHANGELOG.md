# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-07-19

### Added
- Execution preview (`preview`): describes what an action would do before it runs
  and whether it would be allowed, with no side effects - nothing is written, no
  provider is called.
- `IntendedAction`: a generic description (name, summary, required capabilities,
  target paths) that anything can produce, so the preview does not depend on skills.
- Previews report every refusal reason at once - missing capabilities and paths
  escaping the workspace boundary - and render a readable block for confirmation.


## [0.5.0] - 2026-07-19

### Added
- Audit log (`audit`): append-only JSON Lines records written inside the workspace,
  with the path resolved through the workspace boundary. Each event carries a UTC
  timestamp, the `run_id`, a closed-set event kind, a message, and optional detail.
- `audit_level` gains behavior: `standard` (the default) records metadata only,
  omitting prompt and completion content; `full` records content as an explicit
  opt-in.
- `audit_failure_policy` in the configuration: `abort` (the default) refuses to
  proceed when a record cannot be written; `continue` proceeds unrecorded. Each
  option documents its consequence.


## [0.4.0] - 2026-07-17

### Added
- Provider port (`provider`): an abstract `Provider` with a single operation
  (prompt in, `Completion` out) so the core never depends on a concrete engine.
  Completions carry the name of the provider that produced them, so results can be
  attributed in an audit record.
- `MockProvider`: a deterministic implementation that touches no network, model, or
  filesystem. Answers from caller-supplied scripted responses, or falls back to a
  predictable response derived from the prompt. Makes every later phase testable
  offline.


## [0.3.0] - 2026-07-17

### Added
- Permissions (`permissions`): a frozen contract with one capability per field
  (`read_files`, `write_files`, `network`, `run_commands`), all disabled by default
  so an empty `Permissions()` grants nothing.
- Configuration as a ceiling: `effective_permissions` intersects granted
  capabilities with what the configuration allows, so a capability the
  configuration forbids cannot be granted by a skill.
- `check` returns a `PermissionCheck` naming exactly which capabilities are
  missing, for execution previews; `require` raises `PermissionDenied` on the
  execution path.


## [0.2.0] - 2026-07-17

### Added
- Workspaces (`workspace`): a validated, frozen contract around a root directory
  with an enforced boundary. `is_within` and `resolve_within` resolve `..` and
  symlinks before checking, so paths cannot escape the workspace. Root creation is
  explicit via `ensure`, never a silent side effect of construction.
- `workspace_from_config`: builds an operational workspace from a configuration's
  `workspace_root`, the seam connecting config to workspace.


## [0.1.0] - 2026-07-17

### Added
- Initial project scaffold: installable package skeleton, packaging
  configuration, and quality gate tooling (linter, type checker, test runner).
- A smoke test that verifies the package imports and exposes a version.
- Documentation as a short book of numbered chapters: overview, architecture,
  roadmap, and development.
- MIT license.
- ADR-based documentation system: a book of numbered chapters plus decision
  records (`docs/adr/`), an index, and the guiding principle that every document
  is written from a real decision.
- Core configuration (`config`): a validated, frozen Pydantic contract
  (`network_access` off by default, `audit_level`, `workspace_root`) loadable
  from YAML, validated at the boundary.
- Run identity (`run`): a human-readable, time-ordered, unique `run_id` for each
  execution.
- Runtime dependencies: pydantic and pyyaml.