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
- Not dependent on paid APIs, or on anybody's computer but your own. It reaches only
  hosts your configuration names, and by default it reaches none.
- Not a large platform. It grows in small, reviewed increments.

## Status

Early development, but working end to end against a real local model.

Every run takes the same shape: LACC plans the action, shows a preview, asks for
confirmation defaulting to no, reads what it was pointed at inside the workspace
boundary under the `read_files` permission, and records the whole thing in an
append-only, hash-chained audit log.

- `lacc run summarize_file <path>` and `critique_file` answer about a document.
- `lacc run extract_claims <path>` returns what a source asserts, each claim with the
  document's own words and a page - and **every quotation is checked against the
  source**. What cannot be found is marked as not found rather than presented as fact.
- `lacc run revise_file <path>` proposes a clearer version *beside* the original,
  approved against a diff. Nothing LACC writes replaces a file that already existed.
- `lacc ingest <document>` turns a PDF or Word file into Markdown you can open and
  correct, preserving page markers so quotations stay checkable.
- `lacc preview` shows what would happen without doing it, `lacc profile` reports what
  the machine offers, `lacc verify` walks the audit chain, and `lacc notify test`
  checks notification settings before you rely on them.

The control core is in place: configuration, workspaces with boundary enforcement,
permissions, a provider port with a deterministic mock and a real Ollama
implementation, the hash-chained audit log, execution previews, the execution cycle,
skills, document conversion, quotation checking, a notifier port, and the
command-line interface.

By default LACC contacts nothing but a local engine. It reaches another machine only
when the configuration both permits network access and names the host - so the model
can run on a desktop you own, on a network you control, and a run that takes minutes
can say when it finished through an ntfy server you host yourself. No destination is
ever contacted unless it is written down in your configuration, and no environment
variable can widen that.

What remains for v1 is adoption: guides, a clear install, and a citable record - see
the [roadmap](docs/02-roadmap.md).

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.