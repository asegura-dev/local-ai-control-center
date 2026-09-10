# ADR-028 - The preview names where the documents are going

## Status

Accepted.

## Context

PRINCIPLES says the human is in the centre: a sensitive action is previewed and confirmed
before it runs, and confirmation defaults to no. The preview is where that promise is kept,
so what it leaves out is what the person is not deciding about.

Today it shows the action, its summary, the capabilities it needs, the files it reads, the
files it writes, and whether it would be allowed. Until v0.26.0 that was the whole story,
because the engine was always on this machine and there was nowhere else for anything to
go.

`engine_host` changed that and the preview did not follow. A run against a configured
remote engine looks exactly like a local one:

```
Action:  summarize_file
Summary: Summarize paper.md
Reads:   paper.md
Status:  would run
```

The single most consequential fact - that the contents of `paper.md` are about to leave
this computer for `100.101.102.103` - is the one thing the confirmation screen does not
say. Every guarantee around it still holds: the host is named in a file the user wrote,
nothing else can widen it, and the whole run is audited. But a control the person cannot
see at the moment of deciding is a control they are not exercising.

This is worse than an omission on a screen. The person most likely to be surprised is
someone using a configuration they did not write - a colleague's, an example copied from a
guide, a machine set up months earlier.

## Decision

**The preview names the destination whenever it is not this machine.**

```
Action:  summarize_file
Summary: Summarize paper.md
Reads:   paper.md
Sends:   the contents read above, to http://100.101.102.103:11434
Status:  would run
```

**The line appears only when the engine is elsewhere.** A loopback engine adds nothing, and
a line that is always there is a line nobody reads. Absence carries meaning: no `Sends:`
means nothing leaves the machine.

**The caller says whether a run sends anything, rather than the preview inferring it.**
`preview_action` takes the destination as an argument. `run_action` passes it because it
calls a provider; `run_conversion` passes nothing because converting a PDF never contacts
an engine. Guessing from an action's capabilities would be exactly the implicit behaviour
PRINCIPLES rules out, and it would be wrong for conversions.

**`Config` learns to report its own remote engine.** A `remote_engine` property returns the
configured host when it is not loopback, and an empty string otherwise. It reports and does
not judge: whether reaching it is permitted is `network_access`, and refusing is still the
provider's job. Putting it on the configuration contract keeps one definition of "not this
machine" for both the code that discloses it and the code that enforces it.

**The wording says what travels, not just where.** "Sends: the contents read above" rather
than a host on its own, because the risk is not that a connection is made - it is that the
text of the document goes with it.

## Consequences

- `ExecutionPreview` carries the destination, and `render` shows it when there is one.
- `Config.remote_engine` becomes the one place that decides whether an engine is elsewhere,
  and `resolve_engine_host` uses the same helpers.
- `lacc preview` shows the destination too, so it can be checked without running anything.
- A person reading a configuration they did not write learns, at the confirmation prompt,
  that their document is leaving the machine.
- Conversions keep a preview with no destination, which is true and now says so.

## Trade-off

One more line on a screen people already skim, and the more a preview shows the less each
line is read. Accepted because it appears only when it is true, which is what keeps it from
becoming noise - a warning shown on every run teaches people to click past it.

This does not stop anything. A user who confirms without reading sends the document
anyway, and the guarantee remains what it always was: the destination is named in a file
the user wrote. Accepted, because informing at the point of decision is what a preview is
for, and the alternative was a control nobody could see.
