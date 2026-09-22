# ADR-086 - A variable is not a call

## Status

Accepted. The rule this project leans on hardest had a hole in it, and the hole was found by
adding a function to the list of names it excuses and then checking whether the excuse was
needed. It was not.

## Context

`test_a_view_contains_no_logic` is the converse rule (ADR-066): a function in `cli.py` or
`window.py` that never touches the presentation, directly or through anything it calls, does
not belong in the view. It is the check that would have caught ADR-065, where both writers of
the corpus format lived in `cli.py` while its reader lived in `core` - and they drifted, and
assembling a corpus twice silently stripped the meaning from every quotation in it.

Its closure over calls was built like this:

```python
def mentioned(node):
    found = set()
    for inner in ast.walk(node):
        if isinstance(inner, ast.Name):
            found.add(inner.id)
        elif isinstance(inner, ast.Attribute):
            found.add(inner.attr)
    return found

calls = {name: {plain[c] for c in mentioned(fn) & set(plain)} for name, fn in functions.items()}
```

**`mentioned` collects every name a function writes down**, and the edges of the call graph
were drawn from that set. A parameter called `corpus`, a local called `plan`, a loop variable
called `main` - each of them was read as a call to the function of that name.

`cli.py` has `@app.command() def corpus(...)`, which prints. Three functions take a corpus:

    _retriever_for(config, corpus)          -> builds the ranking
    _passages_for(question, corpus_file, ...) -> reads it, ranks it, renders it
    _asking_for_the_window(config, workspace) -> composes what the window may run

All three were joined to the `corpus` command by a variable name, inherited its presentation,
and became invisible to the rule.

## What that cost

**`_passages_for` was a third copy of one decision.** Reading a corpus, keeping only what was
found in its document, turning it into passages, computing the budget and ranking it existed
three times: inline in the `ask` command, in `_passages_for` for `measure`, and - as of
ADR-085 - in `features/ask.py` for the window. Three writers of one decision, in a view, which
is the exact shape of defect this rule exists to catch, hidden by the rule's own blind spot.

Nothing had drifted yet. That is luck, not design: ADR-065 is what happens when it does.

## Decision

**The closure is drawn from call sites, not from names.**

```python
def called(node):
    found = set()
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        if isinstance(inner.func, ast.Name):
            found.add(inner.func.id)
        elif isinstance(inner.func, ast.Attribute):
            found.add(inner.func.attr)
    return found
```

The **direct** check still uses every name, because a presentation type can arrive as an
annotation or a bare reference and that is still a view touching a view. What changes is only
what counts as *one function reaching another*.

Applied, it makes three functions visible in `cli.py` and none in `window.py`:

| | |
|---|---|
| `_retriever_for` | composition - named in the exception list beside `_build_provider` |
| `_asking_for_the_window` | composition - named there too (ADR-085) |
| `_passages_for` | **a duplicate. It does not get an exception; it goes.** |

**`ask`, `measure` and the window now take one path.** `features/ask.py::prepare` is the one
place that decides what a question would send; `_prepared_or_exit` in the view prints it and
exits when there is nothing to send. The `ask` command lost thirty lines and gained nothing it
did not have.

**An exception that is no longer needed now fails.** `test_the_named_debt_is_really_still_there`
checked that every excused name still exists in a view. It did not check that the excuse was
still *needed*, so a name could stay after its function started touching the presentation - an
excuse nobody needs is an excuse nobody re-reads. It now asserts both directions.

**And `tools/measure.py` stops keeping its own copy of the vocabulary.** It had one, and the
copy was **thirteen names behind** the enforced set: `yview_scroll`, `CTkTextbox`, `winfo_width`,
`clipboard_append`, `set_appearance_mode` and eight more had been added to the test and never
to the tool. The visible consequence was the tool reporting `Window._wheel` as logic in a view
when the rule did not. It reads the vocabulary, the views and the excused names from
`tests/test_layering.py` now, and when it cannot read them it says so and measures nothing -
because a stale answer here is worse than none.

## Consequences

- One decision where there were three, and the CLI and the window give the same answer to the
  same question by construction rather than by care.
- `Prepared` carries the passages it chose, not only their rendering, because `--judge` offers
  candidates from them.
- The exception list is six names: `main`, `_build_provider`, `_page_range`, `_words`,
  `_retriever_for`, `_asking_for_the_window`, and `Window._state`. Each is the entry point,
  composition, or the parsing of a view's own argument.
- `tools/measure.py` and `tests/test_layering.py` now agree by construction: seven excused
  names in `cli.py`, one in `window.py`, and nothing unexcused.

## Trade-off

**Call sites are still a heuristic.** A function passed as a value - `command=self._go`,
`lambda: _prepare(...)` - is not a call site, so the closure does not follow it. That direction
of error is the safe one: it makes the rule report *more* as logic, never less, and the
exception list is where each of those gets argued by name. The old direction of error was the
dangerous one.

**The rule got stricter and the list got longer.** Two names added at once looks like the list
growing, and a list that grows is how an absolute rule becomes a negotiable one. The defence is
that `_LOGIC_THE_VIEW_STILL_HOLDS` - the debt list, as opposed to the legitimate-exception list
- is still empty, and that the new test makes every name on either list justify itself on every
run.

**And this is the second time a check of this project was measured and found wrong in the
flattering direction.** The first was the corpus. The rule reported a view with no logic in it
while three functions sat outside its view.
