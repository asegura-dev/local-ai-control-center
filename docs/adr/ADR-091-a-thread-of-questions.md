# ADR-091 - A thread of questions, not a conversation

## Status

Accepted. It delivers what was asked for and refuses the mechanism that was asked for, so
most of this record is the difference between the two.

## Context

Asking one question at a time works and is tiring. The second question is always about the
first: *and what about node size?*, *does anyone disagree?*, *where does that number come
from?* Each one starts over - retrieve, send, read, and none of what was established survives
into the next.

The request was for a chat, and for good reason: with a corpus behind it, asking feels like
talking to something that has read your library. **It has not.** Nothing was learned, nothing
was fine-tuned, no weight changed. Passages are chosen and shown, every time, and that is
exactly why every sentence still has a document and a page under it. A model that had
absorbed the corpus could not be asked where a claim came from.

That distinction is not pedantry here: it decides what a thread may carry.

## The mechanism that was refused

A conversation puts turn N's **answer** into turn N+1's prompt. That single move breaks the
only guarantee this program makes.

Every quotation is checked against what the model was shown. If turn 1 invents a quotation and
turn 2 is given turn 1's answer, then turn 2's material contains the invention - and the
invention now **verifies**, because it really is in what was sent. The check does not fail. It
confirms. One turn later the corpus can no longer tell you anything about that sentence.

Measured on this project's own bibliography, a 14B model puts a quotation that is not in the
document into about one answer in five. A conversation is a mechanism for laundering those.

## Decision

**A thread carries what was checked, never what was said.**

Each turn:

1. retrieves **freshly** from the corpus for the new question
2. adds the passages that were **verified in earlier turns of this thread**, marked as
   already established
3. sends question + passages
4. checks the answer's quotations against what was sent, as always
5. keeps the ones that were found; discards the prose

**The model's own words never re-enter a prompt.** What accumulates across a thread is a
working set of checked passages - which is strictly more useful than accumulating prose,
because it is the material you will cite.

**The questions carry; the answers do not.** Earlier questions are kept and shown, so a person
reads the thread as a thread, and so a follow-up can be written the way people write follow-
ups. They are *not* put in the prompt either: a question is not evidence, and a model given
its own earlier questions starts answering the conversation rather than the corpus.

**A follow-up is resolved by the person, not by the program.** *"And what about size?"* means
nothing to a retriever. The window shows the thread and the box starts empty; what goes in it
is a whole question. This is the same refusal as everywhere else here - **nothing is guessed**
- and it costs the one thing a chat is pleasant for.

**The thread is not saved.** It lives while the window is open. A thread is a way of working,
not a record; the record is the audit log, which already has every question, every prompt and
every answer, and is hash-chained.

## Consequences

- `features/thread.py`: a `Thread` of `Turn`s, and the rule for what a turn is given. Pure,
  and the only thing in this feature a test can exercise.
- Asking twice about related things costs two retrievals, and the second is cheaper only in
  attention, not in tokens.
- The verified set grows monotonically within a thread. A passage that was checked in turn 1
  is carried into turn 5 whether or not the ranking would have chosen it - which is the point,
  and is also the trade-off below.

## What the first real thread did

Two questions over the 1,129-quotation corpus, through the window:

| | passages sent | of those, established earlier | took | established | invented |
|---|---|---|---|---|---|
| *sensitivity for pelvic nodes* | 219 of 1,129 | - | 19s | 3 | 0 |
| *specificity and false positives* | 226 of 1,129 | **3** | 15s | 2 | 0 |

What the thread carried after two turns, in full:

    [10] s00259-016-3573-4.md, p. 1   18F-PSMA-1007 PET/CT detected 18 of 19 lymph node
                                      metastases in the pelvis...
    [10] s00259-016-3573-4.md, p. 9   the sensitivity of 18F-PSMA-1007 for small lymph
                                      node metastases was approximately...
    eau-5.8-clinical-staging.md p.47  pooled sensitivity and specificity of choline
                                      PET/CT for pelvic LN metastases...
    [1] s00259-022-05806-9.md, p. 1   The average number of false positives was 1.8 per
                                      patient.

**Four passages, each with a document and a page.** Not a summary of a conversation - the
material a paragraph would be written from. And checked: none of the model's prose appears
anywhere in what carried.

## Trade-off

**It is not the thing that was asked for, and it will feel like less.** Typing *"and the
specificity?"* will not work. The honest version of that sentence costs eight more words, and
what it buys is that the answer still has a page number.

**The carried set can crowd out the retrieval.** Every turn adds passages the ranking did not
choose for *this* question, and a budget that admits about 214 of 1,129 has no room to spare.
A long thread ends up answering a new question mostly from old material. The turn count is
shown for that reason, and a thread is cheap to abandon.

**And a person can still launder an invention by hand** - read a flagged quotation, believe
it, and type it into the next question as if it were established. Nothing here can prevent
that. What this removes is the machine doing it silently.
