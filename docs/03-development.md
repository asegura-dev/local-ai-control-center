# Chapter 3 - Development: setup, the quality gate, and doc discipline

This chapter explains how to set up the project locally, run its quality gate,
and keep documentation honest as the code grows.

## Requirements

- Python 3.11 or newer.
- [Git](https://git-scm.com/) for version control.
- [uv](https://docs.astral.sh/uv/) for environment and dependency management.

On Windows, Git and uv can be installed with winget:

```text
winget install Git.Git
winget install astral-sh.uv
```

On macOS and Linux, follow the official installation instructions for
[Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/).

## Setup

Clone the repository, then create the environment and install the development
tools:

```text
uv sync
```

This creates a virtual environment and installs the linter, type checker, and
test runner defined in the project.

### If the checkout sits in a synchronised folder

OneDrive, Dropbox and iCloud reach into the environment while a build is running.
`uv sync` then fails partway with `Access is denied` removing the previous
`dist-info`, leaving a half-removed directory that makes the next run warn about an
incomplete environment. With files-on-demand the same synchroniser can dehydrate
`.dll` and `.pyd` files, which surfaces much later as an import error that reads
like a broken package.

**A `.venv` junction pointing outside the folder does not fix this** - synchronisers
traverse reparse points, so the environment is still walked and still locked. What
fixes it is leaving nothing of the environment inside the folder at all:

```powershell
.\run.ps1 sync
.\run.ps1 run pytest -q
```

`run.ps1` sets `UV_PROJECT_ENVIRONMENT` to `%USERPROFILE%\.venvs\lacc` and forwards
everything to uv. On a checkout outside a synchronised folder it is unnecessary, and
plain `uv` works as above. Setting `UV_PROJECT_ENVIRONMENT` in the shell does the same
thing on any platform; the script only saves remembering it.

## Quality gate

Before committing, the following checks are expected to pass:

```text
uv run ruff check .
uv run ruff format --check .
uv run python -m mypy src
uv run python -m pytest -q
```

In order, these lint the code, verify formatting without changing files, type
check the package in strict mode, and run the test suite. If formatting fails,
`uv run ruff format .` applies the changes.

Run each check on its own rather than piping it through something that trims the
output. A pipeline reports the exit status of its last command, so `ruff check . | tail`
succeeds even when ruff fails, and a chained gate carries on as though nothing were
wrong.

The test suite also enforces a promise the documentation used to make on its own: it
installs a guard that fails any test opening a connection to an address that is not
loopback (ADR-022). LACC does not use the network, and a dependency or a future feature
that reaches outward fails the build rather than shipping. Talking to a local engine over
loopback is inter-process communication and stays allowed.

`uv run mypy` and `uv run pytest` may fail with `failed to canonicalize script path` when
uv has just reinstalled the project; invoking them as `python -m` avoids it.

## Where to keep a workspace

Not inside the repository. Everything LACC reads, converts and records in a workspace is
your own material, and inside a working tree it is one `git add -A` from being committed
and pushed. LACC refuses to run in that case unless the configuration acknowledges it
(ADR-022), because the risk lasts as long as the project while a warning is read once.

Keeping it out of a synchronising folder - OneDrive, Dropbox and the like - is the same
argument: such a folder copies its contents to another computer. LACC warns about that
one rather than refusing, and says it is guessing from the folder's name.

The virtual environment has its own version of this problem, for different reasons; see
[the guide](guides/virtualenv-outside-a-sync-folder.md).

## Taking the measurements

    .un.ps1 run python tools/measure.py                  the project
    .un.ps1 run python tools/measure.py ~/lacc-workspace  the project and the material

Layers and their sizes, logic that has drifted into a view, records against their index, the
suite, and for a workspace: every document with its tokens, pages and structure, and every
corpus with what is citable in it.

**Nothing it prints is stored**, for the same reason the inventory below is not committed: a
number in a file is true for a while and then quietly stops being, which is this project's
most frequent defect. A figure that can be re-taken in seconds never has to be trusted.

The habit is smaller than the tool. **Before writing a sentence with a number in it, take the
number.** Twice, a count refused half of a plan that was already being written.

[How a change is made here](guides/how-a-change-is-made-here.md) is the whole method in six
steps, and [`docs/adr/TEMPLATE.md`](adr/TEMPLATE.md) is the record to copy.

## The record-to-code inventory

    .
un.ps1 run python tools/record_coverage.py

Prints, for every decision record, the symbols it names and where the source uses them, plus
what a record names that the source never mentions. **It detects nothing**, and a symbol low
in its output is not a defect. It exists to make one question finite (ADR-059):

> What does the record claim this does, and does the code do it in every place it should?

That question found deduplication running on one of the four call sites it belonged on, and
no test would have. The report is not committed: one in the repository would be stale by the
next commit, and a stale inventory reads exactly like a current one.

Module names, packages named in `pyproject.toml`, and symbols that live in the suite are
filtered out of the "never mentioned" list, because a record citing `cycle` or `pypdf` is
citing something real. What is left is a renamed symbol, a plan deliberately not built, or
prose that happens to look like code - and the reader tells them apart. On its first run it
found `require` named throughout ADR-004 after the function had been removed.

## Documentation discipline

Documentation is treated as part of the code, not an afterthought. The rule is
simple: documentation is updated in the same phase as the code it describes. A
phase is not done until its docs match reality.

In practice this means verb tense tracks the state of the code. What exists is
described in the present tense; what is planned is described as direction, with
words like "will", "is intended to", or "is designed to". When a feature moves
from plan to implementation, its documentation moves with it.

## Releasing

Version numbers live in three places, and all three move together:

- `pyproject.toml`
- `src/local_ai_control_center/__init__.py`
- `CITATION.cff` - both `version` and `date-released`

A `CITATION.cff` naming an older version is worse than none: it tells someone citing the
project that they used a release they did not. Then `uv lock`, a green gate, a commit, an
annotated tag, and push both the branch and the tag.

## Chapter layout

The documentation is written as a short book of numbered chapters, compiled into
a single navigable HTML file. Chapters are added when there is something true to
say; empty chapters are not created in advance. Numbering leaves room for
chapters that are introduced in later phases.