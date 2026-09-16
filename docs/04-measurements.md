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

## Seven wrong figures, and which way each one leaned

| Reported | What it actually was | Fixed in |
|---|---|---|
| The model is inconsistent between runs | Temperature was never sent; the engine sampled at its own default of 0.8 | ADR-033 |
| A third of quotations do not verify | A third could not be placed on a page. They were in the document | ADR-042 |
| The model fabricated two quotations | The PDF held `sensi- tivity` across a line break; the model had quoted faithfully | ADR-034 |
| The model extracts very few claims | The output format was stated 9,000 tokens before the point of generation | ADR-037 |
| A quotation was not in the paper | A running header had been extracted into the middle of the sentence | ADR-036 |
| Twenty-two more fabrications | Extraction had written `A c c o r d i n gt o`; spacing, not words | ADR-046 |
| **Zero fabrications in 237 quotations** | **48 of 237, of which 44 are absent in any form tried** | ADR-042 |

Six of these made the model look worse than it was. The seventh was the correction to that
pattern, published in the same release that introduced it, and it overshot: it credited a
model that had invented forty-four quotations. **Knowing you are biased in one direction
does not make the next figure unbiased.**

There was an eighth during the session that produced this chapter, and it belongs here
because it has the same shape and was not made by the tool. A script written to summarise
the corpus reported that `collect` silently omitted documents it had refused. It does not -
every refusal has its own section naming the token count and the budget. The script's filter
dropped lines beginning with an asterisk, and `**Not collected.**` begins with one. A blind
spot in the measuring instrument was reported as a defect in the thing measured.

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

## What is measured and currently holds

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
