# ADR-093 - A workspace is chosen where you can see it

## Status

Accepted. It lets the window write a second kind of file, which ADR-069 said it would not, so
the conditions are most of this record.

## Context

Everything LACC does happens inside one workspace, named by `workspace_root` in whichever
configuration is in force. The window had a picker for the configuration at the **bottom** of
the rail, under the theme, with the workspace path printed under it in the faintest colour in
the palette - and the request that produced this record was *"it would be great if we could
now create and navigate workspaces"*, from somebody who had been using the window all day.

That is a fair reading of what was there. The single most load-bearing fact about a session -
**which folder every file comes from and goes to** - was the least prominent thing on screen.

And the request came with a second half: *"one for OneDrive, so it synchronises
automatically."*

## What LACC can and cannot do about that

**It cannot synchronise anything, and should not.** A synchronising client does that; what is
being decided here is only whether a workspace sits inside a folder one is watching. So this
record does not build syncing. It makes the consequence visible at the moment the choice is
made.

The consequence, stated once:

- **Everything goes.** The papers, the converted Markdown, every corpus, the audit log with
  every prompt and answer under `audit_level: full`. A local-first tool whose workspace
  synchronises is a tool that copies private research to somebody else's computer, which is
  the one thing this project exists to avoid.
- **It also breaks.** Measured on this machine: four `Access is denied` failures in one day
  from files a synchroniser held mid-write, and Files On-Demand dehydrating files that were
  then read as empty (ADR-084).

`sync_folder_suspicion` has warned about this since ADR-022. It printed to a terminal the
person using the window never saw.

## Decision

**The workspace moves to the top of the rail, with the configuration that names it.** Which
folder you are in, which configuration says so, and any warning about it - first thing, above
everything else. The theme stays at the bottom where a theme belongs.

**Switching workspace is still switching configuration.** The window chooses *which*
configuration is read and never edits one - unchanged from ADR-069, and the reason is
unchanged: the configuration is the user's, and a window that edits it is a window that can
be wrong about what the user meant.

**The window may write one new configuration, and only a new one.** Creating a workspace means
a directory and a file naming it; refusing to write the file would mean the feature is a note
telling you to go and use a text editor. It writes through the same path as everything else -
**exclusive creation, so an existing file is refused rather than replaced** - and it copies
the model, engine and embedding settings from the configuration in force, because a new
configuration without them is a workspace that cannot do anything.

**The form is checked before it can be used**, in the grammar ADR-085 established: pressing
*Check* writes nothing and draws what would happen - the folder, whether it exists, what the
configuration would be called, and every warning that applies. The control that creates is
produced by that drawing.

**A warning is a warning, not a refusal.** A sync folder is a guess from a name; a name may
sync nothing and an unremarkable name may sync everything. Refusing on a guess teaches people
that this program's refusals are noise (ADR-022). A git working tree is still refused, because
that one is a fact and not a guess.

## Consequences

- `features/workspaces.py` holds what a configuration points at, what is risky about a path,
  and what a new configuration would contain. The window draws it.
- Two things the window writes now: its own appearance, and a configuration you asked it to
  create. Both are new files; neither replaces one of yours.
- The configuration picker changes what the *window* reads and does not follow you to a
  terminal. A workspace created here is used from the command line by naming its
  configuration with `-c`.

## Trade-off

**Making it easy to create a workspace in a sync folder is making it easy to leak a thesis.**
The warning is as loud as a warning can be and it is still one sentence next to a button. The
alternative - refusing - was rejected above, and this is the cost of that.

**Two places now know how to write a configuration**: this, and whatever a person does by
hand. There is no format to drift, because it writes the same YAML keys `Config` reads, and a
configuration this produces is an ordinary file with nothing special about it.

**And the rail is longer.** The workspace block at the top costs vertical space on a short
window, above eleven section names. What it buys is that the answer to *where am I* is never
more than a glance.
