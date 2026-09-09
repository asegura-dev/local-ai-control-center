# Chapter 2 - Roadmap: where LACC is and where it is heading

This chapter describes what LACC has today and the path ahead. Nearer phases are
described with more confidence; later ones are direction and are expected to change
as real code reveals what each one actually needs. This is not a schedule and
carries no dates.

## Done

- **v0.0.1 - Scaffold.** An installable package, the quality gate (lint, format,
  strict type checking, tests), the documentation system, and the MIT license.
- **v0.1.0 - Configuration and run identity.** A validated, frozen `Config`
  contract loadable from YAML with network access off by default, and a
  human-readable, time-ordered `run_id`.
- **v0.2.0 - Workspaces and boundary enforcement.** A validated `Workspace` whose
  boundary cannot be escaped: candidate paths are resolved before checking.
- **v0.3.0 - Permissions.** A restrictive-by-default permission contract with the
  configuration acting as a ceiling no permission can exceed.
- **v0.4.0 - Provider port.** An abstract provider with a deterministic offline
  mock, so the rest of the system is testable without any engine.
- **v0.5.0 - Audit log.** Append-only JSON Lines inside the workspace, with privacy
  as the default and a configurable write-failure policy.
- **v0.6.0 - Execution preview.** A side-effect-free description of what an action
  would do and whether it would be allowed.
- **v0.7.0 - Execution cycle.** The one place that runs an action through the whole
  system, with confirmation supplied as a function, plus the first integration
  tests. Continuous integration and an example configuration were added here too.
- **v0.8.0 - Skills.** An abstract `Skill` contract that produces an action through
  a pure `plan`, plus a read-only file-summarization skill.
- **v0.9.0 - Command-line interface.** The `lacc` command (Typer + Rich): `run` and
  `preview`, with human confirmation defaulting to no. **LACC now runs end to end
  from a terminal** against the mock provider - the foundations became a working
  tool.
- **v0.10.0 - Permission sourcing.** A skill is granted the capabilities it
  declares, limited by the configuration ceiling (`grant_for`), removing the CLI's
  hardcoded permission.
- **v0.11.0 - Profiler.** A read-only `lacc profile` that detects Ollama, lists
  installed models, reports hardware, and computes a model-fit table by formula -
  honest about what it cannot know, and never recommending a model.
- **v0.12.0 - Real provider.** An `OllamaProvider` implementing the provider port
  against a local Ollama instance, with model selection from configuration and a
  CLI choice between mock and Ollama. LACC now runs end to end against a live local
  model.
- **v0.13.0 - Reading file contents.** The cycle reads the files an action declares,
  after confirmation and before the provider, so `summarize_file` summarizes real
  content instead of naming a file. A skill's plan supplies a prompt template and
  stays pure; the cycle fills it. **LACC now does useful work on the user's own
  documents** - the first step toward the north in VISION.md.
- **v0.14.0 - Shaping the prompt.** What LACC says to the model becomes deliberate: a
  framed task, a configured output language (`output_language`, English by default),
  and the document fenced between markers and declared to be material rather than
  instruction. `Skill.plan` receives the configuration, amending ADR-009 without
  giving up the plan's purity.
- **v0.15.0 - Ingestion.** `lacc ingest` turns a PDF or `.docx` inside the workspace into
  a `.md` file inside it, through a `Converter` port with two implementations. The cycle
  gains a second entry point for runs that produce a file rather than an answer. A
  security review of the existing surface closed two holes here - a non-loopback engine
  address was honoured without being checked, and a conversion could read or write what
  its action had not declared - and recorded the rest in ADR-017.

- **v0.16.0 - Hardening (ADR-017).** What a security review of the existing surface
  decided: a configured ceiling on input size, checked before a file is opened; Windows
  device names, alternate data streams and names ending in a dot or a space refused at
  the boundary; and a refused run exiting non-zero, while a declined one still does not.
- **v0.17.0 - A second skill: critique.** `critique_file` reads a draft and reports what
  is weak in it, read-only. The document fence moves into one function both skills use,
  since a security mechanism copied per skill is free to drift. The skill registry
  deferred in ADR-010 is declined rather than built, and the reasoning behind expecting it
  here is corrected.
- **v0.18.0 - An honest context ceiling.** LACC asks the engine for the context window
  it will enforce against, estimates each prompt, and refuses one too large rather than
  letting the engine drop what does not fit and answer from the rest. Measuring showed
  why asking matters: the engine loads a 32768-token model with 4096 unless told
  otherwise. Taken before reading several files, since several documents in one prompt
  is what makes prompts long.
- **v0.19.0 - Measuring the estimate.** The engine's own token count is recorded next
  to LACC's estimate, so the context ceiling can be checked rather than argued for. An
  underestimated prompt and an answer cut short are named as such. The ratio is not
  tuned automatically: measurement is for making a decision reviewable, not for
  removing the reviewer.
- **v0.20.0 - What a context window costs.** `lacc profile` reports what each window
  size would cost for each installed model, computed from the model's own published
  shape rather than fitted to the machine it was written on, against the memory free
  now. A range with its assumptions stated, never a recommendation, and it still does
  not set `context_tokens` for anyone.
- **v0.21.0 - Exposure controls.** The quality gate fails if anything reaches a
  non-loopback address, so local-first is enforced rather than asserted. A workspace
  inside a git working tree is refused, and one that looks synchronised is flagged as
  a guess. PRINCIPLES gains the rule the release rests on: approximation is a tool for
  performance, never for exposure.

## The route to v1.0

v0.14.0 leaves LACC able to read one text file inside a workspace and answer about it
from a terminal, with permission, preview, confirmation and audit around the run. The
north in VISION.md - dialogue with your own documents, persisted locally, documented -
needs machinery that does not exist yet. Calling what remains "hardening" would be
false: most of it is new capability, and this chapter says so rather than flattering
the current state.

The first real user is the author, writing a thesis: private research documents on their
own machine that must not leave it. That use orders the phases below. Each one is the
next thing that stops being impossible, not the next thing that would be nice.

- **Ingestion - documents become text LACC can read.** Sources arrive as PDF and
  `.docx`; LACC reads only UTF-8 text and refuses binaries with a clear error. Rather
  than parsing binaries silently at read time, conversion becomes an explicit step that
  writes Markdown into the workspace: the extracted text is a file the user can open,
  check and correct, it sits inside the boundary, and its creation is audited. The core
  keeps reading only text. PDF and `.docx` are two real implementations, so the
  converter port is justified on arrival rather than guessed. A scanned PDF with no
  text layer is reported as such; OCR is out of scope. This is also the first exercise
  of `write_files`, in its safest form: new files only, never overwriting.
- **A second read-only skill - critique.** Done in v0.17.0. Reading a draft chapter and
  reporting gaps in the argument cost almost no machinery and was useful immediately. It
  also settled two questions that needed a second skill to answer: the document fence is
  now shared rather than copied, and the skill registry was declined, since what a formal
  registry adds is discovery of skills from outside this repository - a question about
  trust rather than about how many skills exist (ADR-018).
- **More than one file.** Comparing what several sources say requires reading several.
  The ceiling this bullet used to carry was taken first, in v0.18.0, and the order was
  reversed on purpose: several documents in one prompt is exactly what makes a prompt
  long, so shipping this first would have made silent truncation more likely before
  anything could detect it.
- **Chunking.** A single document larger than the context window, split deliberately,
  with the seams visible rather than hidden.
- **Writing, with a diff shown first.** Editing an existing file is the first
  destructive effect. The preview shows the diff, the human confirms, the change is
  recorded. This is what turns reading into drafting and rewriting.
- **Conversation across turns.** The provider port takes a single prompt today
  (ADR-005). Dialogue makes it carry a history instead, which is the deepest change to
  the core on this list.
- **Persistence of conversations.** Close LACC, come back, and the exchange is where it
  was left - the last promise the north makes.
- **Retrieval.** When the collection as a whole exceeds any context, the relevant parts
  have to be found rather than sent. Needs a local embedding model and somewhere to
  keep vectors: two new dependencies that stay on the machine, and the last capability
  before v1.
- **Documentation for adoption.** Guides and runbooks (`docs/guides/`): a CLI reference
  and a runbook for a first real run, written from the tool as it behaves.

Phases will merge and split. The order will not survive contact with real use intact,
and the chapter will be corrected when it does not, rather than left to describe a plan
that stopped being true.

## Decided, and deliberately after v1.0

Two directions are settled enough to record and deliberately out of v1.0. They are
written here so that decisions taken before them do not quietly rule them out.

**A model running on another machine of the user's own, reached over a private network
(Tailscale).** Small models fit this laptop; thesis-level work does not fit small
models. Sending the prompt to a stronger machine the user owns keeps every promise that
matters - own hardware, own network, own data, nothing sent to a third party - and
VISION.md already says local-first means exactly that. But PRINCIPLES.md today puts a
non-loopback host out of scope, so the two documents contradict each other, and the
contradiction is resolved by decision record rather than by convenient reading. The
moment LACC talks to a port that is not loopback, the threat model changes: permissions
guard against misbehaving skills, not against whoever reaches the interface. That ADR -
covering authentication, authorization, and whether the audit trail belongs outside the
reachable workspace - is written before it is needed, not while wiring it up.

**An interface beyond the CLI.** A terminal UI or a local web application, consuming
the same core. It arrives once the core keeps its promise, so that the interface is
built on something finished rather than becoming the place where behaviour is decided.

Converting the finished Markdown to LaTeX is not on this list. Pandoc does that well
already, and LACC has no reason to reimplement it.

## Toward v1.0

A v1.0 means the north is met and the control loop is trustworthy: dialogue with your
own documents, persisted locally, with permission, preview, confirmation and audit
around every run, and documentation good enough for someone else to adopt it. It does
not mean every feature exists.

Further ideas - a system dashboard consuming the same core, chaining skills together -
are under consideration, not commitments. Some may not happen at all.

## What this roadmap is not

Not a release schedule, and not a promise. It is a statement of direction meant to
keep development focused and honest. Where a feature is not yet implemented, it is
described as intent. Phases may be split, merged, or reordered as real code reveals
what each one needs.