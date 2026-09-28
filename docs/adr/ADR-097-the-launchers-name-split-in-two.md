# ADR-097 - The launcher's name, split in two

## Status

Accepted.

## Context

`.\run.ps1` is the one way this project is run (ADR-084), so it is written in a great many
places. Written through a tool that reads a backslash as the start of an escape, the
backslash and the `r` after it became a single carriage return, and the name was cut in two.

It was found on 24-sep in `scripts/lacc-window.bat`, whose message for a window that does not
open printed `.un.ps1 sync --extra gui`. The repair was deferred to the next release, and the
same entry recorded that this was **the only case in the 263 files of the repository,
measured byte by byte.**

**That was false.** On 25-sep `docs/03-development.md` turned out to hold the same defect in
three places, published since the commit that wrote them. The search had counted carriage
returns that end no line. In the chapter the carriage return had since become an ordinary
line break, so the text read as a lone dot and, on the next line, a command beginning
`un.ps1` - and there was no stray carriage return left for a byte search to find. The
figure was measured; it measured the wrong thing.

**And the checksum certified the broken launcher.** `scripts/SHA256SUMS.txt` held the digest
of the defective file, and `verify-scripts.bat` said *ok*. ADR-071 had stated the limit - a
digest proves a file is the one recorded, not that it is right - and this is that limit,
met.

## Decision

- **The four occurrences are repaired** - one in the launcher, three in the chapter - by
  writing the backslash as its byte rather than as a character a tool could read as an
  escape.
- **The launcher gets a new digest.** The old one described a file that no longer exists,
  and `git log scripts/` shows both.
- **A test asks every text file in the repository two questions**: does any line begin with
  `un.ps1`, and is there a carriage return that ends no line. The first catches the
  chapter's shape, which the second cannot; the second catches the launcher's.

## Consequences

Asked of the files as they stood before this record:

| file | lines beginning `un.ps1` | carriage returns ending no line |
|---|---|---|
| `docs/03-development.md` | 108, 110, 129 | 0 |
| `scripts/lacc-window.bat` | 18 | 1 |

The zero in the first row is the whole reason the 24-sep search called the launcher the
only case. After the repair both questions return nothing, over every text file.

## Trade-off

**The test knows one name.** The failure is general: a backslash eaten with the letter after
it turns `\t` into a tab, `\n` into a line break, `\b` into a backspace, in whatever word
followed it. A check that caught all of those would need to know what the text was meant to
say. This one catches the name that is written most often and was broken twice, and says
nothing about the rest.
