# ADR-050 - Choosing what to send

## Status

Accepted.

## Context

A corpus collected from a real bibliography holds 654 quotations and is about thirty
thousand tokens. The window it would have to enter is 24,576. **The thing this project was
built to produce cannot be read by the thing it was built on.**

Reading in passes does not help. Passes traverse one document exhaustively because every
page of it is wanted; a question asked across a library wants a handful of passages and
nothing else. Traversal and selection are different mechanisms and conflating them is how
an hour of engine time gets spent to answer one question.

So something has to choose what goes in the prompt. That is the first thing in LACC that
discards material on the user's behalf, and this project has measured twice what happens
when selection goes wrong:

| how passages were chosen | on the subject asked about |
|---|---|
| pages with the most keyword mentions | 51% |
| pages under the matching section headings | 46% |

The second was predicted to beat the first and did not. Both were bad. Neither told anybody
what it had left out.

There is a worse failure available. Asked to cover twenty-four documents a model covered ten
and **named none of the fourteen it dropped**. A selection whose misses are invisible is the
shape of failure this project exists to refuse.

## Decision

**Selection is a port, and its first implementation uses no model and no network.** Ranking
by the words a person gave is deterministic, explainable and free. An embedding model may
well do better; nobody here has measured that it does, and a port means the measurement can
decide rather than the fashion.

**Whatever is not sent is counted and reported, always.** A retriever returns what it chose
**and how much it set aside**, and the answer that follows says so. This is not a courtesy:
a selection that hides its discards turns a partial answer into a confident one, which is
the failure mode of every wrong figure in this project's own record.

**Selection happens over quotations that were already checked**, not over raw documents. The
corpus is the input, so anything retrieved has already been found in the document it names.
The alternative - retrieving from raw text and checking afterwards - would put unverified
passages in front of a model and verify only what it echoed back.

**A synthesis skill may cite only what was retrieved.** Its quotations are checked against
the documents they came from exactly as `extract_claims` is, and a quotation it produces
from outside the retrieved set fails that check. The model may reason; it may not remember.

**The question is the user's words, never the standing context.** ADR-041 withheld the
standing context from `extract_claims` so that knowing what a thesis argues could not make
it favour the claims that fit. Retrieval is the same hazard with a shorter fuse: a query
built from the thesis would retrieve the passages that agree with it, and every one of them
would verify.

## Consequences

- `ports/retriever.py` joins the three existing ports; `adapters/` gains a keyword
  implementation with no dependencies.
- `lacc ask` takes a question and a corpus, shows what it selected and what it set aside,
  and asks only after confirmation like every other run.
- The audit records how many passages were considered, how many were sent, and the question.
- An embedding adapter is a later decision, made against a measurement.

## Trade-off

**Ranking by words will miss a passage that is about a subject without naming it**, and that
is exactly the failure measured at 51% and 46%. This decision does not fix relevance; it
makes the discarding visible and puts a seam where a better ranker can go. Claiming more
would repeat the prediction that was announced before it was taken and turned out false.

**Reporting the discard count invites ignoring it.** A line saying "412 passages were not
sent" is easy to skim past, and somebody will. It is still better than the alternative, which
is that nobody could have known.

**This is the first component that decides what a model does not see.** Every control in
LACC until now either refused or reported; this one chooses. The line held is that it chooses
by a rule the user can read, from material already verified, and says what it left behind. If
a later version ranks by something nobody can inspect, that is the sentence it has to argue
with.
