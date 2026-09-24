# ADR-094 - What it does, and what it may do

## Status

Accepted. It lets the window change a configuration you wrote, which ADR-069 forbade and
ADR-093 half-lifted, and the line it draws is the point of the record.

## Context

Three things were said after using the window:

> *In workspace it seems to be the configuration of the workspace, not actually choosing a
> folder for the workspace. Also you still cannot change the path or the configuration inside
> the GUI, and it would be great to test there whether there are models installed, locally
> and on the remote.*

The first is a defect this project introduced one release earlier. ADR-093 put a heading
reading **WORKSPACE** above a picker of **configuration files**, and every configuration in
that folder happens to name the same workspace - so the control labelled with the folder
changes the model and leaves the folder alone. A label that names the wrong thing is worse
than no label, because it is believed.

The other two are the same request from two directions: **the configuration is the only thing
in this program you still have to leave the window to change**, and the setting you most want
to change is the one you cannot check - which models are actually installed, here and on the
machine the configuration names.

## Decision

**The rail says what the control does.** A picker of configurations is labelled
*CONFIGURATION*, and the workspace is what it names, printed under it. One label, one thing.

**The window may change what LACC does. It may not change what LACC is allowed to do.**

That is the whole line, and it falls between two kinds of setting:

| editable here | file only |
|---|---|
| `workspace_root`, `model`, `context_tokens` | `network_access` |
| `embedding_model`, `engine_host` | `workspace_in_repository` |
| `output_language`, `context_file`, `registry_url` | |

The two on the right are not settings. They are **refusals being lifted** - `network_access`
is the ceiling that decides whether anything at all may leave this machine, and
`workspace_in_repository` overrides a refusal to work inside a git tree. Each exists because
this project decided a person should have to write it down deliberately, and a toggle is not
writing it down. `engine_host` is editable because with the ceiling down it is inert: naming a
host LACC may not reach changes nothing.

**A diff is the confirmation.** Pressing *Check* writes nothing and draws every line that
would change, before and after. The control that saves is produced by that drawing, the way
it is for a question and for a new workspace (ADR-085, ADR-093). There is no additional
ceremony for the riskier settings: an extra ritual on some changes teaches people to click
through the ritual, and the diff already says exactly what happens.

**What it writes is the file you can read.** The same hand-written keys ADR-093 produces, not
a dump of the contract with every default in it - and comments in the original are lost,
which is said on the screen before anything is written rather than discovered afterwards.

**And the engines can be asked, from the window, on a button.** Two of them: the host the
configuration names, and this machine. Each says whether it answered, how long it took, and
**which models it holds** - `check_engine` has returned the names since ADR-077 and the
window threw them away to keep a count. Nothing is asked until somebody presses it, which is
the rule that has governed the bottom bar since it was written.

## Consequences

- `EngineSeen` carries the model names it already had.
- An `Engines` section: what the configuration names, what this machine holds, and which of
  them has the model in force.
- The window now writes three things: its appearance, a new configuration, and a changed one.
  Every one of them draws what it would do first.

## Three defects found by driving it

**It was editing a different configuration from the one in force.** The window took its
workspace, its engine and its context file from the configuration `-c` named, and
`chosen_configuration` from what the *preferences* remembered. Launched with `denso.yaml`
against a preference holding `config.yaml`, the Engines section said *"asks for qwen2.5:7b"*
while marking `qwen2.5:14b` in the list - two configurations contradicting each other on one
screen. **The configuration you launched with is the one in force**; the preference only
remembers a switch made in the window.

**A form nobody touched proposed rewriting three lines.** The boxes were filled from the
parsed contract rather than from the file, so `~/lacc-workspace` came back as a Windows path
with backslashes and every setting the file never mentioned came back as today's default. The
boxes read the file now, and a setting it does not mention is an empty box whose note says
what the default is.

**And saving rewrote the whole file.** Re-serialising the parsed settings destroyed every
comment and froze the current defaults into the file as if somebody had chosen them. A
configuration is edited **line by line** now: only a key whose value actually differs is
touched, its own line is rewritten in place, and comments, order and spacing survive byte for
byte. Changing one setting produces a diff of one setting.

## Trade-off

**A configuration is easier to break now.** It was a file you opened deliberately; it is a
form. The defence is the diff, and the defence is thin - somebody will change
`context_tokens` to something the engine cannot serve and get a refusal they do not
understand. That is the cost of not having to leave the window.

**Comments are lost.** A configuration written by hand and commented is rewritten without
them. Said before saving, and still a loss.

**And the line between "does" and "may do" is a judgement.** `registry_url` is on the left,
and pointing it at a different registry is a real change to where a DOI goes - it sits there
because `network_access` already gates whether it goes anywhere at all. Somebody could
reasonably put it on the right.
