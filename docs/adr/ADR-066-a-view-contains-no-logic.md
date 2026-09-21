# ADR-066 - A view contains no logic

## Status

Accepted. The rule it adds is the converse of one this project has enforced since the
restructure, and the defect it would have caught is ADR-065, which cost a user's corpus its
meaning.

## Context

PRINCIPLES says **the core contains no interface code**, and `tests/test_layering.py` proves
it five times over: core imports nothing outside itself, a port imports nothing outside
itself, an adapter reaches only for core and ports, nothing in core imports the cycle, and
every module lives in a layer that has a meaning.

**All five follow dependencies inward. None of them asks whether logic has leaked outward.**

The rule was written in one direction and only that direction was ever checked. What the
other direction costs was measured, not imagined:

| | |
|---|---|
| `_collected_markdown` - **writes** the corpus format | `cli.py` |
| `_assembled` - **writes** the corpus format | `cli.py` |
| `parse_corpus` - **reads** the corpus format | `core/corpus.py` |

Two writers in the view and one reader in the core, free to drift apart with 620 tests green.
They did drift apart, and assembling a corpus twice stripped the meaning from every quotation
in it while reporting figures that were all true (ADR-065).

`cli.py` is **2,588 lines, 72% of all root-level code**: fourteen commands and forty-nine
helpers, of which the six largest that are not presentation account for 341 lines.

## How the rule is stated so that a machine can check it

The difficulty is that "logic" has no syntax. What has syntax is the opposite:

> **A function in a view that never touches the presentation - not directly, and not through
> anything it calls - is not part of the view.**

Presentation here is the concrete vocabulary this view uses: `Console`, `_console`, `_show`,
`Progress`, `Panel`, `Table`, the confirmation prompts. The check walks each function for
those names, then takes the **transitive closure** over calls within the module, because a
helper that only formats a string for a helper that prints it is still presentation.

Three things are exempt and each is named rather than assumed: **the commands themselves**,
which Typer decorates and which exist to be the view; **the entry point**; and **composition**
- the view is the driving adapter, so building a provider from a configuration is its job.

Run against `cli.py` as it stood, the rule names **twelve functions, 284 lines**, and the
first two it names are `_collected_markdown` and `_assembled`. Run against the commit where
the defect was still live, it names them first as well. **The check derived from the defect
finds the defect**, in the code that had it. That is the whole argument for it.

Two things were measured rather than assumed once it existed:

| | |
|---|---|
| logic in the view before the first slice | **12 functions, 284 lines** |
| after `features/corpus.py` landed | **8 functions, 110 lines** |
| after `ask`, `measure` and `ask_once` followed | **4 functions, 30 lines - all of them legitimate** |
| against `cli.py` at the ADR-065 commit | names `_collected_markdown` and `_assembled` first |
| a pure formatter added to the view on purpose | **the test fails, by name** |
| a name left in the list after its function moved | **the second test fails, by name** |

The last row is the one that matters. A check nobody has seen fail is a check nobody has
seen work.

## Decision

**A vertical slice per capability, over a hexagon that stays horizontal.** This was the shape
proposed, and counting refused half of it before it was accepted:

| | |
|---|---|
| core modules used by exactly one capability | **3 of 14** |
| core modules used by three or more places | **9 of 14** |
| `config` alone, imported by | 9 modules |

**So the core is not cut.** Nine of its fourteen modules are genuinely shared, and slicing
them by capability would invent boundaries the code does not have - which is how a refactor
becomes six consecutive releases that advance nothing, something this project's roadmap
already records happening once.

The cut goes where the monolith is. `features/<capability>/` holds what a capability does,
pure where it can be and reaching for the workspace where it must, and the CLI and any later
interface are **two views of the same slice**. A slice may use `core` and `ports`; it may not
use another slice, and it may not use the view.

**`_collected_markdown` and `_assembled` land in the same slice as the reader that has to
agree with them.** That is the point, and it is stronger than the test: the arrangement makes
ADR-065 impossible rather than merely detectable.

**The check shipped with the violations it could not fix yet, named one by one**, and then
they were fixed. The list went 12 -> 4 -> **0**: `corpus` took the two writers and the
re-check, `ask` took `as_material` and `might_support`, `measure` took `spread`, and
`ask_once` went to **the cycle rather than a slice** - running an action through the whole
system is orchestration, and this project has one place for that (ADR-029).

Four functions in the view never print, and all four belong there: the entry point,
composition, and two that parse this view's own arguments. **The exception list is empty, so
the rule is absolute** - the next function of logic written into the view fails the suite the
day it is written.

A list of names was the right shape even while it was full: a baseline that were a *number*
would let one function leave and another arrive in its place.

A baseline that is a number would be a lie waiting to happen - it would let one function
leave and another arrive. A baseline that is a list of names cannot.

## Consequences

- `tests/test_layering.py` gains the converse of the rule it has enforced from the start,
  and grows from five tests to eight: the rule, a check that the exception list still
  describes functions that exist, and the boundary of a slice.
- A second test guards the first. An exception list shrinks by **moving code, never by
  editing the list** - without that, a name could stay after its function left and the list
  would quietly stop describing anything, which is the same failure as a figure whose tense
  has aged.
- `features/` is a layer with a meaning, and `test_every_module_lives_in_a_layer_that_has_a_meaning`
  learns it.
- The first slice is `corpus`, because it is the one whose absence was measured in damage.
- The interface planned for v2.5.0 is bound by this before a line of it is written. That is
  the reason to do it now rather than alongside: a second view doubles whatever the first one
  got wrong.

## What it missed, and how that was found

**The check looked at top-level functions, and a window is almost entirely methods.** For as
long as `cli.py` was the only view that was invisible - it is mostly module-level functions -
and the rule read as complete. The second view arrived as a class, so the rule covered it in
name and barely touched it in fact.

Found the way most things here are found: by writing the window and then asking what the check
had actually looked at. It now walks the methods of a view's classes too, resolving
`self.other()` through the bare name so the transitive closure crosses a class. Run against the
window it named exactly one, `_clear`, which destroys widgets and reaches nothing else - a
false positive answered by admitting `destroy` and `winfo_children` to the vocabulary, since
taking widgets away is as much presentation as putting them there.

Properties and decorated methods are treated as presentation by position: they belong to the
widget that holds them.

**The lesson is the one this project keeps relearning.** A rule is enforced over whatever the
check happens to walk, and the boundary of *that* is invisible until something outside it
arrives. It is the same shape as ADR-065, one level up: a check written for the case that
existed, meeting a case that came later.

## Trade-off

**The rule can be satisfied without being obeyed.** A function that calls `_show` once is
presentation by this definition whatever else it does. The check finds logic that is plainly
separate, not logic braided into printing, and the braided kind is the harder kind. It is a
floor.

**A named-exception list is a thing that can be added to.** Nothing mechanical stops someone
appending a name instead of moving a function, and the honest answer is that this record is
where that would be visible, not the test.

**It is not free.** Moving a function changes import paths, and every decision record that
names one is describing a location that has changed. `tools/record_coverage.py` lists which
symbols each record names and where they are used, which makes the damage countable rather
than discovered later.

**One debt was named here and turned out not to be one.** This record first said `RunResult`
was misplaced in `cycle.py` and belonged in the core. It does not: its `completion` field is
a `Completion`, which is the contract crossing the provider port, and **the core may not
import a port** - the first test in this file has said so since the restructure. `RunResult`
knows both core and ports, which is exactly what the cycle is for, so it is where it belongs.

The correction is left visible rather than edited away, because the claim was written without
being checked and that is the failure this project measures most often. `features/corpus.py`
still imports the type and only the type; the test of slices ignores type-only imports,
because naming a type is not depending on a module.
