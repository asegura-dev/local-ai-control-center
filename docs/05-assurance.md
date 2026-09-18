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
| `.env` supplies secrets, never destinations | **The ntfy server URL arrives through `server_url_env`** | **gap** |
| No arbitrary code execution | No `eval`, `exec`, `pickle`, `subprocess` or `os.system` anywhere in the source; both YAML loads are `safe_load` | **held** |
| A document cannot forge a fence | Fence markers are fixed strings holding no user text (ADR-038), tested against a real model | **held by test** |
| Text a reader cannot see is reported | Detection of invisible render modes and off-page positioning (ADR-040) | **held by test** |
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

## The gap

**The ntfy destination arrives through the environment.** ADR-030 decides that a `.env`
supplies secrets and *"never supplies destinations or permissions"*, and calls that the
load-bearing half of the decision. `server_url_env` names an environment variable holding the
server URL, so a `.env` file - or any environment variable - decides where a notification goes.

What travels there bounds the damage, and it was designed with that in mind. A notification
carries the skill's name, the outcome, the elapsed time, counts, and the audit head digest. A
traverse reports *"16 of 24 documents, 431 of 508 quotations in their source"* and never which
documents or which quotations, on the stated reasoning that **how many is less disclosure than
which ones**. No quotation, no document name and no file content has ever left this way.

So what leaks is metadata about research activity rather than research, to somebody who can
already set environment variables on the machine. It remains the thing ADR-030 says must not
be possible, in the record that calls it load-bearing.

**The fix that matches the principle** splits the field by what each part is. The server URL
is a destination and belongs in the YAML beside `engine_host`. The topic and the token are
secrets and stay named in the configuration with their values in the environment - on a
public ntfy server the topic *is* the access control, which is why it does not move. It costs
anyone with a working setup a move of one value from `.env` to `lacc.yaml`.

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
