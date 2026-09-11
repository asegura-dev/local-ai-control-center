# ADR-043 - What the chain does not catch

## Status

Accepted. Completes the limits named in
[ADR-023](ADR-023-a-trail-you-can-check.md), which stated one and missed the easier one.

## Context

After four releases in which a limit of this project was reported as the model's dishonesty,
the obvious question is which other claims here have never been executed. The security ones
matter most, because that is where "looks correct" and "is correct" come apart quietly - as
the document fence did.

Seven were tested against running code rather than read:

| Claim | Result |
|---|---|
| The chain catches an edited record | holds |
| ...a record removed from the middle | holds |
| ...records reordered | holds |
| **...records removed from the end** | **does not hold** |
| The workspace boundary refuses `..`, absolute paths, junctions, device names, alternate streams | holds |
| `audit_failure_policy: abort` stops a run that cannot be recorded | holds |
| `max_input_bytes` is enforced | holds |
| Declining a diff writes nothing, and approving one without `write_files` is refused | holds |

One failure, and it is the cheapest attack of the set. Editing a record requires
understanding that the file is a chain. **Truncating it requires deleting the last lines.**
ADR-023 named the sophisticated attack - a full rewrite with recomputed digests - and left
the trivial one unstated, so `lacc verify` said "the trail holds" of a trail with records
removed.

## Decision

**Say what it does not catch, in the place it says what it does.** The message names three
outcomes it detects and two it does not, rather than one of each.

**Nothing can be added to the file that would catch it.** A shorter chain is a valid chain:
every remaining record still links correctly. A sequence number does not help - after
truncation the next append continues from the shortened tail and numbers itself
consistently. Detection needs state outside the file, which LACC does not have and will not
invent quietly.

**Report when the trail starts and ends.** That is the one check available without external
state: a trail whose last record predates your last run has lost something, and a person
knows when they last ran something. It is weak, it is honest, and it costs two lines.

**The behaviour is tested, not merely described.** Five tests state exactly what the chain
catches and that truncation is not among them, so the limit is a known property rather than
a surprise for whoever reads the code next.

## Consequences

- `ChainCheck` carries `first_seen` and `last_seen`; `lacc verify` prints them.
- The guide stops saying tampering "becomes locatable" without qualification.
- Six other safety claims are now verified by execution rather than by having been written
  down, including the workspace boundary against Windows junctions - which a previous note
  listed as unverified.

## Trade-off

Naming a hole publicly tells anyone who wants to remove evidence how to do it. Accepted
without much hesitation: deleting the last lines of a file is not an insight, and a user
who believes their trail is tamper-evident when it is not is worse off than one who knows
where it stops. The audience for this project is a researcher protecting their own record,
not an adversary.

The timestamp check depends on a person remembering when they last ran something, which is
exactly the kind of vigilance that fails. It is offered as the only thing available rather
than as a control, and the wording says so.
