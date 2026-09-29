# ADR-109 - One chain, however many writers

## Status

Accepted. Found on 28 September while planning to move the window's Prepare off its thread,
and demonstrated before anything was changed: two logs on one trail broke its chain at the
fourth record.

## Context

Each record carries the digest of the one before it (ADR-023), and a log read that digest from
the file once and kept it in memory afterwards. That is right for one writer. It is wrong for
two, and this program has had two for a while:

- **The window.** Send runs on a worker and records across the whole wait for the engine. A
  Prepare that ranks by meaning records its own run in the meantime (ADR-108), with a log of its
  own. When the answer arrives, Send chains its next record to the digest it last wrote - not to
  the ranking's - and the chain is broken.
- **Two corpora asked at once** in the window, each Send with its log.
- **A terminal and the window**, as when `collect` runs for twenty minutes while questions are
  asked of a corpus.

A broken chain is what tampering looks like. `lacc verify` and the Audit section would have said
the trail had been altered, when all that happened was two writers taking turns badly. The
thesis's trail was intact when this was found: the case had not happened yet, and ADR-108 had
just made it easy - Prepare during a pending Send.

## Decision

**The head is read before every record, never remembered.** From the end of the file, because
the thesis's trail is megabytes long and a single record under `full` can be a hundred
kilobytes: the read widens until it holds a whole line.

**Reading the head and appending are one step, and writers take turns at it.** Within the
program, a lock per trail. Between programs - the window and a terminal - a lock file beside the
trail, `audit.lock`, held for the step and released after it; a writer that cannot have it
within ten seconds fails the way any write fails, under `audit_failure_policy`. The anchor is
written inside the same step, so it always describes the record just written.

**Readers take the same turn.** `verify`, the Audit section and the anchor check read the trail
under the lock, so none of them ever reads a record half written - which would look exactly
like a trail that cannot be read past that point.

**The anchor counts from itself.** Measured before writing this record's cost into it, on a copy
of the thesis's trail - 8.6 MB, 2,142 records: reading the head from the end took 0.4 ms, and a
whole record **199 ms**, 164 of them the anchor recounting every line of the trail on every
record, as it had since ADR-049. Inside a turn that is time every other writer waits. Written in
the same turn as the record, the anchor always describes the record just before it, so it is
now one more than it said - and counts the trail again only when it is missing or names another
head. **A record takes 16 ms** on the same copy.

## Consequences

- A new file beside the trail, `audit.lock`. It holds nothing and is never removed;
  `docs/stack/files-on-disk.md` lists it.
- A record costs 16 ms rather than 199 on the thesis's trail, and no longer grows with it.
- **The anchor stops forgiving a line appended behind LACC's back.** Recounting took the foreign
  line into the count, and the next record made the anchor agree with it; counting from itself
  leaves it one short, and `check_anchor` says so.
- A test writes with two logs interleaved as the window does, another with four threads, and
  another from a second process; each asks the chain whether it holds.

## Trade-off

**A lock file is a convention.** It keeps out anything that asks for it - every version of this
program from now on - and nothing that does not: a LACC older than this record, run against the
same workspace, can still interleave with a newer one. So can a person appending to the file by
hand, which the chain was always meant to catch.
