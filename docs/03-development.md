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
uv run mypy src
uv run pytest -q
```

In order, these lint the code, verify formatting without changing files, type
check the package in strict mode, and run the test suite. If formatting fails,
`uv run ruff format .` applies the changes.

## Documentation discipline

Documentation is treated as part of the code, not an afterthought. The rule is
simple: documentation is updated in the same phase as the code it describes. A
phase is not done until its docs match reality.

In practice this means verb tense tracks the state of the code. What exists is
described in the present tense; what is planned is described as direction, with
words like "will", "is intended to", or "is designed to". When a feature moves
from plan to implementation, its documentation moves with it.

## Chapter layout

The documentation is written as a short book of numbered chapters, compiled into
a single navigable HTML file. Chapters are added when there is something true to
say; empty chapters are not created in advance. Numbering leaves room for
chapters that are introduced in later phases.