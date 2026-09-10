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