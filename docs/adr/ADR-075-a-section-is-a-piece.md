# ADR-075 - A section is a piece

## Status

Accepted. Measured before it was accepted, which is the only reason it was.

## Context

The window reached eight sections in a day. Counted before deciding anything:

| | |
|---|---|
| `window.py` | **763 lines, 28 methods in one class** |
| methods that were `_list_X` / `_show_X` for a section | **16 of 28** |
| places to edit to add a section | **4** |

The four are the menu tuple, the router, the selection handler, and a pair of methods. **Get
three of the four right and the section appears in the menu and does nothing at all** - no
error, no empty panel, just a button that does not respond. That is the shape of defect this
project has found seven times by using the tool, and here it was designed in.

`cli.py` arrived at 2,610 lines by exactly this route: one more command, two more helpers, no
moment at which it was worth stopping.

## Decision

**A section is declared, not wired.** `Section` carries a name, a listing and what to show for
a selection, and the window iterates over a tuple of them. Adding one is adding a piece; there
is no second place to remember, so there is no half-added state to be in.

**The window is the frame and knows nothing about the contents.** Three columns, a theme, a
configuration picker and routing. It hands each section two things - a way to put rows in the
sidebar, a way to draw in the panel - and the state it is allowed to know.

**Sections are grouped by what they read, not one file each.** `views/workspace.py` for the
four that read the material, `views/program.py` for the three that read the program itself,
`views/records.py` for the documentation. Eight files of forty lines would be tidier and
worse: these are related, and a reader looking for "how is a corpus shown" should find it
beside "how a review is shown".

**A section is given its state rather than reaching for the window.** A section that could
reach the window could reach anything on it, and the whole point of this arrangement is that a
section is a piece rather than a part of a whole.

**`Sidebar` and `Panel` are protocols.** Tk cannot be exercised headlessly, and the way around
that is to keep the describable part free of it: a section's contract can be checked without a
display.

**The layer is enforced.** `tests/test_layering.py` gains `views/`: a section may reach
`features/` - which is what it draws - and `core`/`ports` for the contracts that cross, and
nothing else. No cycle, no CLI. And a second test asserts every declared section has a name
and can list, so a malformed one fails the gate rather than appearing as a dead button.

## What the cut measured

| | before | after |
|---|---|---|
| `window.py` | 763 lines, 28 methods | **330 lines, 17 functions** |
| sections | 8 methods pairs inside one class | **8 declarations across 3 modules** |
| places to edit to add one | 4 | **1** |

`views/` is 585 lines across five files, so the total grew - the frame did not shrink by
magic, it moved. What changed is that the part that grows with each section is now the part
that is separate.

## Consequences

- `lacc window` behaves identically. Nothing a user sees changed.
- The scroll defect was fixed in the same pass: Tk delivers the wheel to the widget under the
  pointer and a label does not pass it on, so a panel scrolled only while the pointer was over
  the gaps between cards. The wheel is now bound on every child.
- `tools/measure.py` learns the layer, and says plainly that the names it lists under a view
  are not defects on their own - the test holds the list of which are allowed.

## Trade-off

**This is a refactor, and this project's roadmap records six consecutive releases of
defensible refactors that advanced nothing.** The defence is the count above: the risk was not
aesthetic, it was that a section could be added half-way and look fine. If that had not been
measurable, this should not have been done.

**A protocol is not a test.** `Sidebar` and `Panel` describe what a section is handed, and
nothing checks that the window's implementation of them behaves the way a section expects. The
window still cannot be tested; what changed is how much of it there is to not test.

**One more indirection between a button and what it draws.** Somebody tracing a section now
reads the declaration, then the listing, then the painter. That is three hops where it used to
be one method, and it is only worth it because the alternative was `cli.py` again.
