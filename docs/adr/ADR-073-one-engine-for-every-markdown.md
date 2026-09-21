# ADR-073 - One engine for every Markdown

## Status

Accepted. An extension of ADR-070, made because the window was showing counts of files it
could not open.

## Context

A Markdown engine was built to read this project's own records (ADR-070). Meanwhile the window
had a workspace full of Markdown it could not show:

| what | what the window said about it |
|---|---|
| a corpus of 832 quotations | how many, and from which documents |
| a review report | its findings, painted over the draft |
| a bibliography from `resolve` | nothing - it was filed under "other" |
| `contexto.md`, the user's own notes | its size in kilobytes |
| the papers themselves | their size and a token estimate |

**Everything LACC writes is Markdown, and a reader existed that could not be pointed at any of
it.** The engine was one import away and was being used for the documentation only.

## Decision

**One engine, every Markdown file.** `blocks_in` reads a corpus, a bibliography, a review
report, a paper and a decision record the same way, because they are the same format and the
differences between them are the user's business rather than the parser's.

**What LACC wrote is listed apart from what the user brought.** A new `written` kind,
recognised the way a corpus is recognised - by the heading its writer put at the top,
`# Bibliography` or `# Review of`. Not by filename, because a person renames files. The
sections answer different questions: *what did I collect*, versus *what did this produce*.

**A long document is cut, and says by how much.** A corpus here is 284 KB and thousands of
blocks; a widget per block freezes the window drawing a file nobody reads to the end. Two
hundred and fifty blocks are drawn and the rest is **counted and reported**, never silently
dropped - the remainder is returned rather than a flag, because a reader deciding whether to
open the file properly wants to know whether it is ten more or ten thousand.

**The cut lives in the slice.** How many, and the fact that there is a limit at all, are
decisions. A window that chose them would be a window containing logic (ADR-066).

**A corpus shows its counts first and its text on request.** The counts are what the corpus is
*for*; the text is what it says. Putting the text behind a button keeps the useful view fast
and makes reading it deliberate.

## What using it found

`_show_document` called `documents_in` again on every selection, and `documents_in` opens every
Markdown file in the workspace to estimate its tokens. Selecting a paper re-read the whole
workspace, including a 284 KB corpus. The listing is now read once per section.

That was not reported as slowness; it was found while adding the reader, which is the same
route by which most of the defects here have been found.

## Consequences

- Seven sections in the window, and none of them shows anything the CLI cannot.
- `contexto.md` and the bibliography are reachable for the first time.
- The parser now faces documents it was not written for - generated corpora with thousands of
  block quotations - rather than only hand-written records.

## Trade-off

**Two hundred and fifty blocks is a guess.** It was chosen because it is comfortably more than
any record here and comfortably less than a corpus, not because it was measured. A document
between those sizes will be cut for no better reason than that the number exists.

**A cut document can mislead by omission.** Somebody reading the opening of a corpus sees the
documents that happen to come first. The count says how much is missing, which is the honest
minimum, and it is not the same as showing it.
