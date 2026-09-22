# Chapter 2 - Roadmap: where LACC is and where it is heading

This chapter describes what LACC has today and the path ahead. Nearer phases are
described with more confidence; later ones are direction and are expected to change
as real code reveals what each one actually needs. This is not a schedule and
carries no dates.

## Done

- **v0.0.1 - Scaffold.** An installable package, the quality gate (lint, format,
  strict type checking, tests), the documentation system, and the MIT license.
- **v0.1.0 - Configuration and run identity.** A validated, frozen `Config`
  contract loadable from YAML with network access off by default, and a
  human-readable, time-ordered `run_id`.
- **v0.2.0 - Workspaces and boundary enforcement.** A validated `Workspace` whose
  boundary cannot be escaped: candidate paths are resolved before checking.
- **v0.3.0 - Permissions.** A restrictive-by-default permission contract with the
  configuration acting as a ceiling no permission can exceed.
- **v0.4.0 - Provider port.** An abstract provider with a deterministic offline
  mock, so the rest of the system is testable without any engine.
- **v0.5.0 - Audit log.** Append-only JSON Lines inside the workspace, with privacy
  as the default and a configurable write-failure policy.
- **v0.6.0 - Execution preview.** A side-effect-free description of what an action
  would do and whether it would be allowed.
- **v0.7.0 - Execution cycle.** The one place that runs an action through the whole
  system, with confirmation supplied as a function, plus the first integration
  tests. Continuous integration and an example configuration were added here too.
- **v0.8.0 - Skills.** An abstract `Skill` contract that produces an action through
  a pure `plan`, plus a read-only file-summarization skill.
- **v0.9.0 - Command-line interface.** The `lacc` command (Typer + Rich): `run` and
  `preview`, with human confirmation defaulting to no. **LACC now runs end to end
  from a terminal** against the mock provider - the foundations became a working
  tool.
- **v0.10.0 - Permission sourcing.** A skill is granted the capabilities it
  declares, limited by the configuration ceiling (`grant_for`), removing the CLI's
  hardcoded permission.
- **v0.11.0 - Profiler.** A read-only `lacc profile` that detects Ollama, lists
  installed models, reports hardware, and computes a model-fit table by formula -
  honest about what it cannot know, and never recommending a model.
- **v0.12.0 - Real provider.** An `OllamaProvider` implementing the provider port
  against a local Ollama instance, with model selection from configuration and a
  CLI choice between mock and Ollama. LACC now runs end to end against a live local
  model.
- **v0.13.0 - Reading file contents.** The cycle reads the files an action declares,
  after confirmation and before the provider, so `summarize_file` summarizes real
  content instead of naming a file. A skill's plan supplies a prompt template and
  stays pure; the cycle fills it. **LACC now does useful work on the user's own
  documents** - the first step toward the north in VISION.md.
- **v0.14.0 - Shaping the prompt.** What LACC says to the model becomes deliberate: a
  framed task, a configured output language (`output_language`, English by default),
  and the document fenced between markers and declared to be material rather than
  instruction. `Skill.plan` receives the configuration, amending ADR-009 without
  giving up the plan's purity.
- **v0.15.0 - Ingestion.** `lacc ingest` turns a PDF or `.docx` inside the workspace into
  a `.md` file inside it, through a `Converter` port with two implementations. The cycle
  gains a second entry point for runs that produce a file rather than an answer. A
  security review of the existing surface closed two holes here - a non-loopback engine
  address was honoured without being checked, and a conversion could read or write what
  its action had not declared - and recorded the rest in ADR-017.

- **v0.16.0 - Hardening (ADR-017).** What a security review of the existing surface
  decided: a configured ceiling on input size, checked before a file is opened; Windows
  device names, alternate data streams and names ending in a dot or a space refused at
  the boundary; and a refused run exiting non-zero, while a declined one still does not.
- **v0.17.0 - A second skill: critique.** `critique_file` reads a draft and reports what
  is weak in it, read-only. The document fence moves into one function both skills use,
  since a security mechanism copied per skill is free to drift. The skill registry
  deferred in ADR-010 is declined rather than built, and the reasoning behind expecting it
  here is corrected.
- **v0.18.0 - An honest context ceiling.** LACC asks the engine for the context window
  it will enforce against, estimates each prompt, and refuses one too large rather than
  letting the engine drop what does not fit and answer from the rest. Measuring showed
  why asking matters: the engine loads a 32768-token model with 4096 unless told
  otherwise. Taken before reading several files, since several documents in one prompt
  is what makes prompts long.
- **v0.19.0 - Measuring the estimate.** The engine's own token count is recorded next
  to LACC's estimate, so the context ceiling can be checked rather than argued for. An
  underestimated prompt and an answer cut short are named as such. The ratio is not
  tuned automatically: measurement is for making a decision reviewable, not for
  removing the reviewer.
- **v0.20.0 - What a context window costs.** `lacc profile` reports what each window
  size would cost for each installed model, computed from the model's own published
  shape rather than fitted to the machine it was written on, against the memory free
  now. A range with its assumptions stated, never a recommendation, and it still does
  not set `context_tokens` for anyone.
- **v0.21.0 - Exposure controls.** The quality gate fails if anything reaches a
  non-loopback address, so local-first is enforced rather than asserted. A workspace
  inside a git working tree is refused, and one that looks synchronised is flagged as
  a guess. PRINCIPLES gains the rule the release rests on: approximation is a tool for
  performance, never for exposure.
- **v0.22.0 - A trail you can check.** Documents, prompts and completions are recorded
  by digest at every level, so the trail can say which document without keeping a copy
  of it. The trail is hash-chained and `lacc verify` walks it, making silent tampering
  detectable and locatable - and saying plainly that a deliberate rewrite is not what
  it catches.
- **v0.23.0 - Detecting truncation.** A prompt the engine did not read in full is
  noticed and named, distinguished from an estimate that merely ran low. Closes the
  verification ADR-019 deferred, by watching for the symptom rather than asking the
  engine what it granted.
- **v0.24.0 - Writing, and several documents.** `revise_file` proposes a clearer
  version beside the original, approved against a diff; every skill can be given
  several documents. Nothing LACC writes replaces a file that already existed, and an
  action now separates what it reads from what it writes.
- **v0.25.0 - Verified quotations.** `extract_claims` returns what a source asserts
  with the document's own words and a page, and every quotation is checked against the
  source before it is shown. The first control in LACC that verifies the model instead
  of asking it to behave, and the capability v1 is defined around.
- **v0.26.0 - Machines of your own.** The engine may run on a desktop you own, named in
  the configuration and reached over your own private network; a run that finishes says
  so through a notifier you host yourself. PRINCIPLES changes its network rule to match
  what VISION already said, and the rule that replaces it is narrower than "network
  access": every destination is written down in a file the user wrote.
- **v0.29.0 and v0.30.0 - The fabrications were ours.** An audit against a real paper found
  five defects in LACC that were making faithful quotations fail: words the typesetter broke,
  typographic characters, an asymmetry the first fix created, LACC's own page markers inside
  sentences, and a journal header extracted mid-sentence. The reported rate of invention went
  from three in seven to none, and the paper's unquotable sentences from sixteen to zero. The
  test suite passed throughout.
- **v0.28.0 - Measured, not declared.** The preview names where documents are going, a skill
  declares its temperature and it is zero, and `lacc measure` reports the spread across
  repeated runs - after a model comparison written here turned out to be sampling noise.
- **v0.27.0 - Adoption.** Guides written from what the tool does, a citation file, and a
  README that tells someone how to run it. Completes the v1 feature list, and records why
  v1.0 still does not follow: two paths have never been executed and the premise behind
  them is untested.

## A course correction, recorded

Between v0.18.0 and v0.23.0 six consecutive releases went to making the system honest
about itself - ceilings, measurement, exposure, traceability. Each was justified and
several came from real findings. None of them advanced the north.

The mechanism is worth naming, because every step in it is defensible: each release
surfaced the next gap in what the system could verify, and that gap justified the next
release. That loop has no natural end, since there is always something more to check.
By v0.23.0 the test suite was larger than the code and twenty-four decision records
described a system that could summarize a file, critique a file, and convert a
document - two of the six steps this chapter lays out, with the second finished nine
releases earlier.

Not all of it was a detour. The context ceiling and truncation detection are
prerequisites for chunking: a document cannot be split honestly without knowing what
fits. The exposure controls guard real private material. But the discretionary share
was large enough to notice.

So: the next releases are capability, on the path above. When a verification gap turns
up mid-phase it is written down rather than promoted to the next release - unless it is
a security defect, where PRINCIPLES already says the stricter reading wins. Growing in
a straight line beats a sequence of small correct turns that arrives nowhere.

## The route to v1.0

v1 is deliberately small, and it got smaller once the work it is for became clear. LACC is
being built to produce scientific writing from a base of references - papers first, and a
thesis built on them. Consulting a source is a tool in service of that, not the goal.

That reframing sets the bar. The failure that matters is not a shallow answer: it is an
invented one. A tool that fabricates a citation is not merely unhelpful for published work,
it is dangerous to the person who publishes it. So the capability that defines v1 is not
fluency but grounding.

- **Grounded extraction.** *Delivered in v0.25.0.* What a source claims, returned with quotations and page numbers,
  and **each quotation checked against the document it came from**. What cannot be found is
  reported as unsupported rather than presented as fact. This is the one thing LACC can do
  that a chat service cannot, and it is mechanical: a substring search, deterministic, with
  no model involved in the checking.
- **A stronger machine of your own.** *Delivered in v0.26.0.* v1 assumes the model runs
  somewhere better than a laptop - a desktop on a private network, reached over Tailscale. This laptop stays the
  place where LACC is developed and tested, because that is faster; it is not the place the
  work is expected to be good. The decision record for this comes before the code, and it
  resolves the contradiction between PRINCIPLES and VISION over what counts as local.
- **Finishing without watching.** *Delivered in v0.26.0.* A run that takes minutes is fine,
  provided it says when it is done. A notifier the user hosts themselves, reached over their own private network -
  not a third-party messaging service, which would tell somebody else when you work and on
  what, whatever the message said.
- **Adoption, and citability.** *Delivered in v0.27.0.* LACC is public and is meant to be cited in the thesis it
  helps write, so that others can build on it. That makes guides, a clear install and a
  citable record part of the deliverable rather than an afterthought.

Everything else waited for v2, and waited on purpose. Each is real. None was needed to
write a paper with sources you chose.

A smaller v1 that is true beats a larger one that is late, and there is no shame in the
whole shape of the project arriving at v20.

**All four are delivered, and v1.0 is tagged.** The evidence it waited on was never another
test: it was the tool meeting real sources. That happened - a bibliography of 24 papers, 237
quotations, every one checked - and what it showed is in this document, including the parts
that were unflattering.

v1.0 is a floor, not a finish. It says the tool does not deceive you about its own work: a
quotation that cannot be found is reported, a document that will not fit is refused and named
rather than truncated, and the audit states the one gap it cannot close. It does not say the
model is reliable. One quotation in five was invented, and that is the measurement v1.0
ships with rather than the one it hides.

## What v2 used to mean, and does not any more

**This section described a future that has been delivered.** Reading a document in passes is
built, measured and published (ADR-046), and `--in-passes` is how the EAU guidelines entered
the corpus at all. It is left here because the reasoning still holds and the trade-off it
records is still the trade-off; what changed is the tense. It was read as a statement about
what is coming for longer than it was true, which is the failure chapter 4 names as **asking
when a figure was taken** - and a roadmap is a figure too.

The name is free again. What v2.0 means now is further down.

v2 is one thing, and the list it replaced was six phrases (ADR-045). **A document too large
for the window is read in passes over its pages**, which is what a tool for writing from
sources owes the sources that matter: on the bibliography this was built for, eight of
twenty-four documents were refused, and they were the central ones.

Two entries of the old list are out, and out by decision rather than by scheduling.
**Letting the model choose what to do next** contradicts PRINCIPLES and VISION in as many
words, and does not enter a later version without an ADR saying what "choose" may mean.
**Conversation across turns** makes a prompt depend on earlier runs, at which point a run's
audit record stops explaining that run's output - and the trail is what v1.0 promised.

**Splitting was never a second goal beside library-scale reading. It is the mechanism.**
Counting them apart is what made the plan look twice its size.

Measured on the EAU guidelines, 251 pages and 355,000 tokens, the document this project
could not open: **sixteen passes, every page covered, each pass overlapping the last by one
page.** What it cost is written down beside it - sixteen calls is roughly a quarter of an
hour, and reading in passes is asked for with `--in-passes` rather than substituted, because
a document of that size becoming most of a day is not a thing to begin on someone's behalf.

What it buys and what it spends are both in the ADR. **Every quotation is still checked
against the whole document**, so v1.0's promise survives being divided. What is spent is the
document's coherence: a claim resting on section 2 and section 7 together will not be found
by a reader who saw neither with the other, and no count of passes says which claims those
were.

**This makes documents readable, not libraries.** A corpus assembled from a real
bibliography is itself around thirty thousand tokens and exceeds the same window. Synthesis
across sources needs selection rather than traversal, which is a different mechanism and a
later version.

## Decided, and deliberately after v1.0

One direction is settled enough to record and deliberately out of v1.0. It is written here
so that decisions taken before it do not quietly rule it out.

A second direction used to live here - running the model on another machine of the user's
own - and it moved into v1 above. What changed was not the design but the purpose: v1 is
for work that has to be good enough to publish, and a three-billion-parameter model on a
laptop is not that. The reasoning it carried, about the threat model changing the moment
LACC talks to something that is not loopback, moves with it and is now something v1 has to
answer rather than defer.

**An interface beyond the CLI.** A terminal UI or a local web application, consuming
the same core. It arrives once the core keeps its promise, so that the interface is
built on something finished rather than becoming the place where behaviour is decided.

Converting the finished Markdown to LaTeX is not on this list. Pandoc does that well
already, and LACC has no reason to reimplement it.

## What the first real run showed

v0.28.0 was gated on running LACC against a real source, on real hardware, rather than
declaring the feature list complete. That run happened, and it did not go the way the
feature list implied.

The setup: an RTX 5080 with 15.9 GB, reached over Tailscale, running Ollama; a
self-hosted ntfy for notifications; the same seven-page paper from a real bibliography put
through `extract_claims` twice.

| Document | Model | Claims | Verified | Failed |
|---|---|---|---|---|
| Synthetic, written for the test | qwen2.5:7b | 7 | 6 | 1 |
| Synthetic, written for the test | qwen2.5:14b | 7 | 7 | 0 |
| **A real paper** | qwen2.5:7b | 3 | **1** | 2 |
| **A real paper** | qwen2.5:14b | 4 | **2** | 2 |

**The two paths that had never been executed, were.** The engine reached another machine
and answered; a notification was delivered and recorded. Both had been covered only by
tests with injected transports, which was the right way to test them and not the same as
knowing they work.

**The synthetic test was far too easy, and it flattered the result.** 86% and 100%
verified there; 33% and 50% on a real paper. A document written for a test has short,
clean, quotable sentences. A real paper has dense prose, hyphenation across line breaks,
tables and figure captions. Had the synthetic run been the evidence, v1.0 would have
shipped on a number that was not true of anything anyone would actually do.

**The comparison between models does not survive repetition.** Running the 14B four times
on the same paper gave 4, 5, 7 and 3 claims, of which 2, 4, 3 and 2 verified - a rate
between 43% and 80%. That spread is wider than the gap between the 7B and the 14B on one
run each, so a single run per configuration distinguishes nothing.

This is worth recording as a mistake and not only as a result. The one-run comparison was
written into this document before it was repeated, and it read as a finding. It was noise.
Two runs are a story; four are a measurement.

So the premise v0.26.0 was built on remains untested rather than refuted. "A larger model
produces work good enough to publish" is not something these numbers can speak to yet, and
any future claim about model choice needs repeats before it is written down.

**What repetition does support** is harder to argue with: every run fabricated at least one
quotation, and every run had the check catch it. Across five runs against a real paper
there was no configuration whose output could have been trusted unchecked.

**The check earned its place, and it is the only thing that did.** Without it, a fabricated
range of sensitivity values would have been copied into a citation. With it, the claim was
marked and the run said not to cite it without opening the document. That happened on a
real paper, on the first attempt.

## What v1.0 means, rewritten

The definition that stood here until v0.28.0 said "that a paper can be written with it",
and it was written before there was any evidence. The evidence narrows it.

v1.0 does **not** mean the model does the work. On a seven-page paper, three quarters of
what a 7B model produced could not be trusted, and half of a 14B's could not. Any claim
built on the model being reliable is a claim this project's own measurements contradict.

What v1.0 means is this: **you can work from your own sources without being deceived.**
Every quotation is checked against the document it claims to come from, what cannot be
found is reported as unsupported rather than presented as fact, and the whole run leaves a
record that can be verified afterwards. That is a smaller promise than the one the feature
list implied, and it is one the numbers support.

It does not mean every feature exists. It means nothing it produces has to be taken on
faith, and that the parts which cannot be verified say so.

## What the run left open, and how it closed

Two findings, both from the real paper, neither of them the model being small. Both are now
fixed, and are kept here because the route from symptom to cause is the useful part:

**Very few claims are extracted** - three and four from seven pages. The audit shows
`finish_reason: stop` and answers of 260 and 214 tokens, so nothing was truncated: the
models simply stopped. That points at the prompt rather than at capacity.

*Closed in v0.35.0.* The format was stated once, before a document that then ran for
thousands of tokens. Restating it after the document tripled the claims extracted
(ADR-037).

**Page attribution fails systematically.** Page 4 for something on page 1; page 3 for
something on page 5. The quotations were real and the pages were not, which in a citation
is its own kind of wrong. Worth noting that LACC already locates the quotation itself while
checking it - so this is a question the tool can answer without asking the model at all.

*Closed in v0.31.0.* It does. The page is now found by searching, and what the model said
is kept for comparison and never reported as the answer (ADR-031).

## What a whole bibliography showed

The seven-page run above was one paper. Running `extract_claims` across 24 documents of a
real bibliography produced 237 quotations, and that corpus is now the project's measuring
stick because it is large enough to be re-run and disagreed with.

| | v0.38.0 published | Re-measured | v0.39.0 |
|---|---|---|---|
| quotation found in its document | 237 | 167 | **189** |
| **not in the document** | **0** | **70** | **48** |

The published figure was wrong, and the correction is recorded in ADR-042. Two things came
out of re-running it that the first measurement could not have shown.

**Twenty-two of those "fabrications" were real quotations.** Some PDFs are extracted with
spacing between glyphs rather than words - `A c c o r d i n gt o` - and every quotation
taken from such a page was rejected. Fixed in v0.39.0, with the folding kept out of the
similarity path and a mutation test confirming a changed word or digit still fails.

**Forty-four are absent in any form tried.** Not stitched from separate sentences, not
reworded: not there. About one quotation in five, on a real bibliography, with a 14B model.
That is the number this project should be quoted on, and it is the reason the check exists.

**Eight of 24 documents never entered the window at all.** They were refused for size, which
is correct, and `collect` said so: each one occupies its own section of the corpus naming the
token count, the budget and what to do about it. Nothing was hidden. The library-scale work
deferred to v2 below is not a nicety: without it a bibliography is read only in the parts
that happen to fit.

> **That was the state then, and it is no longer the state.** Reading in passes (ADR-045)
> closed most of it, and the figure was still being quoted as current days later. Measured
> against the corpus on 2026-09-20: **two documents have no quotation in it** - one paper of
> 29,362 tokens, and the EAU guideline of 348,276, which four extracted sections cover with
> 111 quotations. nnU-Net has 39, the NCCN guideline 63. A number from a record is a number
> from the day it was taken.

## Four defects of one shape, and what found them

ADR-055 found a feature nothing could switch on. ADR-056 found a parser discarding an answer
it had been handed. Both passed their tests; both were described accurately in a document and
inaccurately in the program. So the code was swept for the same shape, and two more turned up,
plus one that the fix for the first exposed.

| | |
|---|---|
| the prompt asked for a format the grammar forbade | the same `prompt_sha256` under both conditions (ADR-057) |
| a skill answering in prose *and* blocks could be shape-enforced | a schema would have deleted the prose (ADR-057) |
| deduplication covered one of four paths that produce checked claims | and a single answer repeats too: 3 of 19 measured (ADR-058) |
| ntfy's docstring promised basic credentials | helper tested, called by nothing, no field to reach it (ADR-058) |

**None of these was a wrong belief about a model.** Every one was the program failing to do
what its own record said it did, while the suite stayed green.

**What found them is worth naming, because it was not a test.** ADR-055 added a check that
every setting can be set, and it would have caught neither of the last two: a control applied
in three fewer places than it should be is not a setting, and a sentence in a docstring is
not one either. Reading found them - specifically, asking of each control *"what does this
cover, and is that what its record claims?"*

Three standing checks now encode the three that have a mechanical form (ADR-059), and
**building the first of them immediately found two more**: the judge of readings from ADR-053
- graded, tabled and published in a git tag - was constructed by nothing at all, and `require`
was dead while its docstring called itself the execution path.

**Six defects in three days, on fifty-nine records, is a rate rather than bad luck.** Two
phases followed from that, and both are now built:

- **An inventory from each record to the code it names.** Measured: 52 of 58 records name at
  least one real symbol, 97 distinct. A generated report of what each record mentions and
  where it is used. It detects nothing; it makes the reading finite.
- **One pass over all 59 records** - done, and the instrument was not the inventory. Ranking
  by thinnest symbol found nothing: a low count is usually a CLI command registered by a
  decorator. The question is textual, so what was searched for was **universal claims that
  name code** - a sentence with *every*, *always*, *never* or *nothing* beside a backticked
  symbol. Ninety of them, read in an afternoon. Most hold. One did not, and it was a day old:
  the judge recorded that it had judged and not what.

A ranking was tried and rejected: citations-per-use puts a correct one-caller function at the
top and puts a control **low because it had just been fixed**. It is a reading queue, not a
detector, and shipping it as one would be this project's own recurring error in a new costume.

What stays irreducible is choosing what to verify. The checks make five known defects
impossible to repeat; none of them finds a kind that has not happened yet.

## A feature that was counted as delivered and was not there

Going to run the measurement ADR-052 promised - *does constraining decoding cost content
quality?* - found that it could not be run. `enforce_shape` had no flag, no configuration key
and no field in a skill declaration, so no schema had ever been sent to any engine. The
feature was in the changelog, in a decision record, and in nothing the program could execute.

Six tests passed because they built the plan object directly. The program never does; it
calls `plan`, and `plan` was the part with nothing in it. **This was the second instance** -
`ask_corpus` was tested the same way, was absent from the registry, and failed on its first
real launch with the suite green.

So the rule is in the suite rather than in anyone's memory: every field with a default, on
every model the program builds in code rather than reads from a file, must be set somewhere
in the source. Eighty-seven fields qualify; all pass now, and a third instance fails the build
(ADR-055).

**For a roadmap, the lesson is what "done" is allowed to mean.** This document and the
changelog both listed a feature that existed as a type and not as a path. Neither was lying:
the code was written, reviewed and tested. The question that separates the two is one
sentence - *what in the program sets this?* - and until it is answered, a feature is a design.

## A planned piece, measured and dropped

The next item on the plan was approximate deduplication - MinHash over the corpus - and it
was not built. The reason is worth more than the feature would have been.

It was planned on a premise: *"the corpus has near-duplicates between documents."* That
sentence sat in a planning document reading like something already known, and nobody had
looked. Measured over all 654 quotations across all 26 documents, the corpus holds **zero**
near-duplicates across a document boundary. Every repeat in it is inside a single document,
and there are six.

Two things follow, and the second is the general one.

**MinHash was a solution to a cost that is not there.** It exists to avoid comparing
everything with everything. Here that entire comparison - 213,531 pairs, exact - takes 133
milliseconds. What did need fixing was found by looking at the six: a repeat across passes is
rarely word for word, it is the same sentence with wider boundaries, and equality misses it.
That is exact containment and it is ten lines (ADR-054).

**A threshold would have been wrong in the direction that costs most.** The two most alike
quotations in the corpus that are not identical agree on 0.86 of their wording, and they are
`Apalutamide` and `Darolutamide` in otherwise identical sentences. The conventional
near-duplicate threshold is 0.80. The highest-similarity non-identical pair in this corpus is
one that must be kept.

**The lesson for this roadmap is about plans rather than about duplication.** This project
has a section counting ten figures it got wrong, and it learned to check numbers. The premise
above was never a number. It was a claim about the world, written in the sentence justifying
the work, and it was invisible for exactly that reason - nothing in a plan looks like a
figure. **A plan is where unmeasured claims hide.** The question that catches them is asked
of sentences, not of tables: *has anyone looked?*

## Retrieval, built - and what using it found

The wall named throughout this document: 654 quotations do not fit a window, and the largest
documents had to be read in passes to enter it at all. Choosing by meaning is built (ADR-061), measured, and honest
about its size: decisive across languages - eight relevant of the first eight against about
three by words - better in English on one question, which is a story, and blunted at this
corpus size because a 32k budget admits a third of the corpus whatever the ranking says.

**Then the tool was asked a question somebody actually wanted answered, and that found three
defects 587 tests had not** (ADR-062). A declared skill's prompt never carried the question.
A greater-or-equal sign ended a run while printing it, after the answer had been paid for.
The trail could not recover it, correctly. Two of the three were invisible to every check
here: the prompt was well-formed and the run reported success.

**That is the argument for the phase this document keeps deferring.** Six days of building
checks found six defects of one shape; one real use found three more of a shape no check
looks for, because a check asks whether the code does what it says and a use asks whether
what it says is what somebody needed.

The fourth defect is unfixed and is a choice rather than a bug: `draft` asks for prose of
three to six sentences resting on one quotation, which cannot hold it, so every paragraph is
under-cited by construction and the judge flags all of it. Every figure in those paragraphs is
in the corpus - missing citation, not invention. How to resolve it changes how a person
writes, so it waits for the person.

## The route from here: v2.0 and v3.0

Five steps, and the order is causal rather than preferred. Each one is a prerequisite for the
next in a way that was measured, not assumed.

```
v1.8.1  one corpus format, written by both writers   corrupted data, shipped alone
v1.9.0  metadata from an authority + the last two documents
v2.0.0  the core takes back what is its own  +  coverage
v2.5.0  an interface that reads
v3.0.0  discovery, and an interface that acts
```

**That numbering did not survive, and the record says so rather than being edited to fit.**
Three planned versions ended up in one tree: v1.9.0's registry arrived, v2.0.0's vertical cut
arrived, v2.5.0's interface arrived **early and whole**, and coverage did not arrive at all.
Separating them afterwards would mean rewriting history to match a plan rather than the other
way round.

**So v2.0.0 absorbs v1.9.0 and v2.5.0**, and what each was for is said below where it was
written. What is left of v1.9.0 is not code: two documents that have no quotation in the
corpus, which is a run rather than a release - **a version of the software does not depend on
the state of somebody's corpus**, and putting it on the release checklist was a mistake of
judgement corrected here.

v3.0.0 keeps its meaning: what can happen without you typing.

### v1.9.0 - the material becomes complete, and citable

Two things, and neither is design work. **Reference metadata comes from an authority instead
of a model**: asked for the journal a paper appeared in, with an instruction not to guess in
the prompt, a 14B invented twelve names out of twenty-four (ADR-047). Crossref by DOI is a new
port with a whitelist and its own record. **And the two documents with no quotation in the
corpus are read in passes** - one of 29,362 tokens and the guideline of 348,276, of which four
extracted sections currently carry 111 quotations.

This is the release where the project stops investigating and starts **delivering**: a
bibliography whose entries can be written down without checking each one by hand.

### What v2.0.0 turned out to be, which is not what this section planned

**This is a correction, left visible.** The route above was written one morning and says v2.0
is the vertical cut plus coverage. The cut happened. **Coverage did not**, and what arrived
instead was better, so the plan is wrong and the record of being wrong is worth more than a
tidy plan.

What the version actually holds:

| | |
|---|---|
| `lacc resolve` | metadata from the registry that assigns DOIs, not from a model (ADR-067) |
| `lacc review` | **your** draft against **your** sources - the check turned around (ADR-068) |
| `lacc sections` | a document's own numbering, and one part taken out of it (ADR-076) |
| `lacc window` | a second view: eight sections, and it reads (ADR-069 to ADR-075, ADR-077) |
| `scripts/` | launchers whose digests the gate enforces (ADR-071) |
| the method | measured, written down, and followable without being explained |

**And the reason it is a major version is `review`.** Everything here verified text a *model*
produced. `review` asks the same question of text a *person* wrote, which is not one more
command: it is a different answer to what this tool is for.

**Why coverage did not happen, stated rather than rescheduled.** The work went where it was
asked to go, and each thing asked for turned out to matter more than clustering: a
bibliography that can be handed in, a reviewer for your own prose, a guideline that can be
read one section at a time, and an interface for somebody who is a researcher rather than an
operator. Coverage is still the right idea and still carries its precondition - **a gap
measured over an incomplete corpus is a false gap** - and it is still not built.

### What this section planned, and still argues for

### v2.0.0 - the core takes back what is its own, and coverage becomes a thing that exists

**Coverage is the only remaining phase that produces a paragraph nobody could write before.**
A cluster with two quotations is a subject the bibliography barely touches - a gap **counted**
rather than opined. That distinction was measured the hard way: asked to name the research gap,
both models invented one, and the 32B named as missing the topic of the first paper on its own
list.

It carries a precondition that is not scheduling: **a gap measured over an incomplete corpus is
a false gap.** Cluster today and a subject the guideline covers across forty pages that never
entered the window looks like a hole. That would be a thirteenth wrong figure, and one of the
kind that flatters the tool - which is why v1.9.0 comes first.

The other half of this release is a debt with a receipt. `cli.py` is **2,588 lines, 72% of all
root-level code**, and what lives in it is not only presentation: `_collected_markdown` and
`_assembled` both **write** the corpus format, while `parse_corpus` **reads** it from `core/`.
That asymmetry is the root cause of ADR-065 - two writers in the interface, one reader in the
core, free to drift apart with the suite green.

**The layering rule was written in one direction and only that direction was checked.**
PRINCIPLES says the core contains no interface code, and `tests/test_layering.py` proves it
five times over: core imports nothing, a port imports nothing, an adapter reaches only for core
and ports, nothing in core imports the cycle, every module lives in a layer. Every one of them
follows dependencies **inward**. None of them asks whether logic has leaked **outward** into
the interface. The converse of the rule was never stated and never measured, and it cost a
defect that silently stripped meaning from a user's corpus.

Coverage is the second consumer of that format. Paying the debt immediately before adding the
consumer is what stops ADR-065 from happening again with two interfaces instead of one, and
moving modules breaks import paths, which is what makes this a major version.

**Where the logic goes was decided by measuring, and the measurement refused half the idea.**
The shape proposed was a hybrid: keep the hexagon, cut vertical slices by capability. Counting
first:

| | |
|---|---|
| core modules used by exactly one capability | **3 of 14** (`corpus`, `declared`, `references`) |
| core modules used by three or more places | **9 of 14** |
| `config` alone is imported by | 9 modules |
| commands in `cli.py` | **14**, 1,050 lines |
| helpers in `cli.py` | **49**, 1,225 lines |
| the six largest helpers that are not presentation | **341 lines** |

**So the core does not get cut.** Nine of its fourteen modules are genuinely shared - `config`,
`workspace`, `permissions`, `preview`, `grounding` - and slicing them by capability would
invent boundaries the code does not have, which is how a refactor becomes six releases that
advance nothing. This document already records that happening once.

**The monolith is `cli.py`, and that is where the vertical cut belongs.** Fourteen commands and
forty-nine helpers in one file, where `_judge_the_readings` (92 lines), `_collected_markdown`
(73) and `_assembled` (61) are domain logic wearing a presentation module's clothes.

The result is the hybrid, with each half where the measurement puts it: **the hexagon stays
horizontal and shared** - ports, adapters, and the nine core modules everything uses - **and
each capability becomes a vertical slice** holding its own use case, pure and testable, with
the CLI and the interface as two views of it. `_collected_markdown` and `_assembled` end up in
the same slice as the reader that has to agree with them, which is the arrangement that would
have made ADR-065 impossible rather than merely caught.

**And the converse rule gets written and checked.** `tests/test_layering.py` gains what it
never had: **a view contains no logic.** Stated for the CLI, and binding on the interface
before a line of it exists.

### v2.5.0 - an interface that reads

**A window of its own, with no port listening.** The material this project exists to protect
is private research, so an interface that opens a TCP socket on the machine holding it buys
convenience with attack surface. **CustomTkinter**: Tk ships with Python, the window talks to
Python directly because it *is* Python, nothing listens, nothing is served, and PyInstaller
packages it without a browser runtime.

**The layout is a file explorer and the manner is a reading application.** A tree on the left -
workspace, documents, corpora, runs - and what is selected on the right, which is the shape
every person on Windows already knows. `ttk.Treeview` is literally that widget. The surface is
quiet and warm rather than dense with chrome, because what is on it is prose and quotations,
and a tool for reading should look like one.

Two costs, named now rather than discovered later. **CustomTkinter ships no type information
and `mypy` here runs `strict` over all of `src`**, so it arrives with an override for that one
import - honest, and narrow. **And Tk cannot be exercised headlessly**, so no test can cover a
window on a machine with no display. That is not a reason to skip tests: it is the reason the
vertical slices come first. Everything worth testing lives in the use case the window calls,
and the window is thin enough that looking at it is enough.

**It reads, and reading is the whole of this release.** The corpus, each quotation with its
standing, the audit trail, and the coverage map. Running skills stays in the CLI.

The ordering argument is simple: **the coverage map is the first thing this project produces
that a terminal cannot show.** A gap is a shape. Before it exists, an interface would be a form
that types commands for someone who already knows how to type them.

### v3.0.0 - what can happen without you typing

The two remaining directions both change what is possible without a keystroke, which is why
they share a major version and why that version is about one principle rather than two
features.

**Discovery with a whitelist.** Titles and abstracts from PubMed, Crossref or arXiv reveal a
query, not a document, and the fact that someone researches prostate imaging is public the
moment they publish. It stays bounded: a `discover` capability, a list of domains in the
configuration, metadata only, never a PDF download, and whatever comes back treated as hostile
text until it is accepted into the workspace.

**An interface that acts**, with preview and confirmation on screen. The delicate part is named
in advance: a click must not become easier to give than the confirmation it replaces. That is
where a principle erodes quietly, so it gets its own record rather than arriving as a button.

### Deliberately not on the critical path

Persistent vectors with sqlite-vec, declared pipelines, the one paper whose bare numbering
makes it invisible to `lacc references`, and CACC. Each is real. None of them answers the
question this project now asks of every phase: **what did you write that you could not write
before?**

## What this roadmap is not

Not a release schedule, and not a promise. It is a statement of direction meant to
keep development focused and honest. Where a feature is not yet implemented, it is
described as intent. Phases may be split, merged, or reordered as real code reveals
what each one needs.