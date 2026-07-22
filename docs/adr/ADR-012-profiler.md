# ADR-012 - Profiler: detect and report, never assume, never act

- **Status:** Accepted - implemented (v0.11.0)
- **Date:** 2026-07-20
- **Context:** Before a real provider can choose a model, something has to report
  what the machine offers: whether an inference engine is present, which models are
  installed, and what the hardware is. This ADR defines a profiler that reads and
  reports only. It does not download models, change settings, or run inference -
  those are actions, and actions belong behind the control the rest of LACC
  provides. The profiler answers "what is here?", nothing more. It targets one
  engine, Ollama, deliberately: it is the engine this project uses, and a genuinely
  engine-agnostic detector cannot be designed well against a single case. Supporting
  other engines is future work, taken up when a second real engine exists to shape
  the abstraction.

## Decision

### 1. Detection only, no side effects

The profiler reads and reports. It never pulls a model, starts the engine, or
writes anything. Pulling a missing model is an action with large effects
(gigabytes, time) and belongs behind explicit, confirmed control like every other
action - not as a silent consequence of asking what is installed. This keeps the
profiler safe to run anytime and simple to test.

### 2. Suggesting a pull command is reporting; running it is not

When the engine is present but a needed model is absent, the profiler may report
the command a user could run to fetch one (for example, `ollama pull llama3.2`).
Showing that text is reporting - it has no effect. Running it is an action with
large effects and stays out of the profiler: a real model pull, when it exists,
goes through the same controlled path as any other action, with its own decision.
The profiler points the way; it does not walk it.

### 3. Engine detection by probing, failing gracefully

To detect Ollama, the profiler probes its HTTP API (`/api/tags`) with a short
timeout, using the standard library (`urllib`) rather than adding an HTTP
dependency. A 200 means the engine is present; a refused connection, timeout, or
error means it is treated as absent. Absence is a normal, reported state, never an
exception that stops anything. The address honors the `OLLAMA_HOST` environment
variable that Ollama itself uses, defaulting to `127.0.0.1:11434`.

### 3b. Ollama-specific by choice, not by accident

The profiler detects Ollama specifically: it probes Ollama's endpoint, parses
Ollama's response shape, and suggests Ollama's commands. This is a deliberate choice,
not an oversight. Abstracting "detect any engine" now would mean inventing the shape
that engines have in common while knowing only one, which tends to produce the wrong
abstraction. When a second engine is actually used, the detection can be generalized
against two real cases. Until then, the profiler is honestly Ollama-specific, and the
provider port (ADR-005) - which is genuinely engine-agnostic because the mock was a
real second case from the start - remains the seam where engine independence lives.

### 4. Probing localhost is not network access in the sense the configuration guards

LACC keeps `network_access` off by default, meaning it does not reach out to the
network. Probing the local inference engine on `127.0.0.1` does not cross that line:
the traffic never leaves the machine - it is inter-process communication over a
loopback address, not access to any external network. The profiler therefore probes
the local engine regardless of `network_access`, and this ADR states that
explicitly so it is understood as a deliberate boundary, not a gap in the promise. A
non-loopback `OLLAMA_HOST` - an engine on another machine - would be genuine network
access and is out of scope here; if that is ever supported, it belongs with the
same decision that admits networked execution.

### 5. Installed models come from the engine, not a hardcoded list

When the engine responds, the profiler parses `/api/tags` and reports each model
with the detail Ollama provides: name, size, and quantization. The list is never
embedded in LACC's code - a baked-in model list ages the moment a model is released
or removed. The engine is the authority on what is installed; the profiler only
relays it.

### 6. Hardware: report what is reliably knowable, be honest about the rest

The profiler reports what it can determine portably and truly: CPU architecture
(ARM vs x86, via `platform`), a processor name when the platform gives a useful one,
the operating system, CPU count, total memory, free disk space, and system uptime.
It reports total memory rather than momentary free memory: the free figure changes
second to second and would give false precision, so the profiler states the total,
advises ensuring enough is free, and points to the OS tool for checking in real time.
Uptime is reported because a long-running machine benefits from a restart, which
frees fragmented memory. Architecture matters because it changes the arithmetic -
unified-memory ARM machines share one pool between CPU and any accelerator, unlike a
discrete GPU with its own memory.

It deliberately does **not** claim usable GPU or NPU acceleration. On some platforms
an accelerator exists but the engine cannot use it - a Snapdragon's Adreno GPU and
NPU, which Ollama does not target, running everything on CPU, for example - so "an
accelerator is present" does not mean "it accelerates here". Rather than report a
capability that misleads, the profiler notes honestly that accelerators may exist but
may be unusable, and tells the user to check how their engine reports it runs. What it
cannot determine, it says it cannot determine.

### 7. Capacity guidance is a formula over fixed sizes, not a catalog

The profiler turns hardware facts into rough guidance: for a fixed set of common
model sizes (1, 3, 8, 14, 32 billion parameters) at a fixed set of quantization
widths (3, 4, 8 bits), it computes each model's approximate weight - parameters times
bit-width over eight, in gigabytes - and marks whether it fits the memory left after
reserving some for the system: "fits", "tight" near the limit, or "too_large". Sizes
and bit widths are physical quantities, not a product list, so they do not age the way
model names do.

It is presented as an approximation to verify, never a promise. The guidance is paired
with reminders that the memory must actually be free, that exceeding it forces slow
disk swapping rather than crashing, and how to check free memory in real time. A
machine with 16 GB may still run a 6.5 GB model slowly if much of that is in use. The
formula stays correct as models come and go, because it describes physics, not
products.

### 8. Which model to choose is the user's call, not the profiler's

The profiler computes how much a machine can run; it does not say which model is
"best". That judgment changes constantly and depends on the task and on personal
preference, so it is neither frozen in code nor asserted by the profiler. General
orientation - that established families from large labs (Phi, Qwen, Llama, Gemma,
Mistral) are reasonable starting points, with specific versions changing over time -
lives in the documentation as human advice a reader can weigh, not as program logic
or profiler output. The profiler reports facts; the person chooses.

### 9. Exposed through a read-only CLI command

The profiler is invoked with `lacc profile`, which prints the report - engine
presence, installed models, hardware facts, and the model-fit table - rendered with
Rich. Like the profiler itself, the command only reads and reports: it takes no
confirmation because it does nothing to confirm. How a future real provider consumes
a `SystemProfile` to select a model is deliberately left open here; that is the
provider's decision to make, and closing it now would be guessing ahead of it.

## Trade-off

Refusing to report usable GPU/NPU acceleration makes the profiler less immediately
impressive than one that prints "GPU detected". That is the point: a confident wrong
answer about acceleration is worse than an honest "may not be usable", because it
leads to choosing a model the machine runs slowly. The raw facts are less flashy and
more trustworthy.

Using `urllib` instead of a friendlier HTTP client is a little more verbose per
request. It is accepted to avoid a dependency for what amounts to one GET with a
timeout. Memory and uptime facts are the exception: `psutil` is added solely to read
total memory and boot time portably, because doing so across Windows, macOS, and Linux
otherwise means OS-specific code paths (including a fragile `ctypes` call on Windows)
for a couple of numbers. A small, well-maintained dependency is the better trade for
facts central to the report; everything else - architecture, OS, CPU count, disk,
engine probing - stays on the standard library.

Reporting total rather than free memory trades momentary precision for honesty and
portability: a free figure would be stale the instant it is read. Total memory, plus
the advice to free some and the pointer to a real-time tool, is stable and does not
pretend to a precision it cannot keep.

Giving guidance by formula over fixed sizes rather than recommending named models
means the profiler orients without ever telling the user what to install. The
alternative - embedding recommendations, whether named models or a leaderboard link -
was rejected: named models age, and even a maintained external list makes the profiler
assert a judgment. Data the machine produces plus advice kept in prose, clearly marked
as changeable, keeps the tool honest and the choice with the person.

Targeting Ollama specifically, rather than abstracting engine detection now, risks
rework when a second engine arrives. That is accepted: an abstraction built against
one case tends to be the wrong one, and the provider port already carries genuine
engine independence. The profiler stays honestly specific until a second real engine
can shape a correct abstraction.

## Consequences

- A real provider (the next phase) can select a model informed by what is actually
  installed and what the machine is, rather than guessing; how it consumes the
  profile is that phase's decision.
- Pulling models remains a separate, controlled action, not something the profiler
  does.
- The profiler adds one runtime dependency, `psutil`, used only to read total memory
  and boot time portably; everything else uses the standard library.
- The profiler is Ollama-specific for now; generalizing engine detection waits for
  a second real engine, so the abstraction is shaped by two cases, not guessed from
  one.
- `lacc profile` joins `run` and `preview` as a read-only command.
- The core gains a `profiler` module. Chapter 1 and the CHANGELOG are updated in
  this same phase.