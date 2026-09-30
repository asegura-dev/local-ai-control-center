# ADR-114 - A refusal, not a traceback

## Status

Accepted. Five findings of the test of 29 September - D5, D6, D7, D8 and D12 - that share a
shape; built on 30 September.

## Context

In each case the program decided correctly, and then showed the decision as a crash, or did
something it had said it would not.

- **D5 - a configuration that is not YAML.** `model: [qwen2.5:14b` ended every command in a
  traceback, even though `load_config` promised in its own docstring a clear error for
  malformed YAML. The parser raises its own kind of error, which the loader did not catch.
- **D6 - an engine the configuration forbids.** With `network_access: false` and an engine on
  another machine, `ask`, `review`, `coverage` and `engine test` ended in a traceback reading
  *the engine host … is not this machine, and network_access is off*. Nothing had been sent.
  The rule held; what the person saw was a crash.
- **D7 - a destination the command may not write.** An `--into` outside the workspace, or
  already there, was found out when the result was written.
  - For `review` and `coverage`, that was after the engine had judged or embedded everything,
    and it left a run without an end.
  - For `corpus` and `resolve`, it was a traceback.
- **D8 - where `bring` puts the copy.** A `drafts` that was a folder link leading outside the
  workspace ended in a traceback before the preview. A `drafts` that was a file ended in one
  after the yes, and left a run without an end.
- **D12 - a workspace that does not exist.** `status` and `verify` created it, parents and
  all, while `status`'s help says *nothing is written*. A mistyped `workspace_root` seeded
  folders without a word. ADR-003 had decided that loading a configuration creates its
  workspace deliberately; the creation was deliberate, and it was also silent.

## Decision

- **A broken configuration is named**: the file, the line and column, and what the parser
  expected - *roto.yaml is not valid YAML at line 2, column 1: expected ',' or ']', but got
  '<stream end>'*.
- **An engine the configuration forbids is refused in a sentence**, where each command first
  resolves it: `ask`, `review` and `sections --about` through `_retriever_or_exit`, and
  `coverage` and `engine test` through `_host_or_exit`. Each comes before any run opens, so a
  refusal leaves nothing in the trail.
- **A destination is checked where the command starts**, for `resolve`, `collect`, `corpus`,
  `review`, `coverage` and `sections --take`:
  - inside the workspace;
  - not already there;
  - in a folder that exists.

  It is the early word, not the guarantee. PRINCIPLES prefers attempting a write and
  translating its failure to checking first, and the write still opens the file for
  exclusive creation, so a file made in between is still refused. The early check exists so
  that a refusal costs nothing, not so that it replaces the one that holds.
- **`bring` checks `drafts/` before its preview.** A folder link that leads outside, or a file
  of that name, is refused before anything is asked.
- **A workspace is created by a command that writes, and said to have been**: *Created the
  workspace …: it did not exist*. A command that only reads refuses and creates nothing.
  Those commands are `status`, `verify`, `preview`, `references`, `metadata`, `outline` and
  `engine test`.

## Consequences

Tests:
- the broken configuration, named with its line;
- the forbidden engine in `ask`, `review`, `coverage` and `engine test`, each refused in words
  and leaving no trail;
- `corpus`, `review` and `coverage` refusing a destination outside before any work, and
  `review` refusing one that is already there;
- `drafts` as a file, and, on Windows, as a junction leading outside, both refused before the
  question;
- `status` and `verify` on a workspace that does not exist, creating nothing;
- `bring` creating one, and saying so.

Each test fails on the code before this record: the exception reaches the runner, or the
folder is created, or the sentence is not there.

`status`'s help - *nothing is written* - is true again.

## Trade-off

**The early check and the write can disagree**, if something changes between them. The write
still refuses, and in that case the run ends as ADR-107 records a failed one.

**`bib` and `ingest --into` were left as they were.** `bib` already refused both cases in
words and calls no engine; `ingest --into` was not among the findings.

**The window was not re-checked for the forbidden engine.** It asks through
`_asking_for_the_window` on a worker; whether that refusal reads as well there is its own
question.
