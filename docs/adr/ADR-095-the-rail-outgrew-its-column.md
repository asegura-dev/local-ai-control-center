# ADR-095 - The rail outgrew its column, and only on somebody else's window

## Status

Accepted. Reported as *"there is no bar to scroll down with on the left"*, which is exactly
what it was.

## Context

The rail began as a list of names. Since ADR-092 it carries three group headings above
thirteen sections, and since ADR-093 a configuration picker above those. Each was added on
its own and each was reasonable on its own. Nothing ever asked what the column was now
worth in pixels.

## What was actually wrong

Measured on the machine this was written on, at 125% scaling:

    window  1600 x 1025
    rail     267 x  988
    the rail needs 968 pixels and has 988
    short by: 0
    y=923  h=45  CTkFrame  req=89     <- the theme block

**It fit, by twenty pixels.** And the theme block at the bottom was drawn at **45 pixels
when it asked for 89** - half a control, on the machine where nobody would report it.
Anything shorter than this window loses whole sections off the bottom with no way to reach
them.

This is the pack order of ADR-092 again, one release later and one direction over. There,
`side="bottom"` packed after three `side="left"` siblings became a fourth column. Here, a
fixed block packed after an expanding sibling gets whatever the expanding one left, which is
nothing. **The general shape: a container divides what it has in the order things were
packed, so whatever must not shrink has to be packed before whatever may.**

**And the wheel would not have helped.** Scrolling is bound with `bind_all`, and the handler
scrolled the right-hand panel wherever the pointer was. So even once the rail became
scrollable, every notch went to the other column - a rail too long to fit could not be
scrolled at all.

## Decision

**The theme block is packed first, and the section list takes what is left.** The list
becomes a `CTkScrollableFrame`; the headings and buttons are parented to it rather than to
the rail.

**The wheel scrolls the column the pointer is over.** The rail's right edge
(`rootx + width`) against the event's `x_root` decides which of the two gets the notch.

## Consequences

Driven with `tools/measure_window.py` at three heights, on the same display. The height is
asked in logical pixels and the toolkit scales it by 125%; the tallest request is capped by
the screen:

| asked | got (physical) | of the rail's content shown | sections out of reach |
|---|---|---|---|
| 1025 | 1175 | 100% | none |
| 775 | 969 | 81% | none |
| 575 | 719 | 43% | none |

What the rail drew *before* at a short window was not measured - the defect was found at the
default size, as the clipped theme block above, and fixed before a short window was tried.
So this says the rail is reachable now; it does not say how many sections were lost before.

**The first figures written for this record were wrong.** A scratch script reported the three
requests as if they were physical heights, and showed 90%, 52% and 21%. It had also been
built without the command and prompt lists the real window receives. The table above is the
tool's, which anyone can re-take; the scratch figures are not repeated anywhere.

**The first draft of the tool was wrong too, the other way.** It asked whether each section
was visible with the list scrolled to the end, and reported the top two missing - which is
what a scrolled list is. It asks at five scroll positions now, and a section counts as out of
reach only if none of them shows it.

**The wheel, driven on 25-sep.** Every figure above moves the list by code. On 25-sep the
window was driven with real mouse input: a notch over the rail scrolled the rail and left the
panel alone, and a notch over the panel did the reverse - what this record decided holds.
The same test found that a notch moved three pixels and that the panel had no scroll region
at all, which is ADR-096.

**The check that found it is now a tool rather than a scratch file.** ADR-092 reported *"over
eleven sections and 656 labels: 0"* and left the script that said so outside the repository,
so the figure could not be re-taken. `tools/measure_window.py` asks both questions - what
runs off the right, and what cannot be reached at the bottom - at whatever heights it is
given.

## Trade-off

**A scrollable rail hides that there is more.** A list that fits shows you its own length; a
scrolled one does not, and 21% of a rail is four sections with eight silently below. The
alternative was fewer sections or a smaller minimum window, and both cost more.

**It is still measured at one display's scaling.** Same bound as ADR-092, and the same
answer: incomparably better than looking, and the fix is scaling-independent.

**This is the second instance of the pack-order shape and it is still not checked by the
gate.** A window needs a display, so the tool is run deliberately rather than by `pytest`.
The honest statement is that the rule lives in two ADRs and a tool somebody has to remember
to run.
