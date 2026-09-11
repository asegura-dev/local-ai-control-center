# ADR-039 - A library is read one document at a time

## Status

Accepted. Narrows [ADR-025](ADR-025-writing-and-several-documents.md), which allowed
several documents in one prompt.

## Context

The work this project exists for is writing from a bibliography - thirty papers, not one.
ADR-025 let a skill take several documents, each fenced separately, in a single prompt. That
is right for comparing two papers and wrong for a library, and the arithmetic says why
rather than any judgement about it.

One seven-page paper is about ten thousand tokens. At a 32,768-token window the prompt
budget is 24,576, so **two papers fit**. At 131,072 - which no model here can run, since the
cache alone would be 24 GB for a 14B - nine fit. Thirty papers are three hundred thousand
tokens, twelve times the available budget.

No model size changes this. Parameters do not buy context, and context is bought in VRAM: a
70B at a 128k window needs about 80 GB before any document is loaded. Measured on the
hardware here, the 32B model already runs 45% outside the card and takes seventeen times
longer than the 14B, while verifying fewer quotations.

There is also a correctness argument, and it is the stronger one. With several documents in
one prompt, a model can attribute a quotation from paper A to paper B, and the check will
**verify** it - because the quotation is genuinely present in the text it was given. Mixing
documents creates a failure the grounding check cannot see.

## Decision

**`lacc collect` runs a skill across many documents, one at a time, and assembles the
results.** Each document gets the whole window to itself, and each quotation is checked
against the document it claims to come from.

**Cross-attribution stops being possible rather than being caught.** One document per run
means the source of a quotation is not a thing the model can get wrong - it is a fact about
which run produced it. That is the same move as ADR-031: stop asking a model a question the
system can answer itself.

**One preview, one confirmation, naming every document and the destination.** The same shape
`measure` established: the human sees what would be read and what would be written, and
approves the whole traverse. Each document's run is audited separately, because each one is
a document sent to an engine.

**It collects only skills that check their quotations.** The artefact is a body of claims
whose provenance is verifiable; collecting unchecked prose would produce a long file nobody
can trust more than they trust the model. `extract_claims` qualifies and nothing else
currently does.

**The output never overwrites.** Like ingestion and revision, a destination that already
exists ends the run.

**A document that fails does not end the traverse.** Thirty papers with one unreadable file
should produce twenty-nine papers of results and a note, not nothing. What failed is
recorded in the collected file and in the audit.

## Consequences

- `lacc collect extract_claims <paths> --into <file>` produces a Markdown file grouped by
  source, each claim with its quotation, the page LACC located, and whether it verified.
- Thirty papers run in about six minutes on the hardware here, against not running at all.
- ADR-025's several-documents-in-one-prompt remains, and is now documented as being for
  comparing a handful rather than for traversing a library.
- The collected file is the first artefact LACC produces that is an input to writing rather
  than an answer to a question.

## Trade-off

The model never sees two papers together, so it cannot notice that one contradicts another.
That is a real loss and it is the thing a library most wants. Accepted for now because the
alternative does not fit in any window that exists, and because a claim corpus is the input
that makes such a comparison possible later - across thirty papers it can be done against
the collected claims rather than against the documents.

Thirty runs send thirty prompts, which is thirty times the engine time of one. Accepted:
they are ten seconds each, they can be left running, and the notifier exists for exactly
this.

The collected file is generated, and a generated file invites being treated as a source. It
is not one: every claim in it is the model's paraphrase with a checked quotation attached,
and the quotation is what carries authority. The format puts the quotation first for that
reason.
