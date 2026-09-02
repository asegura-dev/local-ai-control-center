# LACC Principles

The non-negotiables of this project. Every phase, every skill, every change is
measured against these. A change that violates one of them is rejected, however
useful it seems - the principle wins. They are stated as hard rules, not
aspirations.

## Architecture

- **The core contains no interface code.** Presentation (Typer, Rich, any future
  UI) lives only at the edges. The core does not print, prompt, or render. A change
  that puts interface code in the core is wrong by construction.

- **A skill's plan is pure.** `plan` describes intent and touches nothing: it reads
  no files, calls no engine, writes nothing. Side effects belong to the cycle, never
  to a plan. This is what makes a plan safe to preview.

- **Side effects live in the cycle, after permission is verified.** Reading, writing,
  network, running commands - all happen in one place, the execution cycle, and only
  after the permission for that effect has been checked. Nothing with an effect
  happens elsewhere.

- **Verify at the boundary, then trust.** Data is validated once where it enters
  (frozen Pydantic models) and trusted thereafter. The code does not re-check the
  same fact with defensive `if`s scattered through it. The exception is external,
  volatile systems (an engine, the filesystem): there, attempt and translate the
  failure rather than pre-checking a state that can change.

- **No abstraction without two real cases.** A port or interface is introduced only
  when two concrete implementations exist to shape it. Guessing an abstraction from
  one case produces the wrong abstraction. (The provider port earned its shape from
  the mock and Ollama; the profiler stays Ollama-specific until a second engine
  exists.)

- **Small, reviewed increments.** The project grows one phase at a time: a decision
  (ADR) precedes code, code is covered by tests, the quality gate stays green. No
  large unreviewed leaps.

## Security

- **Restrictive by default.** Every capability (`read_files`, `write_files`,
  `network`, `run_commands`) starts `false`. A skill receives only what it explicitly
  declares it needs.

- **Configuration is a ceiling that removes, never a grant.** The config can forbid a
  capability a skill declares; it cannot, by itself, grant one. Permission flows from
  what the skill asks for, limited by what the config allows - never the reverse.

- **Nothing outside the workspace is touched.** Every path is resolved and checked
  against the workspace boundary before any access. Paths that escape it (via `..`,
  symlinks, absolute paths) are refused.

- **No network access by default.** LACC does not reach the network unless a skill
  declares `network` and the config permits it. Talking to a local engine over
  loopback (`127.0.0.1`) is inter-process communication, not network access, and is
  the one explicit exception - a non-loopback host is real network access and out of
  scope.

- **Meaningful executions are audited.** Every run that does something leaves a
  traceable record. Content (prompts, completions, file contents) is recorded only
  under `audit_level: full`; `standard` records metadata, never content.

## Philosophy

- **Human in the loop.** Sensitive actions are previewed and confirmed before they
  run. They are never executed silently. Confirmation defaults to no.

- **Not an autonomous agent.** LACC does not act on its own, chain actions without
  review, or coordinate agents that bypass the human. It is a control layer, not an
  actor. A feature that removes the human from the center is not a LACC feature.

- **Local-first.** LACC runs without paid APIs or a network connection. Local user
  data stays out of version control. "Local-first" means not depending on someone
  else's cloud - not that everything must run on the machine in front of you (own
  hardware on an own private network still qualifies).

- **Explicit over implicit.** Nothing important is guessed. The model is named, not
  defaulted. A permission is declared, not assumed. An empty required value is a
  clear error, not a silent fallback.

## How these are used

When a change is proposed - a new skill, a new phase, a refactor - it is checked
against this list before it is built. If it violates a principle, the design changes
or the change is dropped. These principles are the reason to say no. They are revised
only by explicit decision (an ADR), never eroded quietly by a convenient exception.