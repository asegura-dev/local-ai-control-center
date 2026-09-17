# ADR-053 - Whether the reading follows from the words

## Status

Accepted, and graded. The measurement is at the end and it changes how the verdict is
reported: the three-way label is unreliable and the binary under it is not.

## Context

ADR-026 drew a boundary this project has never crossed: *it can tell you a quotation's words
are in the document, and it cannot tell you the paper means what the model says it means.*
Every claim carries a paraphrase, and no paraphrase has ever been checked.

That gap stopped being theoretical. Drafting a passage from verified quotations, a 14B
produced this:

> **Paragraph:** *"…with PSMA PET/CT showing superior performance compared to choline PET/CT.
> For example, PSMA PET/CT had a pooled sensitivity of 62% and specificity of 92%, whereas
> choline PET/CT had a sensitivity of 62% and specificity of 92%."*
>
> **Quote:** *"pooled sensitivity and specificity of **choline** PET/CT for pelvic LN
> metastases were 62% … and 92% …"*

The quotation is real and verified. The quotation is about **choline**. The paragraph
attributes choline's figures to PSMA, and then contradicts itself by giving both the same
numbers. **Every control this project has passed it.**

There are 548 verified quotations in a real corpus, each with a reading nobody reviewed.

## Decision

**A port asks whether a quotation entails its claim**, answering with one of three labels:
entails, contradicts, or neither.

**The first implementation uses the engine that is already there**, with the shape enforced
by a schema (ADR-052) so the answer can only be one of the three. No new dependency: this
project installs with seven packages, and adding a deep-learning stack to check paraphrases
would cost every user of it whether or not they use this.

**It is not the same kind of check as the substring search, and is never reported as if it
were.** The quotation check compares strings: it is exact, cheap and has no opinion. This is
a model judging a model, which is a weaker guarantee with a different failure mode, and the
output says so in those words. A run reports *"the quotation is in the document"* and
*"the reading was judged to follow from it"* as two separate sentences, because they are two
separate strengths of claim.

**It marks, never removes.** A claim whose reading does not follow is flagged for a person,
not dropped. Dropping would be this project deciding a paraphrase is wrong on the word of a
model, which is the authority it has spent fifty records refusing to take.

**No figure from it is published until it is graded against a fixture whose answers were
written first** - the same demand ADR-044 made of the quotation check, for the same reason.
Pairs where the claim follows, pairs where it contradicts, and pairs where the claim is about
a different subject entirely, like the one above.

**A dedicated entailment model stays possible behind the same port.** A purpose-built NLI
model is smaller, faster and likely better at this than a general model answering a prompt.
It is not first because it costs a dependency the measurement has not yet justified.

## Consequences

- `ports/entailment.py` joins the four existing ports; one adapter, using the engine.
- `lacc corpus` and `lacc ask` can report which readings were judged not to follow.
- Every claim costs one additional engine call when this is on, so it is off by default and
  asked for.

## Trade-off

**This is a model checking a model, and that is a real weakening of what LACC promises.**
Until now every check here was mechanical: a substring, a hash, a path resolution. This one
has an opinion and can be wrong in both directions - passing a bad reading, and flagging a
good one. Naming it as a judgement rather than a verification is the whole of the mitigation,
and it is not much.

**A flagged reading that is actually fine costs the reader time and trust.** A checker that
cries wolf gets ignored, and then it is worse than absent. This is the argument for grading
it against known answers before it is believed, and for marking rather than removing.

**It moves the boundary ADR-026 drew, and only a little.** It can say a reading does not
follow from its quotation. It cannot say whether the claim is true, or whether the paper is
right, or whether the quotation was fairly chosen from its context. The first of those is
outside any tool; the third is a gap this opens and does not close - a quotation can entail
its paraphrase perfectly and still misrepresent the paper it came from.

## Graded (v1.4.0)

Eight pairs, labelled by a person before the judge existed. A 14B, temperature zero, four
seconds a pair.

| question | right |
|---|---|
| which kind of problem is this? | **6 of 8** |
| **should a person look at this?** | **8 of 8** |
| false alarms on readings that were fine | **0 of 3** |

Both errors are the same shape, and the reasoning behind them was correct. On the pair this
port exists for - a quotation about choline read as PSMA - it answered `contradicts` where the
answer is `neither`, explaining: *"The sentence refers to 'choline PET/CT', whereas the
reading mentions 'PSMA PET/CT'. These are different."* **It found the problem and misnamed
it.** The same happened on a single-centre finding widened into a claim about the method in
general.

**So the three-way label is a hint and the binary is the finding.** Reports lead with "a
person should read this before citing it" and give the label beside it, because the
distinction between *says otherwise* and *does not settle it* is where this judge is weak and
the distinction between *fine* and *not fine* is where it is not.

Eight pairs is not a measurement of anything general. It is enough to say the label is
weaker than the binary, which is what the reporting now reflects, and not enough to publish a
rate. Over 548 claims this costs about thirty-six minutes.
