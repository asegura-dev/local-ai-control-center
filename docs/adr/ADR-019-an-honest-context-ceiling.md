# ADR-019 - An honest context ceiling: asking for the window, and refusing rather than being truncated

- **Status:** Accepted - implemented (v0.18.0)
- **Date:** 2026-09-09
- **Context:** A model has a context window, and a prompt longer than it does not fail.
  Ollama drops what does not fit and answers from the rest, so a run that read the last
  third of a chapter returns a confident summary of the chapter. Nothing in the exchange
  says so: the completion looks exactly like one that read everything. LACC has no way to
  notice this today.

  `max_input_bytes` (ADR-017) is a ceiling about memory, deliberately, and says nothing
  about what the model can hold. This is the other question, and it is the one that
  produces a wrong answer rather than a crash.

  The roadmap places this phase after reading several files. That order is reversed here:
  several documents in one prompt is precisely what makes a prompt long, so shipping that
  first would make silent truncation more likely before anything could detect it.

### What was measured

Written down because the design turns on it, and because the numbers are not what the
documentation of either project leads you to expect. Measured against Ollama 0.30.7 with
`qwen2.5:3b` on the machine LACC is being built on:

| | tokens |
|---|---|
| Window the model supports (`/api/show`) | 32768 |
| Window Ollama loads with when not told otherwise (`/api/ps`) | **4096** |
| Window Ollama loads with when `num_ctx` is requested | exactly what was asked |

A factor of eight, silently. Requests for 2048, 8192 and 32768 were each honoured exactly.
Memory scales with the window and is not free: the same model occupied 1990 MB loaded at
2048 tokens and 2300 MB at 8192.

## Decision

### 1. LACC asks for the window rather than inheriting whatever the engine defaults to

This is the decision the measurement forced. An earlier draft of this ADR had the
profiler report the model's maximum and the user configure that; against a default of
4096, LACC would have checked a prompt of 20000 tokens against a window of 32768,
concluded there was room to spare, and watched Ollama discard seven eighths of the
document. A ceiling that checks against a window nobody is using is worse than no ceiling,
because it looks like a check.

So the window LACC enforces is the window LACC asked for. `num_ctx` is sent with the
request, set from the configuration.

This does not open the provider port to generation parameters, which ADR-013 deferred and
which stay deferred. It does not touch the port at all: the window is a property of how
the engine is set up for a run, not of an individual prompt, so it is given to
`OllamaProvider` at construction, where the model name already lives. `complete(prompt)`
is unchanged, and the mock is untouched.

The distinction is worth stating, because "it is an option in the same request" makes them
look alike. `temperature` changes the character of an answer. `num_ctx` changes how much of
the document was read. One is a preference; the other is the difference between having
read the chapter and not.

### 2. The window is configured, not guessed

`context_tokens` is named in the configuration, exactly as `model` is. LACC does not infer
it or default it to a plausible number. Too small and it refuses work that would have run;
too large and the engine cannot allocate it. Both are the user's machine and the user's
call, and the value is verifiable rather than folkloric - see the next decision.

Unset means unknown, and unknown is not treated as unlimited (decision 6).

### 3. `lacc profile` reports both numbers, because reporting one causes the error

It reports what each installed model supports **and** what Ollama loads with when it is
not told otherwise. Reporting only the maximum is exactly what would lead someone to
configure 32768 and believe that is what is running.

Asking for a larger window costs memory, so the profiler says that too. It reports and
does not act, as ADR-012 requires: choosing what to spend memory on stays the user's.

### 4. The size of a prompt is estimated, and the estimate is deliberately pessimistic

LACC has no tokenizer and will not carry one per model family for a number that only
decides whether to refuse. Tokens are estimated from characters at three characters per
token.

Three is low on purpose. Four is the usual rule of thumb for English prose, and text with
accents, code or unusual words tokenizes worse. Estimating low means estimating more
tokens than there probably are, so LACC refuses slightly early. The two errors are not
symmetric: a prompt refused that would have fitted is visible and costs one line of
configuration, while a prompt truncated that should have been refused produces a plausible
wrong answer nobody has reason to check.

The window also has to hold the answer, so LACC compares its estimate against the window
less a reserve for the completion - a quarter of the window, at least 512 tokens - and
says what it reserved when it refuses.

### 5. Over the ceiling, the run is refused before the provider is called

The check happens in the cycle, once the prompt is assembled and before it is sent. The
run ends with a message naming the estimate, the budget, the reserve and the file, and the
refusal is recorded.

Nothing is truncated to fit. Truncating is the behaviour this ADR exists to stop, and
doing it in LACC rather than in Ollama would only move the dishonesty closer to home.
Splitting a document so that it does fit is the real answer and it is the next phase;
refusing clearly is what makes that phase's absence honest rather than hidden.

### 6. When the window is unknown, LACC says so rather than assuming either answer

With `context_tokens` unset, the run proceeds - refusing everything would turn an unset
option into a way to break LACC - but the estimated size is recorded, and the result
carries a note saying no ceiling is set, that the engine will use its own default, and
that a long prompt may be truncated without either of us noticing.

This is deliberately uncomfortable. The gap is real, and the note is what keeps it from
being invisible.

### 7. What LACC asked for is recorded; what the engine granted is not verified, and that is said

The audit records the requested window alongside the estimated prompt size. LACC does not
then re-query the engine to confirm the window it got.

Requests for 2048, 8192 and 32768 were each honoured exactly, so there is no observed case
of an engine quietly granting less. What happens when the machine cannot allocate the
requested window was not observed, and is therefore not claimed either way - a failure to
load would surface as a provider error, but a silent reduction would not, and this
document says so rather than implying it was checked. If it is ever seen, `/api/ps` reports
the granted window and is where verification would go.

## Trade-off

Sending `num_ctx` means LACC now decides something about how the engine runs, rather than
only what to send it. Accepted: the alternative is a ceiling enforced against a number the
engine is not using, which is the failure this ADR exists to prevent. The narrowness
matters - one value, set at construction, from configuration the user wrote.

Estimating tokens from characters is crude and will be wrong in both directions. Accepted:
a tokenizer per model family is a dependency and a maintenance burden for a number that
only decides whether to refuse. The ratio is stated, the estimate is labelled as an
estimate everywhere it appears, and it errs toward refusing.

Configuring the window puts work on the user that the engine could answer. Accepted, and
consistent with refusing to guess which model to run. The profiler closes the gap by
reporting both numbers, which is the part that makes the configured value a fact rather
than a guess.

Proceeding when the window is unknown leaves the original problem for anyone who does not
configure it. Accepted, with the note as the mitigation. A default window is the guess this
ADR refuses, and refusing to run without one would punish every existing user for a field
that did not exist yesterday.

## Consequences

- `context_tokens` in the configuration, unset by default, validated as positive when set.
- `OllamaProvider` takes the window at construction and sends it as `num_ctx`. The provider
  port is unchanged and the mock is untouched.
- `lacc profile` reports each model's maximum window, the window Ollama uses by default,
  and that a larger window costs memory.
- The cycle estimates the assembled prompt's size, compares it against the configured
  window less a reserve, and refuses over it rather than letting the engine truncate.
- New audit events record the estimated size and requested window of every prompt, and a
  refusal for exceeding the ceiling.
- With no ceiling configured, runs proceed and say that no ceiling is set.
- Chapter 1, the roadmap and the CHANGELOG are updated in this phase. The roadmap's
  ordering of this phase against reading several files is corrected there.
