# Working this way, in detail

[How a change is made here](how-a-change-is-made-here.md) is the method in six steps. This is
the same method with the detail that makes it repeatable: what each step actually looks like,
what goes wrong inside it, and the wording that keeps the result honest.

Every example is from this repository and most are from the day it was written.

---

## 1. Measuring is not counting once

The first number is usually wrong, and it is usually wrong in the direction that flatters. The
work is the loop:

    count  ->  look at what was counted  ->  distrust it  ->  narrow the rule  ->  count again

**A worked example, start to finish.** The question was whether a PDF's own section numbering
could be recovered, so that a 348,000-token guideline could be read one section at a time.

**First count.** A line beginning with a number and a capitalised word: **16 of 24 documents**
had three or more. Encouraging.

Then the second step, which is the one people skip - printing what had been counted:

    20:1. INT RODUCTION      11
    66:  3.2.1.1 Ethni
    94:  3.2.2.2 Diet

Those are **table-of-contents entries**. A page number on the end, a title truncated to
`Diet`. The body of that document does not look like that at all: there a heading is `3.2.3`
alone on its line.

**Second count.** Add consecutive numbering - the structural anchor another record had already
justified. It went **up**, to 18. Printing again:

    55   1   Department of Nuclear Medicine, University Hospital
    671  1   Afshar-Oromieh A, Avtzi E, Giesel FL, Holland-Letz T

Author affiliations, and the bibliography. **Every numbered list is consecutive.** The anchor
that works for reference lists is useless for telling a section from one.

**Third count.** Require the dot: a section is `1. Introduction`, an affiliation is
`1 Afshar-Oromieh`. The count fell to **10 of 24**, and the output was finally clean.

Three rules, three counts - 16, 18, 10 - and the honest one is the smallest. **A refinement
that raises your number deserves more suspicion than one that lowers it.**

### What to actually run

Print totals *and* examples, always in the same script:

```python
print(f"{len(found)} candidates in {path.name}")
for line, label, title in found[:14]:          # the part that catches the error
    print(f"  {line:6}  {label:8} {title[:52]}")
```

Fourteen rows is enough to see a table of contents, an affiliation list or a bibliography for
what it is. A total never is.

Scratch scripts belong in a temporary directory, not the repository. When a measurement turns
out to be worth taking again, it moves into `tools/measure.py` - which prints nothing to a
file, because [a stored number goes stale](#7-the-traps-in-this-particular-project).

---

## 2. Deciding on paper before deciding in code

Copy [`docs/adr/TEMPLATE.md`](../adr/TEMPLATE.md). The sections are not ceremony; each one
catches a different way of being wrong.

**Title.** A sentence, not a noun. *"Metadata from a registry, not from a model"* carries the
argument; *"Crossref integration"* carries a vendor.

**Context.** What is true now that makes this worth deciding, with the numbers. If a figure
appears, it is dated by the record's own date - and if it comes from somewhere else, say
where.

**Decision.** Bold sentences somebody could disagree with, one per paragraph, each in the
shape *X, because Y* where Y is measured or is a principle already written down.

And say what was **refused**:

> No contact address is sent, although Crossref offers a faster queue to clients that supply
> one - that address is the user's, and trading their personal data for throughput is not a
> decision this module makes on their behalf.

Half the value of these records is the road not taken. A future reader needs to know it was
considered.

**What was measured.** The table. Include the counts that *changed the plan* - "counting
refused half the idea" is the most useful sentence a record can hold, and it has been true
three times here.

**Trade-off.** Never empty. If it is hard to write, the decision is not understood yet. Write
the strongest version of the objection:

> A named-exception list is a thing that can be added to. Nothing mechanical stops someone
> appending a name instead of moving a function, and the honest answer is that this record is
> where that would be visible, not the test.

---

## 3. Naming

**Functions say what they answer**, not what they are. `might_support` rather than
`get_candidates`. `without_truncations` rather than `filter_dois`. `standing_said` rather than
`format_verdict`.

**Tests are sentences, and they state the rule rather than the mechanics:**

    test_a_contradiction_outranks_support
    test_a_judge_that_could_not_answer_is_not_support
    test_the_abstract_is_not_read_however_it_arrives
    test_a_damaged_cache_is_re_asked_rather_than_guessed_at

Read as a list, those are a specification. `test_concluded_returns_finding` is not.

**A test name that says "rather than" or "however" is usually a good test**, because it names
the wrong behaviour it exists to prevent.

**Modules are named for the question they answer**: `grounding`, `references`, `overview`,
`appearance`, `sections`. Not `utils`, `helpers` or `manager`.

---

## 4. Docstrings carry the why

The what is in the code. A docstring that repeats it is noise that will go stale.

```python
_ENOUGH_WORDS = 8
"""Below this a paragraph is a caption, a label or a transition, not an assertion.

Eight rather than twelve, and the difference matters: "PSMA PET/CT is more sensitive than
CT for nodal staging" is ten words and is exactly the kind of sentence this exists to
check. A threshold that skipped it would skip the strongest claims in a draft, which are
usually the shortest.
"""
```

That says what the number is, why it is that number, and what would break at another. The
constant alone says none of it.

**Comment the surprising line, in place:**

```python
# `holds` is what decides the page, not `found_on_page` directly: the two agree by
# construction in `grounding`, and depending on that here would make this file's output
# rest on an invariant of another module.
number = checked.found_on_page if checked.holds else None
```

**When a defect taught you something, leave it where it happened:**

```python
"""A quoted line, with or without the bullet an assembled corpus uses to mark a subject.

The bullet was added to the writer and broke the reader, which the round-trip test did not
catch because it only ever round-tripped an unmarked corpus. Two hundred and sixty-five
quotations were silently unreadable.
"""
```

---

## 5. Verifying, in three passes

**The gate**, every time, all four:

    .\run.ps1 run ruff check .
    .\run.ps1 run ruff format --check .
    .\run.ps1 run mypy src
    .\run.ps1 run pytest -q

**The mutation.** Break the thing on purpose and watch the check catch it. Two minutes:

    # add a pure formatter to cli.py
    AssertionError: logic in cli.py: ['_quietly_added_logic']
    # then take it out

Do this for every check that is supposed to prevent something. A check nobody has seen fail is
a check nobody has seen work - and this one, when tried, turned out to be **looking at less
than it claimed**: it walked top-level functions, which covered `cli.py` and barely touched
`window.py`, which is almost entirely methods.

**The real run.** On your own material, with the expected answer **written down first**:

> Five paragraphs, each with its correct answer decided before the run. It caught both planted
> errors. The one disagreement was the prediction's fault - the paragraph carried a causal
> clause no quotation supports, and whoever wrote it had not noticed.

That last sentence is only possible because the expectation was written first. Without it, a
disagreement is an argument rather than a result.

---

## 6. Writing it down

**The commit message is the record's short form.** What changed, the measurement, and what it
cost. Not "fix bug".

    fix: one corpus format, written by both writers

    Assembling a corpus twice stripped the paraphrase from every quotation
    in it, silently, while reporting figures that were all true.

    ...

    Found by adding one document to a real corpus and noticing the result
    was 35 KB smaller with 178 more quotations. Nothing else would have
    shown it: the counts were right, the quotations were right, the file
    parsed, and 620 tests passed.

**Reporting a finding**, to yourself or anybody else:

- **The number first.** "0.3 to 0.5%" before "the structure is cheap".
- **A table when there is more than one figure.** Prose hides a comparison.
- **Say which way an error leaned.** Six of twelve wrong figures here flattered the tool, and
  that sentence is more useful than the twelve.
- **Say what you got wrong, in the same breath.** Two corrections in one session: a figure
  written as ten that was four, and a claim about where a class belonged that was checked only
  when someone tried to act on it.

**Finish the documentation in the same session.** The record, the changelog, the chapter, the
index, the log. Late documentation is a false statement about what the code does.

---

## 7. The traps in this particular project

**A figure goes stale silently.** *"Eight of 24 documents never entered the window"* was
measured correctly and then repeated for days after the number had become two. Nothing was
measured wrong; the tense aged. **Ask when a figure was taken** - and prefer a figure you can
re-take in seconds to one written in a file.

**A check covers a type and not a path.** Two features were counted as delivered and were not
there, with green tests, because the tests built by hand the thing the program never builds.
**If only a test reaches a switch, the switch is not there.**

**Two writers of one format drift.** A round-trip test covered one of them; the other arrived
later and nothing connected them. Assembling a corpus twice stripped the meaning from every
quotation in it. **Anything written in two places will disagree in one of them** - which is
why the command list in the window is derived from the application rather than listed.

**A refactor feels like progress.** Six consecutive releases here were defensible refactors
that advanced nothing. The test: can you state, in a number, the risk it removes? *"Adding a
section meant editing four places, and getting three right produced a button that did
nothing"* passes. "It is cleaner" does not.

**Structure is obeyed; instruction is negotiated.** A pre-seeded skeleton took coverage from
10 of 24 documents to 23. The instruction "do not use your own knowledge" did not prevent
twelve fabrications. **Build on structure, never on a request.**

---

## The shortest version

1. Count, then **look at what you counted**.
2. Suspect a number that went up.
3. Write the decision, including what you refused, before the code.
4. Break the check on purpose.
5. Run it on real material with the answer written down first.
6. Report what went wrong, including your own part.
7. Finish the documentation today.
