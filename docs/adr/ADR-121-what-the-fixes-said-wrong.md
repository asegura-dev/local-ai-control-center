# ADR-121 - What the day's fixes said wrong

## Status

Accepted. The regression test of 30 September over ADR-112 to ADR-120 found seven sentences
the fixes themselves wrote wrong (R1 to R7). It also found the one command ADR-114 left
creating a workspace, the headings ADR-120 left cut, and two faults that were not of the day
(P2, P3). Built on 30 September. The third such fault, a writer that waits out its turn under
load (P1), is left for after the release.

## Context

Nothing the test found blocks a release. Several of the day's fixes, though, said something
that was not so, in the sentences they added.

- **R1, severity 3.** `resolve` over Markdown said *the PDF beside each was read for it: none
  carried one* (ADR-117). It said so also for a Markdown file with no PDF beside it, for which
  nothing was read.
- **R2.** Counts and their words in sentences written that day: *1 paragraphs read*, ***1 were
  not judged***, and in the terminal *1 not judged … nothing was concluded about them*.
- **R3.** `status` said *45 from 1 documents*, *1 were not found in their document*, *1
  sections taken out of them* and *1 number their references*.
- **R4.** *…\escape.md Nothing was done.*: no stop between the path and the sentence.
- **R5.** `bring` refused `\\127.0.0.1\…` and `\\localhost\…` as *on another machine*. The
  refusal is right; the sentence is false for a share that leads back here.
- **R6.** A declined `review` said *Nothing was read.*, after reading the draft to count *1
  paragraph against 44 quotations*.
- **R7.** ADR-119 says a host on this machine is carried as it is. From a configuration with
  the network off and an engine on another machine, the host was written as a working line,
  not in a comment. It granted nothing, since the switch stayed false, but it was not what the
  record says.
- **What ADR-114 left.** `lacc sections x.md`, which only lists, created a workspace that did
  not exist, and said so.
- **13 headings of 35 still cut** in the EAU guideline after ADR-120: *T* nine times, *G*,
  *Me*, *A* and *Imp*. The next line under *Imp* reads *roving quality of life…*, which is the
  case ADR-120's rule says it joins.
- **P2, severity 3, not of the day.** An engine on this machine that accepts the connection and
  does not answer was told to listen on 0.0.0.0, which is advice for a network that is not
  there. It is the case of 25 September: `localhost` on the laptop.
- **P3, severity 4, not of the day.** With ntfy off, `notify test` printed *Sending to
  http://…, named in the configuration*, then *No notifier configured*, and sent nothing.

**Measuring the headings found what the tester had not.** ADR-120's join trimmed the next
line, so a heading broken between two words came out glued. That gave *Summaryof evidence…*
three times, and *Repeatbiopsy*, in titles that looked whole enough not to be counted. And its
nine-word limit, meant to keep prose out of a title, is what kept *Imp*, *Me* and two *T*'s
cut: those headings run from ten to thirteen words. The trade-off ADR-120 named, a heading
broken at a word boundary and joined without its space, had already happened.

**And taking this record's figures found one more.** `tools/measure.py` listed `_options`, the
callback behind ADR-120's `--version`, as *not excused by the rule*. The rule does excuse it:
it asks only about functions without a decorator, and the tool asked about all of them. That
is the kind of drift ADR-086 removed.

## Decision

- **Each sentence says what is so.**
  - `resolve` says which Markdown files had a PDF beside them to read, and which had none. It
    names *it* or *them* by the count.
  - The words after a count agree with it, through `agreeing` in `core/wording.py`, beside
    `counted`. ADR-113's rule allows `agreeing` as it allows `counted`, because it returns a
    word the program wrote.
  - A refusal's path ends in a stop.
  - A share is refused as *a network path*, wherever it leads.
  - A declined `review` says *Nothing was sent to the engine*.
  - `notify test` says *The configuration names … as where notifications go*, which is true
    whether or not anything is sent.
- **A host off this machine is named in a comment, whatever the source's switch said.** Only a
  host on this machine is written as a working line.
- **`sections` does not create the workspace.** It joins ADR-114's list of commands that only
  read (ADR-003, amended).
- **A timeout on this machine is told what it is**: something here took the connection and did
  not answer. That is another program holding the port, or an engine still loading a model.
- **A subsection heading the PDF broke is joined to the line that goes on with it.** Three
  rules, measured on the workspace:
  - **The space is the PDF's.** A line that begins with a space goes on after a whole word,
    and is joined with the space. A line that begins without one goes on inside a word, and is
    joined without one.
  - **A single letter is broken too**: *T* / *reatment*.
  - **The nine-word limit counts only what is printed with the number.** There it tells a
    heading from a numbered sentence. The line a broken heading goes on in is not counted.
- **A first-level heading is read as printed.** Nothing measured needs joining there. In one
  variant tried, joining first-level headings changed the structure: a bibliography entry,
  *10. Haas, G.P*, became a section.
- **`measure.py` asks about the functions the rule asks about**, leaving out decorated ones as
  `tests/test_layering.py` does.

## Consequences

- **In the workspace, 21 titles change and no section is gained or lost.** All 21 are in the
  EAU guideline, which has 154 sections before and after:
  - the 13 the tester counted;
  - five that were glued (*Summaryof*, *Repeatbiopsy*);
  - three cut ones nobody had counted: *The role of*, *Recommendations f*, *Long-t*.
- **The rule joins 85 headings in the workspace, all of them in that guideline.** Each was
  read, and each join is made of the heading's own words.
- Tests:
  - `tests/test_wording.py`: *a word after a count agrees*; a heading broken after one letter,
    on the number's line, between words, and past nine words.
  - `test_review.py`: *1 paragraph read*, ***1 was not judged***, *about it*, and a declined
    review that says nothing was sent.
  - `test_stages.py`: *1 document*, *1 was not found in its document*, *1 section taken out of
    it*, *1 numbers its references*.
  - `test_refusals.py`: the stop before *Nothing was done*, and `sections` creating nothing.
  - `test_bring.py`: `//127.0.0.1/C$/…` is refused as a network path, and nothing is asked
    about it.
  - `test_workspaces.py`: a remote host from a configuration with the network off is commented.
  - `test_engine_check.py`: a silent engine on `127.0.0.1` or on `localhost` gets no 0.0.0.0.
  - `test_cli.py`: `notify test` with ntfy off, and `resolve` over Markdown with no PDF beside
    it and with one.
- Seven tests asserted the old sentences, and now assert the new ones:
  - *1 from 1 documents*, *1 were not found*, *sections taken out*;
  - *1 are held up*, *1 were not judged*;
  - *is on another machine*, twice.
- `features/bring.py`: `not_on_this_machine` is now `through_a_share`.
- `tools/measure.py` now lists 9 functions in `cli.py` that never touch presentation, every one
  excused.

## Trade-off

**A join cannot tell a title that ends in a whole word from a body that begins in lowercase.**
`Training` followed by `nnU-Net was trained…` would be read as one title. The nine-word limit
did not prevent that, because a line of a two-column paper is about nine words, and it cut
seven real headings. Measured on the workspace, the case does not occur: every join is a
heading. The thesis's own papers are not in the workspace yet, and will be measured when they
are.

**P1 is left for after the release.** With four writers of 150 records each on a loaded
machine, one waits more than ten seconds for its turn and ends with `AuditWriteError`, its run
left open. The code as it stood before the day's fixes does the same, so it is not of the day.
