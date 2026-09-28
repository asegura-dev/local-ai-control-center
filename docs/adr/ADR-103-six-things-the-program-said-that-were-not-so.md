# ADR-103 - Six things the program said that were not so

## Status

Accepted. Found on 25-sep and 27-sep by using the program on the thesis's own material, the
way ADR-095 to ADR-101 were found; built on 27-sep with the engine switched off. No test had
caught any of the six, and each one is a sentence the program printed that a person would
have acted on.

## Context

1. **The Commands section offered a line to copy that did not run.** For `review` it showed
   `lacc review draft against --into`: `--against` is required and is an option, and the line
   printed it as a bare word, because the slice took "has no default" to mean "is an
   argument". Nothing marked what to fill in. Pasted, the CLI answered `Option '--into'
   requires an argument`.
2. **Ask said the ranking does not cross languages** - a fixed sentence under the question box
   - with an embedding model configured, and the preview right below it saying `words +
   meaning (ollama:bge-m3)`.
3. **Every file LACC refused to replace was refused as "ingestion"**: `resolve`, `coverage`,
   `collect`, `bib`. The rule is general and the sentence named one command.
4. **Seven papers raised the same pypdf warning 594 times in one ingest** - *fontTools is
   required to fully parse the encoding of a CFF Type1 font* - 699 KB of it, burying the three
   lines about hidden text that mattered.
5. **Dou 2020 reported "3 of 3 pieces of text in this document are not visible".** It has
   1,594. The denominator was measured from ADR-040 on and never passed to the report, so the
   report fell back to the count and made three author names in small type read as a
   document that was entirely hidden.
6. **A DOI established for a document was seen by one command and not another.** Established
   on the Markdown, where `identify` is run; `resolve` run on the PDFs did not find it, and
   called **8 of 16 documents** silent that had one. ADR-101's shape again: two files, one
   work, answered by name for one of them.

## Decision

- **A usage line is read from what each parameter declares, and shows what to fill in.**
  `lacc review <draft> --against <against>`. An option keeps its flag whether or not it is
  required, a switch takes no value, and what is optional is listed beside the line rather
  than in it, so a line copied and filled in is a line that runs. The declaration is read by
  the names of the objects Typer leaves in the annotation, without importing Typer:
  presentation stays in the CLI. **Held by a test that hands every usage line, filled in, to
  the CLI's own parser** - which parses and runs nothing - and that fails on the line printed
  before.
- **The sentence under Ask says only what is always true**: ranked by the words you use, and
  also by meaning, across languages, when an embedding model is configured - the preview says
  which. The preview knows; a fixed sentence cannot.
- **The refusal names the rule, not a command: LACC writes its results only to new files.**
  Not "LACC never replaces a file", which was the first wording and is false: the settings
  section rewrites the configuration after showing the difference and asking (ADR-094), and
  LACC rewrites its own records beside your files - the registry's answers, the vectors, the
  audit's anchor.
- **pypdf's font warning is counted, not printed.** Measured before deciding, by extracting the
  five papers that raised it with and without the library it asks for: **16 spaces different
  in 407,000 characters, and no word**; three of the five came out identical. The library is
  2.4 MB and would make every later conversion differ from the ones already checked, for
  spacing. The count is printed once per document and kept in the conversion's audit record.
  Only that message is counted, only while a document is read; every other warning pypdf
  raises still reaches the screen.
- **The hidden-text report is given its denominator**, which is what ADR-040 measured it for.
- **A DOI established for either file of a work answers for both**, the document's own note
  first, finding the other by `ingest`'s naming - the rule ADR-101 set for what a file says
  about itself, applied to what a person said about it.

## Consequences

Ingesting Dou 2020 and Gou 2021 again, in a scratch workspace: **52 lines of output, where
the same two papers printed 514**, and they say `3 of 1594` and `16 of 4483` - three author
names set small, and the labels inside Gou's figures. All twenty usage lines, filled in,
parse. The eight established DOIs are found from the PDFs.

## Trade-off

**fontTools stays uninstalled on five papers' evidence.** A font whose encoding decides a
character rather than a space would come out wrong without it, and nothing here would say
which. The count stays on the screen and in the record so that a document with an unusual
number of them can be looked at; installing it is one line in `pyproject.toml` the day a
measurement says so.

**The usage line relies on where Typer keeps an option's first name** - in `default`, when
declared with `Annotated`, which was seen on the real application rather than read in its
documentation. A Typer release that moves it breaks the parser test, not the window.

**The sentence under Ask is less specific than it could be.** Specific would mean the view
deciding which ranking is configured, and views hold no logic; the preview, which is built
from what will actually run, already says.
