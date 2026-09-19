# ADR-063 - Write dense, and prune

## Status

Accepted. Chooses between three options that were put to the person whose thesis this is, and
builds the part that was missing from the one chosen.

## Context

`draft.yaml` asks for prose of three to six sentences resting on *"one exact sentence from
the passages that the paragraph rests on"*. **A five-sentence paragraph cannot rest on one
sentence.** Every draft is therefore under-cited by construction, and the judge flags all of
it - two of two on a real run, both `neither`, both correct (ADR-062).

The same shape appeared in the capability battery: on both questions the corpus could answer
fully, quotations verified three of three and the judge flagged two of three. The quotation
says *"more sensitive in N-staging"*; the sentence around it says *"pelvic nodal staging"*.

**Every figure in those paragraphs was afterwards found in the corpus.** This is missing
citation, not invention - which is what makes it a contract problem rather than a model one.

Three ways out were put to the author:

| | |
|---|---|
| **A** | one quotation per assertion - maximum verifiability, choppier prose |
| **B** | the paragraph says only what one quotation supports - clean prose, slower going |
| **C** | write dense, and let the judge mark what needs support |

**C was chosen.** The battery is the argument for it: the judge was right in all five
questions, including the three traps, so it can be trusted to mark rather than to be
second-guessed.

**What C was missing.** A flag that says *"this reading is not supported by its quotation"*
sends the writer hunting through 654 quotations for the one that does support it. Pruning
needs the candidates in hand, or it is not a workflow - it is a complaint.

## Decision

**The skill stops promising what it cannot deliver.** The quotation a draft returns is
described as the passage the paragraph is **anchored to**, not the one it rests on. A
description that is structurally impossible to satisfy teaches a reader to distrust the ones
that are not.

**A flagged reading is shown the passages that might support it**, drawn from what was
actually sent and ranked against the reading's own words. Two of them, excluding the one
already quoted.

**They are named as candidates and never as support.** LACC has ranked some sentences; it has
not decided that any of them establishes the claim. This is the discipline ADR-034 set for
`nearest_text`, which reports a match and says plainly that it is not a reconstruction of what
the model meant.

**Nothing is added to the answer, and nothing is removed from it.** The draft is what the
model wrote. The candidates are shown beside it for a person to use or ignore, and no
automatic substitution happens - that would be LACC editing a thesis on the strength of a
similarity score.

## Consequences

- `ask --judge` becomes a usable writing loop rather than a report: draft, see what is
  under-supported, see what could support it, decide.
- The judge will keep flagging most paragraphs, and that is the intended state under C rather
  than a defect. A flag is a prompt to cite, not an accusation.
- `draft.yaml` describes its quotation truthfully.

## Trade-off

**Candidates ranked by similarity will sometimes be wrong**, and they arrive next to a
judgement that is itself a model's opinion. Two weak signals side by side can read as one
strong one. The mitigation is the wording and nothing else: they are labelled as places to
look, the quotation check still decides what is real, and the person still writes the sentence.

**C leaves the under-citation in place by design.** A and B would have removed it structurally
and cost prose or pace. What C buys is that the writing stays dense and the gap is made
visible and fillable; what it costs is that a draft is never citable as it stands. That is the
trade the author chose, and it is written here so a later reader knows it was a choice.


## What the first real use found

The loop works: on a drafted summary of what convolutional networks contribute, the judge
flagged two of three readings and put beside the first the two sentences that would cite it -
*"AI-based method using convolutional neural networks"* from one document and *"U-Net-based
CNNs were trained to identify lesions"* from another. That is the missing citation, served.

**And the second flag offered the same sentence twice.** The candidates were deduplicated
against the quotation and not against each other, and the corpus holds the same sentence in
more than one entry: `without_repeats` drops repeats within one answer, never across the
documents a selection draws from (ADR-054, ADR-058). Two candidates that are one sentence
twice is half a tool.

Fixed on the words rather than on the source, because the same sentence in two documents is
two entries and one citation to offer. It is worth naming that this is the third time the
distinction between *a repeat within an answer* and *a repeat across a corpus* has cost
something.
