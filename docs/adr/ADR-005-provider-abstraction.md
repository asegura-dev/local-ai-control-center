# ADR-005 - Provider abstraction and a deterministic mock

- **Status:** Accepted - implemented (v0.4.0)
- **Date:** 2026-07-17
- **Context:** LACC needs model output, but the core must not depend on any
  particular engine. Calling an engine directly would tie the project to it and
  make everything downstream untestable without that engine installed. This ADR
  defines the boundary between LACC and whatever produces model output, plus a
  deterministic implementation that runs offline so the rest of the system can be
  built and tested before any real engine exists.

## Decision

### 1. A provider is an abstract port

`Provider` is an abstract base class in a flat `provider` module, defining a single
operation: given a prompt, produce a completion. The core depends on this
abstraction, never on a concrete engine - the dependency direction of ADR-001,
applied to the most volatile edge of the system.

### 2. A minimal contract, deliberately

The operation takes a prompt and returns a `Completion`: the produced text plus the
name of the provider that produced it. Nothing else. Generation parameters
(temperature, model selection, token limits) are **not** part of this contract.

They belong to a real engine, and designing them now would mean guessing the shape
of an integration that does not exist yet. Extending an interface with optional
parameters later is cheap; unwinding a wrong abstraction is not. The provider name
travels with the completion because an audit record needs to say what produced a
result, not just what the result was.

### 3. A deterministic mock provider

`MockProvider` implements the port without touching the network, a model, or the
filesystem. It is deterministic: the same prompt always yields the same completion.
This is what makes every later phase - previews, skills, audit - testable with no
engine installed and no network access, honoring the local-first stance even in
development.

It answers in two ways:

- **Scripted.** A caller may supply prompt-to-response pairs, so a test can set up a
  concrete scenario and assert against a known answer.
- **Derived.** Any prompt without a scripted answer gets a predictable response
  derived from the prompt itself.

Both paths are deterministic. The scripted form covers "I need this exact
situation"; the derived form covers everything else without forcing a caller to
enumerate every possible prompt.

## Trade-off

A single-operation interface is less capable than one exposing generation
parameters, and a real engine will eventually need them. The alternative - designing
the full parameter surface now - was rejected because it would mean designing
against an imagined integration while the rest of the system is far less complete.
The interface is deliberately kept at the maturity level of the project around it.

Supporting both scripted and derived mock responses is slightly more surface than
either alone. It is accepted because the two serve different needs: precise test
scenarios and unforced defaults. Both remain deterministic, so neither introduces
the flakiness a random mock would.

## Consequences

- Later phases depend on `Provider`, never on a concrete engine, and can be
  developed and tested entirely offline against `MockProvider`.
- A future real engine (such as Ollama) arrives as another implementation of the
  same port, with its own ADR deciding how generation parameters enter.
- Completions carry their producer, so audit records can attribute a result.
- The core gains a fifth functional module, `provider`. Chapter 1 and the CHANGELOG
  are updated in this same phase.