# ADR-036 - Dropping the furniture of a page

## Status

Accepted.

## Context

The audit behind ADR-035 removed every reason a faithful quotation failed except one. The
journal's running header is extracted *inside* a sentence:

```
The organ mask has three channels, which
3413European Journal of Nuclear Medicine and Molecular Imaging
```

A model quoting that sentence cannot match it, and neither could a person: the Markdown is
wrong, and it is wrong in a way that would also confuse someone reading it. That puts this
in the converter rather than in the comparison - normalisation exists to absorb differences
in how the same text is represented, and this is not the same text.

Measured on that paper: two of its hundred and sixty sentences are broken this way.

What makes the header hard to spot is that it is never literally identical. The page number
is glued to the front, so `3413European Journal...` and `3417European Journal...` are
different strings. Counting repeated lines finds nothing.

## Decision

**A line whose shape repeats across at least half a document's pages is page furniture and
is dropped.** Shape means the line with every run of digits replaced by a placeholder, which
is what makes a running header carrying a page number recognisable as the same line.

On the paper this was found with, that identifies exactly three forms - the journal header
in its two spacings, and the `1 3` that ends every page - removing thirteen lines out of
five hundred and fifty-eight, all of them furniture.

**Half the pages, and never fewer than two.** A line appearing on one page of a
seven-page document is content. A short document needs the line on every page before it
counts, because with two pages "half" is not evidence of anything.

**Only for documents with pages.** This is a property of how a PDF is laid out. Word
documents come through their own converter and are untouched.

**What was dropped is reported, not removed silently.** The conversion says how many lines
it treated as furniture, and the count goes into the audit. A heuristic that quietly deletes
text from a document the user keeps is the wrong shape for this project, and the number is
the thing a person would want to notice if it were ever large.

## Consequences

- `PdfConverter` drops furniture lines before assembling its output.
- Two more of that paper's sentences become quotable; the document also reads correctly
  where it did not.
- The audit records the count, so an ingestion that dropped an implausible amount is visible
  afterwards rather than only at the time.
- Ingestion now edits rather than only transcribing, which is a change in what that step
  claims to do.

## Trade-off

A heuristic will eventually drop something real: a table header repeated on every page of a
long table, a recurring figure caption, a short refrain. Accepted, with the reasoning
stated rather than waved at - the alternative is leaving sentences broken by text that is
not part of them, which corrupts the check that the whole project rests on, and the count
being reported means a bad case announces itself.

It also means the Markdown is no longer a faithful transcription of the PDF. That is a real
loss: until now, ingestion could be described as extracting what is there. Accepted because
the running header was never part of the sentence it interrupted - keeping it is not
fidelity, it is preserving an artefact of how the page was printed - but the honest
description of ingestion is now "extracts the document, dropping what belongs to the page
rather than to the text", and the documentation should say so.
