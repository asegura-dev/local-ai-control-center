# Documentation - Local AI Control Center

Documentation written as a book: numbered thematic chapters, each born from a
**real decision** with its rationale and its trade-off. Written as each phase is
built, not at the end. If a chapter does not document a decision, it does not
belong here.

Internal cross-reference convention: **"Ch. N Sec. M"** for chapters, **"ADR-NNN"**
for decision records.

> **Looking for a specific doc?** [**INDEX.md**](INDEX.md) is the one-line-per-file
> reference - what every chapter and ADR contains, so you can find the right one
> without opening each.

## Table of contents

| Ch. | Title | Status |
|-----|-------|--------|
| [00](00-introduction.md) | Introduction: what LACC is and is **not** | done (v0.0.1) |
| [01](01-architecture.md) | Architecture: core-first, flat modules, contracts at the boundary | done (v0.0.1) |
| [02](02-roadmap.md) | Roadmap: where LACC is and where it is heading | living |
| [03](03-development.md) | Development: setup, the quality gate, and doc discipline | done (v0.0.1) |

> Chapters are written when each phase closes, documenting what was decided and
> why. The book grows with the code, never ahead of it.

## How the docs are organized

The **numbered chapters (00-03)** above are the linear *book* and live flat in
`docs/`. Decisions are recorded separately:

- [`adr/`](adr/) - Architecture Decision Records: the *why* behind each decision,
  with its context, the choice, the trade-off, and the alternative rejected.

As the project grows, other layers will be added when there is something real to
put in them - operational guides, status logs of what each phase produced, and a
teaching course. They are not created in advance; empty folders do not belong here.

## Decisions (ADRs)

- [ADR-001 - Foundational structure](adr/ADR-001-foundational-structure.md):
  core-first dependency direction, the `src/` package layout, flat modules until a
  split is justified, and the base stack (uv, Pydantic contracts at the boundary,
  the quality gate). The decision every later one assumes.

## Guiding principle

This documentation exists to make the project understandable without reverse-
engineering the source. Every document is honest about the state of the code:
what exists is described in the present tense; what is planned is described as
intent. A phase is not done until its docs match reality.