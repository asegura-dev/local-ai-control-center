# ADR-096 - The wheel had nothing to stop against

## Status

Accepted. Found by driving the window with a real mouse, which ADR-095 said had to happen
before its own release and which had never happened before.

## Context

Every figure about scrolling in this project had been taken by moving a list in code:
`yview_moveto`, never a notch of a wheel. ADR-095 said so in as many words - *"that a notch
over the rail scrolls the rail and not the panel is what `_wheel` says, and nobody has
watched it happen"*. On 25-sep the window was driven with clicks and wheel notches sent to
its rectangle as mouse input, and four things turned up that no code path had shown:

- **Ten notches moved the panel 30 pixels.** Reaching the form at the bottom of Workspaces
  took about nine hundred.
- **The wheel went past the content.** On a short section, turning up pushed the heading down
  into an empty band; turning down pushed it off the top.
- **That offset survived a change of section**, so every section opened with its heading
  halfway down the window - which reads as a section that failed to load.
- **The panel's scrollbar filled its track** with 3,957 pixels of content behind it, and
  dragging it did nothing.

The rail, scrolled with the same handler, stopped at its end. That difference was the clue.

## What was actually wrong

A probe opened the real window and asked the panel's canvas what it knew:

    panel <Configure> bindings: 1 - only LACC's _reflow
    Where it stands   scrollregion ''   content 1305 x 1733   canvas 974 tall   yview (0.0, 1.0)
    Workspaces        scrollregion ''   content 1305 x 3957   canvas 974 tall   yview (0.0, 1.0)
    5 notches down: 15 px        40 notches up: origin at -105 and -210
    the rail          scrollregion '0 0 239 651'

**The panel had no scroll region.** `CTkScrollableFrame` keeps its canvas told how tall the
content is through a `<Configure>` binding on the frame itself. `window.py` then bound
`<Configure>` on the same frame to re-wrap text, and Tkinter's `bind` without `add`
**replaces** what was there. CustomTkinter's own widgets refuse that; a scrollable frame is a
plain Tk frame underneath and does not. From then on the canvas believed its content fitted
(`yview` always `(0.0, 1.0)`, hence the full scrollbar), and a canvas without a region has
nothing to stop against in either direction. The rail was never rebound, which is why the
same wheel behaved on one column and not on the other.

**A "unit" was a pixel.** ADR-084 moved the wheel from one unit per notch to three, reading
a unit as a line. On Windows CustomTkinter sets `yscrollincrement` to 1, so three units are
three pixels. Its own handler moves twenty.

**A partial notch was thrown away.** `int(delta / 120)` rounds a precision touchpad's small
deltas to zero, so a touchpad on a Windows laptop would not have scrolled at all. Not seen on
a physical touchpad: measured by sending deltas of 30.

**The general shape: a binding that replaces the toolkit's own.** It is the third defect in
this window that a toolkit's own wiring was silently undone - ADR-092 and ADR-095 were the
pack order - and like those it is invisible until the thing is used.

## Decision

- **The panel's `<Configure>` binding is added, not substituted** (`add="+"`), and so is the
  list's selection binding. The scroll region comes back, and with it the scrollbar and the
  stops at both ends.
- **A notch moves three lines of the text the cards are written in**, which is what the rest
  of the system does. The line is measured from the font at the window's scaling rather
  than written down as a figure, and the step is divided by the canvas's own scroll
  increment, so it holds wherever that is not one pixel.
- **What a notch does not complete is carried**, not discarded: a quarter-notch moves a
  quarter of a notch. The carry resets when the pointer moves to the other column.
- **A column whose content already fits is not scrolled**, as CustomTkinter's own handler
  does, so a short section cannot be pushed into empty space.
- **Changing section, or opening something from the list, starts at the top.**
- **A test reads the window and the views and fails on any `.bind(` without `add`.**
  `bind_all` is left out deliberately: the wheel handler replaces CustomTkinter's two on
  purpose, because with both in place every notch would move the column twice.
- **`tools/measure_window.py` drives the wheel**: pixels per notch in both columns, whether
  the panel stops at both ends, whether a short section moves at all, whether a new section
  starts at the top, and what four quarter-notches add up to.

## Consequences

Driven with `tools/measure_window.py`, which now sends wheel events to the real window, on
the same display at 125%, the panel 974 pixels tall:

| | before | after |
|---|---|---|
| one notch, panel | 3 px | 57 px (three lines of 19) |
| ten notches | 30 px | 570 px |
| turned down to the end of Workspaces | no end | stops at 2,965, where 2,965 + 974 is the content's 3,939 |
| turned up past the top | origin at -105 and -210 | stops at 0 |
| four quarter-notches | 0 px | 57 px, the same as one notch |
| a section opened after scrolling | kept the offset | starts at 0 |
| a section that fits, turned 60 times | slid into empty space | does not move |
| one notch over the rail, at 575 | 3 px | 57 px on the rail, 0 on the panel |

**Restoring the region exposed a second defect it had been hiding.** With a scroll region,
the panel measured what it held - and after Workspaces, Written, Corpora, Documents,
Commands and Prompts all measured about 3,940 pixels while showing a heading. Tk keeps a
frame at its last size when its last child is destroyed, and `_clear` destroys all of them.
Without a region nobody could scroll into that emptiness; with one, everybody would have.
`_clear` now asks the emptied frame for a height of one, and the same sections measure 113
to 132.

**The first run of the new check measured the wrong section.** It chose the longest section
by `bbox` four redraws after opening each one, and got the previous section's figure - which
was the defect above, read as a number. It asks for the content's requested height after a
full settle now.

**Not yet seen with a hand on a wheel.** The figures above are Tk wheel events generated by
the tool. Driven with real mouse input the same morning, before the fix, the wheel showed
exactly the defects this record removes; after the fix the screen had locked, and the real
wheel was not tried again. The window was left open for its owner to try.

The layering rule's vocabulary learned `yview_moveto`, the other half of `yview_scroll`: it
had called the method that moves the panel to its top a piece of logic.

## Trade-off

**Three lines is a choice, not a measurement of anybody's comfort.** It is Windows' default
and it is 57 physical pixels at 125%; a browser moves about a hundred. The figure is one
constant.

**The test is structural and narrow.** It catches `.bind(` without `add` in the window and
the views. It does not catch a replacement made another way - `bind_class`, a `configure`
of a callback - and it does not know which toolkit widgets have bindings worth keeping. It
asks for `add` everywhere because nobody can tell from the call site which ones do.

**The wheel is still driven by a tool somebody has to run**, same as ADR-095: a window needs
a display, and `pytest` does not have one.
