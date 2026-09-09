# ADR-021 - Reporting what a context window costs, without pretending to know the machine

- **Status:** Accepted - implemented (v0.20.0)
- **Date:** 2026-09-09
- **Context:** `context_tokens` (ADR-019) is a number the user has to choose, and choosing
  it badly is easy in both directions. Too small and documents are refused that would have
  fitted. Too large and the engine cannot allocate the window, or allocates it by pushing
  the machine into swap, which does not fail so much as become unusable.

  The number depends on the machine as much as on the model, and the machine changes: free
  memory on the machine this was built on moved from 5.3 GB to 3.1 GB within minutes of
  ordinary use. A window that fits at one moment does not at another.

  The profiler already answers a question of this shape - it computes a rough model-fit
  table by formula and presents it as an approximation to verify (ADR-012). This extends
  that to the window, and the hazard is the same one the fit table was careful about:
  producing a confident number from a thin measurement.

## Decision

### 1. The report shows the arithmetic, not a verdict

Rather than naming a window the machine "can afford", the profiler reports what several
window sizes would cost for a given model, against the memory free right now. The reader
sees the shape of the trade and picks a point on it.

A single recommended number would be the more convenient output and the less honest one.
It hides which assumptions produced it, it goes stale the moment memory moves, and it
invites being copied without being understood - which is how a value chosen for one
machine ends up in someone else's configuration.

### 2. The cost comes from the model's own metadata, not from a measurement of one machine

The attention cache is what a window costs, and its size follows from the model's
architecture: two caches, one key and one value, across every layer, for every attention
head that has one, at the width of a head. The engine reports all of those numbers for
each installed model, so the arithmetic is the model's own rather than something fitted to
the machine that happened to be handy.

Keys are matched by suffix rather than by architecture name, because the metadata is
prefixed per architecture - `qwen2.block_count` here, something else elsewhere - and
hardcoding one family would be exactly the narrowness this decision exists to avoid. Where
a model does not publish what is needed, the cost is reported as unknown. Unknown is a
usable answer; a guessed one is not.

### 3. Overhead beyond the cache is an allowance, and is labelled as one

The cache is not the whole cost: the runtime allocates working buffers that also grow with
the window. On the one setup where this was measured, actual growth was about 1.4 times the
computed cache size.

That factor is not treated as a constant of nature. It is one observation, on one model,
one engine version and one machine, and baking it in as a calibration is precisely how a
tool becomes accurate on the desk it was written at and wrong everywhere else. What is
applied is a round allowance of one and a half, described as an allowance, chosen because
it errs toward reporting less headroom than the machine really has - the safe direction,
by the same asymmetry that governs the token estimate: a window reported as unaffordable
that would have worked costs a retry, while one reported as affordable that swaps the
machine costs the session.

The measured figure is recorded in this document, where a person can see how much evidence
the allowance rests on, rather than in the code, where it would look like a fact.

### 4. What would make this wrong is written down

A number produced by formula deserves to say when it does not apply. The report assumes:

- **A sixteen-bit cache.** Ollama can be told to quantize it, which roughly halves or
  quarters the cost, and then these figures are pessimistic by that factor.
- **The whole model resident in memory.** With part of it offloaded to a GPU, or a machine
  that pages, the arithmetic is about the wrong pool.
- **Ordinary attention.** Architectures that share or compress the cache differently - and
  models that vary attention across layers - do not follow this shape.
- **A snapshot of free memory.** It was 5.3 GB and then 3.1 GB within minutes on the
  machine this was written on. The number was true when printed and need not be true now.

These are limits of the estimate, not caveats added for decoration. A reader who knows the
assumptions can tell when the number applies to them, and that is the difference between a
useful approximation and a confident one.

### 5. LACC still does not choose

The profiler reports and does not act (ADR-012), and nothing here sets `context_tokens`.
Deriving it automatically would be the natural next step and is refused for the same reason
the token ratio is not tuned automatically (ADR-020): the value would then depend on the
memory that happened to be free when the tool last looked, changing behaviour between runs
for reasons invisible in the configuration. The number the user wrote down is the number
LACC uses.

## Trade-off

A table of window sizes is more to read than a single number, and some users want to be
told. Accepted: what they would be told is an approximation resting on four assumptions,
and a number that arrives without them is one nobody can tell is wrong.

Computing the cache from metadata means models that do not publish their shape get no
figure at all. Accepted, and preferred to a fallback estimate: a blank says "look this up"
while a wrong number says nothing at all until it has cost something.

The allowance is a fudge factor, and every fudge factor is somebody's machine. Accepted
narrowly, because it is stated, rounded away from the observation rather than fitted to it,
and points in the direction where being wrong is cheap.

## Consequences

- `lacc profile` reports, for each installed model that publishes the metadata, what the
  attention cache costs at a range of window sizes and what that totals with the model's
  weights, against free memory now, marked the way the existing fit table marks its rows.
- The report states its assumptions where it is shown, not only in this document.
- Models that do not publish enough metadata are reported as unknown rather than estimated.
- Nothing sets `context_tokens`. It stays a value the user writes, informed by a report
  that shows its own arithmetic.
- Chapter 1 and the CHANGELOG are updated in this phase.
