# `tests/` - what holds each promise

Every test file here, with one line on what it holds. The line is the file's own docstring,
shortened; the reasons are in the file. `tests/test_indexes.py` keeps this page true: a test
file added without a line here, or a line left after its file is gone, fails the suite.

Run them through the gate, never with bare `uv` - the repository lives in a synchronised
folder and the environment must not (see `docs/03-development.md`):

    .\run.ps1 run pytest -q

## What every test runs inside

| File | What it is |
|---|---|
| `conftest.py` | **The egress guard**: any connection to anything but this machine fails the suite, so "LACC does not use the network" is enforced rather than claimed (ADR-022). Also builds the PDFs and Word files the ingestion tests read, by hand, so what a test feeds a converter is visible in the test. |
| `fixtures/seeded/` | Documents and answers known before the check ran, for grading the quotation check itself (ADR-044). |

## Guards on the code itself

These test how the program is built, not what it does. Most of this project's defects that no
behaviour test caught were caught - or would have been - by one of these.

| File | What it is |
|---|---|
| `test_layering.py` | The layers are true, not merely described: what each may import, and that a view decides nothing (ADR-066, ADR-075). |
| `test_reachable.py` | A setting the program declares is one it can reach, and nothing public exists that only a test reaches (ADR-055). And every place that completes a prompt, embeds a text or asks a registry is named with what records it - a new place, or a name whose place is gone, fails (ADR-059, ADR-108). |
| `test_bindings.py` | A binding in the window never replaces one it did not make (ADR-096). |
| `test_the_launcher_name.py` | The launcher's name is never split in two (ADR-097). |
| `test_scripts.py` | The launchers are what their recorded digests say they are (ADR-071). |
| `test_indexes.py` | The indexes of `src/` and `tests/` name every file, and nothing that is gone. |
| `test_package.py` | The package imports and has a version. |

## The rules - `core/`

| File | What it is |
|---|---|
| `test_config.py` | The configuration contract and its YAML loader. |
| `test_permissions.py` | The permission contract, the configuration as a ceiling, and checking. |
| `test_workspace.py` | The workspace contract and its boundary, and patterns matched inside it and nowhere else (ADR-112). |
| `test_preview.py` | What a preview reports, and what it must not do. |
| `test_skill.py` | The skill contract and the demonstration skill. |
| `test_declared.py` | Skills written in a file, and what a file may not decide (ADR-048). |
| `test_run.py` | Run identifiers. |
| `test_fence.py` | The fence: what it removes, what it only notices, and what it cannot do. |
| `test_grounding.py` | Parsing claims, and checking quotations against the source. |
| `test_seeded_corpus.py` | The quotation check graded against answers known before it ran (ADR-044). |
| `test_passes.py` | Dividing a document into readings that fit the window. |
| `test_headings.py` | Finding a document's sections so a person can choose one. |
| `test_sections.py` | What a document numbers for itself, and what only looks numbered (ADR-076). |
| `test_references.py` | Reading the reference list a document already carries (ADR-064). |
| `test_corpus.py` | Reading back a collected corpus, and the round trip that makes that safe. |
| `test_kinds.py` | What a file in a workspace is, decided once (ADR-090). |

## The cycle, the trail and the machine

| File | What it is |
|---|---|
| `test_cycle.py` | The execution cycle, end to end against a mock provider. |
| `test_running_in_passes.py` | Reading one document in several passes (ADR-045). |
| `test_audit.py` | The audit log: record format, privacy levels, failure policy, and the chain. |
| `test_anchor.py` | The sidecar that remembers how long a trail was (ADR-049). |
| `test_trail.py` | The trail read back as runs, and `lacc verify`'s sentences (ADR-104). |
| `test_profiler.py` | What the machine offers: fit, model parsing, the work area. |

## Adapters - the world, behind a port

| File | What it is |
|---|---|
| `test_provider.py` | The provider port, the mock, and the Ollama adapter's requests and answers. |
| `test_engine_check.py` | Telling one kind of unreachable engine from another. |
| `test_enforced_shape.py` | A shape the engine enforces, and the path that still works when it cannot (ADR-052). |
| `test_entailment.py` | Judging whether a reading follows from its words (ADR-053). |
| `test_converter.py` | The PDF and Word converters, hidden text, and pypdf's font warning (ADR-040, ADR-103). |
| `test_metadata.py` | What a document says about itself, and what a converted file says (ADR-047, ADR-101). |
| `test_registry.py` | What is accepted from a registry, and what is refused (ADR-067). |
| `test_retrieval.py` | Choosing passages by words, and saying what was left out (ADR-050). |
| `test_dense_retrieval.py` | Choosing by meaning, the vectors beside the corpus, and fusing two rankings (ADR-061). |
| `test_notifier.py` | The notifier port and its ntfy adapter. |

## Features - the decisions a view draws

| File | What it is |
|---|---|
| `test_asking.py` | Asking from the window: what is prepared, and what never raises (ADR-085). |
| `test_thread.py` | A thread of questions, and the one thing it must never carry (ADR-091). |
| `test_review.py` | Reading a draft against a corpus (ADR-068); what could not be judged or read, said apart (ADR-115). |
| `test_coverage.py` | How far the nearest quotation is from a topic (ADR-088). |
| `test_identity.py` | Which work a document is, and a DOI established for either of its files (ADR-087, ADR-103). |
| `test_bibtex.py` | BibTeX written from what a registry said, and nothing else (ADR-102). |
| `test_endings.py` | Every run the trail opens has an end: an interrupted question answered no, the refusal `measure` meets recorded, a record's time taken in its turn (ADR-116). |
| `test_refusals.py` | A refusal, not a traceback: a broken configuration, a forbidden engine, a destination it may not write and a `drafts` that is not a folder, each refused before any work; a command that only reads creates no workspace (ADR-114). |
| `test_printing.py` | What the terminal prints is what was written: every value put into a printed line escaped, answers printed whole with markup off, a stray closing tag printed rather than raised (ADR-113). |
| `test_bring.py` | One named file brought into the workspace: refused for anything wider, shown before it is read, never replacing, recorded (ADR-111); read as typed, never from a share, and shown as it is named (ADR-112). |
| `test_stages.py` | Where the work stands, stage by stage (ADR-080). |
| `test_status.py` | What the bottom of the window says, and what it does not do to find out (ADR-077). |
| `test_navigate.py` | Ordering a document's sections by what a question is about (ADR-079). |
| `test_prompts.py` | What a skill would ask, before it asks it (ADR-074). |
| `test_commands.py` | The commands, read off the application, and usage lines its parser accepts (ADR-072, ADR-103). |
| `test_reading.py` | This project's documentation, turned into blocks for the window (ADR-070). |
| `test_editing.py` | What the window may change about a configuration, and what it may not (ADR-094). |
| `test_workspaces.py` | Which workspace a configuration names, and what it costs to put one somewhere (ADR-093). |
| `test_appearance.py` | Where the window opens, as arithmetic that needs no display (ADR-100). |

## The command line

| File | What it is |
|---|---|
| `test_cli.py` | The `lacc` commands, invoked as a person would, with a temporary workspace and a mock provider. |

## What is not tested here, and why

The window's widgets. Tk cannot be exercised without a display, which is why the window is
kept thin and every decision it draws lives in `features/`, where it is tested.
`tools/measure_window.py` drives the real window instead - text cut off, sections out of
reach, the wheel, Ask against a stand-in engine, the Audit section against the real trail -
and reports; it concludes nothing.
