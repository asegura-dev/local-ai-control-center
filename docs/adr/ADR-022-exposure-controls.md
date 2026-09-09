# ADR-022 - Exposure controls: where approximation stops being acceptable

- **Status:** Accepted - implemented (v0.21.0)
- **Date:** 2026-09-09
- **Context:** LACC exists so that private work can be done with a model without the work
  leaving the machine. Several recent decisions accepted approximation deliberately - a
  token estimate that errs high, a memory allowance rounded away from one observation -
  on the reasoning that being wrong costs a retry.

  That reasoning does not transfer. A retry undoes a refused prompt; nothing undoes a
  document that left the machine. The two kinds of decision have been treated with the
  same tone, and this ADR separates them, then applies the stricter one to the places
  where exposure is actually possible.

  It starts from a finding. The repository's `.gitignore` covers `/lacc-workspace/` and
  `*.jsonl`, and no workspace file has ever been committed - verified across the whole
  history. But it protects by name, not by nature: a `workspace_root` pointing at
  `./thesis` inside the working tree would be covered by nothing, and a routine
  `git add -A` would publish it. `config.example.yaml` proposes a workspace inside the
  repository, so the shipped default is the shape that has this hazard.

## Decision

### 1. Approximation is a tool for performance, not for exposure

Stated as a principle rather than left implicit in individual choices. Where being wrong
costs time, an estimate that leans the safe way is good engineering. Where being wrong
means private material left the machine, there is no safe lean and no acceptable margin:
the failure is one-way and no later correctness recovers it.

This is why the controls below refuse rather than warn wherever refusing is possible, and
say plainly when a check is a heuristic rather than dressing it up as certainty.

### 2. The gate fails if anything reaches for a non-loopback address

"LACC does not use the network" has been an assertion in a document. It becomes a property
the quality gate enforces: the test suite installs a guard that raises on any connection to
an address that is not loopback, so a dependency, a future feature or a careless import
that reaches outward fails the build rather than shipping.

Verified before adopting: the whole suite passes with the guard installed, and nothing
attempts to leave. It begins green, which means it can only ever report a regression.

The dependencies were audited alongside it. `pypdf`, `python-docx`, `rich`, `pydantic` and
`pyyaml` contain no network imports at all. `psutil` imports socket to *read* interface
information, not to open connections. `lxml` has network-capable paths that LACC does not
travel - python-docx parses with entity resolution and network access disabled, which
ADR-017 verified separately. The guard is what keeps that true rather than merely true
today.

### 3. A workspace inside a git working tree is refused

Not warned about. A warning is read once and dismissed; the risk it describes stays for
the life of the project, and it is realised by a command people run without thinking.

LACC cannot tell whether a given path is ignored - answering that requires running `git`,
which is a capability LACC does not grant itself, and guessing at `.gitignore` semantics
would be exactly the kind of approximate check decision 1 rules out here. So it detects
what it can know for certain - a `.git` directory in some ancestor - and refuses.

The refusal is overridable by an explicit configuration field, because the situation is
sometimes genuinely safe and the user is the one who can confirm it. Setting it is an
acknowledgement with a name, sitting in a file, rather than a prompt clicked through.
`config.example.yaml` stops proposing a workspace inside the repository.

### 4. A workspace inside a folder that appears to sync is reported as a suspicion

A synchronising folder copies its contents to somebody else's computer, which is the thing
LACC exists to avoid. But recognising one means matching path names - OneDrive, Dropbox,
iCloud - and that is a guess: a folder named `Dropbox` may sync nothing, and a folder
named `work` may sync everything.

So this one warns, and says it is guessing. Refusing on a name would refuse work that was
never at risk, and would teach the user that LACC's refusals are noise - which is the way
to make decision 3 stop working too.

### 5. What is guessed says it is guessing

Across all of these, a check that cannot be certain names its own limit where it is shown,
not only in a decision record. The value of a strict refusal comes from its refusals being
believable, and every confident-sounding guess spends that.

## Trade-off

Refusing a workspace inside a repository breaks a configuration that works today, including
the example the project ships. Accepted, and the disruption is the point: the safe cases
lose one line of configuration, and the unsafe ones are the reason for the change. Shipping
an example that puts private material in a git working tree is worse than a migration.

The egress guard binds the test suite rather than the running program, so it constrains
what LACC is built to do rather than what it does on a user's machine. Accepted: a runtime
guard would be a second implementation of a boundary the operating system already owns, and
the failure being defended against is a change to this code, which is exactly what a gate
sees first.

A path-name heuristic will miss synchronising folders and will flag ordinary ones. Accepted,
because it is labelled as a guess, and because the alternative - asking the operating system
what is syncing - is a per-platform investigation for a warning.

## Consequences

- The quality gate fails if any test attempts a connection to a non-loopback address.
- A dependency audit is recorded here rather than left to be redone.
- `workspace_from_config` refuses a workspace inside a git working tree unless the
  configuration acknowledges it, and reports a suspicion when the path looks synchronised.
- The configuration gains that acknowledgement, and `config.example.yaml` no longer proposes
  a workspace inside the repository.
- PRINCIPLES.md gains the distinction in decision 1, since it governs future decisions
  rather than only these.
- Chapter 1 and the CHANGELOG are updated in this phase.
