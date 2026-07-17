# Chapter 0 - Introduction: what LACC is and is not

## The decision

Before any architecture, we fixed what we are building and, just as importantly,
what we are **not**.

Local AI Control Center (LACC) is a **local-first orchestration and control
layer** for AI-assisted workflows. It is designed to run tasks on your own
machine with explicit permissions, a preview before anything runs, human
confirmation, and an auditable record of what happened. It sits on top of local
inference engines such as Ollama; it does not replace them.

It is **not** several things, and stating them up front drives real engineering
choices:

- **Not an autonomous agent.** LACC is designed around human oversight: sensitive
  actions are meant to be reviewed before they run, not executed silently.
- **Not a model runtime.** The engine provides the model; LACC is intended to
  handle the permissions, preview, confirmation, and audit around each action.
- **Not a cloud service.** It is designed to run without paid APIs or internet
  access, keeping local data on the machine and out of version control.

## Why it matters

A tool that "does things for you automatically" invites hidden assumptions and
silent failure. A tool that "asks permission, shows what it will do, and records
what it did" invites scrutiny and trust. We chose the second, and the rest of
this book defends the decisions that follow from it.

## Trade-off

We deliberately favor **control and honesty over capability**. LACC starts
restrictive: permissions are disabled by default and each skill opts into only
what it needs. This makes the tool less immediately powerful than one that acts
freely, in exchange for being trustworthy and auditable. Capability grows later,
in small reviewed increments, once the control and audit foundations are real.

## Map of the book

This book grows with the code, one decision at a time:

- **Ch. 0** - this introduction: scope and the guiding trade-off.
- **Ch. 1** - architecture: core-first, flat modules, contracts at the boundary.
- **Ch. 2** - roadmap: where LACC is and where it is heading.
- **Ch. 3** - development: setup, the quality gate, and documentation discipline.

Decisions are recorded separately as ADRs (`adr/`), each with its context, the
choice, the trade-off, and the alternative rejected. The one-line-per-file map is
[INDEX.md](INDEX.md).

## Summary

LACC is a control and audit layer for local AI-assisted work, not a money machine
of automation. Every later decision - restrictive permissions, preview before
execution, an audit trail - exists to make what the tool does explicit, reviewable,
and trustworthy.