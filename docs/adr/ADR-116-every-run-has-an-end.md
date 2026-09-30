# ADR-116 - Every run the trail opens has an end

## Status

Accepted. Four findings of the test of 29 September - D11, D14, D19 and the refusal in
`measure` that ADR-107 had named - built on 30 September.

## Context

ADR-107 promised that a run is recorded however it ends, a no included. The Audit section
(ADR-104) shows a run without an end as *no end recorded*, which is what a crash looks like.
The test found four places where the trail still did not tell the truth about how a run went.

- **D11 - a question interrupted left the run open.** Every command opens its run where it is
  about to ask, so that a no is recorded too. But Ctrl+C at a prompt, or the end of the input,
  made the prompt raise `Abort`, which went past every path that records a no. Five runs were
  left open that way in the test's workspace. An `identify` interrupted at its second question
  showed in Audit as *no end recorded*, after it had asked the registry and written the answer.
- **The refusal in `measure`.** When its preview was not allowed, `measure` said so and
  recorded nothing. `run` and `ask` record `run_refused` through the cycle, and `measure`
  meets the same refusal without it. ADR-107 named this and left it open.
- **D19 - time went backwards.** With four writers, 48 of 607 records had a time earlier than
  the record before them. The time was taken before a writer waited for its turn (ADR-109), so
  a writer that waited stamped the moment it started waiting. The chain held; the order the
  times suggest did not.
- **D14 - `identify` said *Nothing was written* when it had written.** Declining the work the
  registry named, or hearing that the registry holds nothing, printed that. But the registry's
  answer had already been kept in `identified.registry.json`, as every answer is. What had not
  been written was a DOI for the document.

## Decision

- **A question has one way in, `_asked`, and an interrupted one is answered no.** Ctrl+C or
  the end of the input is taken as the default, which is no, and said: *Interrupted: taken as
  no.* It then goes down the same path a no goes down, which records the run as declined.
  - All fifteen prompts in the CLI go through it.
  - A test fails if any function other than `_asked` calls `typer.confirm`.
- **`measure` records the refusal its preview meets**, as a run with `run_refused`, holding the
  same detail the cycle records for `run` and `ask`: what was missing and what was out of
  bounds.
- **A record takes its time inside its turn.** The event is made once the turn is held, so the
  times follow the order of the records.
- **`identify` says what it did**: *No DOI was established*, and that the registry's answer stays
  in its file.

## Consequences

- An interrupted `bring` ends as a declined run: `run_started`, then `confirmation_declined`,
  and exit 0.
- A `measure` refused by its preview leaves `run_started`, then `run_refused`.
- Tests:
  - the one way in for questions, read from `cli.py`;
  - the interrupted `bring`;
  - the refused `measure`;
  - the event made inside the turn, read from `system/audit.py`;
  - `identify`'s sentence, which says what was and was not written.

## Trade-off

**Ctrl+C no longer stops the program with an error at a question.** It stops it as a no does,
with exit 0. Anywhere else, Ctrl+C still ends the program as it did. At a question, the
difference between stopping and declining is only in the exit code. Recording the run as
declined was preferred to recording nothing and exiting 1.

**A run interrupted while it works still has no end.** Ctrl+C while the engine answers, or a
closed terminal, ends the process where it stands, and the trail shows the run as Audit shows
a crash: *no end recorded*. That is true of it, and it is left that way.

**The order of the times is kept by construction, not by a clock.** They are UTC to the
second, and two records in the same second share a time. The order that holds is the order of
the lines.
