# Local AI Control Center (LACC)

[![Quality gate](https://github.com/asegura-dev/local-ai-control-center/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/asegura-dev/local-ai-control-center/actions/workflows/quality-gate.yml)

A local-first framework for private, reproducible, auditable AI-assisted
workflows.

## What LACC is

LACC is designed to run AI-assisted workflows entirely on your own machine,
with an emphasis on privacy, reproducibility, and human oversight. It is built
for developers and researchers who want the benefits of AI assistance without
sending their data to third-party services.

LACC is an orchestration and control layer. It is designed to run on top of
local inference engines such as Ollama, rather than to replace them: the engine
provides the model, while LACC is intended to handle permissions, previews,
confirmation, and audit around each action.

The project is in early development. This document describes the project's
design and direction. Where something is not yet implemented, it is described
as intent, not as a guarantee.

## Design principles

- **Local-first.** LACC is designed to run without paid APIs or internet
  access. Local user data is intended to stay out of version control.
- **Restrictive by default.** Permissions are intended to start disabled; each
  skill opts into only what it needs.
- **Auditable.** The project is designed so that meaningful executions can be
  traced after the fact.
- **Reproducible.** Executions are intended to record enough metadata to be
  understood and repeated later.
- **Human-in-the-loop.** Sensitive actions are meant to be reviewable before
  they run, not executed silently.

## What LACC is not

- Not an autonomous agent that acts without supervision.
- Not dependent on paid APIs or a network connection.
- Not a large platform. It grows in small, reviewed increments.

## Status

Early development. The package currently exposes its version and a placeholder
entry point. Functional modules - configuration, workspaces, providers, audit,
and skills - are introduced one at a time in later phases, each with its own
tests and documentation.

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.