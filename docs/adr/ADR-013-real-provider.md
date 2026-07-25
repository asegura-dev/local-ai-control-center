# ADR-013 - A real provider: talking to Ollama

- **Status:** Accepted - implemented (v0.12.0)
- **Date:** 2026-07-22
- **Context:** Everything so far runs against the deterministic mock. The provider
  port (ADR-005) was built so a real engine could arrive as a second implementation
  without changing the core, and the profiler (ADR-012) can now report what Ollama
  offers. This ADR adds that second implementation: a provider that sends a prompt
  to a local Ollama instance and returns its completion. It is the step that makes
  the loop run against a live model instead of a mock.

## Decision

### 1. A second implementation of the existing port

`OllamaProvider` implements the `Provider` port from ADR-005 - the same
`complete(prompt) -> Completion` the mock implements. The core, the cycle, and
skills are unchanged: they depend on the port, not on which provider is behind it.
The port designed against the mock as a real second case now pays off, absorbing a
real engine without a redesign.

### 2. Complete responses, not streaming, with a progress indicator

The provider requests a complete response (`"stream": false`) rather than streaming
tokens. This keeps the contract intact - one prompt in, one `Completion` out - and
keeps presentation out of the core: a streaming provider would have to print as it
generates, putting interface code where it does not belong. The cost is that a slow
generation would otherwise sit silent; the CLI covers this with a progress spinner
while it waits, and a note that large requests may take longer. Real token-by-token
streaming is a worthwhile future improvement, but it needs the port to grow a
streaming operation deliberately; it is not smuggled in here.

### 3. The model comes from configuration

The model name is not hardcoded. Configuration gains a `model` field, and the CLI
builds the `OllamaProvider` with it. A user sees what they have with `lacc profile`
and names one in their config. The provider carries no default model of its own: if
the config does not name one, that is a clear configuration error, not a silent
guess.

### 4. Talking to local Ollama is not network access the configuration guards

Like the profiler (ADR-012), the provider reaches Ollama over loopback
(`127.0.0.1:11434`, honoring `OLLAMA_HOST`). This is inter-process communication on
the machine, not access to an external network, so it does not fall under
`network_access`, which stays off by default. Requiring `network_access` to talk to
a local engine would make the core feature impossible while protecting nothing. A
non-loopback host would be genuine network access and belongs with the decision that
admits networked execution.

### 5. Failures are translated, not verified in advance

The provider does not check the engine's state before generating. It attempts the
request and translates any failure into a clear, actionable message: a refused
connection becomes "cannot reach Ollama - is it running?"; an unknown model becomes
"model X is not installed - pull it with `ollama pull X`"; a timeout says so. This
follows validate-at-the-boundary-then-trust, adjusted for an external, volatile
system: unlike a frozen `Config`, Ollama can change between a check and the call, so
a pre-check would not guarantee anything and would still require handling the failure
at generation time. Translating the real failure gives the same useful message
without the redundant request or the false guarantee. The CLI shows these messages in
red rather than a stack trace, and may point to `lacc profile`.

## Trade-off

Choosing complete responses over streaming trades a live typing effect for a simpler,
contract-preserving implementation. The spinner recovers most of the "it is working"
feeling at almost no cost, and streaming is left as a deliberate future step rather
than bolted on in a way that would push presentation into the core. The wait on a
large generation is real and acknowledged in a note.

Translating failures rather than verifying beforehand means a failure is learned at
generation time, not a moment earlier. That is accepted because a pre-check against an
external system is a snapshot that can be stale by the time the call runs, so it would
not remove the need to handle the failure anyway - it would only add a request. The
same helpful message is delivered either way.

Adding a `model` field with no default means a missing model is an error rather than a
guess. That is deliberate: guessing a model the user did not choose is exactly the
implicit behavior the project avoids.

## Consequences

- LACC runs end to end against a live local model: a skill's prompt reaches Ollama
  and its real completion flows back through the cycle, audited like any other run.
- The mock remains the provider for tests and offline development; the real provider
  is selected by the CLI when a run is meant to hit the engine.
- Configuration gains a `model` field.
- Generation parameters (temperature, `think`, and so on) are still not part of the
  contract; they remain a future decision, taken when real use shows which are needed.
- The core gains an `OllamaProvider` alongside the mock. Chapter 1 and the CHANGELOG
  are updated in this same phase.