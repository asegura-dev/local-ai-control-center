# ADR-078 - What a digest is for

## Status

Accepted. Written in answer to a good question - *if the launchers carry SHA-256 sums, should
the skills and the code?* - and most of the answer is no.

## Context

`scripts/` carries `SHA256SUMS.txt` and the gate enforces it (ADR-071). The obvious next step
is to do the same for the rest: the Python, the declared skills, the configuration.

Before copying a mechanism it is worth asking what the original one bought. The launchers are
a special case in exactly two ways: **they run outside Git** - somebody double-clicks a `.bat`
that a clone put there - and **they run outside the audit trail**, because nothing records
that a `.bat` was run at all.

Neither is true of anything else here.

## What already exists, and is stronger

**For the code: Git.** Every commit is a hash of the whole tree; `git status` says whether
anything on disk differs from it, and `git log` says when it changed and beside what else. A
`SHA256SUMS` of the Python would restate that less well, and would be one more file that can
go out of step with what it describes - the failure this project has measured more than any
other.

**For what a run did: the audit trail.** Each `provider_called` already records
`prompt_sha256`, `completion_sha256`, and the digest of every file read and written, in a
chain `lacc verify` walks. That is stronger than a static list, because it says what a
particular run *sent*, not what is on disk now.

## The gap that was real

**`prompt_sha256` covers the template and the document together**, and a prompt is the
template with the document inside it. So changing the wording a skill asks with changes the
digest - and so does reading a different file. **Nothing distinguished the two.**

A person asking *"did the instruction change between these runs?"* could not answer it from
the trail, which is exactly what a trail is for.

## Decision

**Record `template_sha256` beside `prompt_sha256`.** One is the skill's wording; the other is
that wording with a document in it. Two runs over different documents now share a template
digest, and two runs over the same document with an edited skill do not.

It costs one field and one hash. A declared skill lives in a YAML file the user can edit, and
this is what makes an edit visible after the fact rather than only before it.

**Nothing else gains a digest file.** Not the Python, which Git covers; not the configuration,
which the trail already records the effect of. Adding one would be a check that looks like
assurance and restates something already true.

**And a third-party answer is bounded in size.** `response.read()` had no limit, so the one
thing a timeout does not cover - an answer that arrives steadily and never ends - was
unbounded. A record for one work is a few kilobytes; two megabytes is the ceiling and
anything past it is refused by name.

## Consequences

- The trail answers "did this skill's wording change" without opening any file.
- `crossref.py` refuses an oversized answer instead of reading it.
- No new file to keep in step with anything.

## Trade-off

**A digest says something changed, never what or why.** `template_sha256` will differ after a
deliberate improvement to a skill exactly as it will after an unwanted edit, and the trail
cannot tell them apart - only that the two runs did not ask the same thing.

**It covers the template, not the skill.** A declared skill has a temperature, a set of
fields, a quotation label; change those and the wording is identical while the behaviour is
not. Covering all of it means hashing the declaration, which is a different thing and
deserves its own decision rather than being smuggled in here.

**The same unbounded read exists in the Ollama adapter** and is deliberately left. That
endpoint is a machine the user owns on their own network, named in their own configuration -
a different relationship from a public API, and the bound would be guessing at how long a
legitimate answer from your own model can be.
