# ADR-029 - Ports and adapters, made visible in the layout

## Status

Accepted, with two deviations from what was proposed, recorded below.

## Context

LACC is already built as ports and adapters. There is a `Provider` port with an Ollama and
a mock implementation, a `Converter` port with PDF and Word implementations, and a
`Notifier` port with an ntfy implementation. The core holds no interface code, and the CLI
is the only thing that knows Typer and Rich exists.

None of that is visible in the file layout. Fifteen modules sit flat in one package, and
the seam the design is organised around - what the core decides, and what the world does -
has to be inferred by reading imports.

Mapping those imports turned up two things that are not cosmetic.

**`skill` depends on `cycle`.** `run_skill` lives in `skill.py` and calls into the
execution cycle, so the module holding the pure planning logic also holds orchestration and
therefore drags in everything the cycle touches. A skill's `plan` is meant to be pure and
provable in isolation; today its module is not.

**Each port shares a file with its adapters.** `provider.py` holds the `Provider` abstract
class, the mock, the Ollama client and the host-resolution policy. `converter.py` and
`notifier.py` have the same shape. The one boundary that most needs to be obvious is the
one thing the layout hides.

There is also a deadline. After v1.0, `from local_ai_control_center.cycle import run_action`
is public API and moving it is a breaking change. This is the last release where the
rearrangement costs nothing but the work.

## Decision

**Five directories, each with a meaning that can be stated in one line.**

```
src/local_ai_control_center/
    core/       the rules: what is allowed, what a plan is, what a claim check concludes
    ports/      the interfaces the core needs the world to satisfy
    adapters/   implementations of those ports, one file each
    system/     machine-facing code that is not behind a port
    cycle.py    the application service that composes them
    cli.py      the driving adapter
```

- **`core/`** - `config` contracts, `permissions`, `preview`, `skill`, `grounding`, `run`,
  `workspace`. Decides things. Depends on no adapter.
- **`ports/`** - `provider`, `converter`, `notifier`: the abstract class and the data
  contracts that cross it, and nothing else.
- **`adapters/`** - `ollama`, `mock`, `documents`, `ntfy`. Each implements a port.
- **`system/`** - `audit`, `configuration`, `profiler`. Touches the machine, is not behind
  a port, and says so by living somewhere else.

**`adapters/` and `system/` are separate because a port is not free.** The project's rule
is that an abstraction earns its place when there are two real implementations. Provider has
two, Converter has two, Notifier has ntfy and its test double. Audit, configuration and
profiling have one each, so they stay concrete. Putting them in a folder named `adapters`
would imply a port that does not exist and invite someone to add one for symmetry.

**`run_skill` moves out of `skill` and into `cycle`.** It is orchestration, and it belongs
where the other orchestration is. `core/skill.py` is then what it always claimed to be:
plans, and nothing that runs.

**`workspace` is in `core`, and that is a deliberate exception.** It calls `Path.resolve`,
so it is not free of the filesystem. But "nothing outside the workspace is touched" is a
rule in PRINCIPLES, not a service the core consumes, and resolving a path is how that rule
is *checked* rather than an effect it governs. Naming the exception is better than a
layering that quietly launders it.

**The public surface is `local_ai_control_center` itself.** The package re-exports what a
caller needs, so an importer names the project rather than its internal shape, and a later
rearrangement does not break them.

**No behaviour changes.** The 293 tests pass before and after, unchanged except for the
paths they import from. A restructure that also fixes something is a restructure whose
failures cannot be told apart from the fix.

## Consequences

- Five directories replace fifteen flat modules; roughly 73 import lines across 31 files
  are rewritten.
- `core/skill.py` becomes genuinely pure, and the `skill` to `cycle` edge disappears.
- Each port is readable on its own, without its implementations in the same file.
- A reader can tell what a module is allowed to do from where it sits, which matters
  because this project is meant to be cited and built on.
- The architecture chapter's "may be organised into subpackages" becomes what the code
  does, and stops being direction.
- A dependency test enforces the layering, so the arrangement is checked rather than
  merely described. Five directories that mean something are five directories somebody
  will eventually break; a layout in a document is a wish.

## What changed between proposing this and doing it

Two deviations, written down rather than quietly absorbed.

**`config` stays whole in `core` rather than splitting into a contract and a loader.** The
proposal put the loading in `system`. In practice `load_config` is thirty lines of
validation at the boundary, which is where ADR-001 says validation belongs, and splitting it
would have changed every import of `Config` twice for no gain anyone could point at.

**`content_slot` moved into `core.fence`, which the proposal did not anticipate.** It was in
the cycle, and `core.skill` imported it to leave a hole for each document - so removing
`run_skill` did *not* break the inversion, and `core` still reached for the cycle. The slot
is part of a prompt's shape, which is what the fence module is about, so it belongs there.
The inversion was only actually fixed once both moved.

That second one is the useful lesson: the dependency the ADR named was real, and it was not
the only one holding the two modules together. Measuring the graph again after each move is
what found it.

## Trade-off

This spends a release on structure while v1.0 is gated on an unexecuted run, which is the
same trade the roadmap's course correction warned about. Accepted for one reason that does
not generalise: after v1.0 it is a breaking change, and the window closes rather than
staying open at the same price.

Five directories for roughly three thousand lines is more ceremony than the size alone
justifies. Accepted because the audience is not only the author - the project is meant to
be cited in a thesis and built on by others, and the layout is the first thing a reader
sees.

The rejected alternative was to split only what hurts: separate the ports from their
adapters and move `run_skill`, leaving everything else flat. It fixes both real findings at
a fraction of the cost. It was rejected because it leaves the project halfway between two
layouts, and the next person to add a module would have no rule to follow.
