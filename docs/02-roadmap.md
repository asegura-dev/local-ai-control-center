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

Everything else waits for v2, and waits on purpose: working with a whole library rather
than a handful of sources, holding a conversation across turns, letting the model choose
what to do next, moving prompt wording out of the code, and splitting documents too large
for a window. Each is real. None is needed to write a paper with sources you chose.

A smaller v1 that is true beats a larger one that is late, and there is no shame in the
whole shape of the project arriving at v20.

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

## What the run left open

Two findings, both from the real paper, neither of them the model being small:

**Very few claims are extracted** - three and four from seven pages. The audit shows
`finish_reason: stop` and answers of 260 and 214 tokens, so nothing was truncated: the
models simply stopped. That points at the prompt rather than at capacity.

**Page attribution fails systematically.** Page 4 for something on page 1; page 3 for
something on page 5. The quotations were real and the pages were not, which in a citation
is its own kind of wrong. Worth noting that LACC already locates the quotation itself while
checking it - so this is a question the tool can answer without asking the model at all.

## What this roadmap is not

Not a release schedule, and not a promise. It is a statement of direction meant to
keep development focused and honest. Where a feature is not yet implemented, it is
described as intent. Phases may be split, merged, or reordered as real code reveals
what each one needs.