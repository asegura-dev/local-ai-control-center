# ADR-085 - A window that runs one thing

## Status

Accepted. It reverses the first sentence of ADR-069, which is why most of this record is
about what stays true rather than what changes.

## Context

ADR-069 opened the window with a rule stated in its first line: **it reads and runs nothing.**
The reason given there is still the right reason:

> A review takes minutes and an engine; a window that ran one would need threads, progress,
> cancellation and a way to report an engine that went away - four new ways to be wrong, in a
> view, on day one.

That was a decision about *when*, argued as though it were a decision about *what*. Eight
sections later the window shows the corpus, the findings, the prompts, the commands, the
configuration and where the work stands - and a person who reads all of that and wants to ask
one question about it has to leave, open a terminal, and retype a path they were just looking
at.

The four ways to be wrong have not gone away. They are now the subject of the record instead
of the reason there is no record.

## Decision

**One command runs from the window: `ask`, against a corpus that is already there.**

Not `collect`, not `review`, not `ingest`, not `resolve`. Asking is the only action in this
program that leaves the workspace exactly as it found it: it reads a corpus, sends a prompt,
and shows what came back. Nothing is written, nothing is converted, no file appears beside
another. If the window's first act of running is also the only one that cannot damage
anything, then a defect in this design costs a wasted minute rather than a corrupted corpus.

**The preview is not a dialog. It is the thing that produces the button.**

In the CLI, `preview_action` prints what would happen and `_confirm` reads a y/n that defaults
to no. A window cannot default a button to no; a button is either there or it is not. So:

    you type a question  ->  [Prepare]  ->  nothing has been sent
                             the corpus is read, its passages are ranked,
                             and what *would* go is drawn: which model, which
                             host, how many passages of how many, how many set
                             aside, how long the prompt is
                         ->  [Send to the engine]  <- this button did not exist
                                                      until the line above was drawn

There is no path from typing to an engine call that does not pass through a drawn preview,
because the control that makes the call is created by the drawing of it. That is the same
guarantee `_confirm` gives, expressed in the only grammar a window has.

**The engine call happens off the Tk thread, and that thread touches no widget.**

Tk is single-threaded and is not thread-safe: a widget written from a worker corrupts the
interpreter's state in ways that surface much later and somewhere else. A forty-second call on
the main thread is worse in a different way - the window stops repainting and Windows retitles
it *Not Responding*, which is an operating system telling the user that this program has
crashed when it has not.

So the worker does one thing: it runs the question and puts the result in a `queue.Queue`. The
window polls that queue with `after()`, and **every widget in this feature is written from
inside that poll**. One rule, mechanically checkable by reading one function.

**Cancel stops the waiting. It does not stop the request, and it says so.**

The button is labelled with what it does. The engine keeps generating, the audit keeps the
record it already wrote, and the answer is discarded unread when it arrives. A control
labelled *stop* that left a model running would be the first dishonest thing in this program,
and this project has spent eighty-four records on the principle that a true sentence is worth
more than a comfortable one.

**A failure is an answer, drawn where an answer would be drawn.**

Engine unreachable, prompt too large for the window, corpus with no usable quotation, question
that matches nothing in it: four outcomes, each of them normal, each of them shown in the same
place and the same shape as a good result. None of them is a dialog box and none of them is a
traceback.

**The window is handed the ability to run one thing. It cannot obtain it for itself.**

`tests/test_layering.py` already forbids what would otherwise be the obvious implementation: a
slice under `features/` may reach only `core` and `ports`, and a section under `views/` only
those plus `features/`. Neither can build an Ollama provider, open an audit log, or call the
cycle. That is not an obstacle to route around - it is the rule doing its job.

So `cli.py`, which is the driving adapter and the one place composition belongs (ADR-029),
builds a single callable - *ask this question against this corpus and give me back what
happened* - and passes it to `show()` beside `check_engine`, which arrived the same way and
for the same reason (ADR-077). If the window is opened without it, the section says the
question box is unavailable and still shows everything else.

**`features/asking.py` holds what is decided**: what a prepared question is, whether it can be
sent and the reason when it cannot, and how a finished run reads as data. It prints nothing,
draws nothing, and is the only part of this feature a test can exercise.

## What the first real run showed

Driven against the real corpus before this record was finished - 777 citable quotations, a
14B model on another machine over Tailscale:

| | |
|---|---|
| passages selected | **214 of 777**, 563 set aside |
| ranking | words + meaning (bge-m3), fused by rank |
| material | about 14,800 tokens |
| answer | drawn after **28 seconds** |
| quotations | **2 of 2 in the passages that were sent** |

Two things the run corrected.

**The waiting text said "about forty seconds" and the measurement said twenty-eight.** A
figure written from memory, in a project whose most frequent defect is exactly that. It now
says what was measured and that a different machine will differ.

**A question about nothing in the corpus was still prepared.** Asked for quantum
chromodynamics in French, the word ranking would have refused - the dense half never does,
because an embedding of anything is near *something*. So the "matches nothing" refusal is
close to unreachable with embeddings on, and the preview's counts are what a person actually
reads to tell a good question from a bad one. That is not a defect of this design and it is
worth knowing: the safeguard here is the quotation check, not the ranking.

## Consequences

- A ninth section, `Ask`, in `views/asking.py`. The window's other eight are unaffected.
- `State` gains the callable, so a section still reaches nothing back through the window.
- The bottom bar's engine check and this share one fact: **nothing reaches the network until a
  person presses something.** Opening the window still contacts nothing.
- A question asked here is audited exactly as one asked from the terminal, because it is the
  same call through the same cycle. The audit does not distinguish the two, and does not need
  to: what was asked, what was sent and what came back are identical.
- **The answer is drawn as the engine wrote it**, labelled lines and all, with no tidying.
  Reformatting a model's output is the first step toward presenting it as the program's own,
  and the checked quotations are shown separately underneath.
- `--judge` is not offered here. One decision per record: it doubles the engine calls and the
  wait, and the reading of its output is the more interesting half of that design.

## Trade-off

**The window can now make a network request, and that is a real widening.** Before this, the
strongest thing that could be said about it was *it reads*. Now the strongest thing is *it
reads, and one button sends one prompt to the host your configuration names*. The second
sentence is still true and still narrow, and it is longer - a property you have to explain is
weaker than one you can state.

**A cancel that does not cancel.** The label is honest, and a person who presses it and then
hears the fan on the other machine keep running will learn that it was literal. The
alternative - no cancel at all - leaves somebody staring at a window with nothing to press,
which is worse, but neither is good.

**Two buttons where one would do.** Every question costs a *Prepare* that a confident user
does not want. That friction is the confirmation; removing it removes the thing this record
exists to protect.

**And the rule ADR-069 stated is now a rule with an exception**, which is a weaker kind of
rule. The honest version is that the window reads, except for one command that writes nothing,
behind a preview, on a thread, with a cancel that admits its limits - and that sentence has to
be defended every time somebody proposes a second exception.
