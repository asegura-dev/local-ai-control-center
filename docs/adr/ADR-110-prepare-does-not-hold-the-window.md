# ADR-110 - Prepare does not hold the window

## Status

Accepted. Closes the gap ADR-106 named and `docs/05-assurance.md` has carried since: the
window's Prepare waited for the engine on the window's own thread.

## Context

ADR-085 put the one call that goes to an engine on a worker, for a reason it stated plainly: a
long call on the Tk thread stops the window repainting, and Windows retitles it *Not
Responding* - an operating system telling somebody this program crashed when it had not. Send
has run that way since. Prepare did not: it ranked the corpus on the window's thread.

Without an embedding model that is a local read of the corpus. With one it waits for the
engine: **4.5 seconds** measured on 28 September for the question alone against the thesis's
corpus, and as long as embedding every quotation the first time a corpus is ranked - 48 seconds
for 654 quotations when that was measured (ADR-061), and the thesis's corpus holds 1,300. For
that long the window was frozen, and the assurance chapter's row said it never froze on an
engine.

## Decision

**Prepare runs on a worker that touches no widget**, the way Send does. What it needs from the
widgets - the question, what the thread carries - is read on the window's thread before the
worker starts; the worker puts the prepared question in a queue, and a look at the queue from
inside `after` draws it. Nothing it does can raise into Tk: an unexpected failure becomes a
refusal, drawn where the preview would be.

**While it works, a card says so and counts the seconds**, and says that nothing goes to the
model that answers until the button that appears after is pressed.

**Only the latest press is drawn.** Pressing Prepare again, or the card's own button, starts a
new preparation for that corpus; an earlier one that finishes later is not drawn over it.

**Leaving the section drops the preview.** A change of section destroys the frame it would be
drawn in, and the preparation's result is not kept - unlike an answer, which ADR-099 keeps: a
preview is cheap to make again and soon stale, and what the ranking sent, if it reached the
engine, is already in the trail (ADR-108).

## Consequences

- The window repaints, scrolls and changes section while a corpus is ranked.
- An answer that arrives while a Prepare works redraws the corpus, and the preview is dropped
  with the rest of the drawing; Prepare is pressed again.
- `tools/measure_window.py` waits for a preview instead of expecting it at once, and drives a
  slow preparation: the seconds move, and leaving mid-way draws nothing into the next section.
- `docs/05-assurance.md`: "asking an engine never freezes the window" is held again, for
  Prepare too.

## Trade-off

**A Prepare left behind still finishes.** Its ranking goes to the engine and is recorded, and
its preview is thrown away. Stopping it would need a way to take back a request already made,
which ADR-085 declined to pretend to have for Send; there is none here either.
