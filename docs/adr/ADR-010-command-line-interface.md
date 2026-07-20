# ADR-010 - Command-line interface: connecting a human to the core

- **Status:** Accepted - implemented (v0.9.0)
- **Date:** 2026-07-21
- **Context:** Every module needed to run a skill end to end now exists, but the
  only way to run one is from a test. This ADR adds the `lacc` command: the first
  human interface to the system, and the first place the confirmation function the
  cycle has always expected (ADR-008) is actually supplied by a person at a
  terminal. It is where the pure core meets an interface, without the core learning
  anything about it.

## Decision

### 1. Typer for the interface, Rich for presentation

The CLI is built with Typer, and Rich renders its output. Typer gives structured
commands, argument parsing, and generated help; Rich formats previews and results
readably. Both are interface concerns and live only in the CLI module. The core is
untouched: the preview's existing `render()` produces plain text, and the CLI
decides how to present it. Nothing in `preview`, `cycle`, or `skill` imports Typer
or Rich.

A graphical or dashboard interface would be premature: there is not yet enough to
fill one, and the terminal is sufficient to prove the end-to-end path. When a richer
interface is warranted, it consumes the same core the same way.

### 2. Two commands: run and preview

- `lacc run <skill> <request>` plans the skill, previews it, asks for confirmation,
  and on approval executes and records it.
- `lacc preview <skill> <request>` shows the preview and stops. It never asks,
  executes, or records an execution - it answers "what would happen?" without doing
  it.

`preview` exists because seeing before acting is central to the design, and it is
nearly free given the preview module already exists. A command to list skills is
deliberately deferred: with one skill there is nothing to list.

### 3. Confirmation defaults to no

`run` prints the preview and asks `Proceed? [y/N]`. The capitalized N signals the
default: pressing Enter, or anything other than an explicit yes, declines. This is
restrictive-by-default at the interface: a run happens only on an explicit yes,
never by inertia. The CLI supplies this as the confirmation function the cycle
expects; the core still knows nothing about how the question is asked.

### 4. Skills are resolved by a minimal mapping

The CLI maps skill names to skill instances with a small dictionary - today, one
entry. A formal registry is not built yet: with one skill, a lookup table is
enough, and a registry has its own questions (how skills register, what a name
collision means) best answered when several skills exist. An unknown skill name
fails with a clear message listing what is available.

### 5. Configuration and workspace come from the environment

`run` and `preview` load configuration from a file (defaulting to a conventional
path, overridable with an option), build the workspace from it via
`workspace_from_config`, and generate a fresh `run_id` per invocation. The CLI wires
the pieces the core already provides; it adds no logic of its own beyond wiring and
presentation.

## Trade-off

Adding Typer and Rich is two dependencies for what `argparse` could do with none.
The plain-standard-library alternative was rejected because the interface is what a
person actually touches: generated help, clear errors, and readable output are worth
the cost for a tool meant to be used and shown, and both libraries are widely used
and well maintained. They are confined to the CLI, so the core stays dependency-light
and they can be swapped without touching business logic.

A lookup dictionary instead of a registry means adding a skill later means editing
the CLI. That is accepted: it is a one-line change today, and building a registry now
would be structure ahead of need, with design questions that only real multiple
skills can answer well.

## Consequences

- LACC can be run from a terminal: the end-to-end path works outside the test suite
  for the first time.
- The confirmation function the cycle has always taken is now supplied by a real
  human decision.
- Typer and Rich become dependencies, confined to the CLI.
- The `lacc` console script (already declared in packaging) now points at a real
  entry point.
- The CLI is the tenth module. Chapter 1 and the CHANGELOG are updated in this same
  phase.
- **Deferred, to be corrected soon:** the CLI currently grants a fixed
  `read_files` permission to the skill it runs. Where granted permissions come from
  - configuration, a per-skill profile, a flag - is a real decision left open here
  and intended to be resolved in the next phase, before a real provider executes
  anything. It must not stay hardcoded for long.