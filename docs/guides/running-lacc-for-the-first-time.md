# Guide - Running LACC for the first time

From nothing to a checked answer about one of your own documents. Everything here was
run; where a number appears it was measured on the machine named, not estimated.

## What you need

- **Python 3.11 or newer**, and [`uv`](https://docs.astral.sh/uv/).
- **[Ollama](https://ollama.com)** running, with one model pulled.
- **A folder for your documents** that is not inside a git repository and not inside
  OneDrive, Dropbox or iCloud Drive. LACC refuses the first outright and warns about the
  second, for reasons under [Choosing a workspace](#choosing-a-workspace).

```bash
git clone https://github.com/asegura-dev/local-ai-control-center
cd local-ai-control-center
uv sync
uv run lacc --help
```

If the checkout itself is inside a sync folder, read
[keeping the virtual environment out of a synchronising folder](virtualenv-outside-a-sync-folder.md)
first. It is the difference between an afternoon of work and an afternoon of confusing
import errors.

## Ask the machine what it can run

Before choosing a model, ask:

```bash
uv run lacc profile
```

It reports the engine, the models installed, the hardware, and what a context window
costs in memory. It changes nothing - it only looks.

Read the **free** memory, not the total. On the laptop this was developed on, 15.6 GB
total showed **2.4 GB free**, because everything else was open. Free memory is what
decides which model actually runs rather than swapping to disk, and a model that swaps
does not fail - it just becomes unusably slow.

## Configuration

Copy the example into the `configs/` folder and edit it:

```bash
mkdir -p configs
cp config.example.yaml configs/config.yaml
```

`configs/` is where LACC looks when you do not pass `--config`, and the whole folder
is ignored by git - more than one configuration is normal, and none of them belongs in
a repository. When you have several, name the one you want:

```bash
uv run lacc run summarize_file paper.md --config configs/desk.yaml
```

Every field is documented in the file itself. Three decide whether your first run works:

```yaml
workspace_root: ~/lacc-workspace   # required
model: qwen2.5:7b                  # a model `lacc profile` listed
context_tokens: 32768              # see below - not optional in practice
```

### `context_tokens` is the setting that bites

Leaving it unset does not mean "unlimited". It means the engine uses **its own default of
4096 tokens** - measured, on the version this was tested against - however much the model
supports, and **silently drops whatever does not fit**. You get a confident answer about
the first few pages of a document and nothing tells you the rest was never read.

Set it, and LACC asks the engine for exactly that window and refuses a prompt it estimates
will not fit, rather than letting it be truncated. What fits, computed from the code:

| `context_tokens` | Document that fits |
|---|---|
| 8,192 | ~10 pages |
| 32,768 | ~41 pages |
| 65,536 | ~82 pages |

A quarter of the window is held back for the answer, and the estimate runs deliberately
high, so these are conservative. Most single papers fit comfortably at 32,768. A whole
thesis does not - splitting documents too large for a window is deferred to v2, and until
then LACC refuses the run instead of quietly answering from a fragment.

The window costs memory. `lacc profile` prints the cost per model, and the same 3B model
held 2.0 GB at 4,096 tokens and 3.5 GB at 32,768.

## Choosing a workspace

`workspace_root` is the only directory LACC will read from or write to. Paths that escape
it - through `..`, a symlink or an absolute path - are refused before anything is opened.

It is on **the machine you run LACC from**, always. Even when the model runs somewhere
else, your documents do not move: LACC reads them here, and only the prompt built from
them is sent to the engine.

**Keep it out of a git repository.** LACC refuses to run if the workspace is inside a
working tree, unless you set `workspace_in_repository: true`. That is not fussiness: your
sources, the text extracted from them and the audit trail all live there, and inside a
repository they are one `git add -A` away from being published. LACC cannot check whether
git ignores that path - checking means running git, which LACC does not do - so it refuses
what it can see and leaves the judgement to you.

**Keep it out of a sync folder** for the same reason one step removed: that folder copies
its contents to another computer. LACC warns rather than refusing, because a sync folder
is sometimes exactly where a person wants their documents.

## Your first run

Put a PDF in the workspace and turn it into text LACC can read:

```bash
uv run lacc ingest paper.pdf
```

You get a preview, and a confirmation that **defaults to no**. Answering `y` writes
`paper.md` beside it - Markdown you can open and correct, with page markers preserved.
Those markers are what makes page checking possible later, so keep them.

Ingestion never overwrites: if `paper.md` exists, the run is refused.

It also **drops page furniture** - running headers, footers and page numbers repeated across
pages - and says how many lines it removed. This is not pure transcription: a journal's
running header gets extracted in the middle of a sentence, which breaks the sentence for a
reader and makes any quotation from it impossible to verify. Open the Markdown and check it
if the count looks large.

Then ask something:

```bash
uv run lacc run summarize_file paper.md
```

Same shape every time: LACC plans, previews what it would do, asks, and only then reads
the file and calls the model. The first run loads the model into memory and takes longer
than the rest.

## The run that is the point

```bash
uv run lacc run extract_claims paper.md
```

This returns what the source asserts - each claim with the document's own words and a
page - and then **checks every quotation against the document**. Each one comes back
marked:

| Mark | What it means |
|---|---|
| **found** | The quotation appears in the source, and the page shown is where LACC located it. |
| **NOT IN THE DOCUMENT** | Those words are not in the document. The model made them up. |
| **found, page unknown** | The quotation is there, but no page can be given: the source has no markers, or the passage spans a boundary. |

**The page shown is the one LACC found, not the one the model claimed.** Locating the
quotation is how it gets verified, so the page comes from searching the text rather than
from a model recalling where it read something. On a real paper that distinction mattered:
the model gave page 4 for a sentence on page 1, with the quotation itself correct.

Nothing is removed. An unverified claim stays in the answer and is marked, because the
point is to show you what the model did rather than tidy it away.

Matching is exact, after collapsing whitespace and folding case. It is deliberately not
fuzzy: "across four hospitals" for "across three hospitals" is precisely the error that
must not pass. So it will occasionally reject a quotation you would accept - a changed
dash, a fixed typo. That errs the right way. A false "not found" costs you a glance; a
false "verified" is the failure the whole check exists to prevent.

**Know what this proves.** A verified quotation means the words are in the document. It
does not mean the claim built on them is sound. A model can quote accurately and reason
badly, and only the first is caught here.

## Using it to compare models

The verified-versus-not-found counts are a number, which makes "is a bigger model worth
it?" an experiment instead of an opinion. Run the same document through `extract_claims`
with different models and compare how many quotations hold:

```bash
# edit `model:` in configs/config.yaml between runs
uv run lacc run extract_claims paper.md
```

A model that fabricates more quotations is worse at the job for a measurable reason, and
you see it in one run rather than after a month of using it.

## Proposing a revision

```bash
uv run lacc run revise_file draft.md
```

You approve against a **diff**, not a preview - the revised text does not exist until the
model answers, so a preview could not show it. Approving writes `draft.revised.md` beside
the original. Nothing LACC writes ever replaces a file that already existed.

That protection ends where you take over: once you copy the revision over the original,
it is an ordinary file you edited.

## Checking the record

Every run that does something leaves a record in `audit.jsonl` inside the workspace, and
each record carries the hash of the one before it.

```bash
uv run lacc verify
```

This walks the chain and reports whether it is intact. Editing a past record breaks its
digest and every one after it, so tampering becomes locatable rather than invisible. It
does not stop a deliberate rewrite of the whole file - a chain proves consistency, not
authorship.

By default the trail records metadata only: which capabilities were requested, whether
they were granted, which model was called. Prompt and completion text are written only
under `audit_level: full`, which you opt into deliberately, because prompts contain
whatever you were working on.

## What to do when a run is refused

A refusal is LACC working, and each one names its reason. The four you are most likely to
meet:

| Message about | What happened |
|---|---|
| the workspace boundary | The path escapes `workspace_root`. Move the file in. |
| a repository | Your workspace is inside a git working tree. Move it out, or acknowledge it. |
| the prompt being too large | The document does not fit the window. Raise `context_tokens`, or use a shorter source. |
| a file being too large | Over `max_input_bytes`, 32 MiB by default. It is a limit about memory, not about the model. |

A refused run exits non-zero. A run you declined exits zero: nothing failed there - you
were asked and said no, which is the system working.

## Next

- [Setting up the machine that runs the model](setting-up-the-server-machine.md), when
  this one is not the place the work should be good - including notifications, for runs
  long enough that you walk away.
- [Choosing hardware for local models](choosing-hardware-for-local-models.md), if you are
  buying or building that machine.
