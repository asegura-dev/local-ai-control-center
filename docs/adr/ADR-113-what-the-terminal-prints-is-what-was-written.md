# ADR-113 - What the terminal prints is what was written

## Status

Accepted. The rest of what the test of 29 September called D9, and a failure found while fixing
it; built on 30 September.

## Context

Everything the CLI prints goes through Rich, and Rich reads anything shaped like `[word]` as a
style: `[bold]`, `[red]`, `[/red]`. The program writes its own lines that way on purpose. But
the same lines carry things the program did not write, and Rich cannot tell the two apart:
- a file's name;
- a quotation or a section's title from a document;
- an error;
- the engine's answer.

- **A name lost a part of itself.** ADR-112 fixed this for the preview of `bring`, where
  `Metodología [v2] ñ.md` had been shown as `Metodología  ñ.md`. Every other line that named a
  file did the same.
- **An answer lost a part of itself.** Of the 174 answers the workspace's trail keeps, 10 hold
  something Rich reads as a style. Among them are the sources an answer cites, such as
  `[eau-6.4.5-nodal-rcN1.md, p. 107]`, which printed as nothing: the one part of an answer that
  says where it came from. Numbered sources such as `[10] …` survived only because Rich's tags
  must begin with a lowercase letter.
- **A stray closing tag raised.** `[/b]` anywhere in an answer ends the program with
  `MarkupError`, after the answer has arrived. ADR-062 made the display the one place where
  failing quietly beats failing correctly, and caught encoding errors and nothing else.

Measured on the working corpus, none of the 1,456 quotations holds a tag-shaped bracket. The
defect was live in names and in answers, and latent in quotations.

## Decision

- **What the program puts into a line it prints goes through `_plain`**, which escapes it for
  Rich. That covers names, paths, quotations, titles, errors, hosts and model names. The
  exceptions are three:
  - a style's name, put between brackets on purpose (`colour`, `style`);
  - a constant the program wrote;
  - a number formatted as a number.

  In `cli.py` that is 216 places, and counts are formatted as counts (`:,`). The status line
  that carried its own markup in a variable now carries a word and a style.
- **What the program prints whole and did not write is printed with markup off**: an engine's
  answer, what ranking would send, a sentence from the trail. Panels of the same get a `Text`,
  which Rich never reads as markup.
- **A line whose markup is broken anyway is printed as it is**, not raised.
- **A rule reads `cli.py`.** It fails on any value put into a printed line without `_plain`, and
  on anything printed whole without markup off. It is shown to fail on the defect before it is
  trusted to pass.

## Consequences

- The ten answers print whole, sources included, and `[/b]` prints as `[/b]`.
- Tests:
  - the rule on `cli.py`, and the same rule failing on the shapes it forbids;
  - `_show` printing a stray `[/b]` instead of raising;
  - `run`, through the mock provider, printing `Dice [v2], luego [/b] y [sic].` as written;
  - `metadata` printing `nota [v2].md`.
- Presentation only: nothing that is recorded, verified or written to a file changes. The
  window does not use Rich.

## Trade-off

**The rule knows the CLI's printers by name**: `_show`, `console.print`, `Panel` and
`add_row`. A new way to print that is none of those is outside it until it is added.

**It trusts names in capitals and two style variables.** A constant is the program's own words
by convention, not by proof, and a variable called `colour` that held a sentence would pass.
