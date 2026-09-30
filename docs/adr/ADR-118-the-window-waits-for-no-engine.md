# ADR-118 - The window waits for no engine, and says when one finished

## Status

Accepted. Two findings about the window: one from the test of 25 September, and one the test
of 29 September confirmed after a change. Built on 30 September, and checked by driving the
real window.

## Context

- **Engines held the window.** Asking an engine what it holds ran on the window's own thread.
  An engine that accepts a connection and never answers makes the check wait its full eight
  seconds (measured: 8.1 s against a local socket that accepts and stays silent). On 25
  September, `localhost` on the laptop did exactly that. The tester saw no notice while it
  waited, and an empty card after. ADR-085 moved Send off the window's thread, and ADR-110
  moved Prepare; Engines was the last place that asked an engine from it.
- **Stop waiting kept saying the engine may still be generating.** After *Stop waiting*,
  the card read *The engine was not told and may still be generating*, and still read that
  8 s after the engine had answered. The watch ended at the stop, so nothing was left to
  notice the answer arrive. The button had meanwhile been disabled, which was the change the
  second test saw.

## Decision

- **Engines asks on a worker**, as Send and Prepare do.
  - The press returns at once.
  - A line counts the seconds: *asking http://… 3s*.
  - Whatever came back is drawn when it arrives: the answer, or that the engine did not
    answer and why.
  - A failure inside the check is drawn as a failure rather than raised into Tk, where it
    left the card empty.
  - Leaving the section drops the result.
- **A stopped question is still watched, only to say when the engine finished**: *Stopped
  waiting. The engine finished after 2s; its answer was discarded unread.* The answer is
  taken off the queue and not looked at. The corpus is free for another question at once, as
  it was.

## Consequences

Driven in the real window with `tools/measure_window.py`, against stand-ins:
- a two-second check that does not answer: the press returned in 0.30 s, the line counted
  and moved, and the card said *unreachable* and why;
- a question stopped and then answered: the card says the engine finished.

The window has no pytest here; it is driven. The suite covers everything below the window,
and it is unchanged.

## Trade-off

**A check nobody waits for still runs to its end.** Leaving Engines does not stop the worker.
Its request finishes or times out, and the result is dropped. That costs a request that was
already made, and nothing else.
