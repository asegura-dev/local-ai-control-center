# ADR-065 - Two writers, one round trip

## Status

Accepted. Found by assembling a real corpus and looking at the file, not by any check here.

## Context

`corpus.py` opens by saying it is uneasy about re-parsing generated prose, and answers the
unease with a round trip: *"what the writer produces, this reads back identically"*.

**There are two writers, and the round trip covers one of them.**

| | what it puts on the page line | where the paraphrase goes |
|---|---|---|
| `collect`, via `_collected_markdown` | `p. 7 - verified` | its own line below |
| `corpus`, via `_assembled` | `p. 7 - it was placed` | **the page line** |

`parse_corpus` is written for the first. Given the second, its verdict pattern matches the
paraphrase, files it as `recorded_verdict`, and leaves `claim` empty. The writer then - quite
correctly, because ADR-042 exists to stop a recorded label being trusted - does not carry a
recorded verdict forward.

So the chain is:

1. `collect` writes a corpus. Good.
2. `corpus` reads it correctly and writes it **in the other format**.
3. `corpus` reads *that* back. The paraphrase lands in the verdict.
4. `corpus` writes again, and the paraphrase is gone.

**Assembling a corpus twice strips the meaning from every quotation in it**, silently, while
reporting success: *"832 quotations from 2 files -> citas-v2.md; 723 are in their document"*.
Every figure in that line is true.

It was found by adding one document to a real corpus of 654 quotations and noticing that the
result was **35 KB smaller with 178 more quotations**. Nothing else would have shown it: the
counts were right, the quotations were right, the file parsed.

## Decision

**One format, written by both.** `_assembled` writes what `_collected_markdown` writes: the
page line carries the **standing**, and the paraphrase goes on its own line below.

The standing comes from the re-check rather than from the file being read, which is ADR-042's
rule and does not change: `verified` when the quotation is there and its page is known, *in
the document, page not determined* when it is there and unplaceable, and the refusal when it
is not. A quotation whose document is no longer in the workspace could not be re-checked, and
says that instead of claiming either.

**The round trip is tested through both writers, and twice.** Once is not enough here: the
first assembly of a `collect` corpus looked correct, and the loss only appears on the second.
The test assembles, parses, assembles again, and asserts the paraphrase is still there.

**The reader recognises the older shape rather than losing it.** The standings are a closed
set this project writes - `verified`, *in the document, page not determined*, the refusal, and
*not re-checked* - so anything else on that line is a paraphrase from the older assembler.
Telling them apart is reading a format this project produced, not guessing at one, and it is
what lets a corpus written by that version keep what each quotation was taken to mean.

Without it the fix would have been forward-only: every paraphrase already written in the old
shape would still have been dropped the next time the corpus was assembled. On the real corpus
that is 654 of them.

## Consequences

- A corpus can be assembled repeatedly without losing what each quotation was taken to mean.
- A corpus written by the older assembler is read correctly and comes out in the new shape
  with its paraphrases intact. Measured on the real one: 832 of 832 carry a paraphrase, where
  the first attempt at the same merge produced a file 35 KB **smaller** with 178 more
  quotations and every paraphrase gone.
- `docs/04-measurements.md` gains this as the kind of defect that reports success.

## Trade-off

**The assembled file gets longer**, by one line per quotation, and the page line stops
carrying the paraphrase a reader could see at a glance. That is the price of the two files
being the same file, and the paraphrase is one line below rather than gone.

**Nothing repairs a corpus already stripped.** Recognising the older shape recovers a
paraphrase that is still on the page line; it cannot recover one already written as an empty
line. The corpus this was found on had not been stripped - the loss was in the output about to
replace it, and the only thing that caught it was the file size.

## What this says about the checks

The round-trip test is a good test. It was written against the writer that existed, a second
writer arrived later, and nothing connected them. `tests/test_reachable.py` asks whether a
setting can be reached and whether paired calls travel together; it has no way to ask whether
**two functions that produce the same kind of file agree about its shape**.

That question has no mechanical form here yet. What found it was a file being 35 KB smaller
than it should have been, and somebody looking.
