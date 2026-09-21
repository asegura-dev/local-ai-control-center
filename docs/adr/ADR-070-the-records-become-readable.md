# ADR-070 - The records become readable

## Status

Accepted. A small feature about a large omission.

## Context

This project has **sixty-nine decision records, six chapters, a set of guides and a book of
eight chapters**. The book is in `.gitignore`, written for whoever ends up using LACC, and
nobody has read it - because reading it means knowing the folder exists and opening files in
an editor.

The documentation is the thing this project has most of, and it was the one thing the tool
could not show.

## Decision

**A section in the window, reading Markdown from the repository.** Grouped the way the folders
group it: the chapters at the top, then `adr/`, `guides/` and `book/`, each document titled by
its own first heading rather than by its filename.

**The folder is found, never configured.** A setting that named where to read documentation
from would be a setting that could name anywhere, in a project whose first rule is that
nothing outside the workspace is touched. `documentation_near` walks up from the package to
see whether it is running inside its own repository, and reads `*.md` from there and nowhere
else. Installed as a package with no repository around it, there is nothing to show and the
window says so rather than looking empty.

**Markdown becomes blocks in a slice; the window gives blocks a font.** What a line *is* - a
heading and its depth, an item, a quotation, code, a table row - is a decision, and a view
that made it would be a view containing logic (ADR-066). `features/reading.py` decides;
`window.py` picks a size and a colour.

**Inline emphasis is flattened; structure is kept.** Bold, italics, inline code and link
targets become the words they wrapped. Styling every inline span in Tk means index arithmetic
over a text widget, and what makes a sixty-page record navigable is its **heading structure**,
not its bold. The words survive.

**No generation step, and no browser.** Turning the Markdown into HTML first would mean a
build to keep in sync and a browser to open it in - and a browser is the thing this window
exists to avoid needing (ADR-069). A tool for publishing the book to somebody else is a
different job and a good one; this is for reading it here.

## What was measured

The parser is run against **every Markdown file in `docs/`** rather than against a fixture,
because a parser that works on an example and not on the corpus it was written for is exactly
the defect this project has found seven times by using the tool instead of testing it. All of
them produce blocks, and all of them produce at least one heading.

## Consequences

- The window gains a fifth section. Everything it shows was already on disk.
- `features/reading.py` is pure and fully covered, which is how a window that cannot be tested
  ends up with the part that matters tested.
- The book is reachable for the first time since it was written.

## Trade-off

**It is a reader, not a renderer.** No images, no tables laid out in columns, no links to
follow. A table becomes its cells separated by spaces in a monospaced row, which reads
correctly for the two-column tables these records use and would not for a wide one.

**Following a link is not possible**, so a record that says "see ADR-042" needs the reader to
find ADR-042 in the list. That is a real cost in a body of documents that cross-reference each
other constantly, and the honest reason it is accepted is that the list is right there and
sorted.

**A document open in the window is a document that has been read from disk**, so it shows what
is on disk now rather than what was published. For this project that is the right way round -
the records are edited constantly and a stale copy would be the exact failure chapter 4 keeps
naming.
