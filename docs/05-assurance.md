# What this project promises, and how each promise is checked

Every row below is a claim LACC makes about itself in `PRINCIPLES.md` or a decision record,
paired with what actually holds it up. **A promise with nothing in that column but a document
is not a promise**, which is the lesson of six defects found in three days where the record
was right and the program was not (ADR-055 through ADR-059).

Verdicts are: **held** - verified in the source at the place named; **held by test** - a test
fails if it stops being true; **gap** - the claim and the code disagree.

Taken 2026-09-18, against v1.5.0 plus the unreleased work. A row here is true on the day it
was written and needs re-checking like any other measurement.

## Cybersecurity

| Promise | What holds it | Verdict |
|---|---|---|
| Every capability starts `false` | `Permissions` fields default to `False`; what is granted derives from what the skill declared | **held by test** |
| Configuration removes, never grants | `grant_for(skill, config)` enables what the skill declares, then the ceiling subtracts | **held by test** |
| Nothing outside the workspace is touched | The cycle's only read site resolves through `workspace.resolve_within` on the line above the open | **held** |
| `..`, symlinks and absolute paths are refused | `resolve_within`, with Windows reserved device names covered (ADR-017) | **held by test** |
| Ingestion never overwrites | `path.open("x")` - exclusive creation, so there is no check-then-write race | **held** |
| Only hosts the configuration names are reached | `ollama_host()` refuses any non-loopback host; a remote engine needs `network_access` **and** an address written in the YAML | **held by test** |
| An environment variable can never widen reach | `OLLAMA_HOST` is honoured only when it resolves to loopback, and refused otherwise | **held** |
| A `.env` cannot override a variable already set | The loader writes only where the name is absent from the environment | **held** |
| `.env` supplies secrets, never destinations | The ntfy address is a `server_url` in the configuration; the topic and token stay named (ADR-060) | **held by test** |
| No arbitrary code execution | No `eval`, `exec`, `pickle`, `subprocess` or `os.system` anywhere in the source; both YAML loads are `safe_load` | **held** |
| A document cannot forge a fence | Fence markers are fixed strings holding no user text (ADR-038), tested against a real model | **held by test** |
| Text a reader cannot see is reported | Detection of invisible render modes and off-page positioning (ADR-040) | **held by test** |
| A registry is reached only with two switches on | `registry_url` is empty by default and `network_access` is the ceiling; neither implies the other, and the command refuses each case by name (ADR-067) | **held by test** |
| Only a DOI leaves, never a document | The request is a URL with a public identifier; no corpus, quotation, question or filename is sent | **held** |
| No contact address is sent unless written | `registry_mailto` is empty by default and is never filled in: it is the user's personal data (ADR-067) | **held** |
| A registry answer cannot carry a payload | No abstract is read at all, control characters are removed, every field is bounded, and none of it enters a prompt | **held by test** |
| Writing happens in three places only | The workspace directory, the exclusive-create write, and the audit trail with its sidecar | **held** |

## Traceability

| Promise | What holds it | Verdict |
|---|---|---|
| Every meaningful execution is audited | `run_started`, `run_refused`, `files_read`, `provider_called`, `run_finished` | **held** |
| Every place that reaches an engine is accounted for | `REACHES_THE_ENGINE` names all three, and a fourth fails the suite | **held by test** |
| Content only under `audit_level: full` | The detail filter drops `prompt` and `completion` at any other level | **held by test** |
| A refusal is recorded, not only a success | `run_refused` carries the missing capabilities and the out-of-bounds paths | **held by test** |
| The trail cannot be altered unnoticed | Hash chain, checked by `lacc verify` (ADR-023, ADR-043) | **held by test** |
| Records removed from the end are noticed | Sidecar anchor, plus the head digest carried in every notification (ADR-049) | **held by test** |
| Which file was read is recoverable | `files_read` carries the path **and the SHA-256 of its contents** | **held** |
| Which reading got which verdict is recoverable | `readings_judged` carries a row per reading: the digests of the quotation, the claim, and what was asked | **held** |

## Reproducibility

| Promise | What holds it | Verdict |
|---|---|---|
| The model is named, not defaulted | An empty `model` is a validation error rather than a fallback | **held by test** |
| Temperature is the skill's, not the engine's | Sent explicitly. Not sending it was the first wrong figure this project published (ADR-033) | **held by test** |
| A run records what it ran against | `provider_called` carries the provider and model, the temperature, and both digests | **held** |
| The window is recorded | `prompt_measured` carries the requested window beside the estimate | **held** |
| Dependencies are pinned | `uv.lock` is committed; `.python-version` pins 3.12 | **held** |
| The same prompt gives the same answer | True within a warmed engine. **Not across a model load** - at temperature zero a warm-up answer differed from the four runs that followed it | **held, with a limit** |

## Degradation

| Promise | What holds it | Verdict |
|---|---|---|
| One failure costs one item, not the traverse | An unreachable judge returns `undecided` for that pair; a malformed page costs that page | **held by test** |
| An answer that was cut says so | `answer_truncated`, from the engine's own stop reason, reported by the CLI | **held by test** |
| A cut answer still yields what arrived whole | Both formats, verified by truncating a valid answer at every character | **held by test** |
| A prompt too large is refused, not truncated | Estimated against the window and refused before sending (ADR-019) | **held by test** |
| A failed sidecar write does not fail the run | The record it describes has already succeeded (ADR-049) | **held** |

## Human in the loop

| Promise | What holds it | Verdict |
|---|---|---|
| Sensitive actions are previewed and confirmed | One preview, one confirmation, defaulting to no | **held by test** |
| Repetition cannot multiply an effect | `measure` refuses any skill declaring `write_files` | **held by test** |
| A selection says what it discarded | `set_aside` is mandatory on a selection and reported before the answer (ADR-050) | **held by test** |
| No step decides the next | Routing is a table the user wrote; a model never chooses what runs (ADR-045, ADR-051) | **held** |

## The gap, and how it closed

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

The five layering tests all follow dependencies **inward**, and for a long time that read as
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

The rows were not gathered by a tool. Three passes produced them:

- **`tools/record_coverage.py`** for what each record names and where the code uses it.
- **A search for universal claims** - a sentence carrying *every*, *always*, *never* or
  *nothing* beside a backticked symbol, which is where a coverage obligation lives. Ninety of
  them across fifty-nine records.
- **Reading `PRINCIPLES.md` line by line** and asking of each sentence: what would have to be
  true, and what makes it true?

The third is what found the gap above. No tool was going to notice that a field named
`server_url_env` is a destination arriving by the one route a record forbids.
