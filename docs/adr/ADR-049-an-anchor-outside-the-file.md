# ADR-049 - An anchor outside the file

## Status

Accepted. Closes, partly, the gap ADR-043 measured and could not close.

## Context

ADR-043 tested seven safety claims by running them. Six held. The one that did not:
**records removed from the end of the audit trail are undetectable, and nothing inside the
file can catch it.** A hash chain proves each record links to the one before; it says
nothing about a record that is no longer there to link from. It is the cheapest attack in
the set and the only one that works.

The obvious fix is an anchor: something outside the trail that remembers how long the trail
was. Designing it runs into a constraint of this project's own making, and the constraint is
load-bearing rather than inconvenient.

**PRINCIPLES says nothing outside the workspace is touched.** So an anchor file lives beside
the trail, under the same permissions, reachable by anybody who can reach the trail. Against
a person with filesystem access as this user it is worth nothing: they truncate the trail and
update the anchor, and the two agree.

That is not a reason to skip it. It is a reason to be exact about which failure it catches.

## Decision

**A sidecar beside the trail records how many records it holds and the digest of the last
one**, rewritten on every append.

**It is described as a guard against loss, not against an attacker.** Truncation by a crashed
write, a synchronisation conflict, an editor that rewrote the file, a backup restored from
the wrong day - these are the failures that happen, and this catches all of them. A person
who wants to remove their own audit records will remove them, and this project should not
imply otherwise. The message says so.

**The notification carries the trail's length and head digest**, and that is the anchor that
is genuinely outside. LACC already sends to a notifier the user hosts themselves; a
notification history on another machine is something a local tamperer cannot edit. It costs
nothing, since the notification is already being sent.

**It is best effort and says so.** Notifications are already best effort (ADR-027), nobody
retains them forever, and a run with no notifier configured has no external witness at all.
An anchor that quietly stopped working would be worse than none, so `lacc verify` reports
which of the two checks it was able to make rather than a single verdict.

**`lacc verify` compares the trail against the sidecar and names the disagreement.** Fewer
records than the sidecar expects is loss. A different head digest with the same count is an
edited last record. Both are reported as what they are rather than as "the chain is broken",
because the chain may be perfectly intact and shorter than it was.

## Consequences

- `AuditLog` writes the sidecar after each append; a sidecar that cannot be written is
  reported and does not fail the run, since the record itself already succeeded.
- `lacc verify` gains two lines: what the chain says, and what the sidecar says.
- A trail with no sidecar - every trail written before this - verifies exactly as it does
  today, with a note that it has no anchor rather than a warning that it failed one.
- The notification body grows by a count and eight characters of digest.

## Trade-off

**This does not close the hole ADR-043 found; it narrows it.** Deliberate removal by someone
with access to the workspace remains undetectable locally, and the notification is the only
thing standing outside. Writing that plainly is the whole value: a project that claimed this
fixed the gap would be making exactly the kind of unearned safety claim ADR-038 had to
correct once already.

Two places now hold the same fact, and two places that can disagree will. That is
intentional - disagreement is the signal - but it means a restored backup, a moved workspace
or a trail legitimately rotated will now raise a question that used to pass in silence.
Accepted: a question about a real change is cheaper than silence about a real loss.

**Putting the head digest in a notification discloses a little.** It says a run happened and
how many records exist, to a server the user chose. Smaller than the notification already
sent, which names the skill and its outcome, and worth naming rather than assuming nobody
minds.
