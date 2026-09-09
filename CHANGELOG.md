# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.18.0] - 2026-09-09

### Added
- `context_tokens` in the configuration: the window to run the model with. LACC asks the
  engine for exactly this window, estimates the size of each assembled prompt, and refuses
  one that will not fit rather than letting the engine truncate it.
- `lacc profile` reports the context window each installed model supports, and says that
  the engine loads with a smaller default unless it is asked otherwise.
- New audit events: `prompt_measured`, recording the estimated size and requested window
  of every prompt, and `prompt_too_large` when a run is refused for exceeding the ceiling.

### Changed
- `OllamaProvider` sends `num_ctx` when a window is configured. The provider port is
  unchanged: the window is given at construction, where the model name already lives,
  because it describes how the engine is set up for a run rather than what is being asked
  of it. Generation parameters stay deferred, as ADR-013 left them.

### Security
- **A prompt too large for the model is refused, not truncated.** An engine given more
  than fits does not fail: Ollama drops what does not fit and answers from the rest, so a
  run that read the last third of a chapter returns a confident summary of the chapter,
  indistinguishable from one that read all of it.
- **The window LACC checks against is the window LACC asked for.** This was found by
  measuring rather than by reading documentation: against Ollama 0.30.7, `qwen2.5:3b`
  supports 32768 tokens and the engine loads it with 4096 unless told otherwise - a factor
  of eight, silently. An earlier draft of ADR-019 would have had the profiler report
  32768, the user configure 32768, and LACC conclude that a 20000-token prompt had room to
  spare while the engine discarded seven eighths of it. A ceiling checked against a window
  nobody is using is worse than no ceiling, because it looks like a check.

### Notes
- Token counts are estimated from characters at three per token, and are called estimates
  everywhere they appear. Three is deliberately low: it overestimates tokens, so LACC
  refuses slightly early. A prompt refused that would have fitted costs one line of
  configuration; a prompt truncated that should have been refused produces a plausible
  wrong answer nobody has reason to check.
- A quarter of the window, and never less than 512 tokens, is held back for the answer.
- With `context_tokens` unset, runs proceed and say so: the engine will use its own default
  and may truncate without either side noticing. The gap is real, and the notice is what
  keeps it from being invisible.
- Requests for 2048, 8192 and 32768 tokens were each honoured exactly. What an engine does
  when it cannot allocate the window it was asked for was not observed, and is not claimed.


## [0.17.0] - 2026-09-08

### Added
- `lacc run critique_file <path>`: a second read-only skill. It reads a draft and reports
  specific, locatable problems - claims made without support, gaps in an argument,
  passages that contradict each other, terms used before they are defined, conclusions
  that do not follow. The other direction from summarizing: not what a document says, but
  what it fails to establish.
- The critique prompt refuses three things on purpose. It does not rewrite, because
  producing replacement text is writing, a phase with its own safety requirement, and a
  read-only run must not return text that looks authoritative. It does not grade or open
  with what the draft does well, because a critique that hedges is one whose findings have
  to be looked for. And it is told to report nothing rather than invent something: a model
  asked for problems will supply problems, and an invented weakness costs more to check
  than a real one saves.

### Changed
- The document fence - the markers plus the instruction that what sits between them is
  material rather than a request - is now written in one place and used by both skills.
  It is a security mechanism, and two copies of one are two things free to drift with
  nothing to say which is right. What is shared stops there: each skill still writes its
  own framing and task.

### Notes
- **No skill registry, and the reason is recorded so the question is not reopened by
  counting skills.** The roadmap said a third skill would give the registry deferred in
  ADR-010 enough cases to take shape; that reasoning was wrong and ADR-018 corrects it.
  The CLI's mapping already answers what a registry is for. What a formal one adds is
  discovery - skills arriving from outside this source tree - and that is a question about
  trust, not about count: a skill LACC did not write is one whose declared capabilities
  are a claim rather than a fact.
- A critique from a small local model will be shallow. Judging whether an argument holds
  is outside what a three-billion-parameter model does well. The prompt is shaped as well
  as it can be; the rest is the engine, and this is the clearest argument yet for the
  stronger machine the roadmap already records.


## [0.16.0] - 2026-09-08

### Added
- `max_input_bytes` in the configuration, 32 MiB by default: the largest file LACC will
  read or convert. Checked before the file is opened, so an oversized document is refused
  with its name, its size and the limit, rather than discovered as a `MemoryError` from
  somewhere deep in the process. The ceiling is about this machine and not about the
  model - whether the text then fits the model's context is a different question, with a
  different answer, in a later phase.

### Changed
- **A refused run now exits 1.** It exited 0, so a script checking the exit code was told
  the work had succeeded when nothing ran. A declined run still exits 0: nothing failed
  there - the human was asked and said no, which is the system working, and conflating
  the two would make the exit code useless for telling them apart.

### Security
- The workspace refuses three path shapes that stayed inside the boundary while breaking
  the other promise it makes: that a path names a file you can find again.
  - **Windows device names** (`NUL`, `CON`, `COM1`, and the rest). Windows resolves them
    to devices whatever directory precedes them and whatever extension follows, so a
    converted document written to `NUL` is discarded while the run reports success.
  - **Alternate data streams** (`notes.md:hidden`), which no directory listing shows. What
    LACC does is meant to be visible; a write that cannot be seen contradicts that.
  - **Names ending in a dot or a space**, which Windows strips before resolving, so the
    file written is not the file that was named.

  None of the three escapes the workspace. They are refused because containment was never
  the only thing the boundary was for.


## [0.15.0] - 2026-09-08

### Added
- `lacc ingest <source> [destination]`: converts a PDF or `.docx` inside the workspace
  into a `.md` file inside the workspace, after preview and confirmation, recorded in the
  audit trail. Sources for real work arrive as PDF and Word while LACC reads only UTF-8
  text, so until now the material it exists to work on was unreadable.
- A `Converter` port with two implementations from the start - PDF via `pypdf`, `.docx`
  via `python-docx` - selected by file suffix. Conversion is an explicit step producing a
  file the user can open and correct, rather than a parse hidden inside a read.
- What is produced is extracted text, and is not called more than that: page boundaries
  are kept as `<!-- page N -->` and Word heading styles become headings, because both are
  recovered rather than invented, while tables are flattened to rows instead of dressed as
  Markdown tables that merged cells would break.
- A second entry point in the cycle, `run_conversion`, for a run that produces a file
  instead of an answer and never reaches a provider. The sequence every run shares -
  preview, refuse or ask, record - is factored into one place rather than written twice.
- New audit events `document_converted` and `ingestion_failed`.
- `permissions.grant`: the configuration-ceiling rule in one place, so an action that is
  not a skill can declare its capabilities without a second copy of the rule. `grant_for`
  becomes a thin reading of it.

### Security
- **A non-loopback engine address is refused.** `OLLAMA_HOST` was honoured without being
  checked, so a value set by an installer, a script or a mistake was enough to send
  documents to another machine while looking exactly like a normal run. PRINCIPLES puts a
  non-loopback host out of scope; until now that was a comment rather than a check. The
  profiler carried its own copy of the same code, so both paths were open - there is one
  now, and it refuses with a message explaining that a remote engine is a recorded
  direction which needs its own decision record before it exists.
- **A conversion must declare both of its effects before either happens.** The preview
  checks only the capabilities an action declares, so a conversion now requires
  `read_files` and `write_files` together and refuses an action that declares less. An
  undeclared effect is one nobody checked, and one the human was never shown before
  confirming.
- Ingestion never overwrites: the destination is opened for exclusive creation, so a `.md`
  the user already corrected by hand cannot be replaced by a fresh extraction.
- A `.docx` is untrusted XML. python-docx does not resolve external entities - verified
  against a document built to try - and a test pins that against a future change of
  parser.
- The trail records which document was converted, by which converter, to where, and how
  many characters resulted. Never the text: it is already a file the record names.

### Notes
- A scanned PDF with no text layer is reported as such, and nothing is written. Producing
  an empty file would turn a legible failure into a silent one. OCR is out of scope.
- PyMuPDF is deliberately not used: it is the most capable option and it is AGPL, which
  an MIT-licensed project cannot take on.
- Input still has no size ceiling, Windows device names and alternate data streams still
  pass the workspace boundary, and a refused run still exits 0. All three are decided in
  ADR-017 and implemented in the phase after this one.

### Dependencies
- Added `pypdf` (BSD-3) and `python-docx` (MIT); `lxml` (BSD-3) arrives with the latter.
  Licences were read from the installed packages rather than recalled. `lxml` is a
  compiled extension rather than pure Python, so `.docx` support depends on a wheel
  existing for the interpreter in use.


## [0.14.0] - 2026-09-02

### Added
- The `summarize_file` prompt is shaped rather than merely stated: it frames the task,
  names the language to answer in, asks for a concise and factual summary, and fences
  the document between markers so the model can tell instruction from material.
- `output_language` in the configuration, naming the language the model is asked to
  answer in. Defaults to `English` - small local models follow instructions and write
  more reliably in it - and is configurable because the right language depends on who
  reads the answer. A blank value is rejected at validation rather than falling back
  to whatever the model would have chosen.
- `Skill.plan` receives the configuration, so a skill can describe intent that depends
  on it. This amends the contract set in ADR-009 and does so deliberately: the plan
  stays pure, since reading a frozen, already validated `Config` is not a side effect.

### Security
- The prompt states that the fenced document is material to summarize, not a request
  addressed to the model. Text read from a file is treated as untrusted input.
- The markers are fixed strings holding no user-supplied text, so a crafted file name
  cannot forge a fence. A document that contains the closing marker verbatim does
  still end the fence early: that limitation is named in ADR-015 rather than left to
  be discovered. What bounds the damage is that nothing acts on the answer - it is
  text returned to a person who previewed and confirmed the run.

### Notes
- Prompt wording still lives in code. External, user-editable templates remain a later
  phase, now with real wording to generalize from rather than a guess.
- Generation parameters (temperature and the like) remain outside the provider
  contract, as ADR-013 left them: they shape an answer through the engine rather than
  through the prompt.


## [0.13.0] - 2026-09-02

### Added
- The execution cycle now reads the files an action declares, so `summarize_file`
  produces a real summary instead of naming a file it never opened. The read happens
  after the human confirms and before the provider is called: a declined action never
  touches a file, and the contents reach the prompt.
- `SkillPlan` carries a prompt *template* (`prompt_template`) instead of a finished
  prompt. The skill leaves a placeholder where file contents belong; the cycle fills
  it with what it read. A plan stays pure - it holds the hole, never the content.
- `ReadError`: a file that cannot be read (missing, locked, not UTF-8 text) fails with
  a clear, actionable message rather than a raw filesystem error, the same posture
  `ProviderError` takes. The CLI reports it and exits.
- New audit events `files_read` (which files were read) and `read_failed` (that a read
  failed, and why).

### Security
- Files are read only when the action declares `read_files`. The preview checks
  declared capabilities and the workspace boundary; an action that names targets
  without declaring the capability passes the preview but is still never read.
- File contents follow the existing privacy rule: they reach the audit trail only
  through the prompt, recorded under `audit_level: full` and omitted under `standard`.
  The `files_read` event records paths, never contents.

### Notes
- Prompt wording still lives in code. Configurable, user-edited templates are a later
  phase with their own questions; this release only splits template from filled prompt.
- Multiple targets are read and joined, but no skill declares more than one yet.
  Chunking and retrieval for files larger than the model's context come later.


## [0.12.0] - 2026-07-25

### Added
- `OllamaProvider`: a real provider that sends a prompt to a local Ollama instance
  (`/api/generate`, streaming off) and returns the completion, implementing the same
  provider port as the mock. Talking to local Ollama over loopback is not network
  access in the sense the configuration guards. Failures (engine unreachable, model
  not installed, timeout) are translated into clear, actionable messages.
- A `--provider` option on `lacc run` to choose between `ollama` (default) and
  `mock`, so runs can hit a live model or stay offline and deterministic.
- A `model` field in the configuration, naming the Ollama model to use. Empty by
  default: a missing model is a clear error, not a guessed default.
- A progress indicator while generating, noting that the first run loads the model
  into memory and may take longer.

### Notes
- Generation parameters (temperature, `think`, and so on) remain out of the provider
  contract, deferred until real use shows which are needed.
- Reading file contents into the prompt is still pending: the summarize skill names
  the file but does not yet read it, so a real model reports it lacks the content.
  That is a known next step, not a defect.


## [0.11.0] - 2026-07-20

### Added
- Profiler (`profiler`) and the `lacc profile` command: detects and reports what the
  machine offers - whether Ollama is present, which models are installed (with size
  and quantization), and hardware facts (architecture, processor, OS, CPU count,
  total memory, free disk, uptime). Reads and reports only; it never pulls a model
  or runs inference.
- A rough model-fit table computed by formula (weight is parameters times bit-width
  over eight) across common sizes and quantizations, marked fits / tight / too large,
  presented as an approximation to verify rather than a recommendation.
- Honest notes instead of guesses: that capacity assumes free memory, that exceeding
  it causes slow swapping, how to check free memory in real time, and that GPU/NPU
  accelerators may exist but be unusable (Ollama runs on CPU on Snapdragon).

### Dependencies
- Added psutil, used only to read total memory and boot time portably.


## [0.10.0] - 2026-07-20

### Changed
- Permissions granted to a skill now come from what the skill declares, limited by
  the configuration ceiling (`grant_for`), replacing the hardcoded `read_files`
  the CLI used as a stopgap. A skill receives exactly the capabilities it declares,
  minus any the configuration forbids - nothing more, nothing vetoed.


## [0.9.0] - 2026-07-21

### Added
- Command-line interface (`cli`): the `lacc` command, built with Typer and
  rendered with Rich, both confined to the CLI so the core stays free of interface
  code.
- `lacc run <skill> <request>` plans a skill, shows the preview, asks for
  confirmation (defaulting to no), and on an explicit yes executes and records it.
- `lacc preview <skill> <request>` shows what would happen without asking,
  executing, or recording.
- The `lacc` console script now points at the real CLI entry point, replacing the
  scaffold placeholder.

### Dependencies
- Added typer and rich, confined to the command-line interface.


## [0.8.0] - 2026-07-20

### Added
- Skills (`skill`): an abstract `Skill` contract mirroring the provider port. A
  skill declares its name and required capabilities and implements `plan`, which
  turns a request into an action and a prompt without side effects.
- `SummarizeFileSkill`: the first demonstration skill, read-only. It declares a
  `read_files` requirement and a target path inside the workspace, exercising the
  permission check and the boundary end to end.
- `run_skill`: wires a skill to the execution cycle, so a skill is always run
  through preview, permission check, confirmation, execution, and audit - never on
  its own.


## [0.7.0] - 2026-07-20

### Added
- Execution cycle (`cycle`): `run_action` drives an action through the whole
  system in order - preview, refuse or ask, execute, record - so callers describe
  what they want done without knowing how a run proceeds.
- Human confirmation is supplied as a function, not performed by the core, so the
  cycle works from a terminal, a test, or any future interface without containing
  interface code.
- Refused and declined runs are recorded, not just completed ones: the audit trail
  can answer whether something was ever attempted. New audit events `run_refused`
  and `confirmation_declined`.
- The first integration tests, exercising configuration, workspace, permissions,
  provider, preview, and audit together rather than in isolation.
- Continuous integration: the quality gate runs on every push via GitHub Actions.
- An example configuration file (`config.example.yaml`) with each option's
  consequence documented.


## [0.6.0] - 2026-07-19

### Added
- Execution preview (`preview`): describes what an action would do before it runs
  and whether it would be allowed, with no side effects - nothing is written, no
  provider is called.
- `IntendedAction`: a generic description (name, summary, required capabilities,
  target paths) that anything can produce, so the preview does not depend on skills.
- Previews report every refusal reason at once - missing capabilities and paths
  escaping the workspace boundary - and render a readable block for confirmation.


## [0.5.0] - 2026-07-19

### Added
- Audit log (`audit`): append-only JSON Lines records written inside the workspace,
  with the path resolved through the workspace boundary. Each event carries a UTC
  timestamp, the `run_id`, a closed-set event kind, a message, and optional detail.
- `audit_level` gains behavior: `standard` (the default) records metadata only,
  omitting prompt and completion content; `full` records content as an explicit
  opt-in.
- `audit_failure_policy` in the configuration: `abort` (the default) refuses to
  proceed when a record cannot be written; `continue` proceeds unrecorded. Each
  option documents its consequence.


## [0.4.0] - 2026-07-17

### Added
- Provider port (`provider`): an abstract `Provider` with a single operation
  (prompt in, `Completion` out) so the core never depends on a concrete engine.
  Completions carry the name of the provider that produced them, so results can be
  attributed in an audit record.
- `MockProvider`: a deterministic implementation that touches no network, model, or
  filesystem. Answers from caller-supplied scripted responses, or falls back to a
  predictable response derived from the prompt. Makes every later phase testable
  offline.


## [0.3.0] - 2026-07-17

### Added
- Permissions (`permissions`): a frozen contract with one capability per field
  (`read_files`, `write_files`, `network`, `run_commands`), all disabled by default
  so an empty `Permissions()` grants nothing.
- Configuration as a ceiling: `effective_permissions` intersects granted
  capabilities with what the configuration allows, so a capability the
  configuration forbids cannot be granted by a skill.
- `check` returns a `PermissionCheck` naming exactly which capabilities are
  missing, for execution previews; `require` raises `PermissionDenied` on the
  execution path.


## [0.2.0] - 2026-07-17

### Added
- Workspaces (`workspace`): a validated, frozen contract around a root directory
  with an enforced boundary. `is_within` and `resolve_within` resolve `..` and
  symlinks before checking, so paths cannot escape the workspace. Root creation is
  explicit via `ensure`, never a silent side effect of construction.
- `workspace_from_config`: builds an operational workspace from a configuration's
  `workspace_root`, the seam connecting config to workspace.


## [0.1.0] - 2026-07-17

### Added
- Initial project scaffold: installable package skeleton, packaging
  configuration, and quality gate tooling (linter, type checker, test runner).
- A smoke test that verifies the package imports and exposes a version.
- Documentation as a short book of numbered chapters: overview, architecture,
  roadmap, and development.
- MIT license.
- ADR-based documentation system: a book of numbered chapters plus decision
  records (`docs/adr/`), an index, and the guiding principle that every document
  is written from a real decision.
- Core configuration (`config`): a validated, frozen Pydantic contract
  (`network_access` off by default, `audit_level`, `workspace_root`) loadable
  from YAML, validated at the boundary.
- Run identity (`run`): a human-readable, time-ordered, unique `run_id` for each
  execution.
- Runtime dependencies: pydantic and pyyaml.