# Documentation index - what is in each file

The reference for finding the right doc **without opening it**. One line per file:
what it contains. For the reading order and status, see [README.md](README.md).

## Chapters - the book (`docs/NN-*.md`)

| # | File | What's in it |
|---|---|---|
| 00 | [00-introduction](00-introduction.md) | What LACC is and is **not**: a local-first orchestration and control layer for private, auditable AI-assisted workflows - not an autonomous agent, not a model runtime. The guiding trade-off (control and honesty over capability) and a map of the book. |
| 01 | [01-architecture](01-architecture.md) | The core-first design: logic lives in the package and interfaces consume it; dependencies point one way. Flat modules until a split is justified. The guiding quality principles (cohesion, coupling, explicit over implicit, incremental design) and their honest tensions. |
| 02 | [02-roadmap](02-roadmap.md) | Every release so far and what each one settled; the route to v1.0 and why it is capability rather than polish; the two directions decided and deliberately deferred past v1.0 - a model on another machine of your own, and an interface beyond the CLI. Direction, not a schedule, and corrected when the order changes. |
| 03 | [03-development](03-development.md) | How to set up the project (uv, the requirements), the quality gate - which now also fails if anything reaches the network - where to keep a workspace and why not inside the repository, and the documentation discipline: docs are updated in the same phase as the code they describe. |
| [04-measurements.md](04-measurements.md) | What this project measured about itself: seven published figures that were wrong and which way each leaned, the injection and hidden-text tests, the rates that currently hold, and how to read a figure from here. |

## Reading paths

Forty-five records front to back is a history. These are the threads through them, for
someone who wants to understand one thing rather than all of them. Each record's full
description is on [the annotated list](adr/README.md).

**How the quotation check learned it was wrong about itself — six times**
[026](adr/ADR-026-verified-quotations.md) → [031](adr/ADR-031-the-page-is-found-not-asked-for.md)
→ [034](adr/ADR-034-showing-what-the-document-does-say.md)
→ [035](adr/ADR-035-what-counts-as-the-same-text.md)
→ [036](adr/ADR-036-dropping-the-furniture-of-a-page.md)
→ [042](adr/ADR-042-what-unverified-was-actually-counting.md)
→ [044](adr/ADR-044-an-answer-we-already-know.md)
The most useful thread in the project, and the least flattering. Each step is a defect of
this tool that had been reported as the model's dishonesty.

**What a document can try, and what a fence can actually do**
[015](adr/ADR-015-prompt-shaping.md) → [037](adr/ADR-037-the-instruction-goes-after-the-document.md)
→ [038](adr/ADR-038-a-document-that-pretends-to-be-an-instruction.md)
→ [040](adr/ADR-040-text-a-reader-cannot-see.md)
→ [041](adr/ADR-041-standing-context-and-what-it-must-not-touch.md)
Both injection vectors were tested against a real model, and both worked before 038.

**Refusing rather than misleading**
[017](adr/ADR-017-hardening-limits-paths-and-exit-codes.md) → [019](adr/ADR-019-an-honest-context-ceiling.md)
→ [020](adr/ADR-020-measuring-the-estimate.md)
→ [024](adr/ADR-024-detecting-truncation-by-its-symptom.md)
→ [023](adr/ADR-023-a-trail-you-can-check.md)
→ [043](adr/ADR-043-what-the-chain-does-not-catch.md)
Ends on the one safety claim that did not hold, which is why it is worth reading to the end.

**Reading more than a single short file**
[014](adr/ADR-014-reading-file-contents.md) → [016](adr/ADR-016-document-ingestion.md)
→ [025](adr/ADR-025-writing-and-several-documents.md)
→ [039](adr/ADR-039-a-library-is-read-one-document-at-a-time.md)
→ [045](adr/ADR-045-a-document-read-in-passes.md)

**The shape of the program**
[001](adr/ADR-001-foundational-structure.md) → [005](adr/ADR-005-provider-abstraction.md)
→ [008](adr/ADR-008-execution-cycle.md) → [009](adr/ADR-009-skills.md)
→ [029](adr/ADR-029-ports-and-adapters-made-visible.md)

**The human in the middle**
[004](adr/ADR-004-permissions.md) → [007](adr/ADR-007-execution-preview.md)
→ [011](adr/ADR-011-permission-sourcing.md)
→ [028](adr/ADR-028-the-preview-names-the-destination.md)

**Running it on your own hardware**
[012](adr/ADR-012-profiler.md) → [021](adr/ADR-021-what-a-context-window-costs.md)
→ [013](adr/ADR-013-real-provider.md) → [027](adr/ADR-027-reaching-your-own-machines.md)
→ [022](adr/ADR-022-exposure-controls.md) → [030](adr/ADR-030-secrets-from-a-dotenv-file.md)
→ [032](adr/ADR-032-measuring-is-not-running.md)
→ [033](adr/ADR-033-the-skill-declares-its-temperature.md)

## Decisions - ADRs (`docs/adr/`)

| ADR | File | The decision |
|---|---|---|
| 001 | [foundational-structure](adr/ADR-001-foundational-structure.md) | Core-first dependency direction, the `src/` package layout, flat modules until a split is justified, and the base stack (uv, Pydantic contracts at the boundary, the quality gate of ruff/mypy/pytest). |
| 002 | [core-configuration-and-run-identity](adr/ADR-002-core-configuration-and-run-identity.md) | The first functional slice: a validated `Config` contract (network off by default, audit level, workspace root) loadable from YAML, and a human-readable time-ordered `run_id`. |
| 003 | [workspaces-and-boundary-enforcement](adr/ADR-003-workspaces-and-boundary-enforcement.md) | Turns `workspace_root` into an enforced boundary: a validated `Workspace` that resolves `..` and symlinks before checking containment (`is_within`, `resolve_within`), with explicit root creation (`ensure`) and a `workspace_from_config` seam. |
| 004 | [permissions](adr/ADR-004-permissions.md) | The mechanism the project is built around: a closed set of capabilities, all disabled by default, with the configuration acting as a ceiling that no permission can exceed. `check` reports what is missing for previews; `require` raises on the execution path. |
| 005 | [provider-abstraction](adr/ADR-005-provider-abstraction.md) | An abstract `Provider` port kept deliberately minimal (prompt in, completion out, no generation parameters yet) so the core never depends on an engine, plus a deterministic `MockProvider` that makes every later phase testable offline. |
| 006 | [audit-log](adr/ADR-006-audit-log.md) | Append-only JSON Lines inside the workspace, contained by its boundary. `audit_level` decides detail with privacy as the default (metadata always, content only under `full`), and `audit_failure_policy` decides whether a failed write stops execution, with each option's consequence stated. |
| 007 | [execution-preview](adr/ADR-007-execution-preview.md) | A side-effect-free preview that reports whether an action would be allowed, built on a generic `IntendedAction` so it never depends on skills. |
| 008 | [execution-cycle](adr/ADR-008-execution-cycle.md) | The one place that knows the order: `run_action` previews, refuses or asks, executes, and records. |
| 009 | [skills](adr/ADR-009-skills.md) | An abstract `Skill` contract mirroring the provider port: a skill declares its name and capabilities and implements a pure `plan` that describes an action without doing anything. |
| 010 | [command-line-interface](adr/ADR-010-command-line-interface.md) | The `lacc` command (Typer + Rich, confined to the CLI): `run` previews, confirms (defaulting to no), executes, and records; `preview` shows without doing. |
| 011 | [permission-sourcing](adr/ADR-011-permission-sourcing.md) | Removes the CLI's hardcoded permission: `grant_for` grants a skill the capabilities it declares, minus any the configuration vetoes. |
| 012 | [profiler](adr/ADR-012-profiler.md) | A read-only profiler (`lacc profile`) that detects Ollama, lists installed models, reports hardware, and computes a model-fit table by formula - never acting, never claiming usable acceleration it cannot verify. |
| 013 | [real-provider](adr/ADR-013-real-provider.md) | A real provider (`OllamaProvider`) implementing the existing port against local Ollama: complete responses (no streaming) with a progress spinner, model from configuration, localhost exempt from `network_access`, and failures translated into actionable messages rather than verified in advance. |
| 014 | [reading-file-contents](adr/ADR-014-reading-file-contents.md) | Turns a granted-but-unused `read_files` into a real read: the cycle reads the action's declared targets after confirmation and before the provider, never the skill's pure `plan`. |
| 015 | [prompt-shaping](adr/ADR-015-prompt-shaping.md) | Shapes what LACC actually says to the model: a framed task, a configured output language (`output_language`, default English), and the document fenced between fixed markers and declared to be material rather than instruction. `Skill.plan` gains the configuration, amending ADR-009 while keeping the plan pure. |
| 016 | [document-ingestion](adr/ADR-016-document-ingestion.md) | How a PDF or `.docx` becomes text LACC can read: conversion is an explicit step writing a `.md` into the workspace, not a parse hidden inside a read, so the most fragile link in the chain is the one you can inspect. |
| 017 | [hardening-limits-paths-and-exit-codes](adr/ADR-017-hardening-limits-paths-and-exit-codes.md) | What a security review of the existing surface found and decided: a configured ceiling on input size, Windows device names and alternate data streams refused at the boundary, and a refused run exiting non-zero while a declined one does not. |
| 018 | [a-second-skill-critique](adr/ADR-018-a-second-skill-critique.md) | A read-only `critique_file` skill, and the two questions only a second skill could answer. |
| 019 | [an-honest-context-ceiling](adr/ADR-019-an-honest-context-ceiling.md) | Why a prompt too large is refused rather than truncated, and why the window LACC checks against has to be the one it asked for: measured, the engine loads a 32768-token model with 4096 unless told otherwise, so a ceiling checked against the model's maximum would look like a check while the engine discarded most of the document. |
| 020 | [measuring-the-estimate](adr/ADR-020-measuring-the-estimate.md) | The engine reports how many tokens it actually processed, and LACC was discarding it. |
| 021 | [what-a-context-window-costs](adr/ADR-021-what-a-context-window-costs.md) | `lacc profile` reports what a context window costs at a range of sizes, so the number the user has to choose is informed rather than guessed. |
| 022 | [exposure-controls](adr/ADR-022-exposure-controls.md) | Separates approximation, which is fine when being wrong costs a retry, from exposure, where the failure is one-way and nothing recovers what has left the machine. |
| 023 | [a-trail-you-can-check](adr/ADR-023-a-trail-you-can-check.md) | Two blind spots in the audit trail, answered by one instrument. |
| 024 | [detecting-truncation-by-its-symptom](adr/ADR-024-detecting-truncation-by-its-symptom.md) | Closes the verification ADR-019 deferred, and closes it differently: rather than asking the engine what window it granted, LACC notices when the token count it reports reaches the window, which is the symptom that actually matters and arrives in a response already received. |
| 025 | [writing-and-several-documents](adr/ADR-025-writing-and-several-documents.md) | Two capabilities in one decision: LACC writes a revision beside the original and never over it, approved against a diff rather than a preview, because the revised text does not exist until the model answers; and every skill can be given several documents, each fenced separately. |
| 026 | [verified-quotations](adr/ADR-026-verified-quotations.md) | The first control that checks a model rather than asking it to behave: claims come with verbatim quotations and pages, and every quotation is looked for in the source before anything is shown. |
| 027 | [reaching-your-own-machines](adr/ADR-027-reaching-your-own-machines.md) | Resolves the contradiction between PRINCIPLES and VISION over what counts as local: not depending on someone else's computer, rather than staying on one machine. |
| 028 | [the-preview-names-the-destination](adr/ADR-028-the-preview-names-the-destination.md) | `engine_host` shipped in v0.26.0 and the preview did not follow, so the confirmation screen omitted the one fact that had changed: that the text of a document was about to leave the machine. |
| 029 | [ports-and-adapters-made-visible](adr/ADR-029-ports-and-adapters-made-visible.md) | Five directories whose names mean something: `core` decides and reaches for nothing, `ports` holds the abstract classes, `adapters` implements them, `system` is machine-facing code not behind a port, and the cycle and CLI sit above. |
| 030 | [secrets-from-a-dotenv-file](adr/ADR-030-secrets-from-a-dotenv-file.md) | ADR-027 said secrets are named rather than written, and did not account for how the value reaches the environment - a step the first person to follow the guide skipped, writing a live token into the configuration instead. |
| 031 | [the-page-is-found-not-asked-for](adr/ADR-031-the-page-is-found-not-asked-for.md) | The first real run showed page attribution failing on its own - page 4 for a sentence on page 1, with the quotation itself correct. |
| 032 | [measuring-is-not-running](adr/ADR-032-measuring-is-not-running.md) | Repeating a run five times on one paper gave verification rates from 25% to 85%, so single-run comparisons measure nothing and the prompt work that comes next cannot be evaluated without repeats. |
| 033 | [the-skill-declares-its-temperature](adr/ADR-033-the-skill-declares-its-temperature.md) | LACC had never sent a temperature, so the engine sampled at 0.8 on work that copies text verbatim - and made the audit's completion hashes irreproducible, which for a citable record is the more serious half. |
| 034 | [showing-what-the-document-does-say](adr/ADR-034-showing-what-the-document-does-say.md) | A quotation reported as not found now comes with the closest text that is in the document, without softening the verdict. |
| 035 | [what-counts-as-the-same-text](adr/ADR-035-what-counts-as-the-same-text.md) | Refines ADR-026's matching rule with a line it lacked: a difference a reader cannot see is representation, one they can see is content, and normalisation removes only the first. |
| 036 | [dropping-the-furniture-of-a-page](adr/ADR-036-dropping-the-furniture-of-a-page.md) | The last reason a faithful quotation failed: a journal's running header extracted inside a sentence. |
| 037 | [the-instruction-goes-after-the-document](adr/ADR-037-the-instruction-goes-after-the-document.md) | Turns the audit on what LACC asks for rather than what it does with the answer. |
| 038 | [a-document-that-pretends-to-be-an-instruction](adr/ADR-038-a-document-that-pretends-to-be-an-instruction.md) | Corrects a security claim the code had made for twenty-three releases. |
| 039 | [a-library-is-read-one-document-at-a-time](adr/ADR-039-a-library-is-read-one-document-at-a-time.md) | Thirty papers are twelve times the budget of the largest window this hardware can run, and no model size changes that because parameters do not buy context. `lacc collect` traverses a bibliography one document at a time. |
| 040 | [text-a-reader-cannot-see](adr/ADR-040-text-a-reader-cannot-see.md) | Closes the hole ADR-038 named: a quotation of text hidden in a PDF verifies, because the text really is in the document. |
| 041 | [standing-context-and-what-it-must-not-touch](adr/ADR-041-standing-context-and-what-it-must-not-touch.md) | A context file the user writes, used only by skills that declare it. |
| 042 | [what-unverified-was-actually-counting](adr/ADR-042-what-unverified-was-actually-counting.md) | A check has three outcomes and LACC reported two, so quotations that were in the document were tallied as failures. |
| 043 | [what-the-chain-does-not-catch](adr/ADR-043-what-the-chain-does-not-catch.md) | Seven safety claims tested against running code rather than read. |
| 044 | [an-answer-we-already-know](adr/ADR-044-an-answer-we-already-know.md) | Every rate this project published was measured where the correct answer was unknown - the condition that produced six mis-measurements, all flattering. |
| 045 | [a-document-read-in-passes](adr/ADR-045-a-document-read-in-passes.md) | Sets the scope of v2 at one thing: a document too large for the window is read in passes over its pages, overlapping by one so a passage crossing a break stays whole. |
| 046 | [how-much-to-show-at-once](adr/ADR-046-how-much-to-show-at-once.md) | Reading in passes was built for documents too large for the window and turns out to help documents that fit: measured over three of them, three-page readings gave 4.6x the verified quotations for twice the time. Makes pass size a setting, and derives the generation timeout from the window after a fixed 300 seconds reported slow work as an unreachable engine. |

## Guides (`docs/guides/`)

Practical, written from the tool as it behaves. Added one at a time, when a phase earns
one, rather than all at once.

| File | What's in it |
|---|---|
| [setting-up-the-server-machine](guides/setting-up-the-server-machine.md) | The hub for turning a machine you own into the one LACC talks to: a diagram of the three pieces and what each is for, links to the per-operating-system walkthrough, then the laptop-side configuration, the checks to run in order, and a table of what each symptom usually means. Ends with the measurement that says whether a bigger model was worth the setup. |
| [running-the-server-day-to-day](guides/running-the-server-day-to-day.md) | Getting your graphics card back without shutting anything down. The engine holds almost no VRAM; the model does, and it unloads itself after five minutes - or immediately, with one request sent from your laptop. Covers `keep_alive`, stopping and starting the engine per operating system, the Windows boot race that leaves Ollama running with nothing listening, and why the context window makes a 14B model measure 13.63 GB rather than 9. |
| [server-setup-on-linux](guides/server-setup-on-linux.md) | One continuous path on Ubuntu Server: Tailscale, Ollama bound to the tailnet rather than to every interface, ufw, a model, and ntfy. Numbered steps with the expected output shown, and checkpoints that say to stop rather than continue with a broken layer underneath. |
| [server-setup-on-windows](guides/server-setup-on-windows.md) | The same path on Windows 10 and 11: the installers, `SetEnvironmentVariable` for the bind address, `Get-NetTCPConnection` to verify it, and ntfy under Docker Desktop with the published port pinned to the tailnet address. Includes the sleep setting that makes a Windows server stop answering. |
| [running-lacc-for-the-first-time](guides/running-lacc-for-the-first-time.md) | From nothing to a checked answer about your own document: what to install, what `lacc profile` tells you before you pick a model, why `context_tokens` is the setting that bites (unset means the engine's own 4096 and silent truncation), how to choose a workspace that is not inside git or a sync folder, and how to read a verified, not-found or wrong-page mark. Includes using the verification counts to compare models as an experiment rather than an opinion. |
| [choosing-hardware-for-local-models](guides/choosing-hardware-for-local-models.md) | What makes a machine good at running a model, which is not what the spec sheet leads with: generating a token means reading the whole model out of memory, so bandwidth sets the speed and cores mostly do not. Covers the invisible trap of single-channel memory, why VRAM capacity is a cliff rather than a slope, and the context cache that has to fit on the card alongside the weights - the figure an earlier draft got wrong. Ends by using LACC's own verification counts to decide whether the upgrade paid off. |
| [virtualenv-outside-a-sync-folder](guides/virtualenv-outside-a-sync-folder.md) | Why a `.venv` inside OneDrive or another sync folder breaks `uv`: compiled extensions hollowed out by Files On-Demand, which fail quietly and are the reason that decides it, plus locked files that fail loudly and turn out to have more than one cause. The directory-link fix, the two alternatives, and what each costs. |

## Top-level files

| File | What's in it |
|---|---|
| [CITATION.cff](../CITATION.cff) (repo root) | Citation metadata in Citation File Format, so the project can be cited in published work. GitHub reads it and offers a formatted citation. Its `version` and `date-released` are part of the release checklist. |
| [README.md](../README.md) (repo root) | The public landing page: what LACC is, its design principles, what it is not, and the current status. |
| [docs/README.md](README.md) | The book's table of contents: the numbered chapters with per-version status, the guiding principle, and the ADR index. |
| [CHANGELOG.md](../CHANGELOG.md) (repo root) | Notable changes, newest first. The "what's new since I last looked" skim. |