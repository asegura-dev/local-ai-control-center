# ADR-040 - Text a reader cannot see

## Status

Accepted.

## Context

ADR-038 closed the fence and named what it could not close. The sharpest remaining hole is
specific to citation work: **the grounding check verifies that a quotation is in the
document, and text hidden in a PDF is in the document.** A reader never sees it, extraction
captures it, a model quotes it, and the check reports *verified* - correctly, and uselessly.

Four ways to hide text were tested against PDFs built for the purpose. All four were
extracted into the text LACC feeds a model:

| Technique | In the extracted text | Visible in the operators |
|---|---|---|
| Rendering mode 3 | yes | `3 Tr` in the content stream |
| Font size zero | yes | the extractor reports the size |
| Positioned off the page | yes | coordinates against the `MediaBox` |
| White on white | yes | only by tracking fill colour |

The first three are cheap to detect. The fourth needs colour state tracked through the
content stream and is not attempted here.

There is a complication that shapes the whole decision. **Rendering mode 3 is what a scanned
document's OCR layer uses.** Every word of a scanned paper is drawn invisibly, over the
image a person actually reads, and that is entirely correct. A detector that called mode 3
an attack would cry wolf on an ordinary scan and be switched off within a week.

## Decision

**LACC reports how much of a document a reader cannot see, and does not judge it.**

The report is a proportion and the text itself, not a verdict. A scanned paper is a hundred
per cent invisible and fine. An ordinary paper with three invisible lines among five hundred
visible ones is not, and the difference is obvious to a person and not available to a rule.

**Three signals, each cheap and each named separately** so a reader knows which one fired:
text drawn in an invisible rendering mode, text at a font size too small to read, and text
positioned outside the page. White-on-white is not detected and is written down as not
detected, because a control whose gaps are unlisted is worse than one whose gaps are known.

**It is reported at ingestion.** That is the moment the document becomes text, before any
model sees it and while the person still has the PDF open. The count goes into the audit and
the hidden text is shown.

**Nothing is refused and nothing is stripped.** A scan would be destroyed by stripping, and
LACC cannot tell a scan from an attack. The user can, once told.

**The guides stop implying the grounding check covers this.** It never did.

## Consequences

- `PdfConverter` reports the fragments a reader cannot see, by reason.
- `lacc ingest` prints them and records a count in the audit.
- A scanned document says "all of it is an invisible layer", which is informative rather
  than alarming once phrased that way.
- White-on-white text passes undetected, and the documentation says so.

## Trade-off

Showing hidden text puts an instruction that was meant for a model in front of a person.
Accepted: it is displayed as a finding rather than fed to anything, and a hidden instruction
nobody is shown is the situation being fixed.

Proportion rather than judgement means LACC hands the decision back to the user at the
moment they are least equipped to make it - they have just converted a file and are thinking
about something else. Accepted because the alternative is a rule that is wrong on every
scanned paper, and because the information is genuinely not decidable from the document: the
same `3 Tr` is correct in a scan and hostile in a typeset paper.

This closes three of four known techniques and an unknown number of unknown ones. It is a
detector, not a barrier, and the honest description is that LACC now notices the crude
attempts.
