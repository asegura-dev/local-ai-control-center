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
| [05-assurance.md](05-assurance.md) | Every claim this project makes about itself in PRINCIPLES or a record, paired with what actually holds it up, and a verdict on each: held, held by test, or gap. Covers cybersecurity, traceability, reproducibility, degradation and the human in the loop. Names the one gap found - the ntfy destination arrives through the environment, which ADR-030 forbids - and bounds what it discloses. Ends with how to re-take it. |

## Reading paths

Sixty-four records front to back is a history. These are the threads through them, for
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
→ [046](adr/ADR-046-how-much-to-show-at-once.md)
→ [054](adr/ADR-054-the-same-passage-read-twice.md)
Ends where reading twice does: two entries for one passage, and the measurement that said
not to reach for an approximate algorithm to find them.

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
| 047 | [metadata-the-file-already-carries](adr/ADR-047-metadata-the-file-already-carries.md) | A model asked for a journal invented one twelve times in twenty-four, with an instruction not to. Reports the title, authors, DOI and date a file carries and nothing else; the journal is omitted because the embedded field names the publisher in ten of eleven files, and a DOI lets a reference manager resolve the rest. Defers Crossref, because a DOI sent to a third party says what you are reading. |
| 048 | [a-skill-you-can-write-down](adr/ADR-048-a-skill-you-can-write-down.md) | Five skills were five Python classes, so asking for something new meant a release. A skill can now be declared in a file - but LACC generates the structure from the declared fields, because structure is obeyed where instruction is negotiated. A declaration cannot grant itself capabilities, replace a built-in skill, or define a new kind of check. |
| 049 | [an-anchor-outside-the-file](adr/ADR-049-an-anchor-outside-the-file.md) | Narrows the one gap ADR-043 measured and could not close. A sidecar remembers how long the trail was, so truncation is noticed; because nothing outside the workspace is touched it sits under the same permissions and guards against loss rather than against a person. The notification carries the head digest, which is the only witness not on the machine. |
| 050 | [choosing-what-to-send](adr/ADR-050-choosing-what-to-send.md) | A corpus of 654 quotations exceeds the window it would have to enter, so something must choose. Makes selection a port whose first implementation uses no model and no network, requires every selection to count what it set aside, retrieves only over quotations already checked, and keeps the question the user's words rather than the standing context - which would retrieve the passages that agree with the thesis. |
| 051 | [a-model-per-kind-of-work](adr/ADR-051-a-model-per-kind-of-work.md) | Two models differ in kind rather than quality - the larger is more faithful to what it is handed, the smaller more productive - so one model for everything takes the worse half of both trades. A configuration may name a model per skill. The routing is a rule the user wrote, never a choice a model makes, and the record says the mapping makes the experiment possible without making the hypothesis true. |
| 052 | [a-shape-the-engine-enforces](adr/ADR-052-a-shape-the-engine-enforces.md) | Structure is obeyed and instruction is negotiated, and every skill still asked for its format in prose. A skill may now declare a schema the engine constrains decoding to, generated from the fields it already names. The line parser stays for engines that cannot enforce, it is off by default, and whether constraining costs content quality is to be measured rather than assumed. |
| 053 | [whether-the-reading-follows-from-the-words](adr/ADR-053-whether-the-reading-follows-from-the-words.md) | 548 verified quotations each carry a reading nobody checked, and one of them attributed choline PET/CT's figures to PSMA while passing every mechanical control. A port judges whether a quotation entails its claim - named a judgement rather than a measurement, marking rather than removing, and graded against labels written before it ran. |
| 054 | [the-same-passage-read-twice](adr/ADR-054-the-same-passage-read-twice.md) | A repeat across passes is rarely word for word: it is the same sentence with wider boundaries, which equality misses. Drops a quotation wholly inside another and keeps the longer, exactly and without a threshold. Records the approximate deduplication that was planned and dropped - the corpus has zero near-duplicates across documents, the exact comparison of all 213,531 pairs takes 133 ms, and its most alike non-identical pair differs by one word that is the name of a different drug. |
| 055 | [a-feature-nothing-could-switch-on](adr/ADR-055-a-feature-nothing-could-switch-on.md) | The schema ADR-052 decided shipped unreachable: no flag, no configuration key, no declaration set it, so `output_schema` always returned nothing. Six tests passed by building the plan object the program never builds by hand - the second instance after `ask_corpus`. Names the skills in the configuration, refuses prose a schema by construction, and puts the missing test on the path instead of the type. |
| 056 | [what-arrived-whole](adr/ADR-056-what-arrived-whole.md) | A shaped answer cut at the token cap parsed to nothing - one unclosed brace defeats `json.loads` - so an answer carrying 76 entries was published in v1.4.0 as zero, with advice not to use the feature. Recovers every entry that arrived whole with `raw_decode`, repairing and guessing nothing. Corrected: 32 verified quotations against the line format's 15, at the same fidelity, and the advice was backwards. |
| 057 | [the-prompt-and-the-grammar-disagreed](adr/ADR-057-the-prompt-and-the-grammar-disagreed.md) | The prompt was byte-identical whether or not a schema was sent, so a constrained run was told to write `CLAIM:` lines while the grammar forbade them - an instruction the model could not obey, and very likely why it never stopped. Builds both forms from one description of the fields, and replaces ADR-055's condition: `assess_source` checks its quotations and answers with prose *and* blocks, which a schema would delete. |
| 058 | [controls-that-did-not-cover-what-they-claimed](adr/ADR-058-controls-that-did-not-cover-what-they-claimed.md) | A sweep for the shape found twice in two days. Deduplication covered one of the four paths that produce checked claims, though a single answer repeats passages too - three of nineteen measured. ntfy's docstring promised basic credentials with a tested helper nothing called and no configuration field to reach it. Notes that ADR-055's reachability test would have caught neither: reading did. |
| 059 | [checking-that-a-control-covers-what-it-claims](adr/ADR-059-checking-that-a-control-covers-what-it-claims.md) | Three standing checks, each from a defect that happened: nothing public is defined that only a test reaches, paired controls travel together, and neither answer format loses everything when cut. Building the first found two more - `AskingJudge`, graded and published, was constructed by nothing, and `require` was dead while calling itself the execution path. Wires the judge as `lacc ask --judge`; names the record-to-code inventory and a one-time audit of all 58 records as the phases not yet built. |
| 060 | [the-address-is-not-a-secret](adr/ADR-060-the-address-is-not-a-secret.md) | ADR-030 forbids a `.env` supplying destinations and calls it load-bearing, while the ntfy server URL arrived exactly that way. The address moves into the configuration beside `engine_host`; the token and the topic stay named, the topic because on a public ntfy server it *is* the access control. The old field is kept only to refuse it by name. Found by reading PRINCIPLES a line at a time - no mechanical check asks whether a field is a secret or a destination. |
| 061 | [choosing-by-meaning-as-well-as-by-words](adr/ADR-061-choosing-by-meaning-as-well-as-by-words.md) | An `Embedder` port and a dense retriever behind the `Retriever` ADR-050 built for it, fused with the word ranking by Reciprocal Rank Fusion. Measured: embedding the corpus costs 48 s and searching all 654 vectors costs 137 ms, so the design is a cache and an exhaustive search rather than an index. A Spanish question reaches eight of eight against an English corpus where words reached about three. Names what was not measured. |
| 062 | [the-question-the-terminal-and-the-answer](adr/ADR-062-the-question-the-terminal-and-the-answer.md) | Three defects between a question and its answer, found by one real use: a declared skill's prompt never carried the question, so a request about convolutional networks returned radiation dosimetry; a greater-or-equal sign ended the run while printing, after the answer was produced; and `standard` was right not to keep it. Each minor, together enough to turn a paid-for answer into nothing and report success. |
| 063 | [write-dense-and-prune](adr/ADR-063-write-dense-and-prune.md) | A paragraph of several sentences cannot rest on one quotation, so every draft was under-cited by construction and the judge flagged all of it. Of three ways out, the author chose to write dense and let the judge mark what needs support - and this builds the piece that was missing from it: a flagged reading is shown two passages from what was already sent that might support it, named candidates and never support, with nothing added to the draft. |
| 064 | [what-your-papers-cite](adr/ADR-064-what-your-papers-cite.md) | 2,315 references sit inside 24 papers, and a work several of them cite is one the field treats as load-bearing. Parsed rather than generated - a model invents reference metadata, and the list is already in the file - and with no network at all. Records that folding the section as a whole ran each DOI into the next reference, making every one distinct and the count of shared works zero where it is eight. Names its ceiling: 9% of references carry a recoverable DOI, and only 11 of 23 documents can be compared against. |

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
| [asking-a-corpus-and-writing-from-it](guides/asking-a-corpus-and-writing-from-it.md) | Where the first-time guide stops: turning a folder of papers into paragraphs you can defend. How to ask - name the parts you want rather than the topic, ask in the language you think in, put a premise in if you want it tested - and how to read the four things that come back. The rule the measurements keep pointing at: copy the quotations, rewrite the sentences around them. When it says it does not know, believe it. Ends with what it will not do, including write your argument. |
| [choosing-hardware-for-local-models](guides/choosing-hardware-for-local-models.md) | What makes a machine good at running a model, which is not what the spec sheet leads with: generating a token means reading the whole model out of memory, so bandwidth sets the speed and cores mostly do not. Covers the invisible trap of single-channel memory, why VRAM capacity is a cliff rather than a slope, and the context cache that has to fit on the card alongside the weights - the figure an earlier draft got wrong. Ends by using LACC's own verification counts to decide whether the upgrade paid off. |
| [virtualenv-outside-a-sync-folder](guides/virtualenv-outside-a-sync-folder.md) | Why a `.venv` inside OneDrive or another sync folder breaks `uv`: compiled extensions hollowed out by Files On-Demand, which fail quietly and are the reason that decides it, plus locked files that fail loudly and turn out to have more than one cause. The directory-link fix, the two alternatives, and what each costs. |

## Top-level files

| File | What's in it |
|---|---|
| [CITATION.cff](../CITATION.cff) (repo root) | Citation metadata in Citation File Format, so the project can be cited in published work. GitHub reads it and offers a formatted citation. Its `version` and `date-released` are part of the release checklist. |
| [README.md](../README.md) (repo root) | The public landing page: what LACC is, its design principles, what it is not, and the current status. |
| [docs/README.md](README.md) | The book's table of contents: the numbered chapters with per-version status, the guiding principle, and the ADR index. |
| [CHANGELOG.md](../CHANGELOG.md) (repo root) | Notable changes, newest first. The "what's new since I last looked" skim. |