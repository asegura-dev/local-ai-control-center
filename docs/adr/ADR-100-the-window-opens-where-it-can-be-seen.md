# ADR-100 - The window opens where it can be seen

## Status

Accepted. Found in the test of 25-sep; built with the engine switched off, which this never
needed.

## Context

The window asks for 1280 by 820 logical pixels and lets Windows choose where to put it. On
the machine it was tested on - a 1920 by 1200 screen at 125%, with a work area of 1920 by
1140 once the taskbar is taken out - that is 1618 by 1072 physical pixels with its frame. The
first opening landed at y=96, with its bottom 28 pixels under the taskbar. **The second
landed at y=224, with 156 pixels below the screen**: no status bar, no theme picker, and no
sign that anything was missing. Windows offsets each new window from the last, so the longer
somebody works, the further down it opens.

## Decision

- **The window is placed, not left to be placed.** At start it asks the system for the work
  area - the screen without the taskbar - and opens at its top, centred across it.
- **The default size is a ceiling, not a demand.** Where the work area is shorter or
  narrower than 1280 by 820 at the display's scaling, the window is made to fit it, leaving
  room for its own frame: 60 physical pixels, against 47 measured at 125% for the title bar
  and the lower border together.
- **Where the system cannot say**, anywhere but Windows or on a failed call, the window asks
  for its default size and is placed as before. Nothing is guessed about a screen nobody
  measured.
- **The arithmetic is a function of numbers** in the slice that owns the window's appearance,
  tested without a display. The call to the system lives with the rest of what the program
  reads about the machine.

## Consequences

Opened twice in a row with `lacc window`, the frame read from the system both times:

| opening | before | after |
|---|---|---|
| first | y=96, bottom 28 px under the taskbar | 160,0, 1618 by 1072 - bottom at 1072 of 1140 |
| second | y=224, 156 px below the screen | 160,0 again: no cascade |

`tools/measure_window.py` now reports it too, before anything resizes the window:

    client area at 169,38, 1600 by 1025; work area 0,0 to 1920,1140: inside

The arithmetic has its own tests, which need no display: the screen it was found on, a 1366
by 728 one, a taskbar across the top, 150% scaling, and a screen narrower than the window.

## Trade-off

**Only the primary screen.** A second monitor with a different work area is not consulted;
the window opens on the primary one, which is where it opened anyway.

**The frame allowance is a figure, not a measurement taken at run time.** Tk cannot say how
tall the title bar is before the window is on the screen, and moving a window after it has
appeared is visible. 60 pixels covers the 47 measured at 125%, with room for the larger frame
a higher scaling draws; 150% was not measured.
