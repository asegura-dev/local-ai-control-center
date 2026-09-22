# Decision records

Seventy-nine records, in the order they were decided. The number is the identity: it is how
they are cited from docstrings and from the chapters, and there are several hundred such
citations. They are not filed into folders for that reason, and because the records worth
most cross topics - a record about measurement is usually also about grounding and about
honesty, and filing it under one of those would hide it from the other two.

**Reading them front to back is a history, not a reference.** For a thread through them, see
the reading paths in [INDEX.md](../INDEX.md). For a one-line-per-record list, the same file.
This page is the long form: what each record decided, and why.

### 001 - foundational structure

[`ADR-001-foundational-structure.md`](ADR-001-foundational-structure.md)

Core-first dependency direction, the `src/` package layout, flat modules until a split is justified, and the base stack (uv, Pydantic contracts at the boundary, the quality gate of ruff/mypy/pytest). The decision every later one assumes.

### 002 - core configuration and run identity

[`ADR-002-core-configuration-and-run-identity.md`](ADR-002-core-configuration-and-run-identity.md)

The first functional slice: a validated `Config` contract (network off by default, audit level, workspace root) loadable from YAML, and a human-readable time-ordered `run_id`. Adds pydantic and pyyaml.

### 003 - workspaces and boundary enforcement

[`ADR-003-workspaces-and-boundary-enforcement.md`](ADR-003-workspaces-and-boundary-enforcement.md)

Turns `workspace_root` into an enforced boundary: a validated `Workspace` that resolves `..` and symlinks before checking containment (`is_within`, `resolve_within`), with explicit root creation (`ensure`) and a `workspace_from_config` seam.

### 004 - permissions

[`ADR-004-permissions.md`](ADR-004-permissions.md)

The mechanism the project is built around: a closed set of capabilities, all disabled by default, with the configuration acting as a ceiling that no permission can exceed. `check` reports what is missing for previews; `require` raises on the execution path.

### 005 - provider abstraction

[`ADR-005-provider-abstraction.md`](ADR-005-provider-abstraction.md)

An abstract `Provider` port kept deliberately minimal (prompt in, completion out, no generation parameters yet) so the core never depends on an engine, plus a deterministic `MockProvider` that makes every later phase testable offline.

### 006 - audit log

[`ADR-006-audit-log.md`](ADR-006-audit-log.md)

Append-only JSON Lines inside the workspace, contained by its boundary. `audit_level` decides detail with privacy as the default (metadata always, content only under `full`), and `audit_failure_policy` decides whether a failed write stops execution, with each option's consequence stated.

### 007 - execution preview

[`ADR-007-execution-preview.md`](ADR-007-execution-preview.md)

A side-effect-free preview that reports whether an action would be allowed, built on a generic `IntendedAction` so it never depends on skills. Reports every refusal reason at once: missing capabilities and paths escaping the workspace.

### 008 - execution cycle

[`ADR-008-execution-cycle.md`](ADR-008-execution-cycle.md)

The one place that knows the order: `run_action` previews, refuses or asks, executes, and records. Confirmation is supplied as a function so the core holds no interface code. Refused and declined runs are audited, not just completed ones. Home of the first integration tests.

### 009 - skills

[`ADR-009-skills.md`](ADR-009-skills.md)

An abstract `Skill` contract mirroring the provider port: a skill declares its name and capabilities and implements a pure `plan` that describes an action without doing anything. The cycle owns side effects. First skill: read-only file summarization. No registry yet - it arrives with the command line.

### 010 - command line interface

[`ADR-010-command-line-interface.md`](ADR-010-command-line-interface.md)

The `lacc` command (Typer + Rich, confined to the CLI): `run` previews, confirms (defaulting to no), executes, and records; `preview` shows without doing. Skills resolved by a minimal mapping, no registry yet. Notes a deferred decision: where granted permissions come from.

### 011 - permission sourcing

[`ADR-011-permission-sourcing.md`](ADR-011-permission-sourcing.md)

Removes the CLI's hardcoded permission: `grant_for` grants a skill the capabilities it declares, minus any the configuration vetoes. Configuration is a ceiling that removes, not an allowlist that grants; the stricter allowlist model is deferred to when untrusted skills exist.

### 012 - profiler

[`ADR-012-profiler.md`](ADR-012-profiler.md)

A read-only profiler (`lacc profile`) that detects Ollama, lists installed models, reports hardware, and computes a model-fit table by formula - never acting, never claiming usable acceleration it cannot verify. Ollama-specific by choice until a second engine exists. Model choice stays the user's.

### 013 - real provider

[`ADR-013-real-provider.md`](ADR-013-real-provider.md)

A real provider (`OllamaProvider`) implementing the existing port against local Ollama: complete responses (no streaming) with a progress spinner, model from configuration, localhost exempt from `network_access`, and failures translated into actionable messages rather than verified in advance. The CLI chooses mock or Ollama per run.

### 014 - reading file contents

[`ADR-014-reading-file-contents.md`](ADR-014-reading-file-contents.md)

Turns a granted-but-unused `read_files` into a real read: the cycle reads the action's declared targets after confirmation and before the provider, never the skill's pure `plan`. The plan supplies a prompt template with a placeholder; the cycle fills it with what it read. Read failures are translated like provider failures, and contents are audited only under `full`.

### 015 - prompt shaping

[`ADR-015-prompt-shaping.md`](ADR-015-prompt-shaping.md)

Shapes what LACC actually says to the model: a framed task, a configured output language (`output_language`, default English), and the document fenced between fixed markers and declared to be material rather than instruction. `Skill.plan` gains the configuration, amending ADR-009 while keeping the plan pure. Names the fence's limitation instead of overclaiming, and keeps wording in code until external templates earn their own phase.

### 016 - document ingestion

[`ADR-016-document-ingestion.md`](ADR-016-document-ingestion.md)

How a PDF or `.docx` becomes text LACC can read: conversion is an explicit step writing a `.md` into the workspace, not a parse hidden inside a read, so the most fragile link in the chain is the one you can inspect. Ingestion is a command-line action rather than a skill, since it never asks a model; the cycle gains a second entry point with the shared order factored out. A `Converter` port with two implementations from the start, create-only writes, and an empty extraction reported rather than written.

### 017 - hardening limits paths and exit codes

[`ADR-017-hardening-limits-paths-and-exit-codes.md`](ADR-017-hardening-limits-paths-and-exit-codes.md)

What a security review of the existing surface found and decided: a configured ceiling on input size, Windows device names and alternate data streams refused at the boundary, and a refused run exiting non-zero while a declined one does not. Also records what was checked and found sound - no XXE in `.docx`, boundary escapes refused - and what could not be verified on the reviewing machine.

### 018 - a second skill critique

[`ADR-018-a-second-skill-critique.md`](ADR-018-a-second-skill-critique.md)

A read-only `critique_file` skill, and the two questions only a second skill could answer. The document fence is extracted into one function, because a security mechanism copied per skill is free to drift. The skill registry is declined, and the reasoning corrected: the trigger was never the number of skills but the arrival of one nobody in the repository wrote. The prompt refuses to rewrite, to grade, or to invent a weakness where there is none.

### 019 - an honest context ceiling

[`ADR-019-an-honest-context-ceiling.md`](ADR-019-an-honest-context-ceiling.md)

Why a prompt too large is refused rather than truncated, and why the window LACC checks against has to be the one it asked for: measured, the engine loads a 32768-token model with 4096 unless told otherwise, so a ceiling checked against the model's maximum would look like a check while the engine discarded most of the document. Tokens are estimated pessimistically, a reserve is held back for the answer, and an unset window is reported rather than assumed either way.

### 020 - measuring the estimate

[`ADR-020-measuring-the-estimate.md`](ADR-020-measuring-the-estimate.md)

The engine reports how many tokens it actually processed, and LACC was discarding it. Recording it turns the context ceiling from an assertion into something with evidence - measured, the estimate runs 7 to 18 per cent high, in the safe direction. LACC refuses to tune the ratio automatically: a constant that drifts makes the ceiling depend on invisible past runs. Names an underestimated prompt and an answer cut short, both discovered too late to prevent and reported rather than hidden.

### 021 - what a context window costs

[`ADR-021-what-a-context-window-costs.md`](ADR-021-what-a-context-window-costs.md)

`lacc profile` reports what a context window costs at a range of sizes, so the number the user has to choose is informed rather than guessed. Draws the line between arithmetic that travels - the attention cache, computed from each model's own published shape - and a number fitted to one machine, which would be accurate where it was written and quietly wrong elsewhere. States what would make the estimate wrong, and still refuses to set `context_tokens` for anyone.

### 022 - exposure controls

[`ADR-022-exposure-controls.md`](ADR-022-exposure-controls.md)

Separates approximation, which is fine when being wrong costs a retry, from exposure, where the failure is one-way and nothing recovers what has left the machine. The quality gate fails on any non-loopback connection; a workspace inside a git working tree is refused rather than warned about, since it is one `git add -A` from being published; a workspace in a folder that looks synchronised is flagged as a guess that says it is one. Records a dependency audit rather than leaving it to be redone.

### 023 - a trail you can check

[`ADR-023-a-trail-you-can-check.md`](ADR-023-a-trail-you-can-check.md)

Two blind spots in the audit trail, answered by one instrument. A digest records which document was read without keeping a copy of it, so `standard` no longer trades away the ability to check. A hash chain binds each record to the one before it, so an edit becomes locatable rather than silent, following NetGuard's ADR-003 rather than inventing it again. `lacc verify` walks the chain. States plainly that it catches silent tampering and not a deliberate rewrite.

### 024 - detecting truncation by its symptom

[`ADR-024-detecting-truncation-by-its-symptom.md`](ADR-024-detecting-truncation-by-its-symptom.md)

Closes the verification ADR-019 deferred, and closes it differently: rather than asking the engine what window it granted, LACC notices when the token count it reports reaches the window, which is the symptom that actually matters and arrives in a response already received. Records why the comparison must be against the window and not against LACC's own estimate, which runs high by design. Supersedes ADR-019's decision 7.

### 025 - writing and several documents

[`ADR-025-writing-and-several-documents.md`](ADR-025-writing-and-several-documents.md)

Two capabilities in one decision: LACC writes a revision beside the original and never over it, approved against a diff rather than a preview, because the revised text does not exist until the model answers; and every skill can be given several documents, each fenced separately. Keeps the general 'action carries its own effects' refactor unbuilt, since revising is one more step on an existing shape rather than a new one.

### 026 - verified quotations

[`ADR-026-verified-quotations.md`](ADR-026-verified-quotations.md)

The first control that checks a model rather than asking it to behave: claims come with verbatim quotations and pages, and every quotation is looked for in the source before anything is shown. Exact matching rather than fuzzy, because a near-miss is the error that must not pass. Pages are checked against the markers ingestion preserved. States the boundary too - a verified quotation proves the words are there, not that the claim is sound.

### 027 - reaching your own machines

[`ADR-027-reaching-your-own-machines.md`](ADR-027-reaching-your-own-machines.md)

Resolves the contradiction between PRINCIPLES and VISION over what counts as local: not depending on someone else's computer, rather than staying on one machine. Amends PRINCIPLES. The rule that replaces "loopback only" is narrower than "network access" - every destination is named in a file the user wrote, and an environment variable can never widen it. Adds a `Notifier` port with a self-hosted ntfy adapter, refuses third-party messaging on the grounds that when and on what you work is itself information about the research, and keeps the egress guard intact by injecting the transport in tests.

### 028 - the preview names the destination

[`ADR-028-the-preview-names-the-destination.md`](ADR-028-the-preview-names-the-destination.md)

`engine_host` shipped in v0.26.0 and the preview did not follow, so the confirmation screen omitted the one fact that had changed: that the text of a document was about to leave the machine. The preview now names a destination that is not this computer, and only then - absence carries meaning, and a line shown on every run is a line nobody reads. The destination is passed in rather than inferred, because a guess from the action's capabilities would be wrong for conversions, which contact no engine at all.

### 029 - ports and adapters made visible

[`ADR-029-ports-and-adapters-made-visible.md`](ADR-029-ports-and-adapters-made-visible.md)

Five directories whose names mean something: `core` decides and reaches for nothing, `ports` holds the abstract classes, `adapters` implements them, `system` is machine-facing code not behind a port, and the cycle and CLI sit above. Fixes a real inversion - `run_skill` orchestrating from inside the domain - and records that removing it was not enough, because `content_slot` still tied the two together. A test enforces the layering, since a layout in a document is a wish.

### 030 - secrets from a dotenv file

[`ADR-030-secrets-from-a-dotenv-file.md`](ADR-030-secrets-from-a-dotenv-file.md)

ADR-027 said secrets are named rather than written, and did not account for how the value reaches the environment - a step the first person to follow the guide skipped, writing a live token into the configuration instead. A `.env` beside the configuration supplies the variables it names, the real environment still wins, and a `*_env` field must be an upper-case variable name or the configuration is refused. Draws the line at what the value is: `.env` supplies secrets, never destinations or permissions, so no environment can redirect documents.

### 031 - the page is found not asked for

[`ADR-031-the-page-is-found-not-asked-for.md`](ADR-031-the-page-is-found-not-asked-for.md)

The first real run showed page attribution failing on its own - page 4 for a sentence on page 1, with the quotation itself correct. LACC already locates the quotation while verifying it, so it stops asking a model a question it can answer itself. Removes the `wrong page` verdict by removing the wrong page, keeps the model's answer in the audit as a fidelity signal, and deliberately leaves the prompt untouched so that extraction quality stays measurable while it is under investigation.

### 032 - measuring is not running

[`ADR-032-measuring-is-not-running.md`](ADR-032-measuring-is-not-running.md)

Repeating a run five times on one paper gave verification rates from 25% to 85%, so single-run comparisons measure nothing and the prompt work that comes next cannot be evaluated without repeats. Adds `lacc measure` as a separate command rather than a flag, so `run` keeps its one-preview-one-action meaning; refuses any skill that writes, since repetition would multiply effects; states the count in the confirmation rather than hiding a multiplier; and reports the spread instead of an average.

### 033 - the skill declares its temperature

[`ADR-033-the-skill-declares-its-temperature.md`](ADR-033-the-skill-declares-its-temperature.md)

LACC had never sent a temperature, so the engine sampled at 0.8 on work that copies text verbatim - and made the audit's completion hashes irreproducible, which for a citable record is the more serious half. The skill declares it, the default is zero, and there is no configuration override because temperature is a property of the task rather than a preference. Determinism is the point, not accuracy: it is the prerequisite for measuring anything else.

### 034 - showing what the document does say

[`ADR-034-showing-what-the-document-does-say.md`](ADR-034-showing-what-the-document-does-say.md)

A quotation reported as not found now comes with the closest text that is in the document, without softening the verdict. Written for the worst fabrication - a real sentence with the figure changed - and it immediately found something else: two of three "fabrications" on a real paper were LACC's own ingestion preserving words the typesetter had broken across lines. Rejoining them took that paper from 57% to 85%.

### 035 - what counts as the same text

[`ADR-035-what-counts-as-the-same-text.md`](ADR-035-what-counts-as-the-same-text.md)

Refines ADR-026's matching rule with a line it lacked: a difference a reader cannot see is representation, one they can see is content, and normalisation removes only the first. Case, whitespace, hyphens between letters and typographic look-alikes all fold; a changed word or number never does. Written after an audit found that three of seven "fabrications" from a real paper were LACC's own ingestion and normalisation - the check meant to catch a model deceiving you had been reporting this project's defects as the model's dishonesty for three releases.

### 036 - dropping the furniture of a page

[`ADR-036-dropping-the-furniture-of-a-page.md`](ADR-036-dropping-the-furniture-of-a-page.md)

The last reason a faithful quotation failed: a journal's running header extracted inside a sentence. Never literally identical, because the page number is glued to it - so a line whose shape repeats across half a document's pages is furniture and is dropped. Ingestion therefore edits rather than only transcribing, which is stated plainly, and the count is printed and audited because a heuristic that quietly deletes text from a document the user keeps is the wrong shape for this project.

### 037 - the instruction goes after the document

[`ADR-037-the-instruction-goes-after-the-document.md`](ADR-037-the-instruction-goes-after-the-document.md)

Turns the audit on what LACC asks for rather than what it does with the answer. Every prompt put its instructions thousands of tokens before the model started writing, which is why extraction stopped early with nothing truncated; restating the format after the document gives about three times as many verified claims, deterministically. Also records the variant that did not work, and that the first run after a model loads is a contaminant `lacc measure` now discards.

### 038 - a document that pretends to be an instruction

[`ADR-038-a-document-that-pretends-to-be-an-instruction.md`](ADR-038-a-document-that-pretends-to-be-an-instruction.md)

Corrects a security claim the code had made for twenty-three releases. A document carrying the closing marker ended its own fence, and a real model obeyed the instructions that followed - tested, not reasoned about. The markers are now removed from content, which is a control; instruction-shaped text is detected and reported, which is not. States the limit plainly: LACC cannot stop a model being manipulated by what it reads, and the grounding check is no defence, because planted text really is in the document.

### 039 - a library is read one document at a time

[`ADR-039-a-library-is-read-one-document-at-a-time.md`](ADR-039-a-library-is-read-one-document-at-a-time.md)

Thirty papers are twelve times the budget of the largest window this hardware can run, and no model size changes that because parameters do not buy context. `lacc collect` traverses a bibliography one document at a time. The stronger argument is correctness: several documents in one prompt let a model attribute a quotation to the wrong paper and have the check verify it, while one document per run makes the source a fact about which run produced it.

### 040 - text a reader cannot see

[`ADR-040-text-a-reader-cannot-see.md`](ADR-040-text-a-reader-cannot-see.md)

Closes the hole ADR-038 named: a quotation of text hidden in a PDF verifies, because the text really is in the document. Four hiding techniques were tested and all four reached the model; three are now detected and the fourth is documented as not detected. Reports a proportion rather than a verdict, because rendering mode 3 is also what a scan's OCR layer uses - a rule calling it an attack would be wrong on every scanned paper.

### 041 - standing context and what it must not touch

[`ADR-041-standing-context-and-what-it-must-not-touch.md`](ADR-041-standing-context-and-what-it-must-not-touch.md)

A context file the user writes, used only by skills that declare it. The load-bearing half is which skill must not: telling a model what a thesis argues before asking what a paper asserts invites it to find that argument, and the grounding check cannot catch it because the quotations would all be real. Adds `assess_source`, separate from `summarize_file` because a reading scoped to a thesis is not a summary of the paper.

### 042 - what unverified was actually counting

[`ADR-042-what-unverified-was-actually-counting.md`](ADR-042-what-unverified-was-actually-counting.md)

A check has three outcomes and LACC reported two, so quotations that were in the document were tallied as failures. Separates whether a quotation is real from whether LACC could place it. **Its corpus figures were wrong and are corrected in the ADR (48 of 237 absent, not zero).** Separates whether a quotation is real from whether LACC could place it, and locates passages running across a page break. The fourth time in one session that a limit of this project was reported as the model's dishonesty.

### 043 - what the chain does not catch

[`ADR-043-what-the-chain-does-not-catch.md`](ADR-043-what-the-chain-does-not-catch.md)

Seven safety claims tested against running code rather than read. Six hold, including the workspace boundary against Windows junctions. One does not: records removed from the end of the audit trail are undetectable, and it is the cheapest attack of the set - ADR-023 named the sophisticated one and left this unstated. Nothing in the file can catch it, so the message says so and the trail reports when it starts and ends.

### 044 - an answer we already know

[`ADR-044-an-answer-we-already-know.md`](ADR-044-an-answer-we-already-know.md)

Every rate this project published was measured where the correct answer was unknown - the condition that produced six mis-measurements, all flattering. Decides a fixture corpus whose ground truth the project controls, asserted exactly in both directions: flagging a real quotation fails as hard as missing a fake.

### 045 - a document read in passes

[`ADR-045-a-document-read-in-passes.md`](ADR-045-a-document-read-in-passes.md)

Sets the scope of v2 at one thing: a document too large for the window is read in passes over its pages, overlapping by one so a passage crossing a break stays whole. A pass is what the model sees; the whole document stays what a quotation is checked against. Conversation across turns and letting the model choose what to do next are ruled out, the second because it contradicts PRINCIPLES.


### 046 - how much to show at once

[`ADR-046-how-much-to-show-at-once.md`](ADR-046-how-much-to-show-at-once.md)

How much of a document to show at once becomes a setting rather than a consequence of what fits. Passes of a stated size gave 4.6 times the verified quotations for twice the time, and the confound - seventeen calls against three - is published beside the figure rather than after someone asks.

### 047 - metadata the file already carries

[`ADR-047-metadata-the-file-already-carries.md`](ADR-047-metadata-the-file-already-carries.md)

Title, authors, DOI and date are read from the document's own XMP, with no network and no model, and a field that is absent is reported as absent. The journal is not reported at all: with a correct DOI a reference manager resolves it against a record, and LACC had a DOI for eleven of twenty-three documents where the model had one for none - having invented twelve.

### 048 - a skill you can write down

[`ADR-048-a-skill-you-can-write-down.md`](ADR-048-a-skill-you-can-write-down.md)

A skill can be declared in a file, and LACC generates the structure from the fields it declares rather than handing the author a blank prompt - because the part that works is the part LACC controls. A declaration cannot grant itself a capability: the configuration stays a ceiling that only removes.

### 049 - an anchor outside the file

[`ADR-049-an-anchor-outside-the-file.md`](ADR-049-an-anchor-outside-the-file.md)

A sidecar records how many records the trail holds and the digest of the last one, and the notification carries both to a machine the tamperer does not control. Described as a guard against loss rather than against an attacker, because that is what it is.

### 050 - choosing what to send

[`ADR-050-choosing-what-to-send.md`](ADR-050-choosing-what-to-send.md)

Selection becomes a port, whose first implementation uses no model and no network. Whatever is not sent is counted and reported: a selection that hides its discards turns a partial answer into a confident one, which is the failure mode behind every wrong figure in this project's own record.

### 051 - a model per kind of work

[`ADR-051-a-model-per-kind-of-work.md`](ADR-051-a-model-per-kind-of-work.md)

A configuration may name a model per skill. The routing is a table the user wrote, never a choice the model makes - the same line ADR-045 drew when it ruled out letting a model choose what to do next.

### 052 - a shape the engine enforces

[`ADR-052-a-shape-the-engine-enforces.md`](ADR-052-a-shape-the-engine-enforces.md)

A skill may declare a schema and the engine enforces it, generated from the fields the skill already names. The line parser stays, because enforcement must improve a path that works rather than replace it with one that only works on one engine.

### 053 - whether the reading follows from the words

[`ADR-053-whether-the-reading-follows-from-the-words.md`](ADR-053-whether-the-reading-follows-from-the-words.md)

The first check here that is a judgement rather than a measurement, and it says so: a port asks whether a quotation entails the reading given of it. Graded against eight pairs labelled first, it got the three-way label right 6 of 8 and the binary "should a person look at this" right 8 of 8 - so reports lead with the binary. It marks and never removes.

### 054 - the same passage read twice

[`ADR-054-the-same-passage-read-twice.md`](ADR-054-the-same-passage-read-twice.md)

A quotation wholly inside another is the same passage read twice, and the longer one is kept - exact, unthresholded, no new module. Records the approximate deduplication that was planned and dropped: the corpus has zero near-duplicates between documents, the whole exact comparison takes 133 ms, and its most alike non-identical pair differs by one word that happens to be the name of a different drug.

### 055 - a feature nothing could switch on

[`ADR-055-a-feature-nothing-could-switch-on.md`](ADR-055-a-feature-nothing-could-switch-on.md)

The schema ADR-052 decided was built, released and cited, and nothing in the program could set it: no flag, no configuration key, no declaration. Six tests passed because they built the plan object directly, which the program never does - the second instance of that shape after `ask_corpus`. Adds the configuration key, ties the schema to block-shaped output by construction, and records that coverage of a type is not coverage of a path.

### 056 - what arrived whole

[`ADR-056-what-arrived-whole.md`](ADR-056-what-arrived-whole.md)

Corrects a figure v1.4.0 published hours earlier. A shaped answer cut at the token cap parsed to nothing, because one unclosed brace defeats `json.loads` - so an answer carrying seventy-six entries was published as zero, with advice not to use the feature. Entries that arrived whole are now recovered with `raw_decode`, nothing repaired and nothing guessed, and the corrected figures give 32 verified quotations against the line format's 15 at the same fidelity. Records that the zero was the instrument, and that "content quality did not degrade" came from reading one entry.

### 057 - the prompt and the grammar disagreed

[`ADR-057-the-prompt-and-the-grammar-disagreed.md`](ADR-057-the-prompt-and-the-grammar-disagreed.md)

The prompt was byte-identical whether or not a schema was sent, so a constrained run was instructed to write `CLAIM:` lines by a prompt while the grammar forbade every character of them - very likely why it never stopped. Both forms now come from one description of the fields. Also replaces ADR-055's test for whether a shape may be enforced: `assess_source` verifies its quotations and answers with prose *and* blocks, and a schema would delete the prose.

### 058 - controls that did not cover what they claimed

[`ADR-058-controls-that-did-not-cover-what-they-claimed.md`](ADR-058-controls-that-did-not-cover-what-they-claimed.md)

Two findings from sweeping for the shape ADR-055 and ADR-056 showed twice in two days. Deduplication was applied on one of the four paths that produce checked claims - the one ADR-045 happened to be thinking about - while a single answer repeats passages too, three of nineteen on the measured paper. And ntfy's docstring promised basic credentials whose helper was tested, called by nothing, and had no configuration field. Records that the reachability test from ADR-055 would have caught neither.

### 059 - checking that a control covers what it claims

[`ADR-059-checking-that-a-control-covers-what-it-claims.md`](ADR-059-checking-that-a-control-covers-what-it-claims.md)

Three standing checks, each derived from a defect that happened: nothing public is defined that only a test reaches, controls that must travel together do, and neither answer format loses everything when it is cut. Building the first immediately found two more - `AskingJudge`, the judge of readings with a published grade, was constructed by nothing at all, and `require` was dead while its docstring called itself the execution path. The judge is wired as `lacc ask --judge`. Names the inventory and the one-time audit as phases two and three, and explains why the ranking that was tried is a reading queue rather than a detector.


### 060 - the address is not a secret

[`ADR-060-the-address-is-not-a-secret.md`](ADR-060-the-address-is-not-a-secret.md)

ADR-030 says a `.env` supplies secrets and never destinations, and calls it load-bearing - while the ntfy server URL arrived through `server_url_env`, by the one route that record forbids. Splits the field by what each part is: the address moves into the configuration beside `engine_host`, the token stays named, and the topic stays named too because on a public ntfy server the topic *is* the access control. The old field is kept only to refuse it with a message that says what replaces it. Found by reading PRINCIPLES a line at a time, because no mechanical check asks whether a field is a secret or a destination.


### 061 - choosing by meaning as well as by words

[`ADR-061-choosing-by-meaning-as-well-as-by-words.md`](ADR-061-choosing-by-meaning-as-well-as-by-words.md)

An `Embedder` port and a dense retriever behind the `Retriever` port ADR-050 already built for this, fused with the word ranking by Reciprocal Rank Fusion - a published constant rather than a weight to tune. Measured on the real corpus: embedding costs 48 seconds and searching all 654 vectors costs 137 milliseconds, so the design is a cache and an exhaustive search rather than an index. A question in Spanish against the English corpus reaches eight relevant passages of the first eight where words reached about three. Says plainly what was not measured, and that a 32k budget admits a third of the corpus whatever the ranking says.

### 062 - the question, the terminal, and the answer that was already paid for

[`ADR-062-the-question-the-terminal-and-the-answer.md`](ADR-062-the-question-the-terminal-and-the-answer.md)

Three defects between a question and its answer, found by one real use. A declared skill's prompt never carried the question, so a request for a summary of convolutional networks returned one about radiation dosimetry. A greater-or-equal sign raised `UnicodeEncodeError` while printing and ended the run after the answer had been produced. And the trail could not recover it, because `standard` is right not to record content. Each is minor; together they turn a paid-for answer into nothing and report success.


### 063 - write dense, and prune

[`ADR-063-write-dense-and-prune.md`](ADR-063-write-dense-and-prune.md)

`draft` asked for prose of three to six sentences resting on one quotation, which cannot hold them, so every paragraph was under-cited by construction and the judge flagged all of it. Three ways out were put to the author and the third was chosen: write dense, and let the judge mark what needs support. Builds the part that was missing from it - a flagged reading is shown two passages from what was already sent that might support it, ranked against the reading's own words, named candidates and never support. The skill stops promising what it cannot deliver.


### 064 - what your papers cite

[`ADR-064-what-your-papers-cite.md`](ADR-064-what-your-papers-cite.md)

A bibliography of 24 papers is also 2,315 references, and a work several of them cite is one the field treats as load-bearing. Parsed from the list each document already carries - no model, because reference metadata is exactly what a model invents, and no network. Records the defect the measurement found: folding the section as a whole ran each DOI into the next reference, so every DOI came out distinct and the count of shared works was zero where the answer is eight. Names its own ceiling at nine per cent, since most bibliographies print no DOI, and reports "not among the ones identifiable by DOI" rather than "not held" because only 11 of 23 documents carry one.


### 065 - two writers, one round trip

[`ADR-065-two-writers-one-round-trip.md`](ADR-065-two-writers-one-round-trip.md)

`corpus.py` answers its own unease about re-parsing generated prose with a round trip - and there were two writers, covered by one. The assembler put the paraphrase where the reader expects the standing, so it was filed as a verdict, and a recorded verdict is correctly never carried forward. Assembling a corpus twice therefore stripped the meaning from every quotation in it while reporting the same counts it always had. Found because a merged file was 35 KB smaller with 178 more quotations. One format now, written by both, read through both, and tested twice - because the first pass looked right.


### 066 - a view contains no logic

[`ADR-066-a-view-contains-no-logic.md`](ADR-066-a-view-contains-no-logic.md)

Every layering test followed dependencies inward and none asked whether logic had leaked outward, which is what ADR-065 cost: both writers of the corpus format in `cli.py`, the reader in `core`, free to drift apart with the suite green. "Logic" has no syntax, so the rule is stated by its opposite - a function in a view that never touches the presentation, directly or through anything it calls, is not part of the view. It named twelve functions and the first two were the two writers. A vertical slice per capability over a hexagon that stays horizontal, because counting refused the other half: nine of fourteen core modules are genuinely shared and cutting them would invent boundaries the code does not have.


### 067 - metadata from a registry, not from a model

[`ADR-067-metadata-from-a-registry.md`](ADR-067-metadata-from-a-registry.md)

Asked for a journal name with an instruction not to guess, a 14B invented twelve of twenty-four (ADR-047) - which is the last thing standing between a complete corpus and a bibliography that can be handed in. `lacc resolve` asks whoever assigns DOIs instead. The first destination in this project that is not the user's own machine, so the record spends more length on what leaves than on what arrives: a DOI and nothing else, only with `network_access` **and** `registry_url` both on, only after a preview that says how many and where, and never twice for the same work. No contact address is sent although it would buy a faster queue, because that address is the user's. No abstract is read although the registry returns one, because it is the one long free-text field and a bibliography does not need it - the vector is removed rather than sanitised.


### 068 - the check, turned around

[`ADR-068-the-check-turned-around.md`](ADR-068-the-check-turned-around.md)

Everything here verifies text a model produced. `lacc review` asks the same question of a draft a person wrote: is there anything in my own corpus that holds this paragraph up? Nothing new is invented - the corpus reader, the ranking and the judge all exist and all point the other way. It reads and reports, never rewrites, because a tool that told you a sentence was unsupported and then rewrote it would hand you a fluent unsupported sentence. The unit is the paragraph, which is how scientific prose carries its references. **Uncovered is not false**, and the wording says so wherever it appears. Graded on five paragraphs whose answers were written down first, it caught both planted errors - and the one disagreement was the prediction's fault: the paragraph had a causal clause no quotation supports, and its author had not noticed writing it.


### 069 - a window that reads

[`ADR-069-a-window-that-reads.md`](ADR-069-a-window-that-reads.md)

Most of what LACC produces belongs in a terminal. A review does not: it is a document with a second document painted over it. CustomTkinter, in a window of its own, with **nothing listening** - Tk ships with Python, the window talks to Python because it is Python, and the material this project protects is private research. It reads and runs nothing: a review takes minutes and an engine, and a window that ran one would need threads, progress, cancellation and a way to report an engine that went away, all in a view, on day one. So a review is read from the findings file the CLI writes beside its report. Four sections, all reading what is already on disk. Choosing a configuration changes which is read, never what is in it. Themes are data in the window's own file, because a colour has no business in a frozen `Config`. **ADR-066 bound this window before its first line existed**, which was the point of emptying that exception list first.


### 070 - the records become readable

[`ADR-070-the-records-become-readable.md`](ADR-070-the-records-become-readable.md)

Sixty-nine records, six chapters, the guides, and a book of eight chapters in `.gitignore` that nobody has read - the thing this project has most of was the one thing the tool could not show. A section in the window, reading the Markdown from the repository, grouped the way the folders group it. The folder is **found, never configured**: a setting naming where to read from would be a setting that could name anywhere, so it walks up from the package to see whether a repository is around it, and says so plainly when there is not. Markdown becomes blocks in a slice and the window gives blocks a font, because what a line *is* is a decision (ADR-066). Inline emphasis is flattened and heading structure kept, since structure is what makes a long record navigable. The parser is tested against every record in the repository rather than a fixture.


### 071 - launchers, and their digests

[`ADR-071-launchers-and-their-digests.md`](ADR-071-launchers-and-their-digests.md)

Three `.bat` files in `scripts/`: one opens the window, one starts the engine with an 8-bit KV cache - the four gigabytes of VRAM that had been a pending task in the log for weeks - and one checks the other two against `SHA256SUMS.txt`. The decision is not the launchers, it is that **the test suite enforces the digests**: a checksum nobody checks is decoration, so the gate fails when a script changes without its digest changing in the same commit. What that proves is stated plainly rather than overclaimed - the files are the ones the digests were taken over, not that the digests are honest, since whoever could edit a script could edit the list beside it. Both are in Git, which is what makes it worth something. Git is told not to rewrite them, because a digest over a file whose line endings change on the next machine verifies nothing. The launchers are also tested for what they must **not** do: no download, and loopback by default.

### 072 - the commands describe themselves

[`ADR-072-the-commands-describe-themselves.md`](ADR-072-the-commands-describe-themselves.md)

The window could show a workspace, its corpora and this project's records, but not what LACC can do. The list is **derived from the application, never written down twice** - a hand-written copy would be a second writer of the same thing, which is precisely what cost ADR-065 a corpus. `commands_of` reads the registered commands, the name Typer gives each, its docstring and its parameters; a command added appears, one renamed changes, one without a docstring fails a test. It does not import the CLI: the application is passed in, so a view never imports another view. Typer's naming is copied exactly including where it looks wrong, because the point is what the CLI answers to rather than what it ought to.


### 073 - one engine for every Markdown

[`ADR-073-one-engine-for-every-markdown.md`](ADR-073-one-engine-for-every-markdown.md)

The Markdown engine built for this project's records was one import away from a workspace full of Markdown the window could only count. A corpus, a bibliography, a review report, a paper and a decision record are the same format, so they are read the same way. What LACC **wrote** is listed apart from what the user brought, recognised by the heading its writer put at the top rather than by filename. A long document is cut at 250 blocks and says by how much, because a widget per block over a 284 KB corpus freezes the window - and the cut lives in the slice, since how many and whether-at-all are decisions. Adding it found a defect nobody had reported: selecting a document re-read the entire workspace, corpus included, on every click.


### 074 - what it is about to ask

[`ADR-074-what-it-is-about-to-ask.md`](ADR-074-what-it-is-about-to-ask.md)

Almost every measured finding here is about the distance between what somebody meant to ask and what was sent: an instruction not to guess that produced twelve invented journal names, a schema that delivered the shape and lost the answer, a declared skill whose prompt never carried the question. Each was invisible for exactly as long as nobody looked at the prompt - and the prompt has always been printable, because a plan is pure by design (ADR-014). A section that shows, for every skill, the instruction, the capabilities it would ask you to allow, what it checks, and how long the asking is before any document is added. The document's place is **shown rather than left as a marker**, because the one important fact about a prompt is that the document arrives inside it, surrounded by instructions. A skill that cannot be planned says why in place of its template.


### 075 - a section is a piece

[`ADR-075-a-section-is-a-piece.md`](ADR-075-a-section-is-a-piece.md)

The window reached eight sections in a day, and adding one meant editing **four places** - the menu, the router, the selection handler and a pair of methods. Get three of the four right and the section appears in the menu and does nothing at all: no error, no empty panel, just a button that does not respond. `cli.py` reached 2,610 lines by exactly this route. So a section is now **declared rather than wired**: a name, a listing and what to show, and the window iterates over a tuple of them knowing nothing else. Grouped by what they read rather than one file each, because a reader looking for "how is a corpus shown" should find it beside "how a review is shown". Measured: `window.py` went 763 lines and 28 methods to 330 lines and 17 functions, and the places to edit went from four to one. The refactor was accepted because that risk was countable - this project's roadmap records six consecutive releases of defensible refactors that advanced nothing.


### 076 - the sections a document numbers

[`ADR-076-the-sections-a-document-numbers.md`](ADR-076-the-sections-a-document-numbers.md)

A PDF does not say what a heading is - measured, seven of eight papers carry none at all - but where an author numbered their sections, the numbering survives extraction. **The record is the measurement**: four rules were tried and the count went 16, 18, 10, **6 of 24**. The second *rose*, and was the worst: adding consecutive numbering counted author affiliations and bibliographies, because every numbered list is consecutive. The third required the dot and looked clean until it was run on the real guideline, which numbers its references `10. Haas, G.P` **with the dot**. Two structural conditions more - sections appear in order, and a section has a body - and the guideline came out as its nine real sections and nothing else. Detected, never written into the document: hundreds of quotations are checked against these files as they are. `lacc sections --take 5` pulled 42,149 tokens out of 348,276 without anybody cutting the file up.


### 077 - a line along the bottom

[`ADR-077-a-line-along-the-bottom.md`](ADR-077-a-line-along-the-bottom.md)

A bar with what is on disk on the left and what the configuration may reach on the right. The only interesting decision is when **not** to act: **the engine is not asked when the window opens**, only when somebody presses `check`. A window that pings on opening is a window that talks to the network because somebody looked at it, and reaching anywhere here is deliberate. `not checked` and `unreachable` are different words, because the engine may be perfectly fine and simply never have been asked. The check is passed in as a function rather than performed, so a view never touches an adapter.


### 078 - what a digest is for

[`ADR-078-what-a-digest-is-for.md`](ADR-078-what-a-digest-is-for.md)

Written in answer to a good question - if the launchers carry SHA-256 sums, should the skills and the code? - and most of the answer is **no**. The launchers are a special case in two ways: they run outside Git, and outside the audit trail. Neither is true of anything else. Git already hashes the whole tree and says when it changed; the trail already records `prompt_sha256`, `completion_sha256` and the digest of every file read and written, in a chain `lacc verify` walks. A `SHA256SUMS` of the Python would restate that less well and be one more file to go out of step. **But one gap was real**: `prompt_sha256` covers the template and the document together, so changing a skill's wording and reading a different file were indistinguishable. `template_sha256` is recorded beside it now, which is what lets the trail answer *did the instruction change between these runs*. And a third-party answer is bounded at two megabytes, because a timeout stops a slow answer and not an endless one.


### 079 - opening a document at the right part

[`ADR-079-opening-a-document-at-the-right-part.md`](ADR-079-opening-a-document-at-the-right-part.md)

Nothing new was built: `sections` found 154 parts of a guideline and `Retriever` has ranked passages against a question since ADR-061, so they were pointed at each other. The part that makes it work is that **a section is represented by its title *and* the opening of its body** - ranking titles alone would be ranking fragments like `Imag` and `N-st`, and would fail exactly on the documents that need it most, because the worst extraction is in the largest files. A summary stops at the next section so a short one cannot borrow its neighbour's words. Every section is returned in order, not the best few: which to read is the reader's decision. Measured on the real guideline, the section that answers *nodal staging* comes fourth of 154 and a related one second - which is "154 down to a handful", not "it finds the section", and the record says the weaker thing.
