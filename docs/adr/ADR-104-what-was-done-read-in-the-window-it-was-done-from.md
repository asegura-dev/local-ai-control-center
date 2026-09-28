# ADR-104 - What was done, read in the window it was done from

## Status

Accepted. Asked for on 27-sep: the program says everything significant it does is audited,
and the only way to read the audit was `lacc verify`, which says whether the trail holds and
nothing about what is in it.

## Context

The trail is `audit.jsonl` inside the workspace (ADR-006), hash-chained (ADR-023) with an
anchor beside it (ADR-049). On 27-sep the thesis's workspace held **1,723 records, 5.6 MB,
from 10-sep to 25-sep, none unreadable, grouped into 250 runs**: 237 that started a skill, a
conversion or a question to a corpus, and 13 notifications. Under `audit_level: full` a single record carries a
prompt and its answer - the largest is 91,000 characters.

Read with the program's own code: **walking the chain took 1.0 to 1.8 seconds, the anchor
another 0.7**. The trail grows by a few megabytes a week of real use. A window that read it on
the Tk thread would freeze for seconds today and, before the thesis is done, long enough for
Windows to call it "not responding" - which ADR-085 set out never to let happen.

## Decision

- **One trail: the workspace's the window is open on.** The trail lives inside the workspace,
  resolved through its boundary like anything else LACC touches, and a view across workspaces
  would read outside the one it was opened on. Another workspace's trail is read by opening
  the window on its configuration, which is how every other section already works. This was
  the question asked - "by workspace, or not?" - and the principle answers it.
- **Runs, not records.** The sidebar lists runs, newest first, under the day they happened,
  each as the time, what ran and how it ended. A run's panel lists its events in order, with
  every detail they recorded.
- **How a run ended is read from what it recorded, never guessed**: finished, refused - by
  permission or because the prompt did not fit - declined, failed, or **no end recorded**,
  which is what a crash or a closed window leaves and is worth seeing as such.
- **Integrity first, in the same words as `lacc verify`.** The heading says whether the chain
  holds, from when to when, and what the anchor says. The sentences moved into a slice so the
  command and the window say the same thing from one place; two writers of the same sentence
  is the drift ADR-065 measured. **A broken trail is still shown**, with the break named and
  every run from there on marked as not vouched for - hiding it would hide the evidence.
- **The trail is read once per pass, on a worker, and verified as it is read.** One walk
  parses each record once, checks its link and keeps it. The section draws "reading" and fills
  in when the walk is done, and a walk whose answer arrives after you have left the section
  is dropped, as ADR-099 does. A trail that has not changed since it was last read is not
  read again.
- **Content is shown cut, and says how much.** Up to 4,000 characters of an answer and 1,500
  of a prompt, each with the number left out and its SHA-256, which is the whole of it for
  checking. A record written under `standard` holds no content, and the run says so.
- **The latest 300 runs are listed**, and the heading gives the total. The whole trail is
  walked anyway - the chain has to be read from its start to vouch for its end.
- **Messages are shown as recorded.** Which model answered lives only in a message
  (`Called ollama:qwen2.5:7b for extract_claims`), and reading it back out of the sentence
  would be a second, weaker record of a fact the first one already states.
- **Nothing is written.** No clearing, no export, no editing. The trail is append-only, and a
  window that could change it would be a window its own chain would have to be checked
  against.

## Consequences

Driven in the real window over the thesis's trail (`tools/measure_window.py`): **250 runs
under 11 days**, the chain holding and the anchor agreeing. They ended as 218 finished, 9
refused because the prompt did not fit, 1 failed, 13 notifications - and **9 with no end
recorded**: seven skill runs, and two questions that sent a notification and never recorded a
finish. Leaving the section before the walk was done drew nothing into the next one, and a
second opening, the trail unchanged, listed from what was kept.

Reading the frame before building found one thing in it. `_go` hides the list column when a
section lists nothing, and looked once, right after the listing - so rows arriving from a
worker would have arrived into a column already put away. The column is now shown whenever
something is added to it, and the drive above found it shown.

Times shown in the window are local; the trail keeps UTC, as it always has.

`lacc verify` prints the same sentences it did, now from `features/trail.py`, and says "no
trail yet" of a workspace where nothing has been recorded, where it used to say the trail
could not be read at record 1. `verify_chain` is gone: `walk` returns the same verdict with
the records, and nothing in the program called the other any more.

The window's own description said "eight sections read, one asks" and that it wrote only its
appearance. Both had stopped being true two records earlier, when Workspaces and Configuration
began to write (ADR-093, ADR-094). It now says which of the fourteen sections act, and
what the window writes.

## Trade-off

**The first reading still costs the walk**, in the background. On a trail of tens of megabytes
the section shows "reading" for several seconds before anything is listed. Verifying only what
was added since the last walk would remove that, and would keep a second copy of the chain's
state in memory; it waits for a trail that needs it.

**Three hundred runs is a cut**, stated, not a window onto everything. A search or a filter by
command would answer "when did I last ask about X" directly, and belongs to a later record,
measured against what somebody actually looks for.
