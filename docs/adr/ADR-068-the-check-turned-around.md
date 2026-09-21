# ADR-068 - The check, turned around

## Status

Accepted. Nothing new is invented here. Every part already exists and points the wrong way.

## Context

Everything this project verifies, it verifies about **text a model produced**. A quotation is
checked against the document it came from; a reading is judged against the quotation under it;
a corpus records which of its own claims survive re-checking.

That is the right thing to build first, because a model is the thing most likely to be wrong.
It is not what a person writing a thesis needs most.

**The writing is theirs.** They have the data, the cohort, the model they trained and the
argument. What they need is not another writer: it is somebody who reads what they wrote and
says *"this sentence is not supported by anything in your sources"* - which is what a
supervisor does, and what nobody has time to do on every draft.

The pieces for that are all here and all aimed at the generated side:

| piece | what it does today |
|---|---|
| `parse_corpus` | reads 832 collected quotations, 699 verified with a page |
| `Retriever.select` | ranks passages by meaning against a question (ADR-061) |
| `Judge.judge(claim, quotation)` | says whether a quotation supports a reading (ADR-053) |

Turned around, those three answer: **for this paragraph I wrote, is there anything in my own
sources that holds it up?**

## Decision

**`lacc review <draft> --against <corpus>` reads and reports. It writes nothing and changes
nothing.** Revision already exists and is a different act with a different risk (ADR-025);
mixing them would mean a tool that tells you a sentence is unsupported and then rewrites it,
which is how an unsupported sentence becomes a *fluent* unsupported sentence.

**The unit is the paragraph.** A sentence is more precise and produces far more noise, and it
is the wrong unit besides: scientific prose carries its references per paragraph, not per
clause. A paragraph is what a reader cites and what a reviewer objects to.

**Three answers, and the third is the one that needs care.**

- **supported** - something in the corpus was judged to hold it, and that quotation is named.
- **the corpus says otherwise** - a quotation was judged to contradict it. Reported first,
  because it is the one that can put a false statement in a thesis.
- **nothing in your corpus holds this** - and that is *all* it means.

**"Unsupported" is not "false", and the wording says so every time it appears, not once in a
legend.** A paragraph can be true, correct and excellently argued while resting on a paper
that is not in the corpus - which on a bibliography of 24 papers is the common case, not the
edge case. A tool that let those two read alike would be worse than no tool, because it would
teach the user to distrust correct sentences.

**Only prose is judged.** Headings, code blocks, tables and anything too short to assert
something are passed over and counted, so the report says what it looked at rather than
implying it looked at everything.

**What it costs is shown before it runs.** Each paragraph is judged against its best few
candidates, so a draft of twenty paragraphs is on the order of sixty judgements. That is
minutes, not seconds, and a person should know that before starting rather than after.

**The judge's own grading travels with the output.** Graded on eight labelled pairs it got
*should a person look at this* right 8 times out of 8, and the three-way label right 6 times
(ADR-053). So the report leads with **look at this / no need** and prints the finer label
beside it, exactly as `--judge` already does.

## Graded on a draft whose answers were written down first

Five paragraphs, each with its correct answer decided **before** the run, against the real
corpus of 723 usable quotations.

| what the paragraph said | expected | reported |
|---|---|---|
| a fixture disclaimer, asserting nothing about the domain | uncovered | uncovered |
| PSMA PET/CT is more sensitive than conventional imaging for nodal staging **and that is what drove its adoption** | supported | **uncovered** |
| choline PET/CT is more sensitive than PSMA for nodal detection | contradicted | **contradicted** |
| PSMA detects essentially all nodal metastases, near 100% sensitivity | contradicted | **contradicted** |
| Mexican reimbursement policy has been evaluated in cost-effectiveness analyses | uncovered | uncovered |

**The one that disagreed with the prediction was the prediction's fault.** The corpus holds
*"PSMA PET/CT is more sensitive in N-staging as compared to MRI, abdominal contrast-enhanced
CT or choline PET/CT"* - which holds up the first half of that sentence and says nothing
whatever about what drove adoption into staging pathways. The paragraph claimed more than its
support establishes, the judge declined to call that supported, and it was right.

That is the failure this project has named from the start and measured before: a quotation
about *"more sensitive in N-staging"* under a sentence about *"pelvic nodal staging"* -
real, checkable, and narrower than the source supports. **The author of the test paragraph
did not notice while writing it**, which is the entire argument for the feature.

**And the run found a defect in the report, which is now fixed.** A finding of "nothing
covers this" named no candidates, so a reader could not tell whether their support had never
been retrieved or had been retrieved and rejected - and those call for opposite responses:
collect more, or rewrite the sentence. The report now prints what was ranked closest and
judged, which is ADR-034's rule applied one level up: report the match, decide nothing.

The run cost about fifteen judgements over five paragraphs and finished in under two minutes
against a 14B over Tailscale.

## Consequences

- A person can ask of their own draft the question this project could only ask of its own
  output.
- `features/review.py` holds the pure half: splitting into paragraphs, deciding which ones
  assert something, and writing the report. The slice rule of ADR-066 applies from the start.
- The retrieval step means a corpus with embeddings configured answers much better than one
  without, for the reason already measured: ranking by shared words reached about three
  relevant passages of eight where meaning reached eight (ADR-061).

## Trade-off

**This is a judgement, not a measurement, and it is the second feature built on one.** Every
other control in this project compares strings or walks a hash chain. This asks a model about
meaning, over a candidate set chosen by another model's embeddings, which means two fallible
steps in series: a paragraph whose support exists in the corpus but ranks below the cut is
reported as uncovered.

Printing what was considered makes that **visible rather than invisible** - a reader who sees
three candidates none of which is their source knows the ranking missed it, and a reader who
sees their source listed knows the judge declined it. It does not make it go away. Neither
does it help when the support ranks fourth: what is not printed cannot be recognised as
missing, and the number of candidates is a budget, not a guarantee.

**It will flag correct writing.** That is the intended failure direction - a tool that missed
unsupported claims would be worse than one that over-reports - but it has to be said plainly,
because a reviewer that cries wolf gets ignored, and an ignored check is decoration.

**It cannot tell you a source is wrong.** The boundary that has never moved: this says whether
your sources hold your sentence up, not whether your sources are right (ADR-026).
