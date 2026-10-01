# `src/` - where each thing lives

One package, `local_ai_control_center`, in seven layers. This page names every module in it
with one line on what it is for, so you can find the file before you open any. The line is the
module's own docstring, shortened; the docstring is where the reasons are.

`tests/test_indexes.py` keeps this page true: a module added without a line here, or a line
left after its module is gone, fails the suite.

## The layers, from the inside out

| Layer | Holds | May import | Held by |
|---|---|---|---|
| `core/` | The rules: what is allowed, what a plan is, what a quotation check concludes | nothing outside `core/` | `test_core_depends_on_nothing_outside_itself` |
| `ports/` | What LACC needs from the world: abstract classes and the contracts that cross them | nothing outside `ports/` | `test_a_port_depends_on_nothing_outside_itself` |
| `adapters/` | One implementation of a port per file: Ollama, Crossref, PDF and Word, ntfy, rankings | `core/`, `ports/` | `test_an_adapter_reaches_only_for_core_and_ports` |
| `system/` | Machine-facing code that is not behind a port: the audit trail and the profiler | today `core/`, `ports/`, `adapters/` - no test sets a rule | - |
| `features/` | Pure slices: every decision a view draws, testable without a display | `core/`, `ports/` | `test_a_slice_reaches_only_for_core_and_ports` |
| `views/` | The window's sections, one module each, and the shapes they are drawn with | `core/`, `ports/`, `features/`, `views/` | `test_a_section_reaches_only_for_what_a_view_may_reach` |
| the root | `cycle.py`, the one place a run proceeds; `cli.py` and `window.py`, the two views | anything - they compose | `test_a_view_contains_no_logic` |

Two rules cross the layers. **A view decides nothing**: a function in `cli.py` or `window.py`
that never touches the screen is logic, and belongs in `features/` (ADR-066). **The rules do
not know how a run proceeds**: nothing in `core/` imports the cycle
(`test_nothing_in_core_imports_the_cycle`), and every skill run and every conversion goes
through `cycle.py`, the only module that knows the order - preview, refuse or ask, act,
record (ADR-008).

## Where to start reading

1. `core/permissions.py` and `core/workspace.py` - what a skill may do, and where.
2. `core/skill.py` - what a skill is: a pure `plan`, and nothing else.
3. `cycle.py`, from `run_action` - how a plan becomes a run, and where every effect happens.
4. `core/grounding.py` - how a quotation is checked against the document it names.
5. `cli.py`, the `run` command - how a person reaches all of it.

`docs/stack/` follows one run through these files, and says what each technology is for.

## The root

| Module | What it is |
|---|---|
| `__init__.py` | The package, and its version. |
| `cycle.py` | The execution cycle: the one place that knows how a run proceeds - preview, permission, provider, quotation check, audit (ADR-008, ADR-014). |
| `cli.py` | The `lacc` command: every subcommand, and the composition that hands the window what it cannot build (ADR-029). |
| `window.py` | The second view: three columns, a theme, a configuration picker and routing; the sections live in `views/` (ADR-069, ADR-075). |

## `core/` - the rules

| Module | What it is |
|---|---|
| `__init__.py` | The layer. |
| `budget.py` | How much of a context window a prompt may use, and how much is held back for the answer. |
| `config.py` | The configuration: a validated contract for how LACC is allowed to run, and its YAML loader (ADR-002). |
| `corpus.py` | Reading back a collected corpus, so several can be assembled into one. |
| `drafts.py` | Where brought drafts live in a workspace, and how one is told from a file put there by hand (ADR-111). |
| `declared.py` | Skills written down in a file rather than in code, and what a file may not decide (ADR-048). |
| `fence.py` | The fence around a document in a prompt: what it removes, what it only notices (ADR-038). |
| `grounding.py` | Checking that a quotation appears in the document it claims to come from (ADR-026). |
| `headings.py` | Finding the sections of a document, and what a PDF says about itself. |
| `kinds.py` | What a file in a workspace is, decided once (ADR-090). |
| `passes.py` | Dividing a document too large for the window into readings that fit (ADR-045). |
| `permissions.py` | What a skill is allowed to do, restrictive by default; the configuration only removes (ADR-004). |
| `preview.py` | Describing an intended action before it runs, with no effect of its own (ADR-007). |
| `references.py` | Reading the reference list a document already carries (ADR-064). |
| `run.py` | A unique, readable identifier for one execution, and its progress (ADR-002). |
| `sections.py` | The sections a document numbers for itself (ADR-076). |
| `skill.py` | Skills: named units of work whose `plan` is pure; effects happen in the cycle. |
| `wording.py` | A count and the word it counts, agreeing: `1 section`, `2 sections` (ADR-120); and the words after a count: `1 was`, `2 were` (ADR-121). |
| `workspace.py` | The bounded area LACC may operate in, and the boundary that refuses `..`, links and absolute paths (ADR-003, ADR-017); what a typed name or pattern names inside it (ADR-112). |

## `ports/` - what LACC needs from the world

| Module | What it is |
|---|---|
| `__init__.py` | The layer. |
| `converter.py` | Anything that turns a document into text. |
| `embedder.py` | Anything that turns text into a vector (ADR-061). |
| `entailment.py` | Anything that judges whether a quotation supports the reading given of it (ADR-053). |
| `notifier.py` | Anything that says a run finished, to a machine the user named. |
| `provider.py` | Anything that completes a prompt: the engine's contract (ADR-005). |
| `registry.py` | Anything that says what a work is, given its DOI (ADR-067). |
| `retriever.py` | Anything that chooses which passages go into a prompt (ADR-050), and says what choosing would send to an engine before it sends it (ADR-106). |

## `adapters/` - one implementation per file

| Module | What it is |
|---|---|
| `__init__.py` | The layer. |
| `asking.py` | Judging a reading by asking the engine already configured (ADR-053). |
| `crossref.py` | Asking Crossref what a work is, and keeping every answer (ADR-067, ADR-102). |
| `dense.py` | Choosing passages by meaning, and fusing that with choosing by words (ADR-061). |
| `documents.py` | Converters for PDF and Word; what a converted file says about itself (ADR-101). |
| `embedding.py` | Embedding text with the engine LACC already talks to (ADR-061). |
| `mock.py` | A provider that touches nothing outside the process, for tests and dry runs. |
| `ntfy.py` | Notifying through ntfy, to a server the configuration names. |
| `ollama.py` | The Ollama provider: the boundary between LACC and what produces model output. |
| `vectors.py` | Keeping vectors beside the corpus they were made from (ADR-061). |
| `words.py` | Choosing passages by the words a question uses - no model, no network (ADR-050). |

## `system/` - the machine, not behind a port

| Module | What it is |
|---|---|
| `__init__.py` | The layer. |
| `audit.py` | The append-only, hash-chained trail of what LACC did, its anchor, and the walk that checks it (ADR-006, ADR-023, ADR-049, ADR-104). |
| `profiler.py` | What the machine offers - memory, graphics, the work area, whether a drive is on the network - reported, never acted on. |

## `features/` - the decisions a view draws

| Module | What it is |
|---|---|
| `appearance.py` | How the window looks and where it opens, and what it remembers (ADR-069, ADR-100). |
| `ask.py` | Turning selected passages into what a question is asked against (ADR-085). |
| `bibliography.py` | A bibliography in Markdown from what a registry said (ADR-067). |
| `bibtex.py` | A bibliography LaTeX can cite from, from the same answers (ADR-102). |
| `bring.py` | Whether one named file may be brought into the workspace - never from another machine - and what its copy is called (ADR-111, ADR-112). |
| `commands.py` | The commands, read from the application that registers them (ADR-072, ADR-103). |
| `corpus.py` | Writing a corpus, and re-checking one written before (ADR-066). |
| `coverage.py` | How far the nearest quotation is from each topic you name (ADR-088). |
| `editing.py` | What a configuration may be changed to from the window, and what it may not (ADR-094). |
| `identity.py` | Which work a document is, when nothing in it says so (ADR-087). |
| `measure.py` | Describing repeated measurements of the same thing. |
| `navigate.py` | Finding the part of a document a question is about (ADR-079). |
| `overview.py` | What can be known about a workspace without running anything (ADR-069). |
| `prompts.py` | What each skill asks the model, before anything is asked (ADR-074). |
| `reading.py` | Reading this project's own documentation inside the window (ADR-070). |
| `review.py` | Reading a draft against the sources its writer collected (ADR-068). |
| `stages.py` | Where the work stands, stage by stage (ADR-080). |
| `status.py` | What is true about a workspace right now, for the line along the bottom (ADR-077). |
| `thread.py` | A thread of questions over one corpus, and what it carries (ADR-091). |
| `trail.py` | What LACC did in a workspace, as runs, and whether the trail holds (ADR-104). |
| `workspaces.py` | Which workspace a configuration points at, and what it would cost to put one somewhere (ADR-093). |

## `views/` - the window's sections

| Module | What it is |
|---|---|
| `__init__.py` | The layer. |
| `section.py` | What a section is, and the state the window hands it (ADR-075). |
| `paint.py` | The few shapes every section is drawn out of. |
| `work.py` | *Where it stands* and *Coverage*. |
| `asking.py` | *Ask*: a question behind a preview, on a worker, as a thread (ADR-085, ADR-091, ADR-099). |
| `workspace.py` | *Reviews*, *Written*, *Corpora* and *Documents*. |
| `making.py` | *Workspaces*: making one, after saying what it would cost (ADR-093). |
| `audit.py` | *Audit*: what was done, read from the trail (ADR-104). |
| `program.py` | *Commands* and *Prompts*. |
| `settings.py` | *Configuration* and *Engines* (ADR-094). |
| `records.py` | *Documentation*: this project's own records (ADR-070). |
