# ADR-088 - How far the nearest quotation is

## Status

Accepted. Coverage has been on this roadmap since v1 and deferred three times, each time on
the same condition: **a gap measured over an incomplete corpus is a false gap.** Two of the
three measurements taken before building it killed the design that was written down, and the
one that survived is not the one that was planned.

## Context

The plan was clustering: group the corpus, show the groups, call a small group a gap. Before
building it, three instruments were measured against twelve real questions from this thesis,
with a thirteenth deliberately outside the subject as a floor.

**First: the ranking already built.** Count the documents behind the top twenty passages.

    7 to 11 documents, for every question asked, including the control

A top-N ranking fills N whatever it is asked. The number measures the retriever, not the
corpus, and "paediatric bone sarcoma chemotherapy" drew on eight documents of a prostate
bibliography. **Refused.**

**Second: shared words.** Count the quotations sharing three significant words with the topic.

| passages | documents | topic |
|---|---|---|
| 0 | 0 | paediatric bone sarcoma *(the control)* |
| 0 | 0 | inter-reader variability among nuclear medicine physicians |
| 0 | 0 | histopathology as the reference standard |
| 28 | 6 | radiation dosimetry of 18F-PSMA-1007 |

It differentiates, and the control comes out zero. But **inter-reader variability comes out
zero too, and the corpus is not silent on it** - it holds *"the corresponding sensitivity for
the human readers was 77% on average"*, which shares no three words with the question. That is
a false gap, reported by the tool, about the user's own corpus. **Refused.**

**Third: distance by meaning**, over the vectors already cached beside the corpus.

| nearest | topic |
|---|---|
| **0.49** | paediatric bone sarcoma chemotherapy *(the control)* |
| 0.54 | histopathology as the reference standard |
| 0.54 | prostate cancer incidence and mortality in Mexico |
| 0.60 | inter-reader variability among nuclear medicine physicians |
| 0.63 | external validation on an independent cohort |
| 0.66 | radiation dosimetry of 18F-PSMA-1007 |
| 0.69 | sensitivity of PSMA PET for pelvic lymph node metastases |
| **0.75** | deep learning segmentation of PSMA PET lesions |

The control is the floor. The ordering is the one a person would give. And the topic the word
test called absent sits at 0.60 - **above the control, below everything well covered**, which
is what "thin" should look like. This one holds.

## Decision

**`lacc coverage --against <corpus> --topics <file>` reports how far the nearest quotation is
from each topic, orders the topics by it, and decides nothing.**

**No threshold.** This project has a record of a threshold that would have been wrong in the
direction that costs most (ADR-054), and a cosine number has no meaning on its own: it depends
on the embedding model, the language and the length of what is compared. So nothing is called
a gap. The topics are ordered and the numbers are printed.

**A control topic is required.** One line of the topics file must be marked as deliberately
outside the subject, and the report shows it as the floor. Without it the numbers are
unanchored, and a reader would supply an anchor from somewhere - usually from what the number
would have to be for the corpus to be fine. It is the same reason a selection must report what
it set aside.

**It refuses to run without an embedding model, and says why with the measurement.** Word
overlap is available and would produce a report that looks the same and is wrong: it called
inter-reader variability a gap in a corpus that speaks to it. A coverage report built on words
would invent gaps in the one place a false gap is most expensive - a bibliography a thesis
rests on.

**The nearest quotation is shown, not just its distance.** A number saying a topic is thin is
a claim to check; the sentence that came closest is how you check it in three seconds. Same
discipline as `nearest_text` when a quotation is not found: report the match and say plainly
what it is (ADR-034).

## Consequences

- Fase 4 is answered, and not by clustering. Two designs were written down, measured and
  dropped; what shipped is the third.
- Measured on this bibliography, two real gaps: **histopathology as the reference standard**
  and **Mexican epidemiology**, both at 0.54 against a floor of 0.49.
- `docs/04-measurements.md` gains the two refuted instruments. They are the useful half.

## Trade-off

**It tells you what is thin, never what is missing.** LACC has no knowledge of the field
beyond the documents you brought; a subject absent from your corpus and absent from your
topics file is invisible to it, and always will be. Anything else would be the model's memory,
which this project exists to refuse.

**A cosine number is not an interval and nobody should read it as one.** 0.60 against 0.54 is
an ordering, not a doubling of anything. The report prints the control on the same page for
exactly this reason, and it will still be quoted out of context one day.

**And the ordering rests on one embedding model.** Change `embedding_model` and every number
moves. The report names the model and the date, and a comparison across two models is
meaningless - the same limit the vector cache already enforces by refusing a foreign file.
