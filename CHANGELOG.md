# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.29.0] - 2026-09-10

### Added
- **A quotation that is not found now comes with the closest text that is actually in the
  document.** The verdict does not change - nothing fuzzy is ever accepted as verified -
  but the refusal stops being a dead end:

  ```
  Not in the document:
    the model wrote    ...metastases was 76-90%
    closest in source  Results The sensitivity of the AI method for detecting
                       pelvic lymph node metastases was 82%
  ```

  Built for the worst kind of fabrication: a real sentence with the figure changed. Right
  topic, right wording, false number - the part that would be copied into a table, and the
  part nobody skimming catches.

### Fixed
- **Words the typesetter broke across a line no longer fail verification.** A real paper
  produced two quotations reported as fabrications that were nothing of the kind: the model
  had quoted faithfully, and the PDF held `sensi- tivity` and `avail - able` across line
  breaks, which LACC's own ingestion preserved. **The check was reporting a defect in this
  project as dishonesty in the model.**

- **Typographic characters no longer fail verification either.** The paper is set with
  en-dashes, non-breaking hyphens and curly quotes; a model reading `76-90%` writes the
  ASCII a keyboard has. Sixteen of that paper's hundred and sixty sentences could not be
  verified even when quoted perfectly.
- **And the first hyphen fix created an asymmetry, now removed.** Rejoining only when
  whitespace followed the hyphen fixed `sensi- tivity` and broke `inter- reader` - a real
  compound the typesetter split at its own hyphen, so the document normalised one way and
  a model writing `inter-reader` normalised the other. A hyphen between letters is now
  removed on both sides, with or without space; numbers keep theirs, since `the 5 - 10
  range` must not become `the 50 range`.

  **On that paper the 14B model went from four verified quotations out of seven to seven
  out of seven**, at temperature zero, repeatedly. Every apparent fabrication was this
  project's own defect.

  This number has now been wrong three times in two releases, and each correction moved it
  down as another LACC defect was found: three fabrications in seven, then one, then none.
  The check that exists to catch a model deceiving you was reporting this project's
  defects as the model's dishonesty. A feature built for something else found it, on a real
  document - see [ADR-035](docs/adr/ADR-035-what-counts-as-the-same-text.md).

### Measured
- **The 32B model is not worth its cost on a 16 GB card, and more parameters did not help.**
  All three models against the same paper at temperature zero:

  | Model | Quotations | Verified | Rate | Seconds |
  |---|---|---|---|---|
  | qwen2.5:7b | 3 | 2 | 66% | 2 |
  | **qwen2.5:14b** | 7 | **4** | 57% | **11** |
  | qwen2.5:32b | 7 | 3 | 42% | **186** |

  The 32B loaded as 26.83 GB - 13.63 in VRAM and 13.20 in system memory - because 18.5 GB
  of weights do not fit a 15.9 GB card at any cache setting. It delivered fewer verified
  quotations than the 14B and took seventeen times longer. Scaling stopped at 14B for this
  task on this hardware, which is not the obvious result.

  (These rates predate the de-hyphenation fix above; the 14B now measures 85% on the same
  paper.)

### Notes
- **The feature that found the bug was built for something else.** Showing the nearest text
  was meant to make a fabrication correctable. The first time it ran on a real paper it
  showed that two of the three fabrications were the project's own ingestion, which is a
  better argument for the feature than the one it was written for.
- The suggestion makes an unverified claim more comfortable to work with, and comfort is
  not automatically a virtue here: the point of marking a claim is that someone opens the
  document. It is drawn from the document itself, so acting on it is acting on the source -
  but it makes the failure easier to live with, which is not the same as making it rarer.


## [0.28.0] - 2026-09-10

### Added
- **The preview names where your documents are going.** A run against an engine on another
  machine now says so before you confirm:

  ```
  Reads:   paper.md
  Sends:   the contents read above, to http://100.101.102.103:11434
  ```

  The line appears only when the engine is elsewhere; a loopback engine adds nothing, and
  absence carries meaning. `Config.remote_engine` becomes the single definition of "not
  this machine", used by the code that discloses it and the code that enforces it.
- **A `configs/` folder**, ignored by git in full, is where LACC looks when no `--config`
  is given. More than one configuration is normal - an engine here and an engine elsewhere
  are different configurations of the same tool.
- **A `.env` beside the configuration supplies the variables it names.** No `setx`, no
  shell profile, no new terminal. The configuration still holds no secret and can be
  shared; the `.env` holds the values and is never shared. A variable already set in the
  environment always wins, so a server or a CI job keeps the last word.
- **A `*_env` field must name a variable, in upper case, or the configuration is refused**
  with a message saying what to put there instead.

- **`lacc measure <skill> <path> --runs N`** runs a skill several times and reports the
  spread rather than a number. It exists because the first real run produced a comparison
  between two models that did not survive being repeated, and because the extraction work
  that comes next cannot be evaluated without it.

  Measuring is treated as a different act from running: a separate command, not a flag, so
  `run` keeps its meaning exactly. It refuses any skill declaring `write_files`, because
  repeating something with effects would multiply them. The confirmation says how many
  times before asking, rather than hiding a multiplier behind "Proceed?". Every repetition
  is audited separately, with its own run id.

  It reports minimum, maximum and median, never an average - a mean would reproduce the
  error the command exists to correct.

- **A skill declares the temperature it needs, and it is zero.** LACC had never sent one,
  so the engine applied its own default of 0.8 - sampling rather than taking the most likely
  token, on work whose entire job is copying words out of a document. Measured: three
  requests at 0.8 gave three different answers; three at 0.0 gave one.

  The deciding reason was not accuracy but the audit. Every run records `prompt_sha256` and
  `completion_sha256`, and at a non-zero temperature those hashes cannot be reproduced - the
  trail said something happened and nobody could obtain it again. For a record meant to be
  citable, reproducibility is what makes it mean anything.

  There is no configuration override: temperature is a property of the task, and a setting
  able to raise it could quietly make a grounded task unreliable while everything appeared
  to work.

### Changed
- **The page a claim is reported with is the one LACC found, not the one the model said.**
  Locating a quotation is already how it gets verified, so the page falls out of work being
  done anyway - and it is right by construction, where a model asked to remember a page was
  wrong often enough on a real paper to put a bad citation into a thesis. The `wrong page`
  verdict is gone, because the situation it described no longer produces a bad page. How
  often the model misplaced a passage it quoted correctly is recorded in the audit instead,
  where a fidelity signal belongs and a person checking citations does not have to read it.
- The default configuration path is `configs/config.yaml` rather than `config.yaml`. Move
  an existing one: `mkdir configs && mv config.yaml configs/`.
- Guides reorganised by operating system. `server-setup-on-linux` and
  `server-setup-on-windows` are each a single continuous path, because alternating
  "Linux:" and "Windows:" made a reader filter half of every page - which is exactly what
  someone who has not done this before cannot do. The hub explains what is being built and
  sends you to one of them.
- `choosing-hardware-for-local-models` replaces `a-remote-engine-over-tailscale`, which had
  become a hardware guide with a title about something else. `notifications-with-self-hosted-ntfy`
  is gone, its unique content folded into the hub.

### Measured

**This is the first release of LACC tested end to end against the hardware it was designed
for**, rather than declared finished. An RTX 5080 reached over Tailscale, a self-hosted
ntfy, and a real seven-page paper from a real bibliography.

| Document | Model | Claims | Verified | Failed |
|---|---|---|---|---|
| Synthetic, written for the test | qwen2.5:7b | 7 | 6 | 1 |
| Synthetic, written for the test | qwen2.5:14b | 7 | 7 | 0 |
| **A real paper** | qwen2.5:7b | 3 | **1** | 2 |
| **A real paper** | qwen2.5:14b | 4 | **2** | 2 |

- **The two paths that had never been executed, were.** The engine reached another machine
  and answered; a notification was delivered, recorded in the audit trail, and arrived on a
  phone. Both had been covered only by tests with injected transports - the right way to
  test them, and not the same as knowing they work.
- **The synthetic test was far too easy and flattered the result.** 86% and 100% verified
  there, against 33% and 50% on a real paper. A document written for a test has short,
  clean, quotable sentences; a real paper has dense prose, hyphenation across line breaks
  and tables. Publishing on the synthetic number would have meant publishing something not
  true of anything anyone would actually do.
- **The comparison between models does not survive contact with repetition, and it was
  published here before it was checked.** Running the 14B four times on the same paper gave
  4, 5, 7 and 3 claims, of which 2, 4, 3 and 2 verified - a rate between 43% and 80%. That
  spread is wider than the gap measured between the 7B and the 14B on one run each, so the
  single-run comparison distinguishes nothing. What was written first - that a larger model
  helps but does not solve it - is not supported by this evidence. The honest statement is
  that **one run per configuration cannot tell these models apart at all**, and any future
  claim about model choice needs repeats.
- **What repetition does support:** every run fabricated at least one quotation, and every
  run had the check catch it. Across five runs on a real paper there was no configuration
  in which the output could have been trusted unchecked.
- **The check earned its place, and is the only thing that did.** Without it a fabricated
  range of sensitivity values would have gone into a citation. With it the claim was
  marked, and the run said not to cite it without opening the document.
- **The roadmap's definition of v1.0 has been rewritten** to what the measurements
  support: not that the model does the work, but that you can work from your own sources
  without being deceived.
- Left open, and neither is the model being small: only three and four claims were
  extracted from seven pages, with `finish_reason: stop` and no truncation - so the prompt
  rather than capacity. And page attribution failed systematically, giving page 4 for
  something on page 1. LACC locates the quotation itself while checking it, so that is a
  question it need not ask the model at all.

**After temperature was fixed** (ADR-033), the same paper measured five times per model:

| Model | Quotations | Verified | Rate | Spread across 5 runs |
|---|---|---|---|---|
| qwen2.5:7b | 3 | 2 | 66% | none - identical every run |
| qwen2.5:14b | 7 | 4 | 57% | 57-60% |

- **Variance fell from sixty points to three.** The comparison that was noise before is a
  measurement now.
- **The rate the variance was hiding is worse than its median suggested.** The 14B settled
  at 57%, below the old median of 66% and far below the lucky 85% run. Sampling had been
  producing occasional good runs and concealing the real quality behind them.
- **The larger model is better, and not for the reason anyone assumed.** Its rate is
  *lower* - it extracts more than twice as many claims, and delivers twice as many verified
  ones. For work that needs checkable facts, claims delivered matters more than the
  proportion, since the unverified ones are marked and cost a glance rather than a citation.
- One document. Enough to answer a question that could not be answered at all before, not
  enough to generalise.

### Notes
- **`engine_host` shipped in v0.26.0 and the preview did not follow.** PRINCIPLES puts the
  human in the centre and makes the preview the place that promise is kept, so the most
  consequential fact of a remote run - that the text of a document is about to leave this
  computer - was the one thing the confirmation screen did not say. Every guarantee around
  it held; a control nobody can see is a control nobody exercises.
- **The destination is passed to the preview, never inferred.** Guessing it from an
  action's capabilities would be wrong exactly where it matters: converting a PDF contacts
  no engine, and a preview that claimed otherwise would be lying in the direction that
  teaches people to ignore it. There is a test for that case.
- **The naming indirection was protecting nobody, because it depended on a step people
  skip.** The first person to follow the setup guide wrote the server URL, the topic and a
  live token straight into the `*_env` fields. Nothing complained: LACC looked for
  variables with those literal names, found none, and reported itself unconfigured. The
  misreading is entirely reasonable - the fields sit in a configuration file and look like
  where values go - and it put a secret into a file, which is the exact outcome naming the
  variable exists to prevent. The `.env` removes the step; the validation catches the
  misreading.
- **Requiring upper case is what makes the validation work.** A shape check alone accepts
  `tk_f0yn7rfgs48l94eq41y5u7ddh2irw`, which is a valid identifier and also precisely the
  thing being guarded against. Case is the only thing that reliably separates the name of
  a variable from the value of one.
- **A `.env` cannot redirect your documents.** It supplies secrets; `network_access` and
  `engine_host` stay in the YAML. ADR-027's rule is that no environment may widen what
  LACC contacts, and a test proves that an `OLLAMA_HOST` arriving through `.env` is still
  refused.
- **`config.yaml` was not in `.gitignore`.** Anyone creating one inside the checkout could
  commit their workspace path and their tailnet address with a `git add -A`. The rule now
  matches `config*` at the root by shape and re-includes the template by name, because the
  file that actually turned up was called `config.yaml.txt` - a rule that catches only the
  spelling you predicted catches nothing you did not.
- **The `configs/` folder is ignored in full, never a mix.** A folder where some
  configurations are tracked and others are not is how a private one eventually gets
  committed by someone filling in the wrong file - and everything keeps working, which is
  what makes it hard to notice. `config.example.yaml` stays at the root, holds no real
  values, and is the only configuration that is committed.


## [0.27.0] - 2026-09-10

### Added
- **Four guides, which is what "adoption" meant.** Setting up the server machine from
  nothing - Tailscale, Ollama and ntfy, step by step, for Linux and for Windows; running
  LACC for the first time; the reasoning and sizing behind a remote engine; and
  notifications. Written from what the tool actually does, with the numbers measured
  rather than estimated.
- **The setup walkthrough is the one authoritative copy of every instruction.** The other
  two guides keep the reasoning and point at it for the steps, because two copies of a
  binding instruction is two copies that drift, and the one that drifts is the one nobody
  re-reads.
- **`CITATION.cff`**, so the project can be cited in published work and GitHub can offer a
  formatted citation. Its version and release date are now part of the release checklist -
  a citation file naming an older version tells someone they used a release they did not.
- **A "Getting started" section in the README.** Someone landing on the repository could
  read what LACC is, what it is not, and its whole design philosophy without ever learning
  how to run it.
- A "Releasing" section in the development chapter, naming the three places a version
  lives.

### Notes
- **The remote-engine guide leads with the thing that is actually dangerous.** Ollama has
  no authentication of any kind, and the advice found everywhere is to set
  `OLLAMA_HOST=0.0.0.0`, which binds it to every interface the machine has - including
  whatever network it joins next. The guide binds it to the tailnet address, and then
  verifies with `ss` rather than trusting the configuration, because the verification is
  the part people skip.
- **The GPU advice counts the context window, not only the weights.** The first draft of
  the guide said 12 GB of VRAM holds a 14B model, which is true of the weights and false
  of the configuration LACC actually runs: the KV cache lives in VRAM too and a 32k window
  adds 3 GB at 8-bit, putting the total at 12.0 GB against roughly 11.5 usable. So 12 GB
  buys a choice - the same 7-8B model with headroom, or a 14B model over a shorter
  document - and 16 GB is the first size that holds both a 14B model and a full window.
  The corrected figures use the same formula `lacc profile` uses.
- **The hardware advice is ordered by memory bandwidth, not by processor.** Generating a
  token means reading the whole model out of memory once, so bandwidth sets the speed and
  cores mostly do not. That reordering matters commercially: a machine sold as "16 GB" may
  ship one memory stick and run at half the bandwidth of the same capacity as two, and
  nothing on the listing distinguishes them.
- **The verification counts are documented as an experiment.** Running the same document
  through `extract_claims` with different models and comparing how many quotations hold
  turns "is a bigger model worth it" into a measurement. This is the first use of the
  grounding check for something other than trusting a single answer.
- **v1.0 does not follow from this release, and the roadmap now says why.** Every
  capability on the v1 list is built, but the engine has never once reached another
  machine, a notification has never once been delivered, and the premise that a larger
  model produces publishable work has never been tested. Their logic is verified and their
  behaviour is unobserved - the same shape of gap ADR-019 was written to name. v1.0 is
  gated on a real run, not on a feature.


## [0.26.0] - 2026-09-09

### Added
- **A configured engine may run on another machine you own.** `engine_host` names where
  Ollama is, and `network_access: true` is the ceiling over it. A host that is not written
  down is never contacted; `OLLAMA_HOST` may still only ever point at this machine.
- **Notifications when a run finishes**, through a `Notifier` port with an ntfy adapter.
  Self-hosted ntfy only, reached over your own private network. Off by default.
- **`lacc notify test`** sends one notification, so settings are checked before they are
  relied on. Exits non-zero when nothing was delivered, so a script can check it.
- A `notifier` block in the configuration. It names the environment variables the server,
  topic and token are read from; it does not hold their values.
- Two audit events, `notification_sent` and `notification_failed`, recorded under the same
  run id as the run they report.

### Changed
- **PRINCIPLES no longer says a non-loopback host is out of scope.** Local means not
  depending on someone else's computer, not staying on one machine - which is what VISION
  already said. The rule that replaces it is narrower than "network access": every
  destination is named in a file the user wrote.
- **The configuration now wins over `OLLAMA_HOST`.** A file naming a stronger machine is a
  deliberate choice, and an ambient variable quietly sending the work back to this laptop
  would answer from a smaller model without saying so.

### Notes
- **A notification carries no document content.** It says which skill ran, how it ended and
  how long it took. Never a prompt, an answer, a path, or the text of anything read. The
  destination is a machine the user named, and that is still not a reason to send it work.
- **Delivery is best effort and never blocks.** A notifier that cannot be built or cannot
  reach its server does not fail a run that already succeeded; the failure is printed and
  recorded, and the answer stands.
- **The quality gate still forbids reaching the network.** Tests inject the transport, so
  the egress guard from ADR-022 is exactly as strict as it was: LACC gained the ability to
  reach out, and the suite still fails if anything does it by accident.
- Secrets are named, not written. A token in a configuration file is a token in a backup.
  There is no field that could hold the topic either: on a server without authentication the
  topic *is* the authentication, and a configuration that could hold it is one that ends up
  committed with it. Refusing the field beats warning about it - a warning that prevents
  nothing is the guard that gets ignored.
- **Notification titles are folded to ASCII, and the body is clipped on character
  boundaries.** An HTTP header is latin-1, so a title carrying an emoji raised
  `UnicodeEncodeError` - a `ValueError`, not an `OSError` - which would have sailed past the
  handler catching network failures and taken down a run that had already produced its
  answer. Accents fold rather than drop, so "Revisión lista" stays readable; a carriage
  return can no longer reach a header at all. Clipping the encoded body directly had the
  matching flaw: a body in Spanish ended on half an accented character and arrived as
  invalid UTF-8. Neither could be triggered by today's titles, all of which are ASCII
  literals - which is exactly the problem, since the guarantee would have held by accident.
- The ntfy server address is checked to be `http` or `https` before anything is posted to
  it. It arrives from the environment, and the environment is not a place to discover that
  LACC will post a body to an arbitrary scheme.
- Telegram is not implemented and will not be. It is a third party, and a message telling
  it that you are working, on what and when, is information about your research whatever
  the body says.


## [0.25.0] - 2026-09-09

### Added
- **`lacc run extract_claims <path>` returns what a source asserts, and LACC checks the
  quotations.** Each claim comes with the document's own words and a page; every quotation
  is then looked for in the source, and each claim is marked found, not in the document,
  or on a different page than claimed. Nothing is removed: an unverified claim stays in the
  answer and is marked, because the point is to show what the model did.
- A `grounding` module holding the parsing and the checking, both pure functions over text.

### Notes
- **This is the first control in LACC that does not ask a model to behave.** Every prompt
  saying "add nothing the document does not contain" is a request. This is a check: a
  quotation either appears in the source or it does not, and what verifies the model is not
  another model.
- **Matching is exact after collapsing whitespace and folding case, and deliberately not
  fuzzy.** A quotation that only nearly appears is not a quotation - "across four hospitals"
  for "across three hospitals" is precisely the error that must not pass. A false "not
  found" is visible and costs a glance; a false "verified" is the failure this exists to
  prevent.
- **Pages are checked too**, against the `<!-- page N -->` markers ingestion preserves
  (ADR-016). A real quotation attributed to the wrong page is reported as that, and the
  page it actually appears on is named. A source LACC did not ingest has no markers, and
  the page is then reported as unchecked rather than as wrong.
- The check bounds what can be trusted and does not extend it: a verified quotation proves
  the words are in the document, not that the claim built on them is sound. A model can
  quote accurately and reason badly, and only the first is caught here.
- A line-oriented format is asked for rather than JSON, because a small local model follows
  it far more reliably and a malformed block costs one claim instead of the whole answer.


## [0.24.0] - 2026-09-09

### Added
- `lacc run revise_file <path>` proposes a clearer version of a document and writes it
  beside the original, never over it. The run asks twice: the preview authorises reading
  and asking the model, and a second question shows the unified diff and decides whether
  the result is kept. Declining writes nothing and prints the revision.
- Every skill can be given several documents: `lacc run <skill> <path> [<path>...]`. Each
  is fenced separately, with its own name and its own content placeholder, so the model can
  attribute what it reads. `revise_file` requires exactly one and says so.

### Changed
- **Nothing LACC writes replaces a file that already exists.** Ingestion already refused to
  overwrite; that is now the rule everywhere.
- `IntendedAction` separates what an action reads from what it writes. `targets` meant both,
  which was ambiguous rather than merely imprecise: the revision path is checked against the
  boundary and shown in the preview, and must not be read - a file about to be created
  cannot be. Ingestion carried the same ambiguity without it ever surfacing.
- The preview shows `Reads:` and `Writes:` separately.
- `Skill.plan` takes a tuple of paths, and `SkillPlan` carries an optional destination. Both
  amend ADR-009 again, in the open.

### Notes
- **`revise_file` deliberately ignores `output_language`.** That setting governs what LACC
  says *about* your documents; a revision is the document itself, so asking for it in the
  configured language translated a Spanish passage into English instead of revising it.
  Found by reading a diff during a real run - which is precisely what the diff is for.
- A model told not to change what a passage claims may change it anyway. The diff is not a
  courtesy shown before writing; it is the control that makes an unreliable rewrite usable.


## [0.23.0] - 2026-09-09

### Added
- **A truncated prompt is detected and named.** When the engine reports a prompt whose
  token count reaches the configured window, it did not read all of the document and
  answered from the rest. `lacc run` says the answer is built on part of the document, and
  the trail records it.

### Changed
- Truncation and an underestimated prompt are now reported as the different things they
  are. Until now both were called an underestimate, which described one of them. A
  truncated prompt means the answer should not be trusted; an estimate that ran low means
  LACC's arithmetic was off on this text while the prompt still fitted, and the answer
  stands.

### Notes
- **This closes the gap ADR-019 left open, and closes it better than the check it
  deferred.** That gap was "LACC does not verify the window the engine granted". Measuring
  showed the symptom is visible without asking: a prompt sent to a 2048-token window came
  back reported as 2047 tokens, one short of the window, while the same prompt in an
  8192-token window reported its real size of 4230. Detecting the symptom also catches
  every other route to the same outcome, including a window honoured but too small.
- **The comparison is against the window, never against the estimate.** The naive test -
  "the engine counted far fewer tokens than we estimated, so it must have clipped" - was
  tried and is wrong: the estimate runs seven to eighteen per cent high by design, so a
  healthy run reports fewer tokens than estimated as a matter of course. The run that
  fitted would have been flagged by it.


## [0.22.0] - 2026-09-09

### Added
- **Every file LACC reads or converts is recorded with the SHA-256 of its contents**, at
  every audit level. A path is a name that outlives its contents: the chapter summarised on
  Tuesday and the chapter at that path today may share nothing. A digest says which
  document without keeping a copy of it, so `standard` stops trading away the ability to
  check. Prompts and completions are recorded by digest for the same reason.
- **The audit trail is hash-chained.** Each record folds in the digest of the record before
  it, so an edit or a deletion breaks the chain from that point on and becomes locatable
  rather than silent. The design is taken from this author's own NetGuard ADR-003 rather
  than invented again.
- **`lacc verify`** walks the chain and reports either that it holds or the first record
  where it does not. Verified by tampering: altering a record reports a break at record 3
  of 6; deleting one reports a break at record 4 of 5. Both exit non-zero.
- Records written before this release verify as unverifiable rather than as broken. A trail
  cannot vouch for what predates the mechanism, and saying so is the honest reading.

### Notes
- **What the chain claims is that silent tampering becomes detectable, and no more.** It
  catches modification by anything that does not know the file is a chain - an editor, a
  sync conflict, a careless script, a person removing an inconvenient line. It does not
  catch a deliberate, informed rewrite: whatever can write the file can recompute every
  digest from the point it changed. Closing that needs a signing key and somewhere to keep
  it, which is an operational story this project has repeatedly declined. Overstating the
  property would be worse than not having it, because a trail believed stronger than it is
  gets relied on where it should not be.
- Hashing is not configurable. An audit level that could switch off the integrity of the
  audit would be a setting whose only use is making the record less trustworthy.

### Changed
- Documentation that had fallen behind is brought up to date rather than left to drift:
  the book's contents page listed one decision record of twenty-three and marked chapters
  as finished at v0.0.1 though they are revised every phase, and the development chapter
  described a quality gate that is no longer the one that runs.


## [0.21.0] - 2026-09-09

### Security
- **The quality gate now fails if anything reaches for a non-loopback address.** "LACC
  does not use the network" was an assertion in a document; it is now a property the
  build enforces, so a dependency, a future feature or a careless import that reaches
  outward fails rather than shipping. Loopback stays allowed: talking to a local engine
  is inter-process communication, which PRINCIPLES treats as the one exception. Verified
  before adopting - the suite passes with the guard installed and nothing attempts to
  leave - and verified again by deliberately reaching out and watching it fail.
- **A workspace inside a git working tree is refused.** Everything LACC reads, converts
  and records there is one `git add -A` away from being committed and pushed. The
  repository's `.gitignore` covers the default workspace name and no workspace file has
  ever been committed - checked across the whole history - but it protects by name rather
  than by nature: a `workspace_root` pointing at `./thesis` would have been covered by
  nothing.
- **A workspace inside a folder that looks synchronised is reported as a suspicion.**
  A synchronising folder copies its contents to another computer, which is the thing LACC
  exists to avoid. Recognising one means matching folder names, so this warns and says it
  is guessing rather than refusing on a name.
- A dependency audit is recorded in ADR-022 rather than left to be redone: `pypdf`,
  `python-docx`, `rich`, `pydantic` and `pyyaml` contain no network imports at all;
  `psutil` imports socket to read interface information rather than to open connections;
  `lxml` has network-capable paths LACC does not travel.

### Added
- `workspace_in_repository` in the configuration: an acknowledgement, false by default,
  that lifts the refusal above. LACC cannot tell whether git ignores a path - answering
  that means running git, which it does not do - so it refuses what it can see and leaves
  the judgement to the person who can check.

### Changed
- **`config.example.yaml` no longer proposes a workspace inside the repository.** Shipping
  an example that puts private material in a git working tree was the shape of the hazard,
  not a detail of it.
- PRINCIPLES.md gains the distinction this release rests on: approximation is a tool for
  performance, never for exposure. Where being wrong costs time, an estimate that leans the
  safe way is good engineering. Where being wrong means private material left the machine,
  there is no safe lean - that failure is one-way, and nothing later recovers what has
  already gone.

### Notes
- This is a breaking change for anyone whose workspace sits inside a repository. That is
  deliberate: the safe cases lose one line of configuration, and the unsafe ones are the
  reason for the change.
- Checks that cannot be certain say so where they are shown. A strict refusal is only
  useful while its refusals are believable, and every confident-sounding guess spends that.


## [0.20.0] - 2026-09-09

### Added
- `lacc profile` reports what a context window costs: for each installed model that
  publishes its shape, the attention cache at a range of window sizes and what that totals
  with the model's weights, against the memory free at that moment, marked the way the
  existing fit table marks its rows.
- The report states its assumptions where it is shown, not only in the decision record.

### Notes
- **The cost comes from each model's own metadata, not from a measurement of one machine.**
  The attention cache is two caches across every layer for every attention head that has
  one, at the width of a head, and the engine publishes all of those numbers. Keys are
  matched by suffix rather than by architecture name, so nothing is tied to one model
  family. A model that does not publish enough is reported as unknown: unknown is a usable
  answer and a guessed one is not.
- **The overhead beyond the cache is an allowance, not a calibration.** Actual growth was
  about 1.4 times the computed cache on the one setup where it was measured - one model,
  one engine version, one machine. Baking that in as a constant is how a tool becomes
  accurate on the desk it was written at and wrong everywhere else. What is applied is a
  round one and a half, described as an allowance, erring toward reporting less headroom
  than the machine has. The measurement lives in ADR-021, where its weight can be judged,
  rather than in the code, where it would look like a fact.
- **The report is a range, not a recommendation.** A single suggested number would be
  easier to read and would hide the assumptions that produced it, which is how a value
  chosen for one machine ends up in someone else's configuration.
- Nothing sets `context_tokens`. Deriving it automatically would make it depend on whatever
  memory happened to be free when the tool last looked, changing behaviour between runs for
  reasons invisible in the configuration - the same reason the token ratio is not tuned
  automatically (ADR-020).
- The figures assume a 16-bit cache, the whole model resident in memory, and ordinary
  attention. Free memory is a snapshot: it moved from 5.3 GB to 3.1 GB within minutes of
  ordinary use on the machine this was written on.


## [0.19.0] - 2026-09-09

### Added
- Every provider call records the token estimate and the engine's own count side by side,
  so the trail can say whether the estimate was any good without anyone re-deriving it.
  `Completion` carries the engine's prompt and answer token counts and its stop reason,
  all optional; `MockProvider` leaves them unset.
- A new audit event when the engine's count exceeds the budget while the estimate did not.
  That is LACC letting through a prompt it should have refused, with the engine silently
  dropping part of it - the exact failure the ceiling exists to prevent - and it is named
  rather than left to be spotted by comparing two figures.
- A new audit event when the engine says the answer stopped for want of room rather than
  because the model had finished. An answer that ran out of room ends mid-thought and
  looks like an answer.
- `lacc run` reports both conditions, because each means the answer is not what it appears
  to be.

### Notes
- **The three-characters-per-token estimate now has evidence behind it, and it holds.**
  Measured against Ollama 0.30.7 with `qwen2.5:3b` on Spanish prose: the engine counted
  750 tokens where LACC estimated 800 - seven per cent high, in the safe direction. Four
  characters per token, the usual rule of thumb, would have estimated 600: a fifth low, in
  the direction that lets an oversized prompt through. On a longer document the estimate
  ran eighteen per cent high. The constant is unchanged.
- **LACC does not tune the ratio from what it measures, deliberately.** A constant that
  drifts on its own makes the ceiling depend on invisible past runs, and would loosen
  itself after a stretch of token-cheap text - exactly when the next document might not be.
  The evidence is recorded so a person can change the number deliberately, in one place.
- These signals arrive after the prompt was sent, so neither can prevent anything. They are
  recorded, and reported when they say something is wrong. Retrying or trimming on the
  strength of them would build behaviour on a number whose only job is to describe what
  already happened.


## [0.18.0] - 2026-09-09

### Added
- `context_tokens` in the configuration: the window to run the model with. LACC asks the
  engine for exactly this window, estimates the size of each assembled prompt, and refuses
  one that will not fit rather than letting the engine truncate it.
- `lacc profile` reports the context window each installed model supports, and says that
  the engine loads with a smaller default unless it is asked otherwise.
- New audit events: `prompt_measured`, recording the estimated size and requested window
  of every prompt, and `prompt_too_large` when a run is refused for exceeding the ceiling.

### Changed
- `OllamaProvider` sends `num_ctx` when a window is configured. The provider port is
  unchanged: the window is given at construction, where the model name already lives,
  because it describes how the engine is set up for a run rather than what is being asked
  of it. Generation parameters stay deferred, as ADR-013 left them.

### Security
- **A prompt too large for the model is refused, not truncated.** An engine given more
  than fits does not fail: Ollama drops what does not fit and answers from the rest, so a
  run that read the last third of a chapter returns a confident summary of the chapter,
  indistinguishable from one that read all of it.
- **The window LACC checks against is the window LACC asked for.** This was found by
  measuring rather than by reading documentation: against Ollama 0.30.7, `qwen2.5:3b`
  supports 32768 tokens and the engine loads it with 4096 unless told otherwise - a factor
  of eight, silently. An earlier draft of ADR-019 would have had the profiler report
  32768, the user configure 32768, and LACC conclude that a 20000-token prompt had room to
  spare while the engine discarded seven eighths of it. A ceiling checked against a window
  nobody is using is worse than no ceiling, because it looks like a check.

### Notes
- Token counts are estimated from characters at three per token, and are called estimates
  everywhere they appear. Three is deliberately low: it overestimates tokens, so LACC
  refuses slightly early. A prompt refused that would have fitted costs one line of
  configuration; a prompt truncated that should have been refused produces a plausible
  wrong answer nobody has reason to check.
- A quarter of the window, and never less than 512 tokens, is held back for the answer.
- With `context_tokens` unset, runs proceed and say so: the engine will use its own default
  and may truncate without either side noticing. The gap is real, and the notice is what
  keeps it from being invisible.
- Requests for 2048, 8192 and 32768 tokens were each honoured exactly. What an engine does
  when it cannot allocate the window it was asked for was not observed, and is not claimed.


## [0.17.0] - 2026-09-08

### Added
- `lacc run critique_file <path>`: a second read-only skill. It reads a draft and reports
  specific, locatable problems - claims made without support, gaps in an argument,
  passages that contradict each other, terms used before they are defined, conclusions
  that do not follow. The other direction from summarizing: not what a document says, but
  what it fails to establish.
- The critique prompt refuses three things on purpose. It does not rewrite, because
  producing replacement text is writing, a phase with its own safety requirement, and a
  read-only run must not return text that looks authoritative. It does not grade or open
  with what the draft does well, because a critique that hedges is one whose findings have
  to be looked for. And it is told to report nothing rather than invent something: a model
  asked for problems will supply problems, and an invented weakness costs more to check
  than a real one saves.

### Changed
- The document fence - the markers plus the instruction that what sits between them is
  material rather than a request - is now written in one place and used by both skills.
  It is a security mechanism, and two copies of one are two things free to drift with
  nothing to say which is right. What is shared stops there: each skill still writes its
  own framing and task.

### Notes
- **No skill registry, and the reason is recorded so the question is not reopened by
  counting skills.** The roadmap said a third skill would give the registry deferred in
  ADR-010 enough cases to take shape; that reasoning was wrong and ADR-018 corrects it.
  The CLI's mapping already answers what a registry is for. What a formal one adds is
  discovery - skills arriving from outside this source tree - and that is a question about
  trust, not about count: a skill LACC did not write is one whose declared capabilities
  are a claim rather than a fact.
- A critique from a small local model will be shallow. Judging whether an argument holds
  is outside what a three-billion-parameter model does well. The prompt is shaped as well
  as it can be; the rest is the engine, and this is the clearest argument yet for the
  stronger machine the roadmap already records.


## [0.16.0] - 2026-09-08

### Added
- `max_input_bytes` in the configuration, 32 MiB by default: the largest file LACC will
  read or convert. Checked before the file is opened, so an oversized document is refused
  with its name, its size and the limit, rather than discovered as a `MemoryError` from
  somewhere deep in the process. The ceiling is about this machine and not about the
  model - whether the text then fits the model's context is a different question, with a
  different answer, in a later phase.

### Changed
- **A refused run now exits 1.** It exited 0, so a script checking the exit code was told
  the work had succeeded when nothing ran. A declined run still exits 0: nothing failed
  there - the human was asked and said no, which is the system working, and conflating
  the two would make the exit code useless for telling them apart.

### Security
- The workspace refuses three path shapes that stayed inside the boundary while breaking
  the other promise it makes: that a path names a file you can find again.
  - **Windows device names** (`NUL`, `CON`, `COM1`, and the rest). Windows resolves them
    to devices whatever directory precedes them and whatever extension follows, so a
    converted document written to `NUL` is discarded while the run reports success.
  - **Alternate data streams** (`notes.md:hidden`), which no directory listing shows. What
    LACC does is meant to be visible; a write that cannot be seen contradicts that.
  - **Names ending in a dot or a space**, which Windows strips before resolving, so the
    file written is not the file that was named.

  None of the three escapes the workspace. They are refused because containment was never
  the only thing the boundary was for.


## [0.15.0] - 2026-09-08

### Added
- `lacc ingest <source> [destination]`: converts a PDF or `.docx` inside the workspace
  into a `.md` file inside the workspace, after preview and confirmation, recorded in the
  audit trail. Sources for real work arrive as PDF and Word while LACC reads only UTF-8
  text, so until now the material it exists to work on was unreadable.
- A `Converter` port with two implementations from the start - PDF via `pypdf`, `.docx`
  via `python-docx` - selected by file suffix. Conversion is an explicit step producing a
  file the user can open and correct, rather than a parse hidden inside a read.
- What is produced is extracted text, and is not called more than that: page boundaries
  are kept as `<!-- page N -->` and Word heading styles become headings, because both are
  recovered rather than invented, while tables are flattened to rows instead of dressed as
  Markdown tables that merged cells would break.
- A second entry point in the cycle, `run_conversion`, for a run that produces a file
  instead of an answer and never reaches a provider. The sequence every run shares -
  preview, refuse or ask, record - is factored into one place rather than written twice.
- New audit events `document_converted` and `ingestion_failed`.
- `permissions.grant`: the configuration-ceiling rule in one place, so an action that is
  not a skill can declare its capabilities without a second copy of the rule. `grant_for`
  becomes a thin reading of it.

### Security
- **A non-loopback engine address is refused.** `OLLAMA_HOST` was honoured without being
  checked, so a value set by an installer, a script or a mistake was enough to send
  documents to another machine while looking exactly like a normal run. PRINCIPLES puts a
  non-loopback host out of scope; until now that was a comment rather than a check. The
  profiler carried its own copy of the same code, so both paths were open - there is one
  now, and it refuses with a message explaining that a remote engine is a recorded
  direction which needs its own decision record before it exists.
- **A conversion must declare both of its effects before either happens.** The preview
  checks only the capabilities an action declares, so a conversion now requires
  `read_files` and `write_files` together and refuses an action that declares less. An
  undeclared effect is one nobody checked, and one the human was never shown before
  confirming.
- Ingestion never overwrites: the destination is opened for exclusive creation, so a `.md`
  the user already corrected by hand cannot be replaced by a fresh extraction.
- A `.docx` is untrusted XML. python-docx does not resolve external entities - verified
  against a document built to try - and a test pins that against a future change of
  parser.
- The trail records which document was converted, by which converter, to where, and how
  many characters resulted. Never the text: it is already a file the record names.

### Notes
- A scanned PDF with no text layer is reported as such, and nothing is written. Producing
  an empty file would turn a legible failure into a silent one. OCR is out of scope.
- PyMuPDF is deliberately not used: it is the most capable option and it is AGPL, which
  an MIT-licensed project cannot take on.
- Input still has no size ceiling, Windows device names and alternate data streams still
  pass the workspace boundary, and a refused run still exits 0. All three are decided in
  ADR-017 and implemented in the phase after this one.

### Dependencies
- Added `pypdf` (BSD-3) and `python-docx` (MIT); `lxml` (BSD-3) arrives with the latter.
  Licences were read from the installed packages rather than recalled. `lxml` is a
  compiled extension rather than pure Python, so `.docx` support depends on a wheel
  existing for the interpreter in use.


## [0.14.0] - 2026-09-02

### Added
- The `summarize_file` prompt is shaped rather than merely stated: it frames the task,
  names the language to answer in, asks for a concise and factual summary, and fences
  the document between markers so the model can tell instruction from material.
- `output_language` in the configuration, naming the language the model is asked to
  answer in. Defaults to `English` - small local models follow instructions and write
  more reliably in it - and is configurable because the right language depends on who
  reads the answer. A blank value is rejected at validation rather than falling back
  to whatever the model would have chosen.
- `Skill.plan` receives the configuration, so a skill can describe intent that depends
  on it. This amends the contract set in ADR-009 and does so deliberately: the plan
  stays pure, since reading a frozen, already validated `Config` is not a side effect.

### Security
- The prompt states that the fenced document is material to summarize, not a request
  addressed to the model. Text read from a file is treated as untrusted input.
- The markers are fixed strings holding no user-supplied text, so a crafted file name
  cannot forge a fence. A document that contains the closing marker verbatim does
  still end the fence early: that limitation is named in ADR-015 rather than left to
  be discovered. What bounds the damage is that nothing acts on the answer - it is
  text returned to a person who previewed and confirmed the run.

### Notes
- Prompt wording still lives in code. External, user-editable templates remain a later
  phase, now with real wording to generalize from rather than a guess.
- Generation parameters (temperature and the like) remain outside the provider
  contract, as ADR-013 left them: they shape an answer through the engine rather than
  through the prompt.


## [0.13.0] - 2026-09-02

### Added
- The execution cycle now reads the files an action declares, so `summarize_file`
  produces a real summary instead of naming a file it never opened. The read happens
  after the human confirms and before the provider is called: a declined action never
  touches a file, and the contents reach the prompt.
- `SkillPlan` carries a prompt *template* (`prompt_template`) instead of a finished
  prompt. The skill leaves a placeholder where file contents belong; the cycle fills
  it with what it read. A plan stays pure - it holds the hole, never the content.
- `ReadError`: a file that cannot be read (missing, locked, not UTF-8 text) fails with
  a clear, actionable message rather than a raw filesystem error, the same posture
  `ProviderError` takes. The CLI reports it and exits.
- New audit events `files_read` (which files were read) and `read_failed` (that a read
  failed, and why).

### Security
- Files are read only when the action declares `read_files`. The preview checks
  declared capabilities and the workspace boundary; an action that names targets
  without declaring the capability passes the preview but is still never read.
- File contents follow the existing privacy rule: they reach the audit trail only
  through the prompt, recorded under `audit_level: full` and omitted under `standard`.
  The `files_read` event records paths, never contents.

### Notes
- Prompt wording still lives in code. Configurable, user-edited templates are a later
  phase with their own questions; this release only splits template from filled prompt.
- Multiple targets are read and joined, but no skill declares more than one yet.
  Chunking and retrieval for files larger than the model's context come later.


## [0.12.0] - 2026-07-25

### Added
- `OllamaProvider`: a real provider that sends a prompt to a local Ollama instance
  (`/api/generate`, streaming off) and returns the completion, implementing the same
  provider port as the mock. Talking to local Ollama over loopback is not network
  access in the sense the configuration guards. Failures (engine unreachable, model
  not installed, timeout) are translated into clear, actionable messages.
- A `--provider` option on `lacc run` to choose between `ollama` (default) and
  `mock`, so runs can hit a live model or stay offline and deterministic.
- A `model` field in the configuration, naming the Ollama model to use. Empty by
  default: a missing model is a clear error, not a guessed default.
- A progress indicator while generating, noting that the first run loads the model
  into memory and may take longer.

### Notes
- Generation parameters (temperature, `think`, and so on) remain out of the provider
  contract, deferred until real use shows which are needed.
- Reading file contents into the prompt is still pending: the summarize skill names
  the file but does not yet read it, so a real model reports it lacks the content.
  That is a known next step, not a defect.


## [0.11.0] - 2026-07-20

### Added
- Profiler (`profiler`) and the `lacc profile` command: detects and reports what the
  machine offers - whether Ollama is present, which models are installed (with size
  and quantization), and hardware facts (architecture, processor, OS, CPU count,
  total memory, free disk, uptime). Reads and reports only; it never pulls a model
  or runs inference.
- A rough model-fit table computed by formula (weight is parameters times bit-width
  over eight) across common sizes and quantizations, marked fits / tight / too large,
  presented as an approximation to verify rather than a recommendation.
- Honest notes instead of guesses: that capacity assumes free memory, that exceeding
  it causes slow swapping, how to check free memory in real time, and that GPU/NPU
  accelerators may exist but be unusable (Ollama runs on CPU on Snapdragon).

### Dependencies
- Added psutil, used only to read total memory and boot time portably.


## [0.10.0] - 2026-07-20

### Changed
- Permissions granted to a skill now come from what the skill declares, limited by
  the configuration ceiling (`grant_for`), replacing the hardcoded `read_files`
  the CLI used as a stopgap. A skill receives exactly the capabilities it declares,
  minus any the configuration forbids - nothing more, nothing vetoed.


## [0.9.0] - 2026-07-21

### Added
- Command-line interface (`cli`): the `lacc` command, built with Typer and
  rendered with Rich, both confined to the CLI so the core stays free of interface
  code.
- `lacc run <skill> <request>` plans a skill, shows the preview, asks for
  confirmation (defaulting to no), and on an explicit yes executes and records it.
- `lacc preview <skill> <request>` shows what would happen without asking,
  executing, or recording.
- The `lacc` console script now points at the real CLI entry point, replacing the
  scaffold placeholder.

### Dependencies
- Added typer and rich, confined to the command-line interface.


## [0.8.0] - 2026-07-20

### Added
- Skills (`skill`): an abstract `Skill` contract mirroring the provider port. A
  skill declares its name and required capabilities and implements `plan`, which
  turns a request into an action and a prompt without side effects.
- `SummarizeFileSkill`: the first demonstration skill, read-only. It declares a
  `read_files` requirement and a target path inside the workspace, exercising the
  permission check and the boundary end to end.
- `run_skill`: wires a skill to the execution cycle, so a skill is always run
  through preview, permission check, confirmation, execution, and audit - never on
  its own.


## [0.7.0] - 2026-07-20

### Added
- Execution cycle (`cycle`): `run_action` drives an action through the whole
  system in order - preview, refuse or ask, execute, record - so callers describe
  what they want done without knowing how a run proceeds.
- Human confirmation is supplied as a function, not performed by the core, so the
  cycle works from a terminal, a test, or any future interface without containing
  interface code.
- Refused and declined runs are recorded, not just completed ones: the audit trail
  can answer whether something was ever attempted. New audit events `run_refused`
  and `confirmation_declined`.
- The first integration tests, exercising configuration, workspace, permissions,
  provider, preview, and audit together rather than in isolation.
- Continuous integration: the quality gate runs on every push via GitHub Actions.
- An example configuration file (`config.example.yaml`) with each option's
  consequence documented.


## [0.6.0] - 2026-07-19

### Added
- Execution preview (`preview`): describes what an action would do before it runs
  and whether it would be allowed, with no side effects - nothing is written, no
  provider is called.
- `IntendedAction`: a generic description (name, summary, required capabilities,
  target paths) that anything can produce, so the preview does not depend on skills.
- Previews report every refusal reason at once - missing capabilities and paths
  escaping the workspace boundary - and render a readable block for confirmation.


## [0.5.0] - 2026-07-19

### Added
- Audit log (`audit`): append-only JSON Lines records written inside the workspace,
  with the path resolved through the workspace boundary. Each event carries a UTC
  timestamp, the `run_id`, a closed-set event kind, a message, and optional detail.
- `audit_level` gains behavior: `standard` (the default) records metadata only,
  omitting prompt and completion content; `full` records content as an explicit
  opt-in.
- `audit_failure_policy` in the configuration: `abort` (the default) refuses to
  proceed when a record cannot be written; `continue` proceeds unrecorded. Each
  option documents its consequence.


## [0.4.0] - 2026-07-17

### Added
- Provider port (`provider`): an abstract `Provider` with a single operation
  (prompt in, `Completion` out) so the core never depends on a concrete engine.
  Completions carry the name of the provider that produced them, so results can be
  attributed in an audit record.
- `MockProvider`: a deterministic implementation that touches no network, model, or
  filesystem. Answers from caller-supplied scripted responses, or falls back to a
  predictable response derived from the prompt. Makes every later phase testable
  offline.


## [0.3.0] - 2026-07-17

### Added
- Permissions (`permissions`): a frozen contract with one capability per field
  (`read_files`, `write_files`, `network`, `run_commands`), all disabled by default
  so an empty `Permissions()` grants nothing.
- Configuration as a ceiling: `effective_permissions` intersects granted
  capabilities with what the configuration allows, so a capability the
  configuration forbids cannot be granted by a skill.
- `check` returns a `PermissionCheck` naming exactly which capabilities are
  missing, for execution previews; `require` raises `PermissionDenied` on the
  execution path.


## [0.2.0] - 2026-07-17

### Added
- Workspaces (`workspace`): a validated, frozen contract around a root directory
  with an enforced boundary. `is_within` and `resolve_within` resolve `..` and
  symlinks before checking, so paths cannot escape the workspace. Root creation is
  explicit via `ensure`, never a silent side effect of construction.
- `workspace_from_config`: builds an operational workspace from a configuration's
  `workspace_root`, the seam connecting config to workspace.


## [0.1.0] - 2026-07-17

### Added
- Initial project scaffold: installable package skeleton, packaging
  configuration, and quality gate tooling (linter, type checker, test runner).
- A smoke test that verifies the package imports and exposes a version.
- Documentation as a short book of numbered chapters: overview, architecture,
  roadmap, and development.
- MIT license.
- ADR-based documentation system: a book of numbered chapters plus decision
  records (`docs/adr/`), an index, and the guiding principle that every document
  is written from a real decision.
- Core configuration (`config`): a validated, frozen Pydantic contract
  (`network_access` off by default, `audit_level`, `workspace_root`) loadable
  from YAML, validated at the boundary.
- Run identity (`run`): a human-readable, time-ordered, unique `run_id` for each
  execution.
- Runtime dependencies: pydantic and pyyaml.