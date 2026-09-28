# ADR-099 - An answer that arrives while you are elsewhere

## Status

Accepted. Found in the test of 25-sep; built and checked with the engine switched off, against
a stand-in that answers after a delay.

## Context

A question was sent from Ask at 12:27:52 and the section was changed while it was with the
engine. The audit shows the run finished at 12:28:09 with both of its quotations found. Back
in Ask, the corpus was not selected, its thread said *0 questions so far*, and nothing said an
answer had come and gone. **The answer was lost, and only the audit knew it had existed.**

The same test found two smaller faults in the same place. After an answer, the heading still
said *0 questions so far* while the answer under it said *2 established*; and **Start over**
appeared only after choosing the corpus again, so a thread could not be ended from the screen
that showed it.

## What was actually wrong

`_watch` polled for the answer and did two things with it: recorded the turn, and drew it. It
stopped as soon as the widget it drew into was gone - which is what a change of section does
to every widget in the panel. So the turn was recorded only if somebody was still looking.
Drawing and keeping were one step, and leaving the screen cancelled both.

The heading and the button were drawn once, when the corpus was opened, and an answer added
a card under them without drawing them again.

## Decision

- **Keeping is separated from drawing.** The watch runs on the panel's frame, which lives as
  long as the window, and records the turn whether or not anybody is looking. Only **Stop
  waiting** discards an answer - it was already the one thing that said so.
- **When the corpus is on the screen, it is drawn again whole**, so the heading counts the new
  turn and **Start over** is there. Whatever was being typed in the box survives the redraw.
- **When it is not, the answer waits.** Opening the corpus again shows its check and a line
  saying it arrived while you were elsewhere. The corpus's row in the list already counts it.
- **A question in flight survives a change of section.** Opening its corpus again shows it
  still waiting, with the seconds counting and the button that stops the wait.
- **One question per corpus at a time.** A second send while one is with the engine is
  refused on the screen, because the second answer would have taken the first one's place.
- **Start over also stops waiting** for anything in flight: its answer belonged to the thread
  that was just ended.

## Consequences

Checked with `tools/measure_window.py`, which now drives Ask against a stand-in engine that
answers after a delay - no model, no network - pressing the same buttons a person would:

    answered while in another section: kept True, marked unseen True
       back in Ask: heading counts it True, says it arrived elsewhere True, Start over there True
    answered while looking: heading counts it True, draft kept True
    in flight after a change of section: still waiting on the screen True
       a second send while it waits is refused True
       then answered: True
    stopped waiting: answer discarded True, nothing left in flight True
    Start over: thread empty True

**The check was wrong twice before it was right, and both times it blamed the window.** It
typed the draft in front of the question already in the box and compared the result to the
draft alone. Then it came back to a question it believed was still in flight and found it
answered: opening another section counts the whole workspace, which took longer than the
one-second stand-in; and after a slower stand-in was swapped in, the corpus's buttons still
held the fast one they had been drawn with. Each false result is now a comment in the tool.

**ADR-055's rule caught the first version.** The record of a pending question carried two
fields for the widgets its waiting was drawn in, with a default and set by assignment - which
the rule reads as a setting nothing reaches. It was right about the shape: those widgets change
with every redraw and the question does not. They are kept apart, in a map of where each
corpus's waiting is on the screen now.

Not yet seen with a real engine: the stand-in answers in one to five seconds, a real one in
tens.

## Trade-off

**The threads and the waiting live as long as the window.** Closing it ends them, as ADR-091
decided for threads; the audit keeps every question and answer either way.

**One question per corpus is a limit.** Two questions on the same corpus at once would need
two threads or an order between their answers, and neither exists.
