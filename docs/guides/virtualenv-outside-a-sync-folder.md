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

## The fix: nothing of the environment inside the folder

**Run every `uv` command through `run.ps1`.** It points `uv` at an environment in
`%USERPROFILE%\.venvs\lacc` by setting `UV_PROJECT_ENVIRONMENT` for that one command, so
nothing belonging to the environment exists inside the checkout at all:

```powershell
.\run.ps1 sync
.\run.ps1 run lacc --help
.\run.ps1 run pytest -q
```

Never run `uv` bare from the checkout: `uv sync` then creates a `.venv` inside the
synchronised folder, and you have two environments. That is how this project once found a
111 MB `.venv` in its checkout, beside the one `run.ps1` uses (ADR-084).

On macOS or Linux, set the same variable in the shell you work in, or in a small wrapper
of your own, before any `uv` command:

```sh
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/lacc"
```

Verify it took effect: there should be no `.venv` in the project directory, and
`.\run.ps1 run python -c "import sys; print(sys.prefix)"` should print a path under
`.venvs\lacc`. Expect the occasional locked `dist-info` even so: it comes from elsewhere,
and the fix is to delete the orphaned directory and run the command again.

## What does not work, and what works better

**A directory link does not.** A `.venv` junction or symlink pointing outside the folder
looks like the tidy answer and is not one: synchronisers traverse reparse points, so the
environment behind the link is still walked and still locked. This guide recommended the
link until 4 October 2026, while `run.ps1` and ADR-084 already said it was not enough.

**Moving the checkout out of the synchronised folder works better.** It removes the cause
rather than the symptom, and it is the right answer if you are free to do it. A git
repository does not belong in a sync folder in the first place: git already keeps the
history, the remote already is the backup, and the sync client contributes only lock
contention and conflicted copies. It is also why the checkout has to be left alone while
git runs.

## What this does not protect

`run.ps1` keeps the environment out of the sync client's way. It does nothing about the
rest of the checkout, which is still synchronised - so a `git` operation can still collide
with the client, and pausing syncing during git work remains sensible until the checkout
is moved out entirely.
