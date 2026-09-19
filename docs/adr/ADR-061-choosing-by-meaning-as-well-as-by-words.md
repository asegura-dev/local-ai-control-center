# ADR-061 - Choosing by meaning as well as by words

## Status

Accepted, with the measurements taken and one of them smaller than hoped.

## Context

The tool verifies quotations well and cannot yet assemble a piece of writing worth
submitting. Four measured reasons, and this record addresses two of them:

| | |
|---|---|
| **Eight of 24 documents never entered the window** - the largest and most central | ADR-042 |
| **Selection is half noise** - 51% relevant by keyword count, 46% by section heading | ADR-046 |
| One quotation in five is invented | marked, not fixed here |
| Journal names are fabricated 12 times in 24 | needs Crossref, not this |

The first two are the same problem seen twice. `WordRetriever` ranks by rare words shared
with the question, which cannot see that *nodal staging* and *lymph node involvement* are the
same subject - and the eight refused documents were refused because whole documents were being
sent when passages would have done.

**A question in Spanish finds almost nothing.** Pinned by a test: two of 654 quotations, on a
corpus written in English by a person who thinks in Spanish. That is not a corner case here.

## Decision

**An `Embedder` port, and dense retrieval as a second `Retriever` behind the port that
already exists.** ADR-050 made selection a port so a measurement could decide rather than a
fashion, and wrote that implementations *"may rank by words, by embeddings, or by something
not invented yet"*. This is that, and it needs no change to `Retriever` or `Selection`.

**Embeddings come from the engine that is already configured**, over Ollama's embedding
endpoint. No new Python dependency: this project installs with seven packages and refused a
deep-learning stack once already for the same reason (ADR-053). The model is named in the
configuration like every other, never defaulted.

**`bge-m3`**, for a reason this corpus produced rather than a benchmark: it is multilingual,
so a question asked in Spanish reaches quotations written in English. A stronger
English-only model would be the better choice for a corpus nobody queries in another language,
and this is not that corpus.

**Fusion by Reciprocal Rank Fusion, not by a tuned weight.** RRF sums the inverse of each
ranking's position, so the word ranking and the dense ranking combine with **no coefficient to
choose**. This project has a rule about numbers invented to make examples look right, and a
blend weight is exactly that. The constant in RRF is published (k=60, from the paper) rather
than fitted here.

**The word ranking is kept, not replaced.** It is exact, free, and it is what finds a rare
term - a tracer name, a cohort size - that a dense model smooths away. The fused retriever
holds both.

**Vectors are stored beside the corpus and recomputed only for what changed.** The cost
embeddings add is recomputation on every run, not memory: at 654 quotations the vectors are a
few megabytes and searching them exhaustively is exact. **What is not decided yet** is the
file format, because that decision needs the measurement below - the same discipline that
stopped MinHash being built for a cost that was not there (ADR-054).

## Measured

All on the real corpus: 654 quotations, 26 documents, `bge-m3` on the configured engine.

| | |
|---|---|
| embedding the whole corpus, cold model | **91 s** |
| the same, warm | **48 s** |
| vector width | 1024 |
| searching all 654 exhaustively, in pure Python | **137 ms** |
| the cache: size on disk, and time to load it | **2.7 MB, 72 ms** |

**The cost is embedding, not searching**, and that decided the design. An index structure
would optimise 137 milliseconds; persistence saves 48 seconds. So the vectors are a file and
the search is exhaustive and exact - the same reasoning that stopped MinHash being built for
a cost that was not there (ADR-054). A second question against the same corpus took **2.8
seconds** end to end.

**Cross-language is where it is decisive.** A question in Spanish against the English corpus:

| | on topic, of the first eight |
|---|---|
| word ranking | ~3, and the top hits were noise - a ten-year survival figure, a different disease state |
| meaning | **8** |

Every one of the eight was about PSMA PET/CT sensitivity for nodal detection. The existing
test pinning *"two of 654"* for the word ranking is still true and still passes; what it says
about the reason to build this is now satisfied.

**In English it is better, and not by enough to publish a rate.** On one question it found as
its first result a sentence the word ranking missed entirely - *"18F-PSMA-1007 PET/CT
demonstrated excellent sensitivity (94.7 %)"* - and about seven of its first eight were on
topic against about six. One question is a story. Four would be a measurement, and this is not
one.

**And a caution that came out of running it end to end.** With a 32k window the budget admits
**218 of 654 passages** - a third of the corpus goes in whatever the ranking says. So at this
size retrieval decides the *order* and the *discards*, not membership, and the gain is smaller
than the framing above implies. It becomes decisive when the corpus grows: at 50 references
the same budget admits perhaps 15%.

**Fusion was not measured against either ranking alone.** It is in the code, it is tested for
mechanism, and no figure says it beats them. That is the honest state, and ADR-046 is the
reason to say so - it published a prediction that failed in the direction of the thing being
built.

## Consequences

- `ports/embedder.py` joins the five existing ports; one adapter, using the engine.
- `lacc ask` gains a retriever the configuration names. Word ranking stays the default until
  a measurement says otherwise.
- The corpus gains a companion file of vectors, ignored by git like the workspace.
- A question in Spanish becomes answerable against an English corpus, which is the whole
  reason for the model choice.

## Trade-off

**It adds a model to install and a file to keep in step.** Embeddings computed against one
model are meaningless against another, so the file records which model made it and is
recomputed when that changes rather than silently mixed.

**Dense retrieval is a judgement, like the entailment judge and unlike the quotation check.**
It ranks by similarity in a space nobody can inspect, and it will be confidently wrong in ways
keyword matching is not - a passage about the wrong organ that uses all the right words around
it. What protects against that is unchanged: every passage it chooses was already verified
against its document, and every selection still says how much it set aside.

**It does not fix the eight refused documents by itself.** Retrieval chooses among passages
that were extracted; a document that never entered the window has no passages. Reading those
in passes is what puts them in the corpus (ADR-045), and retrieval is what makes a corpus that
size usable afterwards. Both are needed and this is one of them.


## A defect found while testing it

`_fill` returned its choices in **corpus order** rather than ranked order, with a docstring
inventing a reason for it. Two things depended on the order and both were broken: a model
reads a prompt from the top, and `FusedRetriever` reads each ranking's positions out of
`chosen` - so RRF was combining the word ranking with the order the corpus happened to be
assembled in, which is no ranking at all.

It was found by a test that failed for the right reason after being rewritten, having first
been written to pass for the wrong one: it listed the passages nearest-first, so corpus order
and ranked order agreed and the assertion proved nothing. The test now hands the corpus in
reverse.
