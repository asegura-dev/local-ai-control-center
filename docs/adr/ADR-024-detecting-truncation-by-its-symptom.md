# ADR-024 - Detecting truncation by its symptom, not by asking what was granted

- **Status:** Accepted - implemented (v0.23.0)
- **Date:** 2026-09-09
- **Context:** ADR-019 left a gap on purpose and said so: LACC records the context window it
  asks the engine for, and does not check what the engine actually granted. Requests for
  2048, 8192 and 32768 tokens had each been honoured exactly, and what an engine does when
  it cannot allocate the window was never observed, so nothing was claimed either way.

  The obvious way to close it is to ask - query the engine after a run and compare the
  loaded window against the requested one. Measuring first produced a better answer.

### What was measured

A prompt of 14800 characters, which LACC estimates at 4934 tokens, sent to `qwen2.5:3b`
with two different windows:

| Window requested | Window loaded | Tokens the engine reported |
|---|---|---|
| 2048 | 2048 | **2047** |
| 8192 | 8192 | 4230 |

The truncated run reports a prompt one token short of the window. The run that fitted
reports the prompt's real size - 4230 against an estimate of 4934, the estimate running
seventeen per cent high, as ADR-020 found it does.

## Decision

### 1. Truncation is detected by what the engine counted, not by what it granted

When the engine reports a prompt whose token count reaches the window, the prompt did not
fit and the answer was produced from part of it. That is the symptom, it arrives in a
response LACC already receives, and it needs no second call to a second endpoint.

Detecting the symptom is also the better question. A granted window smaller than the one
requested only matters because it truncates; checking the count catches that case and every
other route to the same outcome - a window honoured but too small, an engine that clips
differently, a future engine that does not report windows at all.

The gap ADR-019 named is closed by this, and closed better than the check it deferred.

### 2. The comparison is against the window, never against the estimate

A naive reading - "the engine counted far fewer tokens than we estimated, so it must have
clipped" - is wrong, and was tried. The estimate is deliberately seven to eighteen per cent
high (ADR-020), so a healthy run reports fewer tokens than estimated as a matter of course.
The run that fitted above would have been flagged by that test.

The signal is the window. A prompt that fits is processed whole and its count sits below
the window; a prompt that does not is clipped to it. A small tolerance covers engines that
reserve a token or two differently - the one measured here stops at exactly one short - and
a false positive means warning about a prompt that filled the window exactly, which is
worth saying anyway.

### 3. Truncation and an underestimate are reported as the different things they are

v0.19.0 already noticed when the engine's count exceeded the budget and called it an
underestimated prompt. That covers both cases and describes only one of them.

They are now distinguished, because the reader needs different things. A truncated prompt
means the answer was built on part of the document and should not be trusted. An estimate
that ran low means LACC's arithmetic was off on this text while the prompt still fitted -
worth knowing, and not a reason to distrust the answer.

## Trade-off

A tolerance is a number chosen from one observation, which is the shape of thing ADR-021
was careful about. Accepted, narrowly: it is a tolerance around an equality rather than a
factor scaling a quantity, being wrong costs a warning rather than a wrong answer, and the
value it guards against is the engine reserving a token, not a property of the machine.

Not asking the engine what it granted means LACC cannot report a window quietly reduced
until a prompt is large enough to hit it. Accepted: the reduction is only harmful when it
truncates, and that is exactly when this fires.

## Consequences

- The cycle reports a truncated prompt when the engine's count reaches the configured
  window, distinguishing it from an estimate that merely ran low.
- The audit records the two conditions as different events.
- ADR-019's deferred verification is closed without a second endpoint call, and this ADR
  supersedes its decision 7.
- Chapter 1 and the CHANGELOG are updated in this phase.
