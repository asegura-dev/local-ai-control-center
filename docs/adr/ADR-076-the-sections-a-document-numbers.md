# ADR-076 - The sections a document numbers

## Status

Accepted, and the measurement is the record. **Four** rules were tried and the count fell
each time: **16, 18, 10, 6 of 24**. The last is the honest figure. The second *rose*, and was
the worst of them.

## Context

A PDF does not say what a heading is. A heading in a PDF is text in a larger font, and nothing
in the extracted Markdown distinguishes it from a sentence - measured: **seven of eight papers
carry no Markdown heading at all**, and the one that does has one.

That matters most for the document that has given this project the most trouble. The EAU
guideline is 348,000 tokens and had to be split by hand into four extracted sections to be
usable. If its own numbering could be recovered, any section could be taken out of it without
a person cutting the file up.

## What was measured, four times

**First rule - a line beginning with a number and a capitalised word.** Counted 16 of 24
documents with three or more. Looking at what it had found: **the table of contents**. Entries
like `1. INT RODUCTION      11`, with the page number attached and the title truncated to
`3.2.2.2 Diet`. The body of the EAU does not look like that at all - there a heading is
`3.2.3` alone on its line with the title on the next two.

**Second rule - add consecutive numbering**, the anchor ADR-064 named for reference lists. It
went *up*, to 18, and the examples said why:

    55   1   Department of Nuclear Medicine, University Hospital
    57   2   Department of Urology, University Hospital Heidelberg
    671  1   Afshar-Oromieh A, Avtzi E, Giesel FL, Holland-Letz T
    676  2   Eiber M, Maurer T, Souvatzoglou M, Beer AJ, Ruffani

Author affiliations and the bibliography. **Consecutive numbering does not distinguish a
section from any other numbered list**, because every numbered list is consecutive - which is
the same fact ADR-064 relied on, used against me.

**Third rule - require the dot.** A section is written `1. Introduction`; an affiliation and a
reference are written `1 Afshar-Oromieh`. That one character is the signal, and with it the
count fell to **10 of 24** and the results looked clean:

    1.    Introduction
    2.    Materials and methods
    2.1.  Image acquisition
    2.2.  Data pre-processing

**Fourth rule, and it came from running it rather than from thinking.** On the real guideline
the third rule found the nine real sections **and** a heap of rubbish: numbered lists of
recommendations, and the bibliography - which is written `10. Haas, G.P`, **with the dot**. So
the dot alone does not separate a section from a reference; that guideline simply punctuates
its references differently from the papers.

Two conditions more, both structural. **Sections appear in order**: a `1.` found below the
`5.` is not the first section. And **a section has a body**: ten lines before the next, where
a bibliography entry runs four and a recommendation runs one.

The count fell to **6 of 24**, and the guideline came out exactly right:

    1. INTRODUCTION          5. DIAGNO STIC EVALUATION
    2. METHODS               6. TREA TMENT
    3. EPIDEMIOL OGY...      7. FO LLOW-UP
    4. CL ASSIFICATION...    8. Q UALITY OF LIFE OUTCOMES
                             9. REFERENCES

Nine sections, nothing else. **Ten lines rather than twenty was measured too**: twenty also
produced a clean guideline and cost a paper whose sections are real. Five gained only an
appendix whose numbering restarts.

## Decision

**Sections are detected, never written into the document.** The workspace holds 832 verified
quotations checked against these files as they are. Rewriting a document to insert `##` would
put every one of those checks at risk to gain a convenience, and the gain is available without
it.

**Six conditions, all structural, none about how a line looks:**

1. A number, optionally dotted for depth, **followed by a dot**.
2. A title that starts with a capital and is at most nine words - a section is named, not
   written.
3. **Not ending in a number**, which is what a table-of-contents entry carries.
4. First-level numbers that run **1, 2, 3 without gaps**, and at least three of them.
5. **In the order they appear**: a `1.` found below the `5.` is not the first section.
6. **With a body**: ten lines before the next one starts.

**Inside a confirmed section, the dot is not required.** The parent's number does the work it
was doing: a `5.1` between section 5 and section 6 is a subsection of 5 whatever punctuation
follows. This is not a relaxation - it is a different anchor, and a stronger one, because the
prefix and the position both have to hold.

It matters because the guideline **writes its subsections without the dot** - `5.1 Screening`,
`5.1.4 P opulation-based screening` - and prints some as the number alone with the name on
the line beneath. With the dot required, its nine chapters were visible and its hundred and
forty-five subsections were not.

**A document with no sections reports none.** Eighteen of twenty-four number nothing, and that
is the answer rather than a failure - it is the same shape as ADR-064's reference parsing, where a
document that yields nothing is a document to look at rather than a silent gap.

**The table of contents is excluded by the page number it carries**, not by position. A
document whose contents page is at the end, or which has none, is handled by the same rule.

## Consequences

- `lacc sections <document>` lists what a document numbers, with the line each starts on.
- `--take <number> --into <file>` takes one out, so the guideline can be read a part at a
  time without anybody cutting the file up. Measured on it: **154 sections found**, chapter 5
  comes out at 42,149 tokens of 348,276, and `5.2.4 Imaging` - the part on nodal staging - at
  **1,440**, which fits any window with room to spare.
- `core/sections.py` is pure: text in, sections out, no I/O and no model.

## Trade-off

**Six of twenty-four is the honest ceiling and it is not a rough edge.** Eighteen documents
number nothing, and no rule over extracted text will find a heading that arrived as a font
size. Widening this means guessing, and a guessed heading is worse than none: it would cut a
document in a place its author did not.

**The dot is a convention, not a guarantee.** A publisher that writes `1 Introduction` without
it is invisible to this, and one that numbers its figures `1. Overview of the method` on their
own lines would offer a false section. The second is bounded by the consecutive-numbering
conditions and the first is simply a miss, reported as such.

**Titles come out as the extraction left them, and some are cut in half.** `EPIDEMIOL OGY AND
AETIOLOGY`, `5.1.1 Pr`, a heading that arrives as `Imag` on one line and `ing` on the next:
that is what the PDF gives. The **numbers** are reliable and the titles are as good as the
extraction was, which is enough to navigate by and not enough to read as an index. This does
not repair them - the same spacing damage `_unspaced` exists to see past
when checking a quotation. Repairing it here would mean editing what the document says.
