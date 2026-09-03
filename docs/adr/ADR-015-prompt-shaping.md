# ADR-015 - Shaping the prompt: instructions, output language, and untrusted content

- **Status:** Accepted - implemented (v0.14.0)
- **Date:** 2026-09-02
- **Context:** v0.13.0 made a file's contents reach the model, but the prompt around
  them is a single line: "Summarize the contents of the file at `<path>`." It gives the
  model no role, no output language, and no boundary between the instruction and the
  document. A small local model answers worse for the missing framing, and - more
  seriously - a document whose text happens to read as an instruction is
  indistinguishable from the request itself. This ADR shapes the prompt: what LACC
  tells the model, in which language, and how the document is fenced off as material
  rather than as a request.

## Decision

### 1. The document is delimited, and declared to be data

The file's contents are wrapped in explicit begin/end markers, and the instruction
above them states that the delimited text is material to summarize, not a request
addressed to the model. Files inside the workspace are the user's, but they are not
therefore trusted input: content read from disk enters the prompt the same way a
network response would, and a summary is not a reason to obey it.

This is a mitigation, not a guarantee. A model can still be argued out of an
instruction, and LACC does not claim otherwise. What makes the residual risk
acceptable is the rest of the design: the model's answer is text returned to a person,
nothing in LACC acts on it, no skill chains from it, and every run was previewed and
confirmed before it began. The fence lowers the odds; the human in the middle is what
bounds the damage.

One weakness is worth naming here rather than leaving to be discovered: the markers
are fixed strings, so a document that contains the closing marker verbatim ends the
fence early, and whatever follows it in the file reads as though it came from LACC
rather than from the document. Closing that needs an unguessable per-run delimiter,
which makes the prompt differ on every run. That changes how prompts are built rather
than how they are worded, so it belongs to its own decision if real use shows it is
needed. Until then the fence is described for what it is: it separates document from
instruction for documents that are not trying to escape.

### 2. The output language is configured, and defaults to English

The prompt names the language the answer must be written in, rather than leaving it to
the model. English is the default because small local models follow instructions and
write more reliably in English than in the languages they were less trained on - a
practical property of the models LACC targets, not a preference about users.

It is a configured default rather than a fixed string, because the right language
depends on who reads the answer. `Config` gains `output_language`, defaulting to
`English` and rejecting an empty value: a blank language is a clear error, not a
silent fallback to whatever the model chooses.

No `--language` option is added to the CLI. `--provider` exists because choosing the
mock or a real engine is a per-run decision; the output language is a standing
preference, and it belongs where `model` and `audit_level` already live. One setting
should have one home.

### 3. The skill's plan receives the configuration

`plan` grows a parameter: `plan(request, config)`. A skill's description of intent
legitimately depends on configuration - the language it asks for is part of what it
intends to do - and the skill has no other way to learn it.

This amends the contract fixed in ADR-009, and does so deliberately rather than
quietly. What ADR-009 actually protects is purity: a plan describes and touches
nothing. Reading a frozen, already-validated `Config` is not a side effect, so the
plan stays as pure and as safe to preview as before.

The rejected alternative was a second placeholder - `<<output_language>>` - for the
cycle to fill the way it fills file contents. It looks consistent, but it would turn
a single, purpose-built hole for file content into a general template-variable
system, which is precisely the configurable-templates phase ADR-014 deferred along
with its open questions. A phase should not arrive through the back door of another
one's mechanism.

### 4. Prompt wording stays in code

The text LACC sends is written in the skill, not loaded from a user-editable file.
ADR-014 deferred external templates with their own questions - where the file lives,
how variables are validated, what happens when one is missing - and this ADR does not
open them. Shaping the prompt well in code is what reveals which parts genuinely vary;
that experience is the input to designing an external format, not a substitute for it.

### 5. No prompt-building abstraction

There is one skill and one prompt. A shared prompt builder, a fragment library, or a
`PromptTemplate` type would be an abstraction guessed from a single case, and the
project does not introduce those (PRINCIPLES.md). The wording lives in
`SummarizeFileSkill` until a second skill exists to give a shared shape its form.

### 6. Tests assert the prompt's structure, never the answer's quality

Tests verify what is verifiable: the prompt carries the configured language, the
contents sit between the delimiters, the instruction to treat the document as data is
present. They do not assert that the summary is good. Whether a model writes a good
summary is not a property LACC can test - it depends on the model, and asserting on it
would produce tests that pass or fail for reasons outside the code. Saying so is more
honest than a test that pretends to measure it.

## Trade-off

Naming the output language in configuration adds a field for what could have been a
fixed string. Accepted: the answer's language is the one part of the shaping that
depends on the reader rather than on the model, and a default that can be changed
costs one field, while a hardcoded language costs a fork for anyone who needs another.

Extending `plan` changes an established contract, and every skill and every call site
changes with it. Accepted: the alternative kept the signature at the price of building
the deferred template system early, and a contract that is amended openly in an ADR is
healthier than one worked around.

Ollama's API offers a separate `system` field, which is where role framing
conventionally belongs. It is not used: `Provider.complete(prompt)` is deliberately
minimal (ADR-005), and growing the port for one skill's framing would shape the
abstraction from a single case. The framing goes into the prompt string instead. If a
second real provider or a second skill shows the port genuinely needs it, that is its
own decision.

Generation parameters (temperature, `think`, and so on) remain outside the provider
contract, as ADR-013 left them. They shape an answer too, but through the engine
rather than the prompt, and mixing both in one phase would make it unclear which
change produced which improvement.

## Consequences

- `summarize_file` sends a shaped prompt: a role, an explicit output language, a
  factual-and-concise instruction, and the document fenced between markers.
- Text read from a file is treated as untrusted input, and the prompt says so.
- `Config` gains `output_language` (default `English`, empty rejected), documented in
  `config.example.yaml` like every other option.
- `Skill.plan` takes the configuration; ADR-009's contract is amended, its purity rule
  untouched.
- Prompt wording is still in code. External, user-editable templates remain a later
  phase, now with real wording to generalize from.
- Chapter 1 and the CHANGELOG are updated in this phase.
