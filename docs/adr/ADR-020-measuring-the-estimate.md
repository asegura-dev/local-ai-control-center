# ADR-020 - Measuring the estimate: recording what the engine actually counted

- **Status:** Accepted - implemented (v0.19.0)
- **Date:** 2026-09-09
- **Context:** v0.18.0 refuses a prompt it estimates will not fit, using three characters
  per token. The reasoning for that number was argued in ADR-019 and never shown, which
  left the ceiling resting on an assertion: if the ratio is wrong in the loose direction,
  LACC lets through a prompt the engine then truncates, and nothing says so.

  The engine has been answering this question all along. Ollama's response carries
  `prompt_eval_count` - how many tokens it actually processed - and `done_reason`, which
  says whether the answer stopped because the model finished or because it ran out of
  room. LACC reads neither and throws both away.

### What was measured

Against Ollama 0.30.7 with `qwen2.5:3b`, on Spanish prose of 2400 characters:

| | tokens | against the real count |
|---|---|---|
| Reported by the engine | 750 | - |
| Estimated at three characters per token | 800 | 1.07x |
| Estimated at four | 600 | 0.80x |

The real ratio was 3.20 characters per token. Three was the right choice, and four would
have underestimated by a fifth - in the direction that lets an oversized prompt through.
The decision was sound; it just had no evidence behind it until now.

## Decision

### 1. A completion carries what the engine reported about producing it

`Completion` gains three optional fields: the tokens the engine counted in the prompt, the
tokens it produced, and why it stopped. Unset when a provider does not report them, which
is what the mock does.

This grows the port ADR-005 keeps deliberately minimal, so the line matters. What is being
added is not a control - nothing here changes what the engine does, and generation
parameters stay deferred as ADR-013 left them. It is the engine's account of what already
happened, and it is the only route by which LACC's own estimate can ever be checked. A
port that can ask a question but not hear the answer is minimal in the wrong place.

### 2. The estimate and the measurement are recorded together

Every provider call records both, so the trail can answer whether the estimate was any
good without anyone re-deriving it from characters. The numbers are metadata about a run,
not its content, so they are recorded at `standard` alongside the provider's name.

### 3. LACC does not tune the ratio from what it measures

The obvious next step is to learn the ratio from history and adjust. It is refused.

A constant that drifts on its own makes the ceiling's behaviour depend on invisible past
runs: the same prompt refused today and accepted tomorrow, for reasons no one can see in
the configuration. Worse, the adjustment would move in the dangerous direction on its own
- a run of unusually token-cheap text would loosen the check exactly when the next
document might not be. The number stays a stated constant, and the evidence is recorded so
a person can change it deliberately, in one place, with a reason.

### 4. An underestimate is named, not left in the numbers

When the engine's count exceeds the budget while the estimate did not, LACC allowed a
prompt it should have refused, and the engine silently dropped part of it. That is the
exact failure the ceiling exists to prevent, and it is recorded as its own event rather
than left to be spotted by comparing two figures in a trail nobody reads.

The run cannot be undone - by the time the count comes back, the answer already exists -
so the answer is reported as suspect rather than withheld. Telling the user the reply may
be based on a truncated document is the whole of what can honestly be done at that point.

### 5. An answer cut short is reported too

`done_reason` says whether the model stopped because it was finished or because it hit the
room left for it. An answer that ran out of room ends mid-thought and looks like an answer:
same class of dishonesty, at the other end of the exchange, and free in the same payload.
When the engine says the answer was cut short, LACC says so.

### 6. Measurement changes nothing about the run that produced it

It arrives after the prompt was sent, so it cannot gate anything. It is recorded, and
surfaced when it says something is wrong. Pretending otherwise - retrying, trimming,
re-asking - would build behaviour on top of a number whose only job is to tell the truth
about what already happened.

## Trade-off

Extending `Completion` widens a contract that has been three fields since v0.4.0. Accepted:
the fields are optional, the mock ignores them, and the alternative is a ceiling that can
never be checked against reality. The narrowness is the safeguard - facts about a call that
has already happened, never inputs to the next one.

Recording an estimate next to a measurement invites someone to close the loop
automatically, and decision 3 says not to. That tension is real and is left standing on
purpose: the value of the evidence is that a person reads it, and an automatic adjustment
would remove the person while making the check less predictable.

Reporting a suspect answer after the fact is weaker than refusing beforehand, and it will
feel like a warning that arrives too late. Accepted, because it is the truth: the
alternative is to withhold an answer the user already paid for while still being unable to
produce a better one.

## Consequences

- `Completion` carries the engine's prompt and answer token counts and its stop reason,
  all optional; `MockProvider` leaves them unset.
- `OllamaProvider` reads `prompt_eval_count`, `eval_count` and `done_reason` from the
  response it already receives.
- Every `provider_called` record carries the estimate and the measurement side by side.
- A new event records an underestimated prompt, and another records an answer cut short;
  the CLI reports both, because each means the answer is not what it appears to be.
- The three-characters-per-token constant is unchanged and still stated in one place. It
  now has a measurement behind it in the documentation rather than an argument alone.
- Chapter 1 and the CHANGELOG are updated in this phase.
