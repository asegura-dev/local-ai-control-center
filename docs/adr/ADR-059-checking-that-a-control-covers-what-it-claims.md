# ADR-059 - Checking that a control covers what it claims

## Status

Accepted. Phase one of three; the other two are named here and not built.

## Context

Five defects of one shape in three days, every one with a green suite:

| | |
|---|---|
| `enforce_shape` could be set by nothing | ADR-055 |
| a truncated shaped answer parsed to zero | ADR-056 |
| the prompt asked for a format the grammar forbade | ADR-057 |
| deduplication ran on one of four call sites | ADR-058 |
| ntfy promised basic credentials nothing could reach | ADR-058 |

ADR-058 said reading found the last two and no test would have. That was true and it was not
a plan. This is the plan, and building its first piece immediately found two more.

**`AskingJudge` was unreachable.** The judge of readings from ADR-053 - with a port, an
adapter, its own tests, and a **published grade of 6 of 8 and 8 of 8 in a decision record, a
changelog, chapter 4 and a git tag** - was constructed by nothing. No command, no flag, no
configuration. It was graded by a script that built it directly, which is precisely the
mistake ADR-055 named, made again by the person who named it, two days later.

**`require` was dead, and said it was the execution path.** Its module docstring read *"Checking
returns a result so a preview can report what is missing; `require` raises for the execution
path"*, and the rationale on the function itself was *"so an ignored return value can never
become an unnoticed grant"*. Nothing called it. The gate is real and tested - `preview.allowed`,
refused before any effect, with the missing capabilities named and audited - but it is the
returned-value shape that sentence warns about.

## Decision

**Three standing checks, each derived from a defect that actually happened.** Not a general
theory of correctness: three questions that have each already had a wrong answer here.

**One - nothing public is defined that only a test reaches.** A public function or class
referred to nowhere in the source is either unreachable or called from outside, and outside
callers go in `CALLED_FROM_OUTSIDE` with a reason that can be checked by opening the thing
that calls it. Decorated definitions are excluded, because a decorator is a reference and it
is how every CLI command is registered; string constants count as references, because
`getattr(converter, "furniture_dropped", 0)` is one. This found both defects above.

**Two - controls that must travel together, do.** A short declared list of pairs, currently
one: `check_answer` implies `without_repeats`. Every function calling the first must call the
second. A pair belongs there when the same reasoning applies at every site, so that a new site
forgetting it is a defect rather than a choice; adding one is an argument, not a style rule.

**Three - neither answer format loses everything when it is cut.** A valid answer is truncated
at every character, and what parses out must never collapse to nothing while a whole entry
still precedes the cut, nor exceed what the whole answer held. Verified to **fail** against the
parser as released and pass now.

**Each check guards itself.** A second test feeds each one the defect in its original form and
asserts it is reported. A check that cannot fail is decoration, and three of these were written
by someone who had just shipped four things that could not fail.

**`AskingJudge` is wired rather than removed**, unlike ntfy's helper: `lacc ask --judge`, off
unless asked for, one extra engine call per claim. It leads with the binary and gives the label
beside it, which is what ADR-053's grading concluded and what nothing was able to act on. The
docstring of `require` is removed with the function, because a sentence that reassures about a
control nobody calls is worse than silence.

## Consequences

- Three checks in the suite; five defects of this shape can no longer recur silently.
- The judge is reachable for the first time. Its published grade now describes something a
  person can run.
- `require` is gone and `permissions.py` says what the gate actually is.

## Phases two and three, named and not built

**Two - an inventory from each record to the code it names.** Measured: **52 of 58 records
name at least one real symbol**, 97 distinct. A generated report listing, per record, the
symbols it mentions and every place they are used. It detects nothing. It turns *read the
codebase looking for gaps* into a finite list, and against ADR-054 it would have shown
`without_repeats` used in one place beside a record saying a corpus must not hold the same
sentence twice.

**Three - one pass over all 58 records**, asking of each: what does this claim, where is it in
the code, does it cover that. Five defects in three days is a rate, not bad luck, and it says
there are more. With the inventory this is hours of reading rather than a project.

## Trade-off

**A ranking was tried and is not part of this.** Citations-per-use - a control the records
discuss more than the program executes - puts `parse_claims` at the top, where it is correct
with one caller, and `without_repeats` low **because it had just been fixed**. It is a reading
queue at best, and publishing it as a detector would be this project's own recurring error in
a new costume.

**Three checks encode three known mistakes and no unknown one.** Every one was obvious after
reading the defect and invisible before. This narrows what can recur; it does not find what
has not happened yet, and phase three exists because of that.

**`CALLED_FROM_OUTSIDE` and `PAIRED` are places to hide a defect.** Both are small, both
demand a reason, and neither is a list this project should ever be relieved to add to.
