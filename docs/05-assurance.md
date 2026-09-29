# What this project promises, and how each promise is checked

Every row below is a claim LACC makes about itself in `PRINCIPLES.md` or a decision record,
paired with what actually holds it up. **A promise with nothing in that column but a document
is not a promise**, which is the lesson of six defects found in three days where the record
was right and the program was not (ADR-055 through ADR-059).

Verdicts are: **held** - verified in the source at the place named; **held by test** - a test
fails if it stops being true; **gap** - the claim and the code disagree. A qualified verdict
says which part is which.

First taken 2026-09-18, against v1.5.0. **Re-taken 2026-09-27, against v2.10.0 and the
unreleased work, row by row against the source** - and five rows that had read *held* were
false. Three were fixed the same day (ADR-105); the rest are marked below. On 28-sep ADR-106
closed the gap about preparing a question, and the reading that closed it moved one more row
- the window never freezing - to a gap; ADR-107 closed the one about four commands that left
no record. A row here is true on the day it was checked and needs
re-checking like any other measurement.

## Cybersecurity

| Promise | What holds it | Verdict |
|---|---|---|
| Every capability starts `false` | `Permissions` fields default to `False`; what is granted derives from what the skill declared | **held by test** |
| Configuration removes, never grants | `grant_for(skill, config)` enables what the skill declares, then the ceiling subtracts | **held by test** |
| A command reads and writes only inside the workspace | Every read in the cycle - three routes - resolves through `workspace.resolve_within`, and every result is written inside it. **Two exceptions, deliberate and both in the window, both shown before they happen**: Configuration rewrites a configuration file, and Workspaces creates a new configuration and a folder for it wherever it is asked to (ADR-093, ADR-094). This row read "nothing outside the workspace is touched" until 27-sep | **held, with two exceptions** |
| `..`, symlinks and absolute paths are refused | `resolve_within` resolves the path - following links - and refuses what lands outside; `..`, absolute paths and Windows reserved device names are each tested (ADR-017). A link is refused by the same resolution and **no test tries one** | **held by test, links held** |
| Results go only to new files | Every result a command writes goes through `write_new_file`, which opens with `"x"`. One exception by the letter: coverage's `.reaches.json`, written plainly beside a report that was itself refused if present. What LACC rewrites is its own - the registry's answers, the vectors, the notes of an established DOI, the audit's anchor, the window's preferences - and the configuration, from Configuration only (ADR-039, ADR-094). Every place is in `docs/stack/files-on-disk.md` | **held** |
| Every place LACC writes is listed | `docs/stack/files-on-disk.md`, read on 27-sep from every write in the source: twelve places. This row read "writing happens in three places only", which had not been true since the registry's answers were first kept | **held** |
| Only hosts the configuration names are reached | `ollama_host()` refuses any non-loopback host; a remote engine needs `network_access` **and** an address written in the YAML | **held by test** |
| An environment variable can never widen reach | `OLLAMA_HOST` is honoured only when it resolves to loopback, and refused otherwise | **held** |
| A `.env` cannot override a variable already set | The loader writes only where the name is absent from the environment | **held** |
| `.env` supplies secrets, never destinations | The ntfy address is a `server_url` in the configuration; the topic and token stay named (ADR-060) | **held by test** |
| No arbitrary code execution | No `eval`, `exec`, `pickle`, `subprocess` or `os.system` anywhere in the source; every YAML load is `safe_load`, and the window's preferences are written with `safe_dump` | **held** |
| A document cannot forge a fence | Fence markers are fixed strings holding no user text (ADR-038), tested against a real model | **held by test** |
| Text a reader cannot see is reported, with how much of the document it is | Detection of invisible render modes, off-page positions and unreadable sizes (ADR-040), reported as a count of the fragments read - which the report did not receive until ADR-103 | **held by test** |
| A registry is reached only with two switches on | `registry_url` is empty by default and `network_access` is the ceiling; neither implies the other. `resolve` refuses each case by name, `identify` both with one message (ADR-067). **No test runs either refusal** | **held** |
| Only a DOI leaves, never a document | The request is a URL with a public identifier; no corpus, quotation, question or filename is sent | **held** |
| No contact address is sent unless written | `registry_mailto` is empty by default and is never filled in: it is the user's personal data (ADR-067). When one is written, the trail records that it went and never the address (ADR-107) | **held; the trail's half held by test** |
| A registry answer cannot carry a payload | No abstract is read at all, control characters are removed, every field is bounded, and none of it enters a prompt | **held by test** |
| A registry's text cannot reach LaTeX as an instruction | `lacc bib` writes every LaTeX special character as a character - braces as commands, because BibTeX counts escaped ones - and keeps comments free of `@` (ADR-102) | **held by test** |

## Traceability

| Promise | What holds it | Verdict |
|---|---|---|
| Every meaningful execution is audited | Skill runs, conversions and questions are: `run_started`, `run_refused`, `files_read`, `provider_called`, `run_finished`. **`review`, `resolve`, `identify` and `coverage` were not until ADR-107**: each now opens a run, records what it reached (`registry_asked`, `texts_embedded`, `readings_judged`) and what it wrote (`file_written`), and ends finished, declined or failed. A no in `ask` and `measure` is recorded too. `measure` still records nothing when its preview is refused | **held by test** |
| Every call that completes a prompt is accounted for | `REACHES_THE_ENGINE` names every `.complete(` call, and a fourth fails the suite. **Embedding calls are outside it.** `review` and `coverage` record theirs (ADR-107); the ranking in `ask`, `measure`, the window and `sections --about` does not yet, and no test names every place that embeds | **held by test for completions; gap for the ranking's embeddings** |
| Content only under `audit_level: full` | The filter drops `prompt`, `completion`, `question` and `dois` at any other level; a question keeps its digest, and a list of DOIs its count. **Until ADR-105, every question to a corpus was kept word for word under the default level** - nothing had told the filter it was content. Trails written before keep what they kept | **held by test** |
| A refusal is recorded, not only a success | `run_refused` carries the missing capabilities and the out-of-bounds paths. The first is asserted; the second only through the outcome | **held by test, the paths held** |
| The trail cannot be altered unnoticed | Hash chain, checked by `lacc verify` and by the window's Audit section as it reads (ADR-023, ADR-043, ADR-104) | **held by test** |
| What was done can be read, and not changed | The Audit section lists the latest 300 runs of the workspace's trail - the heading gives the total - and every record of each; the trail is append-only and the section has no control that writes (ADR-104). No test checks that a section cannot write: views are checked only for what they import | **held; the reading by test** |
| Records removed from the end are noticed | The anchor beside the trail (ADR-049), tested. A notification carries the trail's length and head when an anchor exists, which is not tested | **held by test, the notification held** |
| Which file was read is recoverable | `files_read` carries the path **and the SHA-256 of its contents** | **held** |
| Which reading got which verdict is recoverable | `readings_judged` carries a row per reading: the digests of the quotation, the claim, and what was asked | **held** |
| Reasoning is counted, never kept | `provider_called` records how many characters an engine spent reasoning and never the reasoning; an unset `thinking` sends nothing (ADR-098) | **held by test** |

## Reproducibility

| Promise | What holds it | Verdict |
|---|---|---|
| The model is named, not defaulted | An empty `model` loads - it is not a validation error - and is refused when the provider is built: `lacc run` exits saying so, and no model is ever chosen for you | **held by test** |
| Temperature is the skill's, not the engine's | Sent explicitly. Not sending it was the first wrong figure this project published (ADR-033) | **held by test** |
| A run records what it ran against | `provider_called` carries the provider and model, the temperature, and the digests of the prompt, its template and the answer | **held** |
| The window is recorded | `prompt_measured` carries the requested window beside the estimate | **held** |
| Dependencies are pinned | `uv.lock` is committed; `.python-version` pins 3.12 | **held** |
| The same prompt gives the same answer | True within a warmed engine. **Not across a model load** - at temperature zero a warm-up answer differed from the four runs that followed it | **held, with a limit** |

## Degradation

| Promise | What holds it | Verdict |
|---|---|---|
| One failure costs one item, not the traverse | An unreachable judge returns `undecided` for that pair; a malformed page costs that page | **held by test** |
| An answer that was cut says so | `answer_truncated`, from the engine's own stop reason, reported by the CLI | **held by test** |
| A cut answer still yields what arrived whole | Both formats, verified by truncating a valid answer at every character | **held by test** |
| A prompt too large is refused, not truncated | Estimated against the window and refused before sending, when the configuration names the window (ADR-019) | **held by test** |
| A failed sidecar write does not fail the run | The record it describes has already succeeded (ADR-049) | **held** |
| An answer that arrives while you are elsewhere is kept | The waiting lives in the panel's frame and the turn is recorded whichever section is on screen (ADR-099). Driven by `tools/measure_window.py`; Tk has no test here | **held** |
| Asking an engine and walking the trail never freeze the window | Both run on workers that touch no widget (ADR-085, ADR-104). Other sections read on the window's own thread, and a large workspace makes them slow to open. **Prepare, with an embedding model, waits for the engine on the window's own thread**: 4.5 seconds measured for the question alone, and as long as embedding the whole corpus the first time (ADR-106) | **held for sending and for the trail; gap for Prepare with an embedding model** |

## Human in the loop

| Promise | What holds it | Verdict |
|---|---|---|
| What reaches an engine or the network asks first, and no is the default | Every confirmation in the CLI defaults to no - `run`, `collect`, `ingest`, `ask`, `measure`, `resolve`, `identify`, `review`, `coverage`. `review` defaulted to yes and `coverage` did not ask at all until ADR-105. **Ranking by meaning asks too** (ADR-106): `ask`, `measure` and `sections --about` say what would go to be embedded - the question, and every quotation or section never embedded - and ask `Rank by meaning? [y/N]`, where no ranks by words; `review` says it in the question it already asks. In the window a line beside Prepare names what it sends, the question alone, and quotations never embedded need a button of their own. Until ADR-106 the ranking sent before anything asked | **held by test**; the window's line and card driven by `tools/measure_window.py` |
| The window cannot lift a ceiling | Configuration shows `network_access` and `workspace_in_repository` and does not edit them (ADR-094) | **held by test** |
| A git working tree is refused as a workspace, from the window too | Refused when a configuration is loaded unless `workspace_in_repository` says otherwise, and refused by Workspaces before it makes one (ADR-093) | **held by test** |
| Repetition cannot multiply an effect | `measure` refuses any skill declaring `write_files` | **held by test** |
| A selection says what it discarded | `set_aside` is mandatory on a selection and reported before the answer (ADR-050) | **held by test** |
| No step decides the next | Routing is a table the user wrote; a model never chooses what runs (ADR-045, ADR-051) | **held** |
| A key somebody cites is never handed out again | `lacc bib` reads the file you name and gives none of its keys to anything else (ADR-102) | **held by test** |
| A line offered to copy runs | Every usage line in the window's Commands section, filled in, passes the CLI's own parser (ADR-103) | **held by test** |

## The gaps found on 27-sep

Re-taking this page against the source - the first time since v1.5.0 - found five rows that had
read *held* and were not:

- **The default audit level kept every question word for word.** Fixed in ADR-105.
- **`review` asked with yes as the default, and `coverage` sent before it asked.** Fixed in
  ADR-105.
- **Four commands left no record** - `review`, `resolve`, `identify`, `coverage`. Closed on 28-sep
  by ADR-107, which also records a no in `ask` and `measure`.
- **"Nothing outside the workspace is touched"** had stopped being true when the window began
  to write configurations and make workspaces (ADR-093, ADR-094). Those were decided, and shown
  before they happen; the row was what had not followed. Restated above.
- **"Writing happens in three places only"** - it is twelve, listed in
  `docs/stack/files-on-disk.md`.

And one found by the same reading: **preparing a question embedded it** when `embedding_model`
was set, so the question reached the engine before the preview that asked whether to send it.
Closed on 28-sep by ADR-106, which found it wider than named - the first question to a corpus
sent every quotation in it, and `sections --about` sent every section's opening on every run,
asking nothing. What ranking would send is now counted from the stored vectors, without
sending, and agreed to first. Closing it left one gap in sight: Prepare waits for the engine
on the window's own thread.

Every one of these is the shape this page exists to catch: a sentence that was true when it was
written, still reading *held* long after the code beside it had moved.

## The gap of 18-sep, and how it closed

**The ntfy destination arrived through the environment.** ADR-030 decides that a `.env`
supplies secrets and *"never supplies destinations or permissions"*, and calls that the
load-bearing half. `server_url_env` named an environment variable holding the server URL, so a
`.env` file - or any environment variable - decided where a notification went.

What travelled bounded the damage, and it was designed with that in mind. A notification
carries the skill's name, the outcome, the elapsed time, counts, and the audit head digest. A
traverse reports *"16 of 24 documents, 431 of 508 quotations in their source"* and never which
ones, on the stated reasoning that **how many is less disclosure than which ones**. No
quotation, no document name and no file content ever left this way.

**Closed in ADR-060**, by splitting the field according to what each part is: the address is a
destination and now sits in the configuration beside `engine_host`; the token stays named; and
the topic stays named too, because on a public ntfy server the topic **is** the access control
and moving it into a shareable file would trade one exposure for another.

The way it survived is the part worth keeping. Every mechanical check here asks a question
about code - can this be reached, is it called, does it cover its call sites. This was a
question about **meaning**: whether a field called `server_url_env` is a secret or a
destination. Nothing was going to notice that but reading.

## A rule that was written in one direction

The layering tests all follow dependencies **inward**, and for a long time that read as
complete. It is half a rule. PRINCIPLES says the core contains no interface code; the converse
- **a view contains no logic** - was never written down and never checked, and the cost was
ADR-065: both writers of the corpus format in `cli.py`, the reader in `core/`, drifting apart
with the suite green.

It is checkable, because while "logic" has no syntax its opposite does. A function in a view
that never touches the presentation, directly or through anything it calls, is not part of the
view. Against `cli.py` it named twelve functions and the first two were the two writers.

Two things make it more than decoration. The exceptions are **a list of names, not a number**,
so a function cannot leave and another arrive in its place; and a second test asserts the
named functions still exist, so the list cannot shrink by being edited. It was also run
against the commit where ADR-065 was still live, where it names the same two first.

What it does not do is stated in the record: a function that prints once is presentation by
this definition, whatever else it does. Logic braided into printing is the harder kind and
this finds the plainly separate kind. It is a floor.

## One piece of dead surface, which is not a hole

`run_commands` is a declared capability that no skill requires and nothing implements. It
cannot be granted through the configuration, and it would grant nothing if it could. It is
reserved rather than reachable, and it is written down here so nobody reads the capability
list and concludes that LACC runs commands.

## How to re-take this

The rows were not gathered by a tool. Three passes produced them the first time:

- **`tools/record_coverage.py`** for what each record names and where the code uses it.
- **A search for universal claims** - a sentence carrying *every*, *always*, *never* or
  *nothing* beside a backticked symbol, which is where a coverage obligation lives. Ninety of
  them across fifty-nine records.
- **Reading `PRINCIPLES.md` line by line** and asking of each sentence: what would have to be
  true, and what makes it true?

The second time, on 27-sep, each row was handed to a reader with one instruction: find the
thing named in *what holds it*, then find every place in the source the promise could fail -
every write, every confirmation, every call to an engine - and report only what it could point
to. Each finding was checked against the source before a row changed. That is what found the
five: not a tool, a list of every place the claim touches.
