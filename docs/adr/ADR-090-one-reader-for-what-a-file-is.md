# ADR-090 - One reader for what a file is

## Status

Accepted. The third time this project has found two readers of one decision living apart, and
the first time it was found before the drift cost anything.

## Context

A workspace holds papers, corpora, bibliographies, review reports, coverage reports, sections
taken out of documents, a standing context file and a list of topics. Telling them apart is
one decision, made from the opening of the file.

**It was made in two places.** `features/stages.py::_kind` answers it for `lacc status`, and
`features/overview.py::_kind_of` answers it for the window. Neither knows about the other.

They have already drifted. ADR-088 added coverage reports and ADR-089's fix added topics
files - to one of them:

| | the window | `status` |
|---|---|---|
| documents to quote from | **38** | **29** |

The nine the window offers as papers to cite:

- two coverage reports, **written by LACC itself**
- one topics file, which is the *question* rather than a source
- six sections taken out of the guideline, which `status` counts apart because they came out
  of a document rather than being one (ADR-080)

And `contexto.md`, the standing context, which `status` excludes because the configuration
names it and the window has never been told.

Nothing has broken yet. That is luck: ADR-065 is what happens when the same shape is left
alone, and there the two writers of the corpus format drifted and silently stripped the
meaning from every quotation in a corpus.

**The layering test cannot catch this.** It checks that logic has not leaked into a *view*,
and both of these are in `features/` where they belong. A rule about where code lives says
nothing about the same decision being made twice in the right place.

## Decision

**`core/kinds.py` holds the one answer, and both slices ask it.**

Core, not a slice: it is a decision about text with no file system, no model and no
configuration in it - the same reason the corpus format's reader lives there. A slice that
needed its own copy would be a slice with an opinion about what somebody else's file is.

    corpus        a file of collected quotations
    bibliography  written by `resolve`
    review        written by `review --into`
    coverage      written by `coverage --into`
    topics        read by `coverage`: the question, not a source
    extract       written by `sections --take`: it came out of a document
    document      something somebody brought
    other         not text this project reads

**"Written by LACC" is a grouping the view makes, not a kind.** The window shows
bibliographies, reviews and coverage reports together because they answer the same question
about a workspace - *what has this produced* - and that is a presentation decision. The reader
returns what each file **is**.

**The standing context file is excluded by whoever knows the configuration.** It is a
document; what makes it not one to quote from is a setting, and a reader of text has no
business knowing about settings. `status` already passes it in, and the window now does too.

## Consequences

- One place learns about a new kind of file, and both callers get it. The next command that
  writes into a workspace has one reader to teach instead of two, and no way to teach only one.
- The window stops offering ten files as papers to cite.
- `tests/test_kinds.py` pins every kind against a file that opens the way that kind opens.

## Trade-off

**It is still recognition by how a file opens**, and that is a guess dressed as a fact. A
paper whose first line happens to read `# Bibliography` is filed wrong, and a coverage report
somebody edited the heading off becomes a document. Every recogniser in this project makes
this trade and errs toward counting less rather than claiming more.

**A grouping in a view can still drift from a kind in core.** The window decides that a
coverage report belongs with bibliographies; nothing enforces that, and a kind added later
will not appear in that group until somebody adds it. What this record removes is the
duplicate *decision*, not every place that mentions a kind.

**And one more implementation of this still exists.** `features/status.py` recognises a corpus
by its opening marks, for the line along the bottom of the window. It reads one thing and is
not a classifier, so it is left alone and named here rather than quietly excluded.
