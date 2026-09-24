# ADR-092 - What a screenshot showed, and what a check now says instead

## Status

Accepted. Eleven screenshots, four defects, and the third of them had survived two fixes
because it is invisible on the machine it was written on.

## Context

Text running off the right edge of the window has been reported three times and fixed twice
(ADR-084). It kept coming back. What follows is why, and what replaced *looking at it*.

## What was actually wrong

**The line along the bottom was a column on the right.**

    rail    x=0     w=267
    side    x=267   w=412
    panel   x=679   w=671
    bar     x=1350  w=250   h=37

`side="bottom"` spans the window only while the cavity is whole. Packed after three
`side="left"` siblings, the bar became a fourth column against the right edge - so it took
**250 pixels of reading width**, and the half of it that says what the workspace holds was
never drawn at all. `_bar`'s own docstring said *"packed before the columns claim the rest of
the window"*; `__init__` called it last.

**And `wraplength` was scaled twice.** CustomTkinter multiplies every dimension handed to it
by the display scaling. `winfo_width` returns physical pixels. So a room measured at 547 on a
125% display was set as a wrap at **684**, in a label **599** wide:

| | |
|---|---|
| `wraplength` set | 547 |
| what the toolkit used | 684 |
| width the label had | 599 |
| width the text needed | **656** |

**At 100% scaling the two numbers are the same and nothing is wrong**, which is why two fixes
missed it and why it only ever appeared in somebody else's screenshots.

Two more, both visible in the same pictures. A section with nothing to choose from left a
quarter of the window standing empty beside it, which reads as something failing to load. And
eleven section names in a flat list read as eleven unrelated things.

## Decision

**The bar is packed first.** One line moved.

**Room is divided by the widget scaling before it becomes a `wraplength`.** The measurement
is in physical pixels and the toolkit wants logical ones.

**A section with no rows hides the middle column**, and the panel gets the width - 1,305
pixels instead of 643.

**The rail is grouped, and a section declares its own group.** Three headings: what you are
doing, what you are doing it with, and what the program is. Ordering them is
`views/section.py`'s job rather than the window's, because choosing an order is deciding
something and a view does not (ADR-066) - which the layering rule said out loud when the
function was written in the wrong place.

**And the bar counts documents the way everything else does.** `features/status.py` counted
every Markdown file, so it said **61 documents** where the same workspace held 28 - a corpus
counted as a document, a backup counted as a document, a coverage report counted as a
document. ADR-090 named this module as the one classifier left out and said so in its
trade-off. It was invisible while the text was off the edge of the screen, and wrong the
moment it appeared. It asks `core.kinds` now, like the other two.

**The test that pinned it has been corrected**: it asserted two documents for one paper and
one corpus.

## Consequences

- **A check replaces the eye.** `reqwidth > width` on a label *is* "the text runs off to the
  right", and it can be asked of every label in every section at whatever scaling the machine
  has. Over eleven sections and 656 labels: **0**.
- The panel went from 643 pixels to 893 with a list beside it, and 1,305 without.
- The left half of the bottom bar is on screen for the first time.

## Trade-off

**The check runs against this display's scaling and no other.** A defect at 150% would not be
caught by running it at 125%. It is still incomparably better than looking, and the fix it
found is scaling-independent.

**Hiding the middle column moves the panel when you change section.** Content jumps sideways
between a section with a list and one without, which is worse than a fixed layout for someone
flicking between them and better for everyone else.

**And three groups is a judgement.** *Coverage* could be material rather than work; *Reviews*
could be either. The grouping exists to make eleven names scannable, not because the taxonomy
is right.
