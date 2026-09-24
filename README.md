# Local AI Control Center (LACC)

[![Quality gate](https://github.com/asegura-dev/local-ai-control-center/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/asegura-dev/local-ai-control-center/actions/workflows/quality-gate.yml)

A local-first framework for private, reproducible, auditable AI-assisted
workflows.

**New here, or returning after a while?** [docs/ORIENTATION.md](docs/ORIENTATION.md) is one
page: how to run it without breaking the environment, where everything lives, and the four
rules that are not style preferences.

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

## Getting started

You need Python 3.11+, [`uv`](https://docs.astral.sh/uv/), and [Ollama](https://ollama.com)
with a model pulled.

```bash
git clone https://github.com/asegura-dev/local-ai-control-center
cd local-ai-control-center
uv sync

uv run lacc profile                  # what this machine can run
mkdir -p configs                          # LACC looks here; git ignores it
cp config.example.yaml configs/config.yaml   # set workspace_root, model, context_tokens
uv run lacc ingest paper.pdf         # PDF or Word into text LACC can read
uv run lacc run extract_claims paper.md
```

One setting decides whether your first run tells you the truth. Leaving `context_tokens`
unset does not mean unlimited - the engine falls back to its own default of 4096 tokens
and silently drops whatever does not fit, so you get a confident answer about the first
few pages and nothing says the rest went unread. Set it, and LACC asks for that window and
refuses a prompt too large for it.

**Guides**

- [Setting up the machine that runs the model](docs/guides/setting-up-the-server-machine.md)
  - what you are building, then step by step for
  [Linux](docs/guides/server-setup-on-linux.md) or
  [Windows](docs/guides/server-setup-on-windows.md).
- [Running the server day to day](docs/guides/running-the-server-day-to-day.md) -
  getting your VRAM back without shutting anything down.
- [Running LACC for the first time](docs/guides/running-lacc-for-the-first-time.md) - the
  full walkthrough, including how to read a verified or not-found mark.
- [Choosing hardware for local models](docs/guides/choosing-hardware-for-local-models.md) -
  what actually makes a machine fast at this, and how much VRAM a model plus its
  context window really needs.
- [Keeping the virtual environment out of a sync folder](docs/guides/virtualenv-outside-a-sync-folder.md)
  - read this first if your checkout is inside OneDrive or Dropbox.

The [documentation](docs/README.md) explains the design, and every decision has a record
in [`docs/adr/`](docs/adr/) with its context, its trade-off and the alternative rejected.

## Status

v2.10.0, working end to end against a real local model and measured against a real
bibliography rather than against documents written for the test.

Every run takes the same shape: LACC plans the action, shows a preview, asks for
confirmation defaulting to no, reads what it was pointed at inside the workspace
boundary under the `read_files` permission, and records the whole thing in an
append-only, hash-chained audit log.

- `lacc run summarize_file <path>` and `critique_file` answer about a document.
- `lacc run extract_claims <path>` returns what a source asserts, each claim with the
  document's own words and a page - and **every quotation is checked against the
  source**. What cannot be found is marked as not found rather than presented as fact.
- `lacc collect extract_claims <paths> --into claims.md` runs across a whole
  bibliography, one document at a time, and assembles a body of claims whose
  quotations have each been checked against the paper they came from.
- `--in-passes` reads a document too large for the window in several passes over
  its pages, overlapping by one so a passage crossing a break stays whole. Every
  quotation is still checked against the whole document, and the answer says how
  many passes it took.
- `lacc run revise_file <path>` proposes a clearer version *beside* the original,
  approved against a diff. Nothing LACC writes replaces a file that already existed.
- `lacc ingest <document>` turns a PDF or Word file into Markdown you can open and
  correct, preserving page markers so quotations stay checkable.
- `lacc collect <skill> <documents> --into <file>` runs one skill across a whole
  bibliography, one document at a time, and `lacc corpus` assembles several of those
  into one file of checked quotations. A document too large for the window is refused
  by name with its token count, never half-read in silence.
- `lacc ask "<question>" --from <corpus>` answers from passages that were already
  checked against the documents they name, and checks the answer's own quotations
  against what it was shown. It says how many passages it set aside before it asks
  anything: an answer drawn from a selection is an answer about that selection.
- `--judge` adds a second opinion on whether each reading follows from the quotation
  under it, and shows passages that might support the ones it flags. This is a model
  judging a model - weaker than the quotation check, and reported as such.
- `lacc review <draft> --against <corpus> --into <report>` reads **your** writing against
  **your** sources and says, paragraph by paragraph, what your corpus holds up, what it
  contradicts and what it does not cover - with *not covered* stated as not covered rather
  than as wrong.
- `lacc resolve <documents>` asks the registry that assigns DOIs what each reference
  actually is, instead of asking a model. It is the first destination in this program that
  is not your own machine, and it needs both `network_access` and a `registry_url` written
  in your configuration.
- `lacc sections <document>` lists the sections a document numbers for itself, `--about`
  ranks them by a question, and `--take` writes one out - so a guideline too large for any
  window can be read one part at a time without cutting the file.
- `lacc status` says where the work stands, stage by stage, with **what each stage is still
  missing** rather than only what it produced. Counted from the files every time.
- `lacc coverage <topics> --against <corpus>` says how far the nearest quotation in your
  corpus is from each subject you name, ordered, against a **floor**: one line of the topics
  file has to be a subject deliberately outside your field, and that is what the rest are
  read against. **Nothing is called a gap** - a similarity is an ordering, not an interval -
  and the quotation that came closest is printed under each topic so the number can be
  checked rather than believed.
- `lacc identify <document>` lists the DOIs a document prints and asks the registry what
  each one is, and **chooses none of them**: a document prints the DOIs of what it cites
  too, and no test separated the two. With `--doi` it records the one you established
  beside the file, never inside it.
- `lacc window` opens a desktop window on all of it: twelve sections in three groups, and
  one of them asks. A question goes behind a preview you have to see before the button that
  sends it exists, on a worker thread so the window never stops repainting, and asking again
  carries **the passages whose quotations were found** - never what the model said, because
  a conversation is how an invented quotation comes to verify one turn later.
- `lacc preview` shows what would happen without doing it, `lacc profile` reports what
  the machine offers, `lacc verify` walks the audit chain, and `lacc notify test`
  checks notification settings before you rely on them.

Why the checking matters, in one measured number: across 24 papers of a real bibliography,
a 14B model produced 237 quotations and **48 of them are not in the document they cite** -
about one in five, with 44 absent in any form tried. The check catches them. Nothing about
the fluency of the surrounding prose distinguishes the other four.

It is a check on quotations, not on claims: it can tell you the words are really there, and
it cannot tell you the paper means what the model says it means. And it does not see text a
PDF hides from a reader, which `lacc ingest` reports separately.

The control core is in place: configuration, workspaces with boundary enforcement,
permissions, a provider port with a deterministic mock and a real Ollama
implementation, the hash-chained audit log, execution previews, the execution cycle,
skills, document conversion, quotation checking, a notifier port, and the
command-line interface.

Seven ports now, each with an implementation and none of them assumed: the provider, the
document converter, the notifier, a retriever that must declare what it set aside, a
judge of whether a reading follows from its quotation, an embedder, and a registry that is
asked what a reference is rather than a model. Naming an
`embedding_model` lets a question be answered by meaning as well as by shared words -
measured on a real corpus, a question asked in Spanish against English quotations
reached eight relevant passages of the first eight, where word matching reached about
three. It is off unless named, and the word ranking is never removed.

By default LACC contacts nothing but a local engine. It reaches another machine only
when the configuration both permits network access and names the host - so the model
can run on a desktop you own, on a network you control, and a run that takes minutes
can say when it finished through an ntfy server you host yourself. No destination is
ever contacted unless it is written down in your configuration, and no environment
variable can widen that.

v1.0 shipped, and v2.0 turned out not to be what its plan said: the roadmap keeps the wrong
plan visible beside what actually arrived. Coverage was deferred three times on one
condition - *a gap measured over an incomplete corpus is a false gap* - and when the corpus
was complete enough, **two of the three ways of measuring it were refused**: a top-N ranking
returns N whatever you ask it, and shared words called a topic absent that the corpus speaks
to in other words. The third held. See the [roadmap](docs/02-roadmap.md).

## Citing LACC

If you use LACC in published work, [`CITATION.cff`](CITATION.cff) holds the metadata and
GitHub offers a formatted citation from the sidebar.

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.
