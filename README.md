# Local AI Control Center (LACC)

[![Quality gate](https://github.com/asegura-dev/local-ai-control-center/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/asegura-dev/local-ai-control-center/actions/workflows/quality-gate.yml)

A local-first framework for private, reproducible, auditable AI-assisted
workflows.

## What LACC is

LACC is designed to run AI-assisted workflows entirely on your own machine,
with an emphasis on privacy, reproducibility, and human oversight. It is built
for developers and researchers who want the benefits of AI assistance without
sending their data to third-party services.

LACC is an orchestration and control layer. It is designed to run on top of
local inference engines such as Ollama, rather than to replace them: the engine
provides the model, while LACC is intended to handle permissions, previews,
confirmation, and audit around each action.

The project is in early development. Where something is not yet implemented, this
document describes it as intent rather than as a guarantee - and where a property is
enforced rather than merely intended, it says which mechanism enforces it.

## Design principles

- **Local-first.** LACC runs without paid APIs or internet access, and the quality gate
  fails if any part of it reaches a non-loopback address. A workspace inside a git
  working tree is refused, so local material is not one `git add -A` from being
  published.
- **Restrictive by default.** Every capability starts disabled. An action may do what it
  *declared*, not what its permissions happen to allow, and the configuration is a
  ceiling that removes rather than a grant.
- **Auditable.** Every meaningful execution leaves an append-only record, hash-chained so
  that a silent edit becomes detectable and locatable. Documents are recorded by digest,
  which says which document without keeping a copy of it.
- **Reproducible.** A run records what it read, what it asked, how large the prompt was
  and what the engine reported back - enough to understand it later without storing the
  material itself.
- **Human-in-the-loop.** Sensitive actions are previewed and confirmed before they run,
  with confirmation defaulting to no. Nothing acts on a model's answer.

## What LACC is not

- Not an autonomous agent that acts without supervision.
- Not dependent on paid APIs or a network connection.
- Not a large platform. It grows in small, reviewed increments.

## Status

Early development, but working end to end. `lacc run summarize_file <path>` plans
the action, shows a preview, asks for confirmation (defaulting to no), reads the
file inside the workspace boundary under the `read_files` permission, sends its
contents to a local Ollama model, and records the run in an append-only audit log.
`lacc ingest <document>` turns a PDF or Word file inside the workspace into text LACC
can read, writing it as Markdown you can open and correct - after the same preview and
confirmation, and never overwriting a file that is already there. `lacc preview` shows
what would happen without doing it; `lacc profile` reports what the machine offers.

The control core is in place: configuration, workspaces with boundary enforcement,
permissions, a provider port with a deterministic mock and a real Ollama
implementation, the audit log, execution previews, the execution cycle, skills,
document conversion, and the command-line interface. The engine is reached over
loopback only: a non-loopback address is refused rather than used. What remains is hardening through real use and
documentation for adoption - see the [roadmap](docs/02-roadmap.md).

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.