# ADR-111 - A draft brought in, by name

## Status

Accepted. The first deliberate exception to "nothing outside the workspace is touched" that
reads rather than writes, chosen on 29 September by the person whose drafts these are, over a
tray they would fill by hand.

## Context

The writing stage has been empty since `lacc status` first reported it: *nothing of yours has
been read yet*. Not from neglect. The thesis is written in an Obsidian vault in a synchronised
folder, and the workspace is deliberately elsewhere; asked to read a draft there, LACC answered
`Path escapes workspace boundary` - which is the boundary doing its job. `lacc review`, which
reads a draft against the corpus, has never read the thesis.

Two ways across were weighed. **A tray** - a folder inside the workspace the person copies
drafts into by hand, which LACC treats as not accepted until they accept it - keeps the principle
whole and costs a copy by hand every time a chapter changes, which is daily. **A command** that
reads one file the person names, outside the workspace, shows what it will read and where the
copy goes, asks, and records it, is an exception to the principle - narrow, but an exception.
The person chose the command.

## Decision

**`lacc bring <file>` copies one named file into the workspace, and nothing else.** It reads
only the path it is given: never a folder, never a pattern, never a second file. It refuses what
is not a file, what is already inside the workspace, anything over 20 MB, and any format LACC
cannot read - it takes Markdown and text, and PDF and `.docx`, which `ingest` then converts.

**It shows before it reads.** The full path it would read, its size, and where the copy would
go; then `Bring it? [y/N]`. Before the yes, only the file's size is read - what the preview
shows. Its contents, and their digest, are read after.

**The copy is a snapshot, never a replacement.** It lands in `drafts/`, named after the file and
the day - `drafts/03 Metodología (2026-09-29).md` - and a second copy the same day gets a number
after the date. Nothing LACC writes replaces anything, and the original is never opened for
writing. Beside the copy, `<copy>.brought.json` says where it came from, when, and its digest,
the way a section taken out of a document says which document (ADR-082).

**It is recorded.** A run named `bring`: the file read, by path and digest; the files written;
how it ended - declined included (ADR-107).

**`status` counts drafts.** The writing stage says how many were brought and whether any has
been reviewed, and names `bring` where it used to say only that nothing had been read.

**`PRINCIPLES.md` names its exceptions.** It said nothing outside the workspace is touched while
the window already wrote configurations and made workspaces outside it (ADR-093, ADR-094); it
now names those two and this one, each shown before it happens.

## Not decided here

- **The window.** A button that picks a file and draws what `bring` would do belongs with a
  section for writing, which is its own record.
- **The tray.** Whatever CACC brings from outside, without a person naming each file, still
  needs a place that is not accepted until somebody accepts it. The answer here is for a file a
  person names and confirms; that act is the acceptance.

## Consequences

- A thesis chapter can be reviewed against the corpus the day it is written:
  `lacc bring <chapter>`, then `lacc review drafts/<copy> --against <corpus>`.
- Drafts live in `drafts/`, where the stages that count the library do not look: a draft is not
  a document to collect quotations from, and counting it as one would invent a pending item.
- `docs/05-assurance.md`: "a command reads and writes only inside the workspace" is held with
  three exceptions, each named.

## Trade-off

**A boundary with a door is weaker than a wall.** The strongest thing that could be said was
that LACC never touches a path outside the workspace; now it reads one, when the person names it
on the command line and says yes. What keeps that narrow is the shape of the command - one file,
named, shown, confirmed, recorded - and every future proposal to widen it, to a folder, to a
pattern, to a file the window guesses, has to be argued against this record.
