# ADR-069 - A window that reads

## Status

Accepted. The second view in a project that spent ADR-066 making the first one safe to have a
second of.

## Context

Everything LACC does arrives as terminal text, and most of it should. A list of quotations, a
refusal, a count of tokens: a terminal renders those perfectly and a window would add nothing
but chrome.

**One thing it produces cannot be seen in a terminal, and that thing is new.** A review says
of each paragraph in a draft whether the corpus holds it up, contradicts it, or does not cover
it (ADR-068). That is a document with a second document painted over it, and reading it as a
scrolling report means holding the draft in your head while the verdicts go past.

The other pressure is plainer: not everyone who should be able to read a corpus wants to learn
a command line, and the person this is built for is a researcher, not an operator.

## Decision

**CustomTkinter, in a window of its own, with nothing listening.** Tk ships with Python, the
window talks to Python because it *is* Python, no socket is opened, no page is served, and
PyInstaller packages it without a browser runtime. The material this project protects is
private research; an interface that opened a TCP port on the machine holding it would buy
convenience with attack surface, for a user who is sitting at that machine anyway.

**It reads. It does not run anything.** No skill, no model call, no file written. That is not
timidity: running `review` takes minutes and an engine, and a window that ran it would need
threads, progress, cancellation and a way to report an engine that went away - four new ways
to be wrong, in a view, in the first version. Running stays in the CLI until v3, with its own
record for what a click may set off.

**So a review is read from a file, not produced.** `lacc review --into report.md` also writes
`report.findings.json` beside it, the same way the registry cache sits beside the bibliography
(ADR-067). The window opens the draft and its findings and paints one over the other.

**Three columns, not two.** Sections on the far left, the list for that section beside them,
and what is selected on the right. Four sections, each of them reading something already on
disk: **Reviews**, **Corpora** (what a corpus holds and which documents it came from),
**Documents** (size and the same token estimate the budget uses) and **Configuration** (what
the chosen file declares). The surface stays quiet: what is on it is prose and quotations, and
a tool for reading should look like one.

**Choosing a configuration changes which one is read, never what is in it.** A configuration
declares what may run and where it may reach; editing it is writing, and writing has a preview
and a confirmation everywhere else here. It is not smuggled in through a window because a
window is convenient.

**Themes are data, in a file of the window's own.** `Palette` holds the colours, three are
built in, and a palette written in the YAML replaces one by name - somebody who wants their
own colours should not need a release. The window remembers its theme and which configuration
was last chosen in `.lacc-window.yaml`, hidden inside the workspace: **not** in `Config`,
which is frozen, validated with `extra="forbid"` and describes what may run, and where a
colour has no business being.

That split is also who may write what. **The window's own appearance is the window's and it
may save it**; everything else belongs to the user. A window that quietly rewrote `model:`
would be a window deciding what runs.

**ADR-066 binds this window, and that was the point of doing ADR-066 first.** The rule - *a
view contains no logic* - is extended to cover `window.py` with its own vocabulary of
presentation, because Tk's is not Rich's. **The whole reason the exception list was emptied
before writing a line of this is that a second view doubles whatever the first one got
wrong.**

**Tk cannot be exercised headlessly, and that is designed around rather than apologised for.**
No test can open a window on a machine with no display. Everything worth testing therefore
lives in `features/review.py` and in the findings file - which is read and written by pure
functions with tests of their own - and the window is left thin enough that looking at it is
enough.

**The dependency is optional.** `pip install local-ai-control-center[gui]`. Somebody using the
CLI on a server should not acquire a GUI toolkit, and the package's default install stays what
it was.

## Consequences

- `lacc window` opens it. Everything else keeps working with the window never installed.
- `mypy` gains a narrow override for `customtkinter`, which ships no type information. Named,
  scoped to that import, and the rest of `src` stays `strict`.
- `test_every_module_lives_in_a_layer_that_has_a_meaning` learns a second driving adapter.
- The findings file is a contract now. Written by the slice, read by the window, and a change
  to it is a change to both.

## Trade-off

**Tk will not look like a modern web application**, and pretending otherwise would set up a
disappointment. It gives a dark theme, rounded corners, decent typography and a layout that
behaves. It does not give fine typographic control or animation, and a coverage map drawn on
a `Canvas` is bubbles and boxes rather than a physics-simulated graph. That is the price of
opening no port and shipping no browser.

**A window that only reads will feel incomplete to somebody expecting an application.** It is
deliberate and it is a floor, not a finish: the first version establishes that the interface
is a *view* of the same slices the CLI uses, and once that is true, adding an action is adding
a button rather than adding a second program.

**Two views can still drift**, and no rule prevents that entirely. What ADR-066 prevents is
the specific way they drifted last time - logic living in one of them. If the window and the
CLI ever disagree about what a finding means, the findings file is where the disagreement will
be visible, because both read it.
