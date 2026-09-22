# Orientation - read this first

One page. What this is, how to run it without breaking anything, where things live, and the
four rules that are not style preferences.

---

## Run it through the wrapper. Never bare `uv`.

    .\run.ps1 run pytest -q
    .\run.ps1 run lacc status -c configs/denso.yaml
    .\run.ps1 sync --extra gui

`run.ps1` puts the environment in `%USERPROFILE%\.venvs\lacc`, **outside this folder**. Calling
`uv` directly builds a `.venv` here instead, and a synchroniser - OneDrive, Dropbox - locks it
mid-build: `Access is denied`, a half-removed directory, and an environment that then fails
every install. That happened four times in one day, and the wrapper had existed the whole time
(ADR-084).

The same applies to anything that launches LACC: `scripts/lacc-window.bat` goes through
`run.ps1` for this exact reason.

## The gate, all four, before anything counts as done

    .\run.ps1 run ruff check .
    .\run.ps1 run ruff format --check .
    .\run.ps1 run mypy src
    .\run.ps1 run pytest -q

## Where to look

| | |
|---|---|
| **Where does the work stand?** | `.\run.ps1 run lacc status -c <config>` |
| **What is the project like right now?** | `.\run.ps1 run python tools/measure.py` |
| **Why is anything the way it is?** | [`docs/adr/README.md`](adr/README.md) - every record, annotated |
| **What is in each file?** | [`docs/INDEX.md`](INDEX.md) |
| **How is a change made here?** | [`guides/how-a-change-is-made-here.md`](guides/how-a-change-is-made-here.md) |
| **The same, in detail** | [`guides/working-this-way-in-detail.md`](guides/working-this-way-in-detail.md) |
| **What was measured and what was wrong** | [`docs/04-measurements.md`](04-measurements.md) |

**Take a figure rather than remembering one.** Both tools above print everything fresh and
store nothing, because this project's most frequent defect is a true sentence that aged.

## The shape of the code

    core/       decides things, imports nothing outside itself
    ports/      abstract classes and the contracts that cross them
    adapters/   implements a port: Ollama, Crossref, ntfy, documents
    features/   one capability each: corpus, review, sections, prompts...
    views/      the window's sections - draws, never decides
    cli.py      the driving adapter          window.py  the second one
    cycle.py    the one place that runs an action through the whole system

`tests/test_layering.py` enforces all of that, in both directions.

## Four rules that are not preferences

**Nothing is verified by remembering.** A quotation is checked against its document by string
comparison. A figure is counted now. A stage reports what is *missing*, not only what is done.

**A view contains no logic.** If a function in `cli.py` or `window.py` never touches the
presentation, it belongs in `features/`. The exception list in `test_layering.py` is empty and
the rule is absolute (ADR-066).

**Nothing is written into a document.** The corpus points at these files as they are; hundreds
of quotations are checked against them. Facts *about* a file go beside it -
`report.findings.json`, `bibliografia.registry.json`, `part.md.from.json`.

**Reaching anywhere is deliberate.** `network_access` is a ceiling, off by default. A
destination is written in the configuration the user wrote, never an environment variable. The
window makes no request until somebody presses a button.

## What it will not do, and that is the point

It will not tell you whether a claim is **true** - only whether its quotation is real and
whether a reading follows from it. It will not choose your subject. It will not write your
argument, and it does not search the internet for papers: you bring them.

---

*A change is done when the record, the changelog, the chapter, the index, the roadmap and the
log all say the truth about it - not when the gate passes.*
