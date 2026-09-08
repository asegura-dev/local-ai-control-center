# Guide - Keeping the virtual environment out of a synchronising folder

If your checkout lives inside OneDrive, Dropbox, iCloud Drive or any other folder a
client keeps in sync, put the virtual environment somewhere else. This guide is written
from the failures that actually happened while building LACC, not from general advice.

## Why it matters

A `.venv` is thousands of small files that change whenever you install anything. A sync
client tries to replicate every one of them, and two things follow.

**Files get hollowed out.** This is the reason that decides it, because it does not
announce itself. With "Files On-Demand" enabled, OneDrive can dehydrate a file it
thinks is idle, leaving a placeholder to be downloaded on access. When that happens to a
`.dll` or `.pyd` inside the environment, the import fails with an error that reads like a
bug in the library. LACC depends on `lxml`, a compiled extension, so it is exposed to
exactly this. Moving the environment out removes the risk entirely.

**Files stay locked.** `uv` removes a package's `dist-info` directory when it reinstalls
the project, and something holds a handle on it:

```
error: failed to remove directory `...\.venv\Lib\site-packages\<package>.dist-info`:
Access is denied. (os error 5)
```

Each failure leaves an orphaned directory with no `RECORD` file, which makes every later
command warn and retry the same doomed removal until it is deleted by hand.

Be careful about what this proves. Inside the sync folder it happened five times and
eventually on every run; after moving the environment out it became rare - but it did
still happen once, on a path the sync client never sees. So a sync client makes it much
worse and is not the only cause: on Windows a real-time scanner or the search indexer can
hold the same kind of brief handle. The handle is transient, and removing the orphaned
directory by hand succeeds immediately.

A lock is loud, and you retry. A hollowed-out binary lies, and you debug the wrong thing
for an hour. That asymmetry is the argument.

## The fix: a directory link

Keep the environment outside the synchronised tree and leave a link where the tooling
expects it. Nothing then has to be remembered, and no environment variable has to be set
in every terminal.

On Windows, from the project directory:

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\.venvs\lacc"
Remove-Item -Recurse -Force .venv          # only if one is already there
New-Item -ItemType Junction -Path .venv -Target "$HOME\.venvs\lacc"
uv sync
```

A junction needs no administrator rights. On macOS or Linux the equivalent is
`ln -s ~/.venvs/lacc .venv`.

Verify it took effect:

```powershell
Get-Item .venv | Select-Object Name, LinkType, Target
```

The project directory should now hold a link of a few bytes where a few hundred megabytes
used to be, and the sync client has nothing left in the environment to dehydrate. Expect
the occasional locked `dist-info` to survive this: it comes from elsewhere, and the fix is
to delete the orphaned directory and run the command again.

## Two alternatives, and what they cost

**`UV_PROJECT_ENVIRONMENT`.** Point `uv` at a path outside the sync folder. It works, and
it is what a wrapper script usually does. The cost is that it has to be set in every
shell that touches the project: forget once and `uv` silently creates a second
environment inside the synchronised folder, and you now have two. Setting it globally is
worse, because every `uv` project on the machine then shares one environment directory.

**Move the checkout out of the synchronised folder.** This removes the cause rather than
the symptom, and it is the right answer if you are free to do it. A git repository does
not belong in a sync folder in the first place: git already keeps the history, the remote
already is the backup, and the sync client contributes only lock contention and conflicted
copies. It is also why the checkout has to be left alone while git runs.

## What this does not protect

The link keeps the environment out of the sync client's way. It does nothing about the
rest of the checkout, which is still synchronised - so a `git` operation can still collide
with the client, and pausing syncing during git work remains sensible until the checkout
is moved out entirely.
