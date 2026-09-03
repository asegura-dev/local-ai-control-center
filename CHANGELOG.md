# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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