# ADR-117 - More things the program said that were not so

## Status

Accepted. The second batch after ADR-103: sentences from the test of 29 September - D10, D13,
D15, D16, D18, D23 and D24 - and three it confirmed from 25 September. Built on 30 September.

## Context

Each of these is a sentence the program printed that a person would act on, and each was
false. Several had been true when written and were made false by a later record.

1. **`status`: *156 are no longer in their document*.** They never were. The 156 are the
   quotations marked NOT IN THE DOCUMENT when they were collected: 135 on 24 September, and 17
   and 4 from the collections of 25 September. A reading of the panel on 24 September took the
   sentence as *what you had accepted stopped being true*, and the figure was repeated that way
   for five days.
2. **`status` and the window disagreed on how many documents the quotations come from**: 39
   against 38. `status` also counted the document the extracts had been taken out of. That is
   right for saying the document is covered, and wrong for saying where quotations come from.
3. **`ask`, after a no to ranking by meaning,** said a question in Spanish finds no English
   quotations *unless an embedding model is configured*. One was configured; the person had
   declined it.
4. **`resolve --help`: *the one command here that talks to something that is not yours*.**
   `identify` asks the same registry. And *a DOI is never asked twice*: `identify` and then
   `resolve` asked for the same DOI a minute apart, because each keeps its answers beside its
   own file.
5. **`bib --adding-to`: *LACC reads nothing outside it*.** ADR-111 made that false, and `bring`
   does not take a `.bib`.
6. **`resolve` on Markdown advised running it on the PDFs.** ADR-101 had already made it read
   the PDF beside each Markdown file, and for these the PDF carried nothing either.
7. **`identify` with the network off asked to write a `registry_url` that was already written.**
8. **The preview of `ask` said *the contents read above*,** with nothing listed above: a
   question to a corpus reads its passages through a ranking, not as targets.
9. **Commands said 21 where `lacc --help` lists 23.** It read the application's commands and
   not its groups, so `engine test` and `notify test` were missing.
10. **The help printed `**` around every emphasis, and cut paragraphs where the source line
    ended.** The docstrings are written in Markdown and were read as plain text. The window's
    Commands section showed the same text the same way.

## Decision

Each sentence says what is so:

1. `status` says *156 were not found in their document*.
2. It counts the files the quotations come from, as the window does: *1,456 from 38
   documents*.
3. With a model configured, `ask` says *say yes to ranking by meaning to cross them*.
   Without one, it says a configured one would.
4. `resolve --help` names `identify` as the other command, and says a DOI answered for a file
   is not asked again for it.
5. `bib --adding-to` says to copy the `.bib` in, and that outside the workspace LACC reads only
   the draft `bring` is given.
6. `resolve` says the PDF beside each file was read, and names `identify` and `--cited`.
7. `identify` names only the switch that is off.
8. A preview with nothing listed says it sends *the prompt this builds*.
9. Commands lists a group's commands by their whole name. A test counts them against the
   application.
10. The help is read as Markdown (`rich_markup_mode="markdown"`). The window's Commands
    section drops the emphasis marks and joins each paragraph's lines, leaving list items as
    lines.

## Consequences

Taken on the working workspace after the change:
- `status` says *1,456 from 38 documents* and *156 were not found in their document*;
- `lacc review --help` prints its emphasis as emphasis, in whole paragraphs.

The tests that asserted the old sentences now assert the new ones, and each says why:
- `ask`'s refusal;
- `bib --adding-to`;
- the usage lines, which now reach a group's command through the group's parser.

New tests cover:
- the count of commands against the application;
- the refusal with a model configured;
- `status`'s sentence and its count of documents;
- `identify`'s message, which is also held by the rule of ADR-113. That rule caught the
  message on the first run: it put a value into a line without escaping it.

## Trade-off

**Markdown in the help means Markdown's rules.** A line that begins with `-` becomes a list
item, and a backtick becomes code. The docstrings already follow those rules. One that does not
will render as Markdown reads it, not as it was typed.
