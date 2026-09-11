# ADR-041 - Standing context, and what it must not touch

## Status

Accepted.

## Context

Every run starts with no memory of the project it serves. LACC reads one document, answers,
and forgets. For work that spans a bibliography that is a real cost: the tool cannot know
what the thesis argues, which terms are used how, or what has already been settled.

The obvious fix is a standing context file, written by the user, included in prompts. It is
the right fix for some skills and **actively harmful for one**.

`extract_claims` produces an inventory. Telling the model "my thesis argues X" before asking
what a paper asserts invites it to find X - to favour the claims that fit and pass over the
ones that contradict. The grounding check cannot catch that, because the quotations would
all be real. **It would bake confirmation bias into the one tool built to prevent being
deceived**, in a project whose output is a thesis.

The same information is the whole point of a different question. "What does this paper offer
my work?" is meaningless without knowing what the work is.

## Decision

**A skill declares whether it uses standing context, and the default is no.** The flag sits
on the plan beside temperature, so the decision is written per skill rather than implied by
a file's existence.

**`extract_claims` does not use it, and that is the load-bearing part of this decision.**

**The context file is named in the configuration, never searched for.** `context_file:` is
empty by default; an absent file is not an error, because a project without standing context
is the ordinary case.

**The user writes it.** Generating it from the corpus would be the model telling the model
what the thesis is about, and every later answer would rest on an unverified paraphrase -
the failure this project exists to avoid, applied to itself.

**It is fenced like any document.** It enters a prompt, so it carries the same injection
surface, and nothing about being the user's own file makes the fence unnecessary.

**A new skill, `assess_source`, is where this earns its place.** Given a document and the
standing context, it reports what the document offers the work: what is new, what overlaps
what is already known, what contradicts it.

**It is separate from `summarize_file` deliberately.** A summary scoped to a thesis is not a
summary of the paper; they are different documents, and conflating them is how someone cites
a paper for something it barely mentions. A separate skill means the output says, by its
name, that it is a deliberately partial reading.

**It is not grounded, and says so.** `assess_source` makes judgements - is this relevant, does
it contradict - and a judgement has nothing to check it against. Its quotations can still be
verified, and are.

## Consequences

- `Config` gains `context_file`; `SkillPlan` gains `uses_context`; the cycle reads and fences
  the file when a plan asks for it, and records that it did.
- `assess_source` answers both "summarise this for my thesis" and "is this new reference
  useful" - they are the same operation asked twice.
- A run that used standing context says so, because an answer shaped by a file the reader
  may have forgotten writing is an answer they should know is shaped.
- `summarize_file`, `critique_file` and `extract_claims` are unchanged.

## Trade-off

Two skills now read a document and report on it, and the difference between them is a
matter of framing rather than mechanism. Accepted: the framing is the whole point. A reader
who cannot tell a summary from a relevance assessment will eventually cite one as the other.

Standing context makes results depend on a file that is easy to write once and never revisit.
A stale context file quietly shapes every assessment, and nothing will flag it. That is why
the run reports having used it, and why the file is named in configuration rather than
discovered - both make it something the user chose rather than something that accumulated.

The strongest objection to this decision is that the line it draws is not enforceable.
Nothing stops a future skill from declaring `uses_context` when it should not, and the harm -
an inventory shaped by expectation - is invisible in the output and passes every check LACC
has. The protection is that the flag is written down per skill and has to be argued for,
which is weaker than a mechanism and is what is available.
