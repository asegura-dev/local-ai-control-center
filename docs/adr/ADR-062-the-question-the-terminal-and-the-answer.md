# ADR-062 - The question, the terminal, and the answer that was already paid for

## Status

Accepted. Three defects found by one real use, and they compound.

## Context

Asked, in so many words, for a summary of what convolutional networks contribute to nodal
detection - architectures, performance, limitations - `lacc ask --using draft` returned a
paragraph about **radiation dosimetry**. Three separate faults sat between the question and
the answer.

**The question never reached the model.** `prompt_for` builds a declared skill's prompt from
the author's instructions, the fenced passages and the format. It never received the requests.
So the question chose which 218 passages were sent and then stopped: the model got the
passages and a generic instruction to draft a passage of a literature review, and drafted
whatever it liked. Verified in the audit - the prompt contained the word *convolutional* only
because a passage did, and none of *arquitecturas*, *limitaciones* or the question itself.

Not a model wandering off. Nobody had told it the subject.

**A character the terminal could not encode ended the run.** A Windows console defaults to a
legacy code page - cp1252 here - and Rich writes through it, so `console.print` raised
`UnicodeEncodeError` on a greater-or-equal sign. In a corpus of medical papers. Everything
after that call is the part that matters: the quotations checked, the readings judged, the
discards reported. All of it was lost.

**And the answer could not be recovered, because the trail was right not to keep it.** The
run was under `audit_level: standard`, where content is deliberately not recorded (ADR-023).
Sixty seconds of engine time produced an answer that existed for the length of one function
call. The notification even reported the run as finished, which it was.

Each is minor. Together they turn a paid-for answer into nothing, and report success.

## Decision

**A declared skill's prompt carries what was asked.** `prompt_for` takes the requests and
places them after the document, beside the format, for the reason ADR-037 measured: an
instruction thousands of tokens behind the point of generation is one the model has largely
stopped attending to. A skill asked nothing - one over a document rather than a corpus - gains
no empty heading.

**The console is put into UTF-8, and told to replace what it still cannot encode.** A stream
that refuses to be reconfigured - a pipe, a capture, a test harness - is left alone.

**Printing an answer cannot end a run.** `_show` catches the failure, degrades to ASCII, says
the text was altered, and lets everything after it run. Replacing characters is right here and
would be wrong almost anywhere else in this project: this is the last step before a person's
eyes, the answer is already recorded, and a question mark where a sign should be beats no
answer at all.

**The audit level is not changed to compensate.** Recording content by default to survive a
display bug would trade a privacy guarantee for a workaround. `standard` still records no
content; the display no longer needs it to.

## Consequences

- `ask --using <declared skill>` answers the question it was asked. The prompt grows by the
  length of the question.
- A terminal that cannot show a character shows the rest and says so.
- The three built-in corpus skills were unaffected: they put the question in their prompts
  already. Only the declared path dropped it, which is why nothing had caught it.

## Trade-off

**Replacing a character is losing information.** It is bounded - the answer is intact in the
engine's reply, and under `full` in the trail - and it is confined to the one place where
showing something beats showing nothing.

**The question is now in the prompt twice for anyone who wrote it into their skill's
instructions.** Harmless, and better than the alternative of guessing whether an author
already did.

## What one real use found

Three defects, none of which 587 tests had caught, all found by asking the tool a question
somebody actually wanted answered. Two of the three were invisible to every check this
project has: the prompt was well-formed and the run reported success.

**The drafting contract is a fourth, and it is not fixed here.** `draft.yaml` asks for prose
of three to six sentences and *"one exact sentence from the passages that the paragraph rests
on"*. A paragraph of five sentences cannot rest on one, so every draft is under-cited by
construction and the judge flags all of it - 2 of 2 on the rerun, both `neither`, both
correct. Every figure in those paragraphs was checked afterwards and **every one is in the
corpus**: this is missing citation, not invention. The fix changes how a person writes with
the tool, so it is theirs to choose and is recorded rather than taken.
