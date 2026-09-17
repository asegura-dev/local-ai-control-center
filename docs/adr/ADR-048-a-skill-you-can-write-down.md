# ADR-048 - A skill you can write down

## Status

Accepted.

## Context

LACC has five skills and every one of them is a Python class. Asking it to do something it
was not built for means writing code, running the gate and cutting a release, which is the
right cost for a control and an absurd one for "read this and list the assumptions it makes".

ADR-045 named "moving prompt wording out of the code" as deferred v2 work and left it
ambiguous, because nobody knew which part should move. **The ambiguity is now resolved by
measurement, and it resolves the opposite way from the obvious one.**

Asked to cover twenty-four documents, a 14B covered ten. Given the identical request as a
skeleton with twenty-four numbered slots to fill, it returned twenty-three. Asked in the
same prompt, explicitly, not to use its own knowledge and to write "not available" for
anything missing, it invented twelve journal names anyway. The fence behaved the same way:
the instruction not to obey a document was ignored, and removing the markers worked.

**Structure is obeyed. Instruction is negotiated.** So the thing worth making declarable is
not the prose - it is the shape of the answer.

## Decision

**A skill can be declared in a file: a name, a summary, what it needs, the instructions, and
the fields it expects back.** LACC loads it beside the built-in ones.

**The structure is generated from the declared fields, not written by hand.** The author
says a skill returns `claim`, `quote` and `page`; LACC builds the skeleton the model fills.
This is the whole point: the part that works is the part LACC controls, and handing an author
a blank prompt would hand them the part that does not work.

**A declared skill cannot grant itself anything.** It names the capabilities it needs, the
configuration remains a ceiling that only removes, and the preview and confirmation happen
exactly as for a built-in skill. A file that could widen its own permissions would make the
permission system advisory.

**Declared skills live beside the configuration, never inside the workspace.** The workspace
holds documents, some of them downloaded, and `write_files` can put things there. A prompt is
an instruction to a model, and instructions must not live where the material lives.

**Verification is opt-in to the existing check, never a new one.** A skill may name which
field carries the quotation, and that field is then checked against the document exactly as
`extract_claims` is. It cannot define a new kind of check, because a check nobody reviewed
is worse than no check - it would report confidence it has not earned.

**The five built-in skills stay in code.** Their wording was measured - where the instruction
sits relative to the document (ADR-037), whether they see the standing context (ADR-041),
what temperature they run at (ADR-033). Moving them into files would move measured decisions
somewhere nobody reviews them.

## Consequences

- A skill for a seminar summary, a code review, an assumption audit is a file, not a release.
- `lacc run` lists declared skills beside built-in ones and says which is which, because a
  reader of a preview should know whether what is about to run was reviewed by anybody.
- The audit records the skill's name and the digest of its declaration, so a trail says what
  ran and not only that something did.
- `parse_claims` learns the declared field names instead of only `claim`, `quote` and `page`.

## Trade-off

**A declared skill is a prompt nobody reviewed, and that is the cost.** A built-in skill went
through a gate and an ADR; a file goes through whoever wrote it at midnight. Mitigated by
what cannot be declared - capabilities, checks, where the instruction sits - and by saying in
the preview that this one is declared. Not mitigated at all for the quality of the answer,
which is the author's problem and should be.

**Generating the structure takes wording away from the author**, who will sometimes be right
that their phrasing is better. Accepted: the measured difference between a good prompt and a
bad one is smaller than the measured difference between prose and structure, and the second
is the one LACC can guarantee.

**This is the first thing in the project that lets somebody change what a run does without
changing code**, which is a category of surface that was deliberately absent until now. The
line held is that it changes *what is asked*, never *what is allowed* or *what is checked*.
If a later version blurs that line, this paragraph is the one it has to argue with.
