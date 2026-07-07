# Overview

Local AI Control Center (LACC) is a local-first framework for private, reproducible, auditable AI-assisted workflows.

## What LACC is

LACC is designed to run AI-assisted workflows entirely on your own machine,
with an emphasis on privacy, reproducibility, and human oversight. It is meant
for developers and researchers who want the benefits of AI assistance without
sending their data to third-party services.

LACC is an orchestration and control layer. It is designed to run on top of
local inference engines such as Ollama, rather than to replace them. The engine
provides the model; LACC is intended to handle permissions, previews,
confirmation, and audit around each action.

## Who it is for

LACC is aimed at people who want to keep control of what an AI-assisted tool
does on their machine: developers automating local tasks, researchers who need
reproducible runs, and anyone who prefers explicit permission and a clear record
over silent automation.

## Philosophy

- **Local-first.** The project is designed to run without paid APIs or internet
  access, keeping local user data out of version control.
- **Restrictive by default.** Permissions are intended to start disabled. Each
  skill opts into only what it needs.
- **Auditable.** The project is designed so that meaningful executions can be
  traced after the fact.
- **Reproducible.** Executions are intended to record enough metadata to be
  understood and repeated later.
- **Human-in-the-loop.** Sensitive actions are meant to be reviewable before
  they run, not executed silently.

## Status

Early development. This document describes design and direction. Where something
is not yet implemented, it is described as intent, not as a guarantee. The
package currently exposes its version and a placeholder entry point; functional
modules are introduced one at a time in later phases, each with its own tests
and documentation.