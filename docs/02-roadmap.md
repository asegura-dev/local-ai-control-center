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
  human-readable, time-ordered `run_id` for each execution.
- **v0.2.0 - Workspaces and boundary enforcement.** A validated `Workspace` whose
  boundary cannot be escaped: candidate paths are resolved before checking, so `..`
  segments and symlinks are caught rather than trusted.

## Next: completing the control core

These phases build the remaining pieces a control layer needs before anything can
run end to end:

- **Permissions.** A restrictive-by-default permission contract: every capability
  starts disabled, and a skill declares only what it needs. This is the mechanism
  the whole project is built around.
- **Providers.** An abstraction over the thing that produces model output, plus a
  deterministic mock provider that runs offline. The mock makes the rest of the
  system testable without any engine installed.
- **Audit.** An append-only record of what was executed, stamped with the `run_id`,
  so a run can be traced after the fact.

## Then: the first end-to-end run

With the control core in place, these phases connect it into something that
actually runs:

- **Execution preview.** Showing what a skill would do before it does it - the
  human-in-the-loop moment the design exists for.
- **A demonstration skill.** A small read-only skill that exercises the whole path:
  permission check, preview, confirmation, execution, audit record.
- **A command-line workflow.** The `lacc` command that ties configuration,
  workspace, permissions, provider, preview, and audit into one flow.

At the end of this group LACC does something complete from start to finish, against
a mock provider. This is the point where the foundations become a working tool.

## Toward v1.0

Beyond the first end-to-end run, the direction is to make it real and usable:
integrating an actual local inference engine in place of the mock, hardening the
boundaries against real-world use, and documenting the project well enough for
someone else to adopt it. A v1.0 means the control loop is stable and trustworthy,
not that every feature exists.

Further ideas - a system profiler, a dashboard interface consuming the same core,
chaining skills together - are under consideration, not commitments. Some may not
happen at all.

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