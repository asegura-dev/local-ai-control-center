# Chapter 1 - Architecture: core-first, flat modules, contracts at the boundary

This chapter describes how LACC is structured and the reasoning behind those
choices. It grows as the implementation does.

## Guiding principles

The design of LACC is guided by a few well-known quality principles. They are
goals that shape decisions, not properties the current code already proves.

- **High cohesion.** Each module aims to have one clear responsibility.
- **Low coupling.** Modules aim to depend on each other as little as possible,
  communicating through explicit contracts rather than shared internals.
- **Explicit over implicit.** Behavior that matters is declared, not assumed:
  permissions start disabled, a skill declares the capabilities it needs, the
  configuration limits what may be granted, and sensitive actions are shown before
  they run.
- **Incremental design.** Structure is added when a real need appears, not in
  advance. Flat modules stay flat until a module grows enough to justify a split.

These principles pull against each other in places. Low coupling favors splitting
things apart; incremental design favors keeping them together until a split is
clearly needed. LACC leans toward the simpler structure first and accepts a
little more coupling for a while, rather than building abstractions the code does
not yet require. Some of these boundaries are not yet exercised by real code and
may shift as the project grows.

## Core-first

LACC is built core-first. Application logic is intended to live in the package,
and interfaces consume it. The dependency direction is meant to be one-way:

```text
core logic  ->  CLI / dashboard use it
```

The reverse is not allowed: the core must not depend on the CLI or the
dashboard. This is intended to keep the core testable in isolation and to let
interfaces change without touching business logic.

## Module strategy

Early versions use a small set of flat modules rather than many subpackages.
Subpackages are introduced only when a module grows large enough to justify the
split. This avoids empty folders and premature abstraction.

The package currently exposes its version, a validated configuration contract
(`config`), run identity (`run`), a workspace with boundary enforcement
(`workspace`), a restrictive-by-default permission system (`permissions`), a
provider port with a deterministic offline mock and a real Ollama-backed
implementation (`provider`), an append-only audit
log (`audit`), a side-effect-free execution preview (`preview`), the execution
cycle that runs an action through all of them (`cycle`), skills that produce those
actions (`skill`), a converter port that turns documents into text LACC can read
(`converter`), and a command-line interface that ties everything into a usable
tool (`cli`). Interface code (Typer, Rich) lives only in the CLI; the core stays
free of it. A profiler (`profiler`) detects and reports what the machine offers -
the local engine, installed models, hardware, and rough capacity guidance - without
acting; it is Ollama-specific for now, while the provider port stays engine-agnostic.
With the real provider in place, the loop now runs end to end against a live local
model: a skill's prompt reaches Ollama and its completion returns through the cycle,
audited like any other run. The CLI chooses between the mock and Ollama per run.

## Where a side effect lives: reading files

Reading a file is the first side effect a skill needs, and it shows how the layers
divide work (ADR-014). A skill's `plan` is pure, so it cannot read. Instead the plan
produces two things the cycle can act on: the files it wants, as the action's
`targets`, and a *prompt template* with a placeholder where their contents belong.
The plan therefore never holds file content - it holds the hole.

The cycle does the reading, in its established order: preview, confirm, **read**,
call the provider, record. Reading after confirmation means a declined action never
touches a file. Reading before the provider means the contents can reach the prompt.
The cycle fills the template and sends the result; the filled prompt is the cycle's
product, not the plan's.

Permission is not re-derived at the point of reading. The preview has already checked
the action's declared capabilities against the permissions, and every target against
the workspace boundary - so the cycle reads only what the action declared `read_files`
for, and trusts what was verified rather than re-checking it. What it does not trust
is the filesystem itself: a file that passed the boundary check can still be missing,
locked, or not text at the moment of reading, so the read is attempted and its failure
translated into a clear message, the same posture the provider takes.

## What LACC says to the model

The prompt is part of the system, not an afterthought at its edge (ADR-015). It is
built in two places, and the split follows the same rule as everything else: the skill
describes, the cycle acts. The skill writes the wording - the framing, the instruction,
the language to answer in, the markers that fence the document - and leaves a hole. The
cycle fills that hole with what it read. Neither half holds the other's job.

The language the answer must be written in comes from the configuration rather than
from the model's own choice, which is why `plan` takes a `Config`. That widened the
skill contract set in ADR-009, deliberately and in the open: what a skill intends can
legitimately depend on configuration, and reading a frozen, already validated value is
not a side effect, so the plan stays pure and stays safe to preview.

The document is fenced between fixed markers and the instruction says, in words, that
what sits inside them is material to summarize rather than a request. This is where
LACC treats its own inputs as untrusted: a file inside the workspace belongs to the
user, but that does not make its text an instruction LACC should follow. The fence is
a mitigation and the documentation says so - a document containing the closing marker
ends it early. What keeps the residual risk small is structural rather than textual:
nothing in LACC acts on a model's answer. It is returned to a person who previewed and
confirmed the run, and no skill chains from it.

## A second kind of run, and the cost of admitting it

Reading a document that is not text - a PDF, a `.docx` - is the first job that does not
fit the shape everything else has. A skill produces a prompt and the cycle sends it to a
model; converting a document produces a file and never asks a model anything. Making it
a skill would have meant a plan with no prompt and a cycle that sometimes skips the
provider: a hole cut in a contract to admit the one case that does not fit it (ADR-016).

It did not need to be a skill. `IntendedAction` was built generic in ADR-007, and named
a command-line action as one of its producers from the start. That seam had gone unused
for eight releases; ingestion is what it was for. Skills keep meaning "work a model
does", and `lacc ingest` builds its action directly.

What the cycle grew is a second entry point, not a second sequence. Preview, refuse or
ask, record - the order ADR-008 fixed - lives in one function that both entry points
open with; what differs is only the middle, where one reads and calls a provider and the
other converts and writes. Two public functions each re-implementing the order would be
two places that know how a run proceeds, which is the thing that order exists to prevent.

The general design is visible from here: an action carrying its own effects, and one
cycle running any of them. It is deliberately not built. Two cases written by the same
hand on the same afternoon are weak evidence for an abstraction that would touch
everything, and the duplication that remains is small enough to name and wait on.

Conversion itself sits behind a `Converter` port with two implementations from the
start, so the abstraction is shaped by two real cases rather than guessed from one - and
so the extraction library, the part most likely to be wrong, can be replaced behind an
interface instead of unpicked from the system.

## What the preview shows is what was checked

Both effects of a conversion - reading the document, writing the result - have to be
declared by the action before either happens. This is not belt and braces. The preview
checks the capabilities an action declares and nothing else, and the human confirms what
the preview showed; so an effect that was never declared is one nobody checked and one
nobody agreed to. Guarding the write and not the read left exactly that gap, and a
security review found it after the write had already been fixed.

The rule that comes out of it is worth stating plainly, because it is easy to get
backwards: an action may do what it *declared*, not what its permissions happen to
allow. A conversion whose permissions grant `write_files` but whose action never asked
for it is refused - the grant is a ceiling, not an instruction.

## What a path has to be, not only where it is

The workspace boundary was built to answer one question - is this path inside? - and it
answers it well. A security review found that it was being asked to carry a second
promise it had never been given: that a path names a file you can find again (ADR-017).

Three shapes broke that promise without leaving the boundary, all of them specific to
Windows. A device name (`NUL`, `CON`, `COM1`) resolves to a device whatever directory
precedes it, so a document written there is discarded while the run reports success. An
alternate data stream (`notes.md:hidden`) writes to a place no directory listing shows.
A name ending in a dot or a space is silently trimmed before resolving, so the file
written is not the file named.

None of them is an escape, and that is the point worth keeping: a containment check is
not the whole of what a boundary owes. These are refused by shape, in the workspace, next
to the containment check, so that the one module answering "may LACC touch this path"
answers the whole question rather than half of it.

## What a second skill was for

A second skill answers questions a first one cannot. Two of them came due together
(ADR-018).

The first is what to share. Both skills fence the document and tell the model the fenced
text is material rather than instruction, and that fence is not formatting: it is what
stands between a document that reads like an instruction and a model that treats it as
one. Copied, it becomes two implementations of one security boundary, free to drift, with
nothing to say which is right. So it is extracted - and only it. The framing and the task
stay in each skill, because those are what genuinely differ, and they belong next to the
thing they describe.

The second is the skill registry deferred in ADR-010. The roadmap expected a third skill
to give it shape; that expectation was wrong, and the correction is worth keeping because
the mistake is easy to repeat. The CLI's mapping already answers everything a registry is
for: what exists, what a name resolves to, what to say about a name that does not. What a
formal registry adds is discovery - skills arriving from somewhere other than this source
tree - and that is a question about trust, because a skill LACC did not write is one whose
declared capabilities are a claim rather than a fact. Counting skills was never the
trigger.

## Enforcing a limit you did not set is not enforcement

The context window is the second ceiling in LACC, and it taught something the first one
did not (ADR-019). `max_input_bytes` is about this machine's memory, and the machine is
the one LACC runs on, so measuring it is straightforward. The context window belongs to
the engine, and the engine turned out not to be using the number anyone would have looked
up.

Measured: `qwen2.5:3b` supports 32768 tokens, and Ollama loads it with 4096 unless asked
for more. A design that reported the model's maximum and checked prompts against it would
have passed a 20000-token prompt as comfortably within range while the engine discarded
seven eighths of the document - and it would have looked like a check the whole time.

So LACC asks for the window rather than inheriting one. That is a small intrusion into how
the engine runs, and it is confined: one value, given to the provider at construction where
the model name already lives, so the port itself is unchanged and the mock is untouched.
The principle is worth keeping past this case - a limit checked against a value the system
did not set is a limit that can be silently wrong, and the fix is to set it, not to check
harder.

The rest follows from refusing to pretend. Tokens are estimated, because LACC has no
tokenizer, so the estimate errs toward refusing and is called an estimate everywhere.
Nothing is trimmed to fit, because trimming is the behaviour being prevented. And when no
window is configured, the run proceeds and says so, because an unset option should not
quietly become an assumption in either direction.

## Future direction

As the project matures, the package may be organized into subpackages such as
configuration, workspaces, providers, audit, skills, security, and profiler.
This is direction, not current structure. Folders are created when there is real
code to put in them.