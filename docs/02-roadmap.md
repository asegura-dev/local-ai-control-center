# Chapter 2 - Roadmap: where LACC is and where it is heading

This chapter describes what LACC has today and the path ahead. Nearer phases are
described with more confidence; later ones are direction and are expected to change
as real code reveals what each one actually needs. This is not a schedule and
carries no dates.

## Done

- **v0.0.1 - Scaffold.** An installable package, the quality gate (lint, format,
  strict type checking, tests), the documentation system, and the MIT license.
- **v0.1.0 - Configuration and run identity.** A validated, frozen `Config`
  contract loadable from YAML with network access off by default, and a
  human-readable, time-ordered `run_id`.
- **v0.2.0 - Workspaces and boundary enforcement.** A validated `Workspace` whose
  boundary cannot be escaped: candidate paths are resolved before checking.
- **v0.3.0 - Permissions.** A restrictive-by-default permission contract with the
  configuration acting as a ceiling no permission can exceed.
- **v0.4.0 - Provider port.** An abstract provider with a deterministic offline
  mock, so the rest of the system is testable without any engine.
- **v0.5.0 - Audit log.** Append-only JSON Lines inside the workspace, with privacy
  as the default and a configurable write-failure policy.
- **v0.6.0 - Execution preview.** A side-effect-free description of what an action
  would do and whether it would be allowed.
- **v0.7.0 - Execution cycle.** The one place that runs an action through the whole
  system, with confirmation supplied as a function, plus the first integration
  tests. Continuous integration and an example configuration were added here too.
- **v0.8.0 - Skills.** An abstract `Skill` contract that produces an action through
  a pure `plan`, plus a read-only file-summarization skill.
- **v0.9.0 - Command-line interface.** The `lacc` command (Typer + Rich): `run` and
  `preview`, with human confirmation defaulting to no. **LACC now runs end to end
  from a terminal** against the mock provider - the foundations became a working
  tool.
- **v0.10.0 - Permission sourcing.** A skill is granted the capabilities it
  declares, limited by the configuration ceiling (`grant_for`), removing the CLI's
  hardcoded permission.
- **v0.11.0 - Profiler.** A read-only `lacc profile` that detects Ollama, lists
  installed models, reports hardware, and computes a model-fit table by formula -
  honest about what it cannot know, and never recommending a model.

## Next

The end-to-end path works against a mock. What remains turns it into something that
runs real models, safely.

## Next

- **A real provider.** A second implementation of the provider port backed by a
  local engine (Ollama), reached through the same contract as the mock. This is
  where generation parameters and model selection are finally decided, informed by
  what the profiler reports. It is the most unpredictable phase: real models, real
  hardware, real latency, exercised through the CLI that already exists. This is the
  step that makes the loop run against a live model instead of a deterministic mock.

## Toward v1.0

Beyond a working real provider, the direction is to make it dependable: hardening
against real-world failure, and documentation good enough for someone else to adopt
it. A v1.0 means the control loop is stable and trustworthy, not that every feature
exists.

Further ideas - a system dashboard consuming the same core, chaining skills
together - are under consideration, not commitments. Some may not happen at all.

One direction worth naming, because it changes assumptions rather than adding to
them: running LACC across several machines the user owns, on their own private
network, so a laptop can dispatch heavy work to a desktop with a dedicated GPU
while light tasks stay local. This stays local-first in the sense that matters -
own hardware, own network, own data, nothing sent to a third-party service - but
the moment LACC listens on a port, the threat model changes. The current design
assumes one user on one machine; permissions guard against misbehaving skills, not
against someone who reaches the interface. That would need its own decision record
covering authentication, authorization, and whether the audit trail should sit
outside the reachable workspace. It is a direction for after v1.0, not a plan.

## What this roadmap is not

Not a release schedule, and not a promise. It is a statement of direction meant to
keep development focused and honest. Where a feature is not yet implemented, it is
described as intent. Phases may be split, merged, or reordered as real code reveals
what each one needs.