# ADR-071 - Launchers, and their digests

## Status

Accepted. A small addition whose value depends entirely on one test existing.

## Context

Running LACC means knowing `uv run --extra gui lacc window -c configs/denso.yaml`, and getting
the engine into a good state means remembering an environment variable that has been in the
log as a pending task for weeks:

> At a 32k window the KV cache costs about **8.6 GB in fp16 and about 4.3 GB at `q8_0`** -
> roughly four gigabytes of VRAM back, for free, before any hardware decision.

That is not a thing to remember. It is a thing to put in a file.

And the moment a project ships a file people double-click, it has shipped an execution path
that nobody reads. A `.bat` is the easiest place in a Windows project to hide something.

## Decision

**Three launchers, in `scripts/`, and none of them reaches the network.**

- `lacc-window.bat` opens the window, with a configuration named or the default.
- `serve-ollama.bat` starts the engine on **this** machine with `OLLAMA_KV_CACHE_TYPE=q8_0`,
  bound to loopback unless a host is passed deliberately. Variables are set for that session
  only; nothing global is changed.
- `verify-scripts.bat` checks the others against the recorded digests.

**`scripts/SHA256SUMS.txt` records what each one hashes to, and the test suite enforces it.**
This is the whole of the decision. A checksum file that nobody checks is decoration, and this
project has a rule about checks that cannot be seen to work (ADR-066). So the gate fails when
a script changes without its digest changing in the same commit.

**What it proves, stated plainly, because the temptation is to claim more.** It proves the
files on this disk are the ones the digests were taken over. **It does not prove the digests
are honest**: anyone who could edit a script could edit the list beside it. What makes it
worth something is that both are in Git, so `git log scripts/` shows when either changed and a
reviewer can see a script and its digest move together.

It defends against a file corrupted in transit, a partial sync, an edit made and forgotten,
and a change slipped into a launcher without the digest moving. It does not defend against
somebody with commit access, and nothing at this layer could.

**Git must not rewrite them.** `.gitattributes` marks `scripts/**` as `-text`, because a
digest over a file whose line endings change when it is cloned verifies nothing on the next
machine.

**The launchers are also tested for what they do not do.** No `curl`, no `Invoke-WebRequest`,
no `bitsadmin`, no `certutil -urlcache`: a launcher that fetched something would be a supply
chain in a batch file. And `serve-ollama.bat` is asserted to bind loopback by default, because
a default that listened on every interface would expose the machine silently.

## Consequences

- The KV-cache figure stops being a task in a log and becomes something you can double-click.
- Four tests, and the useful one was shown to fail: appending a line to a launcher makes both
  the batch verifier and the gate report it by name.
- `scripts/` is a directory the layering test does not know about, and does not need to: it
  holds no Python.

## Trade-off

**Regenerating the digests is a manual step**, and a manual step is a step that gets skipped.
The mitigation is that skipping it fails the gate rather than passing quietly - the failure is
loud and names the file - but somebody will still regenerate them without looking at the diff,
and at that point the record is a formality.

**Three files people run is three files to keep honest.** Every launcher added is another
thing that could rot, and the reason there are three rather than a script for every command is
that the CLI is the interface: these exist for the two things that are hard to remember and
the one that checks them.
