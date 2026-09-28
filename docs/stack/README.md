# The stack - what LACC is made of, and where each part is used

For somebody who wants to understand the repository without reading its thirty thousand lines
(about 17,700 of source and 12,200 of tests on 27-sep):
what each technology is, why it is here, and where to find it at work. Three pages:

| Page | What it answers |
|---|---|
| this one | What each piece of the stack is, its version, what it does here, and which record chose it |
| [a-run-end-to-end.md](a-run-end-to-end.md) | What happens, function by function, between typing `lacc run` and reading a checked answer |
| [files-on-disk.md](files-on-disk.md) | Every file LACC writes, where, and whether it can ever replace one |

Where each *module* is, one line each, is [`src/README.md`](../../src/README.md); what each
*test* holds is [`tests/README.md`](../../tests/README.md). The reasons behind all of it are the
decision records, listed in [`docs/INDEX.md`](../INDEX.md).

## The program

| Piece | Version | What it does here | Where | Chosen in |
|---|---|---|---|---|
| **Python** | 3.11 or later; 3.12 in use | Everything. `src/` layout, one package | `src/local_ai_control_center/` | ADR-001 |
| **Pydantic** | 2.13 | Every contract that crosses a boundary is a frozen model: configuration, plans, previews, audit records, registry answers. Frozen means written once, never revised | `core/`, `ports/`, `features/` | ADR-001, ADR-002 |
| **PyYAML** | 6.0 | Reading configurations and declared skills, always `safe_load`; the window's preferences, always `safe_dump` | `core/config.py`, `core/declared.py`, `features/appearance.py` | ADR-002, ADR-048 |
| **Typer** | 0.27 | The `lacc` command: one decorated function per subcommand. It carries its own copy of Click | `cli.py` | ADR-001 |
| **Rich** | 15.0 | What the terminal shows: previews, panels, colour. Presentation only, and only in `cli.py` | `cli.py` | ADR-001 |
| **CustomTkinter** | 6.0, optional (`gui` extra) | The window: fourteen sections over Tk. Nothing in it is tested with a display; everything it draws is decided in `features/` | `window.py`, `views/` | ADR-069 |
| **pypdf** | 6.18 | Text out of PDFs, page by page; what a PDF says about itself; text a reader could not see | `adapters/documents.py` | ADR-016, ADR-040 |
| **python-docx** | 1.2 | Text out of Word files, headings and tables kept in order | `adapters/documents.py` | ADR-016 |
| **psutil** | 7.2 | How much memory the machine has, for `lacc profile` | `system/profiler.py` | - |
| **hashlib** (standard library) | - | SHA-256: the audit chain, and digests of every file read and every prompt sent | `system/audit.py` | ADR-023 |

Versions are the ones `uv.lock` pinned on 27-sep; the lock file is where they are true. The
package builds with `uv_build`.

## Outside the program, and reached on purpose

| Piece | What LACC asks of it | Reached how | Chosen in |
|---|---|---|---|
| **Ollama** | Completes prompts, and embeds text when `embedding_model` is set. Local, or on a machine of yours over Tailscale | HTTP to the host the configuration names, which the preview names too; a remote host needs `network_access` | ADR-005, ADR-028, ADR-061 |
| **Crossref** | What a work is, given its DOI | HTTP, only with `network_access` **and** `registry_url` set; only DOIs leave | ADR-067 |
| **ntfy** | A notice that a run finished, carrying the trail's length and head | HTTP to the `server_url` the configuration names | ADR-060 |
| **Tailscale** | A private network between this machine and the one with the graphics card | Not by LACC: by the operating system; LACC sees an address | guides/setting-up-the-server-machine.md |

Nothing else leaves the machine, and in the test suite nothing leaves at all: `conftest.py`
fails any connection that is not to this machine (ADR-022).

## Building and checking it

| Piece | Version | What it does | How it is run |
|---|---|---|---|
| **uv** | - | Environments and the lock file | Always through `run.ps1`, which keeps the environment out of a synchronised folder (ADR-084) |
| **ruff** | 0.15 | Lint (`E`, `F`, `I`, `UP`, `B`, `SIM`) and formatting, 100 columns | `.\run.ps1 run ruff check .` and `ruff format --check .` |
| **mypy** | 2.1, `strict` | Types, over `src` | `.\run.ps1 run mypy src` |
| **pytest** | 9.1 | The suite, including the guards on the code's own shape | `.\run.ps1 run pytest -q` |

The four commands are the gate. Nothing is released without all four passing.

## What the thesis side uses

Not part of LACC, and named because LACC writes for them:

- **pandoc** reads `[@key]` citations from Markdown and a `.bib`; it makes the Word preview.
- **biblatex and biber** (MiKTeX) typeset the final document from the same `.bib`.
- **Obsidian** is where the chapters are written.

`lacc bib` writes the `.bib` all three read from (ADR-102).
