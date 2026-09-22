# ADR-084 - The environment belongs outside

## Status

Accepted. A correction to how this project was being used, not to what it does - and the
guidance it restores was already written down and was being ignored.

## Context

`uv sync` failed four times in one day with:

    error: failed to remove directory `...\.venv\Lib\site-packages\
    local_ai_control_center-2.0.0.dist-info`: Access is denied.

Once it left the environment broken: two `dist-info` directories, both **empty**, one without
a `RECORD` file, so every later install reported "may result in an incomplete environment".

**The project had already solved this.** `run.ps1` sets `UV_PROJECT_ENVIRONMENT` to
`%USERPROFILE%\.venvs\lacc`, and its own documentation describes the failure exactly: *"A
synchroniser that reaches the environment locks files mid-build."* A guide,
[virtualenv-outside-a-sync-folder](../guides/virtualenv-outside-a-sync-folder.md), explains
why a junction is not enough - synchronisers traverse reparse points.

The 111 MB `.venv` inside the repository existed because commands had been run as `uv ...`
instead of `.\run.ps1 ...`. The wrapper works; it was being bypassed.

## Decision

**Nothing belonging to the environment exists inside the checkout.** The stray `.venv` is
removed, and the optional toolkit is installed into the environment `run.ps1` names.

**The launcher goes through the wrapper.** `scripts/lacc-window.bat` called `uv run --extra
gui` directly, which would have rebuilt the 111 MB inside the synchronised folder on the first
double-click. It calls `run.ps1` now - the launcher written to make this easy was reintroducing
the problem it was made to avoid.

**And the instruction to install says the same thing.** The error message pointed at
`uv sync --extra gui`, which is the command that causes this.

## What it changed

| | |
|---|---|
| `.venv` inside the repository | **gone**, 111 MB |
| toolkit in the environment `run.ps1` uses | installed |
| suite | **727 passed, none skipped** |

That last row is the measurable part: the window's section test had been skipping because the
toolkit was not in the environment the tests run in. It runs now.

## Also fixed here, from using the window

**The panel scrolled only after being clicked.** The wheel was bound on each child as it was
drawn, which left gaps - a widget created after the last re-wrap had no binding. It is bound
on the window with `bind_all`, which sees the event wherever it lands.

**Monospaced text ran off the right edge.** `paint.fixed` was the one painter without a
`wraplength`, so a wide table or a long line of code had nothing to wrap and nothing to
scroll sideways with.

**And giving it one was not enough - twice.** First every label was wrapped to the width of
the *panel*, while a label inside a card sits behind two further layers of padding, so text
ran out of its card. Wrapping to the holder's own width did not fix it either, and a
screenshot showed why: **inside a scrollable frame a child can be wider than what is on
screen**, so both the panel and the holder measure something the reader cannot see.

It is measured against the **viewport** now - the canvas the scrollable frame draws into -
minus one inset per frame between it and the text. That is the only width on screen.

**The wheel moved one line per notch.** Windows sends 120 per notch and a notch is three lines
everywhere else on the system, so a long record felt stuck even once it scrolled at all.

**The status bar overlapped itself**, reading `881 quotationsked`. The left half was packed
first with no room given up, so a long one pushed the right half off the end. The right is
packed first now and the left takes what is over.

**And a sidebar title was severed mid-word** - `Chapter 2 - Roadmap: where LACC is and where
it is headi` - because the tree has one column and no horizontal scrolling. Cut deliberately
now, with an ellipsis, so it at least says it was cut.

## Trade-off

**`bind_all` is global.** Every mouse wheel in the window now scrolls the reading panel,
including one over the sidebar tree, which has its own scrolling. In a window with one
scrolling area that is what somebody wants; in a later one with two it will be wrong, and this
is where that will be looked up.

**Wrapping a table makes it a wrapped table.** A wide row folds rather than extending, which
is worse than a horizontal scrollbar and better than being invisible. Tk's canvas can scroll
sideways; every widget in it would have to stop filling the width for that to help, which is a
layout change rather than a setting.
