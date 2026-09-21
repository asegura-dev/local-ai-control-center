# How a change is made here

This is the working method the rest of the documentation is a product of. It is written down
because it is repeatable, and because most of what makes this project worth anything came from
following it rather than from any particular feature.

It is six steps and none of them is long.

---

## 1. Measure before you decide

    .\run.ps1 run python tools/measure.py ~/lacc-workspace

Layers and their sizes, logic that has drifted into a view, records against the index, the
suite, and for a workspace: every document with its tokens, pages and structure, and every
corpus with what is citable in it.

**Nothing it prints is stored.** A number in a file is true for a while and then quietly stops
being, which is this project's most frequent defect - twelve wrong figures, six of them
flattering. A figure you can re-take in four seconds never needs to be trusted.

The habit worth forming is smaller than the tool: **before writing a sentence with a number in
it, take the number.** Twice in one session a count refused half of a plan that was already
being written.

> Deduplication by MinHash was planned over a premise nobody had looked at. Measured: zero
> cross-document near-duplicates. The phase was dropped and containment built instead
> (ADR-054).

> A vertical slice per capability was proposed for the whole codebase. Measured: nine of
> fourteen core modules are genuinely shared. Only the views were cut (ADR-066).

## 2. Write the record before the code

Copy [`docs/adr/TEMPLATE.md`](../adr/TEMPLATE.md), number it, fill it in. The template's
comments say what each section is for.

Two sections carry the weight. **What was measured**, when something was, and **Trade-off**,
always - if the trade-off is hard to write, the decision is not understood yet. Say what was
*refused* as well as what was chosen; half the value of these records is the road not taken.

The code then comes out of the record, and the record is what you argue with in three months
when you have forgotten why.

## 3. Make the check fail on purpose

A check nobody has seen fail is a check nobody has seen work.

    # add a function to cli.py that formats a string and prints nothing
    .\run.ps1 run pytest -q tests/test_layering.py
    # AssertionError: logic in cli.py: ['_quietly_added_logic']

Then take it out. This takes two minutes and is the difference between a test and a comment
that runs. It has caught a rule that looked at less than it claimed: the "a view contains no
logic" check walked top-level functions only, which covered `cli.py` and **barely touched
`window.py`, which is almost entirely methods**.

## 4. Run it on real material

    .\run.ps1 run lacc review my-draft.md --against citas.md --into report.md

Every serious defect in this project was found this way and none was found by a test:

| found by | how many |
|---|---|
| using the tool on real documents | **seven** |
| the test suite | none of those seven |

The suite was green through all of them, because each was a difference between a real
document and the documents the tests imagined.

**Decide what you expect before you run it.** `review` was graded on five paragraphs whose
correct answers were written down first; it caught both planted errors, and the one
disagreement turned out to be the prediction's fault - the paragraph had a causal clause no
quotation supported and its author had not noticed writing it. That is only knowable because
the expectation was written first.

## 5. Report what went wrong, including your own part

The changelog here says which figures were wrong and which way they leaned. Six of twelve
flattered the tool. `docs/04-measurements.md` exists for that and is the chapter most worth
reading.

When a measurement contradicts what you wrote, **the measurement wins and the correction stays
visible**. One record claimed `RunResult` was misplaced and belonged in the core; trying it
showed it could not - its field is a contract crossing a port, and the core may not import a
port. The claim had been written without being checked, so the correction was left in the
record rather than edited away.

## 6. Finish the documentation in the same session

A change is not done when the gate passes. It is done when the record, the changelog, the
chapter it belongs to, the index, the roadmap and the log all say the truth about it.

    .\run.ps1 run ruff check .
    .\run.ps1 run ruff format --check .
    .\run.ps1 run mypy src
    .\run.ps1 run pytest -q

Late documentation is not incomplete documentation: it is a **false statement about what the
code does**, and it costs more to repair than the code cost to write. If there is no time to
document it, there was no time to make the change.

---

## The three sentences worth keeping

**Structure is obeyed; instruction is negotiated.** A pre-seeded skeleton took coverage from
10 of 24 documents to 23; the instruction "do not use your own knowledge" did not prevent
twelve fabrications. Build on structure.

**Coverage of a type is not coverage of a path.** Two features were counted as delivered and
were not there, both with green tests, because the tests built by hand the thing the program
never builds. If only a test reaches a switch, the switch is not there.

**Ask when a figure was taken.** A true sentence in a decision record reads as a current one.
This project repeated *"eight of 24 documents never entered the window"* for days after the
number had become two.
