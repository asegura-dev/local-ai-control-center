# Files on disk - everything LACC writes, and where

Three kinds of file, and the difference between them is the whole point of this page: **what a
command writes for you is only ever a new file**; what LACC keeps for itself beside your files
it rewrites; and outside the workspace it writes two things, both only from the window, both
after showing what it would do.

Read on 27-sep from every place the source writes (`write_text`, `write_bytes`, `open` with
`"w"`, `"a"` or `"x"`, `mkdir`, `safe_dump`), and read again on 2-oct, which found `corpus`
missing from the first table.

## What a command writes for you - never over anything

Every one of these goes through `write_new_file` (`cycle.py`), which opens with `"x"`:
exclusive creation, so an existing file is refused rather than replaced, with no gap between
checking and writing (ADR-039). The refusal reads *"... already exists, and LACC writes its
results only to new files."*

| Written by | What | Where |
|---|---|---|
| `lacc ingest` | The document's text, page by page | `<document>.md` beside it, or `--into` |
| `lacc collect` | A corpus of checked quotations | `--into` |
| `lacc corpus` | The quotations of one or more collected corpora, each checked again against its document and marked when it is not there | `--into` |
| `lacc run revise_file` | The revision, after you approve its diff - beside the original, never over it (ADR-025) | a sibling of the document |
| `lacc review --into` | The report, and the findings as data for the window | `--into`, and `<into>.findings.json` |
| `lacc repeats --into` | Where the files given state the same fact twice, group by group, and with `--propose` a model's proposal under each group, checked; the files themselves are never written (ADR-125) | `--into` |
| `lacc coverage --into` | The report | `--into` (and see below for its numbers) |
| `lacc resolve --into` | The bibliography, as Markdown | `--into` |
| `lacc bib --into` | The bibliography, as BibTeX | `--into`, which must end in `.bib` |
| `lacc sections --take --into` | One numbered section of a document, and where it came from | `--into`, and `<into>.from.json` |
| `lacc bring` | A copy of one file you named outside the workspace, and where it came from (ADR-111) | `drafts/<name> (<day>)<suffix>`, and `<copy>.brought.json` beside it |
| `lacc notes` | A note per reference: where the protocol cites it and what a judge said, the model's reading, its verified quotations (ADR-124). A note already there is refused before anything is asked | `notes/<key>.md`, or `<into>/<key>.md` |

One exception, by the letter: coverage's numbers, `<into>.reaches.json`, are written with a
plain write after the report. The report is refused if it exists, so the numbers are only ever
written beside a new report - but a stray `.reaches.json` of the same name would be replaced.

## What LACC keeps for itself - rewritten as it goes

| File | What it holds | When it changes |
|---|---|---|
| `audit.jsonl` | The trail: one record per event, each chained to the one before (ADR-006, ADR-023) | Appended to, never rewritten |
| `audit.anchor` | How long the trail is and how it ends (ADR-049) | After every record |
| `audit.lock` | Nothing. Writers take turns at it, so two - the window's threads, a terminal beside the window - never chain to the same record (ADR-109) | Created by the first record written; never removed, and never created by a reader |
| `<bibliography>.registry.json`, `identified.registry.json` | Every answer the registry gave, so no DOI is asked twice (ADR-067) | After `resolve` or `identify` asks |
| `<corpus>.vectors` | The embeddings of a corpus's passages, beside it (ADR-061) | When passages without one are embedded |
| `<document>.doi.json` | The DOI a person established for a document (ADR-087) | When you confirm one with `identify --doi` |
| `.lacc-window.yaml` | The window's theme and last configuration (ADR-069) | When you change them |

All of these are inside the workspace, resolved through its boundary like everything else.

## Outside the workspace

| What | Written by | How |
|---|---|---|
| A configuration's settings | The window's **Configuration** section | Only after it draws every line that would change, and never `network_access` or `workspace_in_repository` (ADR-094). **This replaces a file** - the one file of yours LACC ever replaces, because changing a setting is the point |
| A new configuration, and its workspace folder | The window's **Workspaces** section | After it says what it would cost; the configuration is opened with `"x"`, so an existing one is refused (ADR-093) |
| The virtual environment | `run.ps1`, through `uv` - not LACC itself | In `%USERPROFILE%\.venvs\lacc`, deliberately outside the repository and any synchronised folder (ADR-084) |

Nothing else. No temporary files, no caches in the home folder, no registry keys.

**And one read.** `lacc bring` reads the one file you name outside the workspace - after showing
its full path and where the copy goes, and asking - and never writes to it (ADR-111). It is the
only place LACC reads outside the workspace.

## What is never written

- **A document of yours.** Ingestion reads it and writes a new file beside it; a quotation
  check reads it; nothing edits it (ADR-016, ADR-076).
- **The trail, by the window.** The Audit section reads it and has no control that writes
  (ADR-104).
- **The model's answer, into the next question.** A thread of questions carries the passages
  whose quotations were found, never the model's prose (ADR-091). A model's words go back to
  an engine in two places, both to be judged: `--judge`, which sends each reading beside its
  quotation and says that it is a model judging a model (ADR-053), and `notes`, which does the
  same with the reading of each reference (ADR-124).
