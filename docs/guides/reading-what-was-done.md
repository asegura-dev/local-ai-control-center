# Reading what was done

Everything LACC does that matters leaves a record: which skill ran, what it was allowed to
read, what it sent to the engine and what came back, which quotations checked out, what was
refused and why. This guide is about reading that record - in the window, and in a terminal -
and about what it can and cannot prove.

## Where it is

One trail per workspace: `audit.jsonl`, with `audit.anchor` beside it. Each record is one
line of JSON, and each carries the digest of the one before it, so a record edited, removed
from the middle or moved breaks the chain at that point (ADR-023). The anchor remembers how
long the trail was and how it ended, which is what catches records removed from the end
(ADR-049).

How much a record holds is `audit_level` in your configuration. Under `standard`, what
happened: the skill, the files, the model, the counts, the digests. Under `full`, also the
prompt that was sent and the answer that came back - which is what makes it possible to show,
later, exactly what a model was asked and what it said.

## In the window: Audit

`lacc window -c configs/yours.yaml`, then **Audit** under *Your work*.

- It says **reading** while it walks the chain - one to two seconds for 1,700 records - and then
  whether the chain holds, from when to when, and what the anchor says. These are the same
  sentences `lacc verify` prints.
- The list beside it is the trail's **runs**, newest first, under the day they happened: the
  time, what ran, and how it ended. The latest 300 are listed; the heading gives the total.
  Skills, questions, conversions and measurements are there - and since ADR-107 `review`,
  `resolve`, `identify` and `coverage` too, each saying what it reached and what it wrote. A
  registry request says how many DOIs went and whether an address went with them; the DOIs
  themselves are listed only under `audit_level: full`, and the address never.
- How a run ended is what its own records say:

  | Shown | Means |
  |---|---|
  | finished | it recorded its end |
  | refused | a permission it needed was not granted, or a path was outside the workspace |
  | refused: the prompt did not fit | nothing was sent: it was larger than the window |
  | declined | you said no at the confirmation - in `ask` and `measure` too, since ADR-107 |
  | failed | a file could not be read or converted, or a registry or an embedding model could not be reached |
  | no end recorded | it started and never recorded an end - a crash, or a window closed mid-run |
  | notification sent / failed | a run that only notified |

- Choose a run to see every record in it, in order, with what each one recorded. Under
  `full`, the answer is shown up to 4,000 characters and the prompt up to 1,500, each with how
  many characters were left out and its SHA-256 - which is the whole of it for checking.
- A row marked `!` is a run the chain does not vouch for: at least one of its records comes
  after a break, or predates the chain. It is shown rather than hidden, because hiding it would
  hide the evidence.
- Times are this machine's. The trail itself keeps UTC.

It cannot change anything. There is no clearing and no export: the trail is append-only.

It reads the trail of the workspace the window was opened on. Another workspace's trail is
read by opening the window on that workspace's configuration (ADR-104).

## In a terminal: `lacc verify`

    .\run.ps1 run lacc verify -c configs/yours.yaml

It says whether the chain holds and what the anchor says, and exits 1 when the trail has been
altered or cannot be read. A workspace where nothing has been recorded has no trail yet, which
is not a failure.

## What it proves, and what it does not

- **It catches** a record edited, removed from the middle, or reordered; and, with the anchor,
  records lost from the end.
- **It does not catch** a deliberate rewrite. Whatever can write the file can recompute every
  digest after the point it changed, and the anchor sits under the same permissions. If you
  keep notifications, the head digest they carry is the only copy of the chain's state that is
  not on this machine.
- **It records what LACC did**, not what you did with it. A paragraph you wrote after reading
  an answer is yours; the trail shows the answer you read.

## For a thesis

Under `audit_level: full`, the trail is a dated, chained account of every question put to a
model and every answer it gave: the part of the work a committee may ask about when it asks how
AI was used. The Audit section is where to find a given one - by the day, and by what ran.
