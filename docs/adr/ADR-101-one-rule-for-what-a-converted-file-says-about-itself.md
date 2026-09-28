# ADR-101 - One rule for what a converted file says about itself

## Status

Accepted. Found by running `resolve` on 27-sep; built with the engine switched off, which
this never needed.

## Context

A document's own DOI lives in the PDF's metadata, and the workspace works from the Markdown
`ingest` made of it. `resolve` was run on the 31 papers' Markdown files and reported **23
documents that carry no DOI of their own** - Giesel, nnU-Net and Metrics Reloaded among them,
which had been resolved from their PDFs days before. Run again on the PDFs: 14 of 30 own DOIs,
all resolved.

And the screen filled with `invalid pdf header: b'<!-- '` and `EOF marker not found`, dozens
of times: the metadata reader opened each Markdown file as a PDF, and the PDF library wrote
its complaints before the failure was caught.

## What was actually wrong

**The rule already existed, in one command.** `lacc references` looks for the PDF a Markdown
file was converted from - the same name with `.pdf` beside it - and reads that. `resolve` and
`lacc metadata` read the path they were given, whatever it was. Two answers to the same
question, one right and one not, which is ADR-090's shape again.

## Decision

- **One function says what a document says about itself**: from the file when it is a PDF,
  and from the PDF it was converted from when it is not. That PDF is found by `ingest`'s own
  naming - `name.md` is written beside `name.pdf` - and by nothing else. A file written under
  another name with `--into` has no PDF to find, and says nothing, as before.
- **`references`, `resolve` and `metadata` all use it.**
- **The metadata reader opens only PDFs.** Anything else answers with an empty record without
  being opened, so the library has nothing to complain about.

## Consequences

Tested with a PDF and the Markdown beside it, a Markdown file alone, and the log of the PDF
library, which must stay empty when a Markdown file is asked about. The library was asked
directly first, to know the test could fail: handed Markdown, it logs exactly
`invalid pdf header: b'<!-- '` and `EOF marker not found`.

On the real workspace, `lacc metadata` over three Markdown files now answers with the
Giesel and nnU-Net DOIs from their PDFs, and says that Hu 2020's PDF carries no metadata -
which is true of that file - without a line of noise. Not re-run against Crossref here: the
resolution itself did not change, only which file its DOI is read from.

## Trade-off

**The link between a Markdown file and its PDF is a name.** Rename one and not the other and
the link is gone - silently, in the sense that the file then says nothing about itself, which
is what it said before this record. A recorded link would survive a rename, and would be one
more file for every document.
