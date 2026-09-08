# ADR-018 - A second skill: critique, and what a second skill reveals

- **Status:** Accepted - implemented (v0.17.0)
- **Date:** 2026-09-08
- **Context:** LACC has had exactly one skill since v0.8.0. Summarizing tells you what a
  document says; the work it is being built for - writing at length, from sources - needs
  the other direction as well: reading a draft and reporting what is weak in it. That is
  read-only, needs no machinery that does not exist, and is useful the day it lands.

  A second skill also settles two questions that could only be answered once there were
  two. Whether the parts they share should be shared, and whether the skill registry
  deferred in ADR-010 has now earned its shape.

## Decision

### 1. `critique_file`: a read-only skill that reports weaknesses

It reads one file inside the workspace and asks the model for specific, locatable
problems: claims made without support, gaps in an argument, contradictions between
passages, terms used before they are defined, conclusions that do not follow from what
precedes them.

One file, not several. Reading more than one is a phase of its own on the roadmap, and
starting it here would mean designing how several documents are laid out in a prompt as a
side effect of adding a skill.

### 2. The document fence is extracted, because a security mechanism must not be copied

Both skills fence the document between markers and tell the model the fenced text is
material rather than instruction (ADR-015). That fence is not formatting: it is the only
thing standing between a document that reads like an instruction and a model that treats
it as one.

Copied into a second skill, it becomes two implementations of one security boundary, free
to drift - one updated when the wording improves, the other left behind, and nothing to
say which is which. So it is extracted into one function that both skills call.

This is the abstraction PRINCIPLES was waiting for: two real cases, shaping it. It is also
deliberately small. What is shared is the fence and the instruction that goes with it, not
"the way a prompt is built": each skill still writes its own task framing, because that is
the part that genuinely differs and the part that has to be readable next to what it does.

### 3. No skill registry, and the count was never what was missing

ADR-010 deferred a formal registry, and the roadmap said a third skill would give it
enough cases to take shape. Having got here, that reasoning was wrong and is corrected
rather than followed.

The CLI resolves skills through a dictionary. With two entries it is a registry, and it
answers every question a registry is for: what exists, what a name resolves to, what to
say when a name is unknown. What a *formal* registry adds is discovery - skills arriving
from somewhere other than this source tree - and that brings its own questions about
trust, since a skill that LACC did not write is a skill whose declared capabilities are a
claim rather than a fact. ADR-011 already names the allowlist model that would need.

So the trigger was never the number of skills. It is the arrival of a skill nobody in
this repository wrote, and that has not happened.

### 4. The prompt asks for specific problems, and refuses to ask for a verdict

The critique names where a problem is and what is missing. It does not grade, score, or
open with what the document does well: a critique that hedges is one whose findings have
to be looked for.

It also does not rewrite. Producing a better paragraph is writing, that is a phase with a
different safety requirement - a diff shown before anything is replaced - and a skill that
quietly drifted into rewriting would produce text that looks authoritative in a run that
was only ever allowed to read.

And it is told to say when it has no finding rather than manufacture one. A model asked
for problems will supply problems; the honest failure mode of this skill is a confident
list of invented weaknesses in a sound chapter, which costs more to check than it saves.

### 5. The quality of a critique is the model's, and the documentation says so

A small local model can summarize acceptably. Judging whether an argument holds is
outside what a three-billion-parameter model does well, and this skill will produce
shallow criticism on such a model. The prompt is shaped as well as it can be; the rest is
the engine.

That is written down rather than discovered, because the alternative is a user concluding
the skill is broken when it is working exactly as a small model allows. It is also the
clearest argument yet for the stronger machine the roadmap already records as a decided
direction - the phase where a critique becomes worth trusting is the phase where a real
model runs it.

## Trade-off

Extracting the fence means the two skills share code, and shared code is where coupling
starts. Accepted, narrowly: what is shared is a security mechanism whose whole value comes
from being identical everywhere, and the sharing stops there. The framing, the task and
the wording stay in each skill, where they can be read next to the thing they describe.

Declining the registry leaves the CLI's dictionary as the only place that knows which
skills exist, so adding a skill means editing that file. Accepted: that is one line, it is
in version control, and it is a great deal less machinery than a discovery mechanism whose
security model has not been decided.

A second skill doubles the prompt wording that lives in code, which is the thing the
external-templates phase exists to fix. Accepted, and in fact useful: that phase was
deferred twice for want of real cases to generalize from, and this is the second one.

## Consequences

- `lacc run critique_file <path>` reads a document and reports specific weaknesses, under
  `read_files`, through the same preview, confirmation and audit as any other run.
- The document fence lives in one function that both skills use; neither re-implements it.
- No registry. The CLI's mapping stays, and the reason it stays is recorded so the
  question is not reopened by counting skills again.
- The prompt refuses to rewrite, refuses to grade, and is told to report nothing rather
  than invent something.
- Two prompts now exist in code, which is what the configurable-templates phase needs in
  order to be designed from cases rather than guessed.
- Chapter 1, the roadmap and the CHANGELOG are updated in this phase. The roadmap's claim
  that a third skill would trigger the registry is corrected there.
