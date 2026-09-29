# ADR-106 - Ranking by meaning asks before it reaches the engine

## Status

Accepted. Closes the first of the two gaps ADR-105 named and left open: *preparing a question
embeds it before the preview that asks whether to send it*. Reading the code to close it found
the gap wider than it had been named.

## Context

With `embedding_model` set, passages are chosen by meaning as well as by words, and the meaning
half is computed by the engine (ADR-061). Four places ranked before anything had asked:

1. **`ask` and `measure`** prepared the question - ranked the corpus - and only then printed the
   preview and asked `Proceed?`. Somebody who declined had already sent the question.
2. **The window's *Prepare*** ranked when pressed. ADR-085 drew it as
   `[Prepare] -> nothing has been sent`; with an embedding model, the question had been.
3. **Not only the question.** Ranking embeds every quotation that has no stored vector yet, so
   the first question to a corpus sends **all of it** - 1,300 quotations on the thesis's - and a
   question after the corpus grows sends what it gained. `prepare` said the material stayed on
   this machine, which is true only once the vectors are stored.
4. **`sections --about`** ranked a document's sections with no store at all: every run sent the
   question and the opening of every section, asked nothing, and ended with *Nothing was read
   but this document.*

`review` does ask first, but its question counted judgements and did not say that each
paragraph, and every quotation never embedded, goes to the embedding model too.

The preview cannot be drawn without the ranking - which passages, how many set aside - so the
ranking cannot simply move after the confirmation. What can move ahead of it is **knowing what
the ranking would send**. Which texts already have a stored vector is a file on this machine,
read in milliseconds (ADR-061).

## Decision

**What choosing would send is known before it is sent.** The `Retriever` port gains
`would_send(passages)`: nothing for ranking by words; for meaning, the embedding model and how
many of the passages have no stored vector. It is abstract, so a retriever cannot reach an
engine by omission - one that does not say what it sends cannot be built.

**`prepare` stops before sending anything nobody agreed to.** It is told what a person agreed
the ranking may send - nothing, the question alone, or the question and up to so many
quotations - and when the ranking would send more, it returns without ranking and says what it
would send, to which model, reaching which host. **Agreement covers what was shown and not
more**: a corpus that grew between the showing and the agreeing is asked about again.

**The terminal asks, and no is the default.** `ask`, `measure` and `sections --about` print what
ranking by meaning would send and ask `Rank by meaning? [y/N]`. **No ranks by words alone**, on
this machine, and the line that reports the selection says *words*; `Proceed?` still follows,
so nothing has been sent by then either. Two questions, because there are two sendings: the
question to be ranked, and the prompt to be answered. `ask --judge` adds that each reading of
the answer is ranked the same way. `review` says what it embeds in the question it already
asks.

**The window says it beside the button** - chosen on 28 September over a card before every
question. Under the question box, a line names what pressing *Prepare* sends: your question, to
the embedding model, reaching the host the configuration names - or that ranking is by words
and nothing leaves. That line is the preview and the press is the agreement, in the grammar
ADR-085 gave the window. **The press agrees to the question alone.** When quotations have no
stored vector, Prepare sends nothing and draws what they are - how many, to which model - with
a button that sends them and ranks.

## Not decided here

- **Prepare still runs on the window's own thread.** With meaning on it waits for the engine:
  4.5 seconds measured on 28 September for the question alone against the thesis corpus, and
  the length of embedding the whole corpus the first time. `docs/05-assurance.md` said the
  window never freezes on an engine; it now says this one does.
- **The ranking call is not in the audit trail** when the prompt that follows is declined.
  That is ADR-105's second gap - commands and calls that leave no record - and the next record.

## Consequences

- One more keystroke in `ask`, `measure` and `sections --about` when an embedding model is
  configured. None in the window, except the first time a corpus is ranked or after it grows.
- Declining meaning in the terminal still gets an answer, ranked by words, and says so. A person
  who wants words every time says it once, in the configuration.
- `prepare`'s docstring and ADR-085's drawing of *Prepare* said nothing was sent. Both are
  corrected, and `docs/05-assurance.md` moves the row from *gap* to *held by test*.

## Trade-off

**A line is a weaker confirmation than a question.** It is read once and then pressed past, and
a person who has stopped reading it has agreed to something they no longer see. What it has
over a card before every question is that it costs nothing on the tenth question of a thread,
and what it keeps is the thing that matters: nothing leaves before a sentence that says so has
been on the screen, and anything beyond the question itself - a corpus's worth of quotations -
still needs a press of its own.
