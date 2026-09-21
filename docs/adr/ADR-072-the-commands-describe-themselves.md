# ADR-072 - The commands describe themselves

## Status

Accepted. The interesting part is what was refused, not what was built.

## Context

The window shows a workspace, its corpora, its reviews and this project's records. What it
could not show was **what LACC can actually do** - and that is the first question anybody has,
including somebody who has been using it for weeks and has forgotten whether the flag is
`--against` or `--from`.

`lacc --help` answers it, in the terminal, which is the place the window exists to be an
alternative to.

## Decision

**The list is derived from the application, never written down twice.**

That is the whole decision, and it is made against a measured failure. A hand-written list of
commands in the window would be a **second writer of the same thing**, and this project has
already paid for that: two writers of the corpus format disagreed about the format, silently,
with 620 tests green, and assembling a corpus twice stripped the meaning from every quotation
in it (ADR-065). A stale command list is a smaller loss, but the shape is identical - and the
shape is what this project learned to recognise.

So `commands_of` reads the Typer application: the registered commands, the name Typer gives
each one, the first line of its docstring, the rest of it, and the parameters from the
signature. A command added appears. One renamed changes. One with no docstring fails a test.

**It does not import the CLI.** The application is passed in - the CLI has it already, and
hands it to the window. A view importing another view would work and would be the beginning of
the window knowing things about the CLI; passing the object keeps the slice reachable only for
core and ports, and makes the whole thing testable against a plain object of the same shape.

**Typer's naming is copied exactly, including where it looks wrong.** A function named
`engine_test` becomes `engine-test`; a name that would come out oddly comes out oddly. The
point is to say what the CLI **answers to**, not what it ought to answer to. A list that
quietly improved on the real names would be wrong in the way that matters.

**The window shows what to type and runs nothing.** Usage, required parameters, optional ones,
and the docstring's reasoning rendered as blocks (ADR-070). The panel ends with the line to
type in a terminal, which is where commands are run until a record says otherwise (ADR-069).

## Consequences

- A fourth section in the window, and the first one whose content is the program itself.
- `--config` is left out of every listing: nearly every command takes it and it is the point
  of none of them.
- A test runs `commands_of` against the real application and asserts every command has a
  first line. A command shipped without one now fails the gate.

## Trade-off

**The signature is not the interface.** Typer decides an argument from an option using the
same rule this does - a default or no default - but the *flag names* come from
`typer.Option("--against")` annotations this does not read. Where a flag differs from its
parameter name, the window shows the parameter name. That is a real inaccuracy, it is
bounded, and reading the annotations properly means this module knowing about Typer, which is
the coupling it was written to avoid.

**Docstrings written for a developer now face a user.** They are good ones here - most explain
*why* a command behaves as it does - but they were not written as help text, and a few will
read oddly in a panel.
