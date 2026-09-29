# ADR-108 - Every place that embeds is named, and every embedding is recorded

## Status

Accepted. Finishes what ADR-107 left: the ranking's own calls to the embedding model. With it,
everything this program sends to an engine or a registry leaves a record, and a test names
every place that sends.

## Context

ADR-106 made ranking by meaning ask before it sends; ADR-107 made `review` and `coverage`
record what they embed. What was still unrecorded is the ranking itself:

- **`ask` and `measure`** embed the question - and, the first time, the quotations never
  embedded - once `Rank by meaning?` is answered yes. The question's run is opened later, after
  `Proceed?`, and may never be: a no there leaves a declined run with no word of what the
  ranking sent.
- **The window's Prepare** does the same, and a Prepare is often followed by no Send at all: the
  preview is read, the question rewritten, Prepare pressed again.
- **`sections --about`** embeds the question and every section's opening.
- **`ask --judge`** ranks each flagged reading against the passages to offer what might carry
  it, and that embeds the reading.

And nothing checked that a new place would be recorded. `REACHES_THE_ENGINE` names every place
a prompt is completed and fails the suite for a new one (ADR-059); embeddings and registry
requests had no such list, which is how four commands went unrecorded long enough to be named
in ADR-105.

## Decision

**A ranking by meaning is a run of its own.** It has its own agreement - `Rank by meaning?`, or
the line beside Prepare - and it is often not followed by the question it was for. Recording it
inside the question's run would put it in a run that may never exist; recording it as a run
means every ranking that reached the engine is in the trail, when it happened. The run is
`rank_by_meaning`, says what it was for (`ask_corpus`, `sections`), and holds one
`texts_embedded`: the model, where it was reached, and how many texts of which kind - the
question, the quotations or section openings never embedded. The question itself is content: a
digest always, the words only under `full` (ADR-105). A ranking that did not come back ends in
`run_failed` with the engine's message.

**`prepare` says what its ranking sent.** A prepared question carries what went to the engine to
rank it - set whenever the ranking reached the engine, whether it came back or not - so the
terminal and the window record the same thing from the same value, and neither has to work out
afterwards whether a ranking happened.

**`ask --judge` records its candidate rankings in the question's run**, where they happen: after
the answer, inside the run the person agreed to, as a `texts_embedded` counting the readings.

**Every place that sends is named.** `REACHES_THE_EMBEDDER` names each `.embed(` call in the
source with what records it, and `REACHES_THE_REGISTRY` each `.about(` call; a new place fails
the suite until somebody says how it is recorded. And an entry whose place is gone fails too,
in all three lists, so none of them can go on describing code that moved.

## Consequences

- A question asked by meaning shows in the Audit section as two runs: `rank_by_meaning`, then
  `ask_corpus`. A Prepare that was never sent shows as the one.
- The window's Prepare is tested through the composition the section is handed, without Tk:
  a press that sends nothing records nothing, and one that sends is a run at once.
- Counts in a record are plural - `questions`, `quotations` - because a count named `question`
  would share a key with the question's words and be dropped with them under `standard`. The
  record refuses such a count rather than lose it quietly.
- `docs/05-assurance.md`: "every call that completes a prompt is accounted for" becomes every
  call that completes a prompt, embeds a text or asks a registry, held by test.

## Trade-off

**Two rows for one question.** The Audit section lists a ranking and then the question, and a
thread of ten questions is twenty rows. The alternative - folding the ranking into the question's
run - would have been tidier on the screen and wrong about the Prepare that was never sent, and
about the ranking that happened before a question was declined: exactly the events this record
exists to keep.
