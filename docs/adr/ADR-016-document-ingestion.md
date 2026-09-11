# ADR-016 - Ingestion: turning documents into text LACC can read

- **Status:** Accepted - implemented (v0.15.0). Decision 6 - that what is produced is
  extracted text and is not called more than that - is amended by
  [ADR-036](ADR-036-dropping-the-furniture-of-a-page.md): ingestion now drops running
  headers, footers and page numbers, so it edits rather than only transcribing.
  Everything else stands.
- **Date:** 2026-09-08
- **Context:** LACC reads UTF-8 text and refuses anything else with a clear error
  (ADR-014). The material it exists to work on does not arrive that way: research
  sources are PDFs and `.docx` files. The first real body of work is therefore
  unreadable, and no amount of prompt shaping helps. This ADR decides how a document
  becomes something LACC can read, and where that conversion belongs.

## Decision

### 1. Conversion is an explicit step that produces a file

The obvious alternative is to teach the read step to parse a PDF when it meets one, so
that a skill points at `paper.pdf` and it simply works. That is rejected. Extraction is
the most fragile link in the whole chain - columns interleave, tables collapse, running
heads bleed into paragraphs, ligatures break words - and hiding it behind an operation
that looks trivial means its failures surface later, as a model that answered oddly,
with nothing left to inspect.

Instead, conversion writes a Markdown file into the workspace. The extracted text
becomes an artifact: the user can open it, see what was actually recovered, correct it
by hand, and keep it. Every later run reads that file like any other text, so the core
keeps its rule that LACC reads only text, and the fragile step becomes the one thing you
can actually look at.

### 2. Ingestion is a command-line action, not a skill

A skill's product is a prompt: `plan` returns an action and a prompt template, and the
cycle sends it to a provider. Ingestion never talks to a model. Making it a skill would
mean a plan with no prompt and a cycle that sometimes skips the provider - a hole cut in
a contract to admit the one case that does not fit it.

It does not need to be a skill. ADR-007 built `IntendedAction` deliberately generic:
"Produced by whatever is driving the run - a skill, a chain, a command-line action."
Ingestion is exactly that command-line action. `lacc ingest` builds the action itself and
hands it to the cycle. Skills keep meaning "work a model does".

### 3. The cycle keeps the order; only the effects differ

Ingestion still runs preview, permission check, confirmation, effects, record - the order
ADR-008 fixed. What differs is the middle: it converts and writes where a skill's run
reads and asks a model.

So the order stays in one place and the effects do not. The shared part - build the
preview, record a refusal, record a grant, ask for confirmation, record a decline - is
factored into one path that both entry points use; each then performs its own effects.
Two public functions that each re-implemented the sequence would be two places that know
how a run proceeds, which is the thing ADR-008 exists to prevent.

A more general design is visible from here: an action that carries its own effects, and
one cycle that runs any of them. It is not built now. There are two cases, and two cases
written by the same hand on the same afternoon are weak evidence for an abstraction that
would touch everything. The duplication is small, it is named here, and it becomes the
argument for that refactor when a third kind of action turns up.

### 4. A converter port, with two implementations from the start

Conversion sits behind an abstract `Converter`, chosen by the source file's extension,
mirroring the provider port. PDF and `.docx` are two real implementations on day one, so
the port is shaped by two cases rather than guessed from one - the condition PRINCIPLES
sets before an abstraction may be introduced. An unsupported extension is a clear error
naming what is supported, not a silent pass-through.

### 5. New files only; ingestion never overwrites

This is the first exercise of `write_files`, and it takes the safest form available: if
the destination already exists, the run refuses and says so, telling the user to move or
rename it. Overwriting an existing file is a different decision with a different safety
requirement - a diff shown before it happens - and belongs to the phase that makes it. A
conversion that silently replaced a `.md` the user had already corrected by hand would
destroy exactly the work this design exists to make possible.

The destination defaults to the source path with a `.md` extension, and can be given
explicitly. A derived default is not a guess in the sense PRINCIPLES forbids: the preview
names the destination before anything is written, so nothing is hidden and nothing is
assumed behind the user's back.

### 6. What is produced is extracted text, and it is not called more than that

The output is a `.md` file because that is the format the work continues in and the one
models handle best. But extraction rarely recovers real Markdown structure, and LACC does
not pretend otherwise: it preserves paragraph breaks and page boundaries, and does not
invent headings, emphasis or table syntax it cannot actually detect. Calling this
"conversion to Markdown" when it is "text extraction written to a `.md` file" would be a
claim the code cannot keep.

Page boundaries are preserved as an HTML comment (`<!-- page N -->`). That is recovered
structure, not invented: the document really does have pages, and a thesis has to cite
them. The comment form is chosen because it renders as nothing in Markdown and cannot be
mistaken for the document fence markers a prompt uses (ADR-015).

### 7. An empty extraction is reported, not written

A scanned PDF with no text layer yields nothing. LACC does not write an empty file and
call it done: it reports that the document carries no extractable text, and that OCR is
out of scope. Nothing is written on that path. Producing an empty `.md` would turn a
legible failure into a silent one, surfacing much later as a model with nothing to say.

### 8. Dependencies are chosen for licence first, capability second

Extraction needs libraries. PyMuPDF is not used: it is the fastest and most capable
option, and it is AGPL, which this MIT-licensed project cannot take on. The choice is
`pypdf` for PDF and `python-docx` for `.docx`.

Licences were read from the installed packages rather than recalled: `pypdf` 6.18.0 is
BSD-3-Clause, `python-docx` 1.2.0 is MIT, and `lxml` 6.1.3 - which `python-docx`
requires - is BSD-3-Clause. All three are permissive and compatible with MIT.

`lxml` is worth naming rather than passing over as a transitive detail, because it is
not pure Python: it is a compiled extension around libxml2, so LACC now depends on a
wheel existing for the interpreter it is installed under. The machine this is built on
runs Windows on ARM64, but its Python is an x86-64 build running under emulation -
`platform.machine()` reports `ARM64` while `sysconfig.get_platform()` reports
`win-amd64` - so what installed was an x86-64 wheel. That distinction was checked rather
than assumed, and it is written down because the same machine with a native ARM64
interpreter is a different question, and `.docx` support is the part that would fail
first. Nothing added here touches the network, so local-first is untouched.

`pypdf` extracts plainly, and will do worse than a layout-aware library on multi-column
papers. That is accepted for now, and it is precisely the reversible kind of decision the
converter port exists to protect: replacing the implementation is a change behind an
interface, not a change to the system.

## Trade-off

Writing an intermediate file means the workspace fills with derived artifacts, and a
source edited after conversion leaves a stale `.md` that LACC will read without
complaint. Accepted: the alternative is invisible extraction, and a wrong answer traced
back to a silent parse is worse than a stale file the user can see, delete and
regenerate. Detecting staleness is a real feature and can be built when it bites;
guessing at it now would add a mechanism before there is evidence of the problem.

Ingestion bypassing the skill contract means the CLI grows an action of its own rather
than everything flowing through skills. Accepted, and anticipated: ADR-007 named
command-line actions as a producer of `IntendedAction` from the beginning. The rejected
alternative was to loosen the skill contract - an optional prompt, a provider call that
sometimes does not happen - weakening a contract that currently holds for every skill in
order to admit the one thing that is not a skill.

Two entry points into the cycle means the module grows a second public function.
Accepted, with the shared sequence factored out so that what is duplicated is the
effects, not the order.

## Consequences

- `lacc ingest <source> [destination]` converts a PDF or `.docx` inside the workspace
  into a `.md` file inside the workspace, after preview and confirmation, recorded in the
  audit trail.
- A `Converter` port with PDF and `.docx` implementations, selected by extension.
- `write_files` is exercised for the first time, in create-only form: an existing
  destination refuses the run.
- A conversion both reads and writes, so its action must declare `read_files` and
  `write_files` together; the cycle refuses one that declares less. The preview checks
  only what an action declares, and the human confirmed only what the preview showed, so
  an undeclared effect is one nobody checked and nobody agreed to.
- The cycle gains a second entry point, for actions that produce no prompt, with the
  preview-confirm-record sequence shared rather than duplicated.
- New dependencies: `pypdf` and `python-docx`, and `lxml` behind the latter. All three
  permissive, all three offline, and `lxml` compiled rather than pure Python.
- A document with no extractable text is reported clearly, and nothing is written.
- Chapter 1 and the CHANGELOG are updated in this phase.
