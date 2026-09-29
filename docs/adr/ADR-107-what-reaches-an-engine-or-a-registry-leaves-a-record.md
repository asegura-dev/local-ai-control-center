# ADR-107 - What reaches an engine or a registry leaves a record

## Status

Accepted. Closes the second gap ADR-105 named: `review`, `resolve`, `identify` and `coverage`
reach an engine or the network, and none of them recorded that it ran. Three of its choices
were made on 28 September by the person whose trail it is.

## Context

The trail is how a person reads what was done in a workspace: the Audit section draws it run by
run (ADR-104), and `lacc verify` says whether it holds. Four commands were outside it.

| | reaches | writes |
|---|---|---|
| `review` | the engine: three judgements per paragraph, and each paragraph to be embedded | a report and its findings, with `--into` |
| `resolve` | Crossref: DOIs, and a contact address when one is written in the configuration | the answers it received, and a bibliography |
| `identify` | Crossref: the DOIs a document prints, or the one named | the answers it received, and `<document>.doi.json` |
| `coverage` | the embedding model: the topics, and every quotation never embedded | a report and its numbers, with `--into` |

A day of reviewing and resolving left nothing in the Audit section, and `verify` said the trail
held - which it did, about a story with that day missing.

And two commands that do record did not record a no. `ask` opened its run after `Proceed?` and
`measure` after `Run this N times?`, so a declined question left nothing, where a declined `run`
has left `confirmation_declined` since ADR-008.

## Decision

**Each of the four records a run in the shape every other run has.** `run_started` names the
command as its action; the run ends in `run_finished`, `confirmation_declined` or `run_failed`;
in between it says what it reached and what it wrote. The Audit section already reads runs in
that shape, and learns only that `run_failed` is a failure. A run opens where the command is
about to ask or act. A command refused before that - a file not in the workspace, a switch off
- prints why and records nothing, as an argument error never has.

**What reached a registry** is `registry_asked`: which registry, how many DOIs were sent, and
whether a contact address went with them. The DOIs are counted as they leave rather than as
announced, because a DOI the registry does not hold is retried with what extraction stuck to
it cut off, and each cut is a request of its own (ADR-083).

**Three choices, made by the person whose trail this is:**

- **The contact address is recorded as sent or not sent, never as the address.** The trail is
  not a place for it. None is configured today, so none is sent.
- **The DOIs are listed only under `audit_level: full`, and always counted.** A DOI is public;
  the list of them is a bibliography, which says what somebody is reading.
- **A no is recorded**, as `confirmation_declined` - in these four, and in `ask` and `measure`.

**What reached the engine.** `review` records its judgements the way `ask --judge` does: a row
per judgement by digest, the verdicts counted, the judge's reasons only under `full` (ADR-059),
and the draft and the corpus by name and digest. `review` and `coverage` record
`texts_embedded`: the model, where it was reached, and how many texts of which kind went.

**What was written** is `file_written`, with the path and its digest, for every file these four
leave: reports, findings, kept answers, bibliographies, an established DOI.

## Not decided here

**A refusal in `measure`.** When its preview is not allowed - a permission missing - `measure`
exits saying so and records nothing, as before; `run` and `ask` record it as `run_refused`,
through the cycle. It is not a no somebody said, which is what this record is about.

**The ranking's own calls.** `ask`, `measure`, the window and `sections --about` embed a
question when ranking by meaning (ADR-106), and none of them records that it did. It is the same
record, `texts_embedded`, and it is the next one - with a test like the one that names every
place a prompt is completed, so that a new place that embeds without saying how it is recorded
fails the suite.

## Consequences

- The Audit section shows `review`, `resolve`, `identify` and `coverage` as runs, each with how
  it ended, and a declined `ask` or `measure` as declined.
- `RememberedRegistry` keeps the DOIs it sends. What a command announced and what it sent can
  differ, and the record carries what was sent.
- Four new kinds of record - `registry_asked`, `texts_embedded`, `file_written`, `run_failed` -
  and `dois` joins the details kept only under `full`.
- A failed registry request is recorded without its message, which can name the DOI that
  failed: the failure is recorded, the bibliography is not.
- `docs/05-assurance.md`: "every meaningful execution is audited" moves from *gap* to *held by
  test* for these four; the ranking's calls stay a gap until the next record.

## Trade-off

**A no now takes two records in a trail a person reads.** A thread of questions declined one
after another reads as a column of declined runs in the Audit section. That is what `run` has
recorded since ADR-008, and it was chosen here over a trail that says only what was done: a
question that was prepared and not sent is part of what happened, and the absence of a record
cannot be told apart from the absence of the event.
