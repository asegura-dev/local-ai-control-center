# ADR-025 - Writing beside the original, and reading several documents

## Status

Accepted.

## Context

LACC reads one document and returns text to the terminal. Two capabilities are missing and
they arrive together: producing something you keep, and working with more than one source.

Writing is the first effect that can destroy work, and LACC just removed the safety nets
that were there by accident: ADR-022 refuses a workspace inside a git working tree and
warns about one that synchronises, so what this phase writes to has no version history.

## Decision

**Nothing LACC writes replaces a file that already exists.** Ingestion already refused to
overwrite; that becomes the rule everywhere. A revision is written beside the original:

```text
lacc run revise_file chapter.md   ->  chapter.revised.md
```

**A revision is approved against its diff, not against a preview.** The run asks twice: the
preview authorises reading and asking the model, and a second question shows the unified
diff and decides whether the result is kept. The preview cannot carry a diff because the
revised text does not exist until the model answers. Declining writes nothing and prints
the revision.

The diff is computed with `difflib`. No version control system is involved.

**A skill receives every path the user named.** `Skill.plan` takes a tuple of requests
rather than one string, and `lacc run <skill> <path> [<path>...]` accepts several. Each
document is fenced separately, with its own name and its own content placeholder
(`<<file_content:0>>`, `<<file_content:1>>`), so the model can attribute what it reads.

`summarize_file` and `critique_file` accept any number. `revise_file` requires exactly one
and says so, because there is no sensible revision of three documents at once.

**`run_action` gains an optional destination.** It does not become a third kind of run:
revising is reading and asking a model with one more step at the end, not a new shape. The
general "action carries its own effects" design ADR-016 anticipated stays unbuilt.

## Consequences

- `revise_file` proposes a clearer version that does not change what a passage claims.
- Every skill can be given several documents; the ceiling from ADR-019 is what stops a set
  that will not fit, and it now has something to stop.
- `SkillPlan` carries an optional destination; `Skill.plan` takes a tuple. Both are contract
  changes, amending ADR-009 again and in the open.
- Two audit events: a revision written, a revision declined.
- A model told not to change the meaning may change it anyway. The diff is what makes the
  instruction safe to rely on.

## Trade-off

Writing beside the original leaves a manual step and a file to clean up. Accepted: the step
is where the author's judgement belongs, and the alternative trades a reversible decision
for an irreversible one to save a move in an editor.

Asking twice makes a revision slower than any other run. That is the point: the second
question is asked when there is finally something real to look at.
