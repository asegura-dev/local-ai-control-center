# Chapter 4 - What this project measured about itself

This chapter exists because the measurements were more interesting than the code, and
because most of them were wrong first.

LACC is a tool for not being deceived by a language model. The recurring finding is that a
tool built for that is, itself, something you can be deceived by - and in a specific
direction. **A check that fails closed reports its own limits as the thing it was built to
catch, and nothing inside the check can tell the difference. Only looking at what it
rejected can.**

Everything below was measured against a real bibliography on real hardware. Where a figure
was published and later corrected, both are shown, because the correction is the finding.

## Eleven wrong figures, and which way each one leaned

| Reported | What it actually was | Fixed in |
|---|---|---|
| The model is inconsistent between runs | Temperature was never sent; the engine sampled at its own default of 0.8 | ADR-033 |
| A third of quotations do not verify | A third could not be placed on a page. They were in the document | ADR-042 |
| The model fabricated two quotations | The PDF held `sensi- tivity` across a line break; the model had quoted faithfully | ADR-034 |
| The model extracts very few claims | The output format was stated 9,000 tokens before the point of generation | ADR-037 |
| A quotation was not in the paper | A running header had been extracted into the middle of the sentence | ADR-036 |
| Twenty-two more fabrications | Extraction had written `A c c o r d i n gt o`; spacing, not words | ADR-046 |
| **Zero fabrications in 237 quotations** | **48 of 237, of which 44 are absent in any form tried** | ADR-042 |
| Choosing sections by their headings would raise relevance | It did not: 46% on topic against 51% for the cruder method it replaced | measured, below |
| The corpus has near-duplicate quotations between documents | It has none. Every repeat in it is inside one document, and there are six | ADR-054 |
| A schema the engine enforces, shipped and documented | Nothing in the program could switch it on. Six tests passed by building the object the program never builds | ADR-055 |

Six of these made the model look worse than it was. The seventh was the correction to that
pattern, published in the same release that introduced it, and it overshot: it credited a
model that had invented forty-four quotations. **Knowing you are biased in one direction
does not make the next figure unbiased.**

The eighth was not the tool's, and belongs here because it has the same shape. A script
written to summarise the corpus reported that `collect` silently omitted documents it had
refused. It does not - every refusal has its own section naming the token count and the
budget. The script's filter dropped lines beginning with an asterisk, and `**Not collected.**`
begins with one. A blind spot in the measuring instrument was reported as a defect in the
thing measured.

The ninth is different from all of them, and is kept because of it: **nothing was measured
wrong.** A prediction was announced before being taken, it favoured the thing being built,
and it was false. Section headings were expected to select relevant pages better than
counting keyword mentions; they selected slightly worse. The figures below say how much.

**The eleventh is not a figure about a model at all. It is a feature counted as delivered
that did not exist.** ADR-052's schema was built, released, described in the changelog and
cited from a decision record, and `enforce_shape` had no flag, no configuration key and no
field in a skill declaration. All seven places that build a plan left it false, so no schema
was ever sent. Six tests covered it and passed, because **they built the plan object
directly** - and the program never builds it by hand; it calls `plan`, which was the part
with nothing in it.

It is the second instance of that shape. `ask_corpus` was tested through a skill that
constructs it directly, was absent from the registry, and failed on its first real launch with
the suite green. **Coverage of a type is not coverage of a path**, and the question neither
suite asked is one sentence long: *what in the program sets this?* If the answer is "a test",
the feature is not there (ADR-055).

The tenth is the ninth's twin and it cost more, because it had been written into a plan as a
premise rather than as a prediction. The plan's next piece was approximate deduplication, on
the stated grounds that the corpus held near-duplicates between documents. Nobody had looked.
**It holds none** - all 654 quotations, all 26 documents, zero pairs across a document
boundary - and the entire exact comparison it was to be an approximation of takes 133
milliseconds. What it does hold is six repeats inside a document, of which equality was
already catching three. A sentence stated as a fact in a planning document is a figure with no
measurement behind it, and it is harder to notice than a wrong number because it never looked
like a number.

## What was tested rather than reasoned about

**Prompt injection: both attempts worked.** The fence's docstring claimed that markers
"hold no user-supplied text, so nothing read from a file can forge a fence". Two documents
were put through a real model at temperature zero. One said *ignore all previous
instructions*; the model obeyed and produced no summary at all. One carried the closing
marker followed by a new instruction; the model obeyed that too. The markers hold no user
text - the content between them does (ADR-038).

The fix is a control rather than a request: the markers are removed from document content,
so a document cannot end its own fence. Everything else in that area is detection, reported
to a person and never acted on alone, and the documentation says so.

**Hidden text: four techniques tried, four extracted, three detected.** Text drawn in an
invisible rendering mode, at zero size, positioned off the page, and white on white were all
captured into what a model reads. The first three are detected and reported. **White on
white is not**, and that is written down rather than left out, because a control whose gaps
are unlisted is worse than one whose gaps are known (ADR-040).

The complication is that rendering mode 3 is exactly what a scanned document's OCR layer
uses. A scanned paper is a hundred per cent invisible text and entirely correct. LACC
therefore reports a proportion and refuses to judge it.

**Seven safety claims, checked by running them.** Six hold: the workspace boundary refuses
`..`, absolute paths, Windows junctions, device names and alternate data streams; an audit
failure aborts the run; the input ceiling is enforced; declining a diff writes nothing;
approving a write without the permission raises. One does not: **records removed from the
end of the audit trail are undetectable**, and nothing inside the file can catch it. It is
the cheapest attack of the set, and the earlier decision had named the sophisticated one and
left this unstated (ADR-043).

That one is now **narrowed and not closed**. A sidecar beside the trail remembers its length,
so truncation is noticed - by a crashed write, a sync conflict, a restored backup or a
careless tamperer. It sits under the same permissions as the trail, because nothing outside
the workspace is touched, so it does not stop somebody who updates both. The notification
carries the head digest and is the only witness that is not on the machine (ADR-049).

## What is measured and currently holds

**The check, graded where the answer was known first.** Twelve quotations were written into
a fixture corpus and marked real or seeded **by a person, before any check ran**: six that
are in their document and six that are not. The check finds six of six and flags none of
the six real ones. The assertion is exact in both directions, because reporting a limit as a
catch is the failure the corpus exists for (ADR-044).

**This is the only figure here whose answer was known in advance**, and it grades the
detector rather than the model. Everything else in this chapter is an observation of a run.

The corpus was itself checked by breaking the code on purpose, since a test that has never
failed has not been shown to test anything. Disabling the spacing fold loses the
letter-spaced quotation; disabling marker stripping loses the one that spans a page break;
disabling normalisation loses both typesetting cases; a check that answered "found" to
everything accepts all six seeded fabrications. Every seed is caught by at least one
mutation, which is what makes the six-of-six meaningful.

Its limits are written into the fixture beside the data: it grades whether a quotation's
words are in a document, never whether what it says is true, and it measures the detector
against the fabrications somebody thought to seed.


**One quotation in five is invented.** On 24 papers of a real bibliography, a 14B model at
temperature zero produced 237 quotations; 48 are not in the document they cite, and 44 of
those are not present in any form tried - not stitched from separate sentences, not
reworded. The check catches them. Nothing in the fluency of the surrounding prose
distinguishes the other four.

**How much you show at once changes how much you get.** Three papers that fit the window
comfortably were read twice - whole, and in passes of about three pages:

| | whole | three pages at a time |
|---|---|---|
| verified quotations | 45 | **207** |
| wall clock | 6.9 min | 13.2 min |

Four and a half times the verified quotations for twice the time. **The confound is part of
the result**: seventeen calls against three, so more passes are more generation budget, and
per call the whole document does as well or better. The effect is only real in the right
unit - per page examined, a three-page reading yields about 2.8 times a twelve-page one.

**One defect has now appeared in two unrelated layers.** Extraction sometimes spaces
glyphs rather than words, so `According to` arrives as `A c c o r d i n gt o`. It was found
in the grounding check, where it made 22 real quotations look fabricated. It was found again
in heading search, where `PSMA PET/CT` arrives as `PSM A PET/CT` and a search for "psma"
could not find the document's own section on it. Both times folding the spacing away was the
answer. Two places nobody had connected suggests a third, and the useful conclusion is to
fold spacing wherever extracted text is compared to anything at all.

**Structure is obeyed; instructions are negotiated.** Asked to list 24 documents, a 14B
covered 10. Given the same request as a skeleton with 24 numbered slots to fill, it returned
23. Asked in the same prompt, explicitly, not to use its own knowledge and to write "not
available" for anything missing, it invented 12 of 24 journal names anyway - a field the
material did not contain. This is the same shape as the fence: the instruction was ignored
and the structural change worked.

**A model that does not fit its card runs eleven times slower.** 29 tokens per second
against 2.7, for a 32B model at 19.9 GB on a 15.9 GB card. This is the largest single factor
measured in this project, and no architectural decision affects it.

**One run per configuration measures nothing.** The same 14B on the same paper four times
gave 4, 5, 7 and 3 claims, of which 2, 4, 3 and 2 verified - between 43% and 80%. That
spread is wider than the gap between a 7B and a 14B on one run each, which had already been
written into the roadmap as a finding. It was noise.

**Choosing better pages did not produce more relevant claims.** A 251-page guideline was
read three ways, looking for what it says about pelvic nodal staging:

| how the pages were chosen | quotations | verified | on the subject |
|---|---|---|---|
| pages with the most keyword mentions | 27 | 88% | **51%** |
| pages under the matching section headings | 111 | 85% | **46%** |

The better method was slightly worse, and the reason is not the method. `extract_claims`
returns what a page asserts, and a page under *Diagnosis - Clinical Staging* asserts things
about biopsy. **The extractor is blind to the reader's subject by design**: ADR-041 forbids
it the standing context precisely so that knowing what a thesis argues cannot make it favour
the claims that fit. That 46% is the price of refusing confirmation bias, and it is the right
price. Filtering by subject belongs after extraction, where a person can see what was set
aside.

What choosing sections *did* buy was the document at all: sixteen passes that failed twice
and cost fifty-five minutes became four calls and 5.7 minutes.

**A judge of readings finds the problem and misnames it.** The gap ADR-026 left - a
quotation is checked, the paraphrase above it never is - produced a live failure: a 14B
attributed choline PET/CT's figures to PSMA above a quotation that names choline, and every
mechanical control here passed it. A judge graded on eight pairs labelled in advance gets the
three-way label right 6 times, the binary "should somebody look at this" right 8 times, and
raises no false alarm on the 3 readings that were fine. Both its errors came with correct
reasoning attached to the wrong label. The reporting leads with the binary for that reason.

**Similarity is the wrong question where the content lives in the words that differ.** The
two most alike quotations in the corpus that are not identical agree on 0.86 of their
wording, and they name two different drugs - `Apalutamide` and `Darolutamide`, in otherwise
identical sentences. The conventional near-duplicate threshold in corpus deduplication is
0.80. **The highest-similarity non-identical pair in this corpus is one that must be kept**,
which is why deduplication here is exact containment and has no threshold at all (ADR-054).

## How to read a figure from this project

**Ask what the check could not see.** Six of the seven wrong figures above were the check
reporting its own blind spot. The question that found every one of them was not "what is the
rate" but "what did it reject, and was it right to".

**Ask whether the answer was known in advance.** Every rate published here was measured
against real papers where nobody knew the correct answer, which is the condition that
produced the errors. A fixture corpus with seeded truth is decided and deliberately not yet
built (ADR-044).

**Ask how many runs.** Two runs are a story, four are a measurement, and this project has
published figures from one.

**Ask whether the figure was predicted before it was taken.** Both predictions announced in
advance here were wrong, and both were wrong in the direction of the thing being built:
section headings were to select better, and the corpus was to hold near-duplicates across
documents. That is not an argument against predicting. It is an argument for writing the
prediction down where it can embarrass you.

**Ask what in the program sets it.** A feature is a figure too - "this is delivered" is a
claim - and twice here it was wrong while its tests were green. Both times the tests built
the component the program never builds by hand. If nothing but a test reaches a switch, the
switch is not there.

**Ask whether a premise in a plan was ever a measurement.** The second of those was not
phrased as a prediction. It was stated as a fact about the corpus, in the sentence justifying
the work, and it read like something already known. A plan is where unmeasured claims are
hardest to see, because nothing in it looks like a figure.

## What is not measured

Whether a claim is *true* - only whether its quotation is real. That boundary has never
moved (ADR-026).

Whether a larger model extracts better. The one comparison run was on synthesis rather than
extraction, and the 32B did worse there on the things that mattered - it never marked a
missing field, and it renumbered entries so they no longer matched the source.

Whether white-on-white hidden text appears in any real paper. It is undetected, so it would
not be known.

Whether reading in passes loses claims that span distant sections. It must, since no reading
holds them together, and no count of passes says which ones.
