# ADR-102 - A bibliography LaTeX can cite from, written from what the registry said

## Status

Accepted. Built on 27-sep with the engine switched off, which this never needs; found wanting
by the thesis itself, whose chapters are written in Markdown, previewed in Word through pandoc
and typeset with biblatex and biber - all three of which read BibTeX, and none of which reads
the Markdown bibliography `resolve` writes.

## Context

`resolve` (ADR-067) asks a registry what each DOI is and keeps every answer beside what it
writes, in a `.registry.json`. On 27-sep the workspace held three such files: **290 DOIs asked,
218 answers naming 203 distinct works, and 72 DOIs the registry holds nothing for**.

The thesis's `referencias.bib` was assembled that day by a script outside this program, asking
Crossref for its own BibTeX. It worked, and it was a second route to the same answers - the
shape ADR-090 and ADR-101 each had to undo once already. What was missing to write BibTeX from
the answers already kept was not much:

- **Where in the journal a work is.** `Work` held six fields (ADR-067): title, authors,
  container, year, type, DOI. A bibliography in a thesis prints volume, issue and pages. The
  registry's answer carries them; LACC did not read them.
- **Keys.** `[@giesel2016]` in a chapter is a promise that the key will still name that work
  next month.
- **Escaping.** The fields are a third party's text, and a LaTeX document executes what it is
  given.

## Decision

- **`lacc bib <kept answers> --into <file.bib>`, with no network and no model.** It reads the
  `.registry.json` files `resolve` and `identify` keep, and writes one BibTeX file inside the
  workspace, refusing to replace one - the rule every file LACC writes keeps (ADR-039). It
  writes only `.bib`. Like `resolve` and `references`, it is not audited: it calls nothing and
  sends nothing, and writes a file derived from files already in the workspace.
- **Volume, issue and pages are read, short and bounded like every other field.** Nine fields
  now, and still no abstract: the reason ADR-067 refused it - the one long free-text field, and
  the obvious carrier for an injection - does not apply to a volume number. **`None` means not
  read, and differs from empty.** Every answer kept before this has none of the three, and
  "not in the registry record: pages" would be false of a record that has them. An entry
  received before says so, and resolving again into a new file reads them.
- **Keys are the first author's family name and the year, in ASCII: `giesel2016`,
  `schafer2016`, `maierhein2024`.** Derived, never chosen. Without an author, the first word
  of four letters or more in the title; without a year, `nd`. A key already taken gets `a`,
  `b`, `c`.
- **A key somebody cites is never handed out again, and that is only possible against a file
  that is named.** `--adding-to refs.bib` reads the file the person already cites from: the
  works it holds, by DOI, are left out, and no key in it - with or without a DOI, in any case -
  is given to anything else. What is written can be appended to it. Keys are handed out in a
  fixed order, so the same answers give the same file, but stability across runs is not left
  to the order holding.
- **Every character LaTeX would read as an instruction is written as a character.** The braces
  become `\textbraceleft{}` and `\textbraceright{}` rather than `\{`, because BibTeX counts
  every brace, escaped or not, to find where a field ends: one stray brace in a title would
  swallow the rest of the file.
- **A word in a title whose capitals belong to it is kept as written**, inside braces:
  `{U-Net:}`, `{PET/CT}`, `{68Ga-labelled}`. Found by rendering the file through pandoc, which
  lower-cases what it is not told to keep and printed `3D u-Net`.
- **What the record did not hold is named above the entry, as a comment, and never filled
  in** - the rule of ADR-067 in another format. The comments sit outside any entry, where
  BibTeX reads an `@` as the start of one, so the one piece of registry text they carry - what
  the registry calls the work - is reduced to the letters, digits and hyphens a type name is
  made of.
- **Types follow what the registry says**: journal article, proceedings article, book chapter
  and book map to their BibTeX types; anything else is `misc`, which every style accepts, and
  the entry says what the registry called it.

**Refused:** asking the registry for its own BibTeX, which is what the script did. It is a
second format to parse from a third party, it carries fields nobody asked for, and whatever
it holds would reach a LaTeX document unescaped.

## Consequences

Run over the three kept files on 27-sep: **203 entries**, and with `--adding-to` a copy of the
thesis's `referencias.bib` (18 entries), **189 new, 14 left out, no key shared with the file it
adds to and none repeated**. Other Giesel papers of 2016 became `giesel2016a` and `giesel2016b`,
because `giesel2016` is cited already.

**biber read both files together with no warning and no error**, and the test document -
every entry, cited - came out at twenty pages. **pandoc read them with no warning.** Using it
is what found the two things the tests had not: `3D u-Net`, now kept, and the next paragraph.

## Trade-off

**Every answer kept so far predates volume, issue and pages, and pandoc's default style prints
"ahead of print" for an article that has neither volume nor pages.** For these 203 that is
false: the record has them, and LACC had not read them. Each entry says so, and resolving the
same documents again into a new file reads them - which sends the same DOIs to the registry a
second time. It discloses nothing new, and it is still a send, so it is the person's to make.

**A chapter in a series is filed under the series.** For Çiçek 2016, the 3D U-Net, the registry
lists "Lecture Notes in Computer Science" before the proceedings, and LACC reads the first
container name, since ADR-067. The DOI still finds the work; the reference is thinner than it
should be.

**`--adding-to` needs the file inside the workspace**, and the thesis's bibliography lives with
the thesis. Nothing outside the workspace is read, so the file is copied in. This is the same
boundary that keeps the writing stage empty, and it is named there rather than worked around
here.

**`High-Risk` is kept in capitals too.** A title-case word joined by a hyphen looks exactly like
`U-Net`, and nothing short of a dictionary tells them apart. A style that wants `high-risk`
does not get it; a name corrupted in a thesis would cost more.

**The registry's own DOIs only.** An arXiv preprint's DOI is DataCite's, Crossref does not hold
it, and the three preprints in the thesis's bibliography came by another route.
