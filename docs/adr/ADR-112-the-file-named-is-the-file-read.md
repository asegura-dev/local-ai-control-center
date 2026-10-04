# ADR-112 - The file named is the file read

## Status

Accepted. Found on 29 September by a test that used the program the way a person would and
read what it did; built on 30 September.

## Context

ADR-111 promised a command that reads "one file, named - never a folder, never a pattern". The
test found three ways in which the file read was not the file named, and one in which the
preview did not show it:

- **Every argument was rewritten before LACC saw it.** On Windows, the Click library under
  Typer imitates a Unix shell on each argument: it expands `~` and `%VARIABLES%`, and matches
  `*`, `?` and `[...]` against the files in the folder the command runs in.
  - `lacc bring "cap [1].md"`, beside a file called `cap 1.md`, proposed to read `cap 1.md`:
    the brackets were read as a pattern, and the pattern matched the other file.
  - `capit*.md` was accepted as if it were a name.
  - `nota-%USERNAME%.md` became `nota-ana.md`.
  - A pattern that matched several files was refused, by an error that listed every one of
    them, in a folder outside the workspace.

  None of this was particular to `bring`. Every path and every question passed through it, and
  a question holding `%PATH%` or a question mark could have been rewritten the same way. The
  only reason none of it read a file nobody saw is that the preview showed the rewritten path
  before asking.
- **A share on another machine was read with the network off.** With `network_access: false`,
  `\\127.0.0.1\C$\…\capitulo.md` was previewed with its size. That size was read over the
  network before anything was asked, and nothing said the path was on the network. With another
  host in the path, LACC would have reached a machine its configuration does not name.
- **A missing file was refused as a folder**: *"…no-existe.md is not a file. One file is brought
  at a time, never a folder."*
- **The preview dropped part of a name.** `Metodología [v2] ñ.md` was shown as
  `Metodología  ñ.md`, and the command suggested next did not run. The preview is printed as
  Rich markup, and Rich reads `[v2]` as a style tag. The file read was the right one; the name
  shown was not.

And one thing the expansion had hidden. The commands that take several documents resolve each
name against the workspace, and relative names from the workspace's root. But Click matched
`*.md` against the folder the command ran in, which is the repository whenever LACC is run
through `run.ps1`. So `lacc collect extract_claims *.md`, as the guide wrote it, handed over
the repository's own Markdown files and then looked for them in the workspace.

## Decision

- **Arguments reach LACC as they were typed.** The entry point turns Click's Windows expansion
  off.
  - A shell that expands its own syntax - PowerShell's `$env:NAME`, cmd's `%NAME%` - has done
    so before LACC starts, as on any other system. What reaches LACC is what the shell passed,
    and nothing matches it against a folder.
  - `~` is expanded where LACC expanded it already: in the path `bring` reads, and in a path a
    configuration holds.
- **A pattern is LACC's, and it is matched inside the workspace.**
  - This applies to `run`, `collect`, `ingest`, `corpus`, `resolve`, `references` and
    `metadata`, the commands that take several documents.
  - A name that a file has is that file, whatever the name holds: `[10] Hu 2020.md` is a name.
  - A name no file has, holding `*` or `?`, is matched against the workspace. It is never
    matched against the folder the command runs in, and never outside the workspace. It is
    replaced by the files it matches, in order. Those files are what the command reads, and,
    where the command asks first, what its preview lists.
  - `[` and `]` are always part of a name: the papers here are called `[10] …`, and a character
    class would make them unreachable by any pattern.
  - A pattern that matches nothing is kept as typed, so the command says it is not there.
  - `bring` takes no patterns: a name holding `*` or `?` that no file has is refused, and the
    refusal says why.
- **`bring` reads files on this machine.** It refuses a path shaped like a share - `\\host\…`,
  `//host/…`, `\\?\UNC\…` - or on a drive Windows reports as a network drive. The refusal comes
  before anything is asked of the file system, whatever `network_access` says: that setting
  governs the engine and the registry a configuration names, and a file share is neither. If a
  link turns out to lead to another machine once it is followed, that path is refused too.
- **A missing file is called missing**, and a folder a folder.
- **What `bring` shows prints names as text**: the file, the copy and the command suggested
  next. That the same should hold for everything else the program prints, including the
  engine's answers, is ADR-113.

## Consequences

Measured through the real entry point, with the tester's own inputs:

| typed | before | now |
|---|---|---|
| `cap [1].md`, beside `cap 1.md` | would read `cap 1.md` | would read `cap [1].md` |
| `capit*.md` | would read `capitulo.md` | no file there, and `*` is not a pattern here |
| `nota-%USERNAME%.md` | would read `nota-ana.md` | would read `nota-%USERNAME%.md` |
| `Metodología [v2] ñ.md` | shown as `Metodología  ñ.md` | shown as typed |
| `no-existe.md` | "never a folder" | "There is no file at …" |
| `\\archivos.invalid\tesis\03.md` | size read over the network | refused before any file-system call |

- The guide's `lacc collect extract_claims "*.md"` now matches the workspace's files from
  wherever it runs. The pattern is quoted, so that a shell on Linux or macOS leaves it to LACC.
- Tests:
  - the entry point passes `windows_expand_args=False`;
  - on Windows, the tester's bracket case, driven through `sys.argv`;
  - the shapes of a share, and a share refused before `resolve` is ever called;
  - a drive reported remote;
  - missing against folder;
  - a bracketed name in the preview;
  - patterns matched inside the workspace, never outside it, and never as a character class.

## Trade-off

**`~` in `-c` is no longer expanded on Windows.** No shell there expands it for a program, so
`-c ~/x.yaml` now reaches LACC as `~/x.yaml` and fails, saying which file it could not load. Of
the places that read the configuration path - its skills, its `.env`, the window - expanding
it in one and not the others would load one configuration and look for its skills beside
another. None of this project's documents writes `-c ~`.

**A link to a share is found out by following it.** A path on this machine that is a link to a
share is resolved by Windows before LACC sees where it leads, and resolving it may reach that
host; LACC then refuses it. Checking every step of a path for a link before following it would
close this. It was not done, and it is named here.

**Only the shapes of a share, and Windows' own word on a drive.** On Linux or macOS a network
mount looks like any folder, and nothing here tells them apart.
