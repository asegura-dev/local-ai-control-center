"""Reading this project's own documentation, inside the window (ADR-070).

Sixty-nine decision records, six chapters, the guides, and a book of eight chapters that is
in `.gitignore` and that nobody ever sees. All of it is Markdown on disk, and none of it is
reachable from the thing it documents.

Two decisions shape this module.

**Markdown is turned into blocks here, not painted here.** What a line *is* - a heading, a
quotation, an item, code - is a decision, and a view that made it would be a view containing
logic (ADR-066). The window receives blocks and gives them a font.

**The folder is found, never configured.** A setting naming where to read documentation from
would be a setting pointing anywhere, in a project whose first rule is that nothing outside
the workspace is touched. This walks up from the package to see whether it is running inside
its own repository, and reads only Markdown, only from there. Installed as a package with no
repository around it, there is nothing to show and it says so.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
_FENCE = re.compile(r"^\s*```")
_RULE = re.compile(r"^\s*(?:---+|\*\*\*+)\s*$")
_TABLE = re.compile(r"^\s*\|")

_MARKUP = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\[(.+?)\]\([^)]*\)")
"""Bold, italic, inline code and links, flattened to the text a reader wants.

Flattened rather than styled: Tk can style a run of text, and doing it for every inline span
would mean an index arithmetic this project does not need to own. The words survive; the
emphasis does not, and the heading structure - which is what makes a long record navigable -
does.
"""

_FOLDERS = ("docs",)
_SKIP = {"__pycache__", ".git", "node_modules"}


class Block(BaseModel):
    """One piece of a document, as a thing to be drawn rather than as Markdown."""

    model_config = ConfigDict(frozen=True)

    kind: str
    """`heading`, `text`, `item`, `quote`, `code`, `rule` or `table`."""

    text: str = ""
    level: int = 0
    """For a heading, its depth. Zero everywhere else."""


class Page(BaseModel):
    """One document that can be opened, with where it sits."""

    model_config = ConfigDict(frozen=True)

    path: Path
    title: str
    section: str
    """The folder it came from, so a list can be grouped the way the docs are."""


def plain(text: str) -> str:
    """The words of a line, with inline markup removed."""
    return _MARKUP.sub(lambda m: next(g for g in m.groups() if g is not None), text).strip()


def blocks_in(markdown: str) -> tuple[Block, ...]:
    """Turn a document into blocks, keeping paragraphs whole.

    A paragraph wraps across lines in every file here, and treating each line as a block
    would produce a column of fragments. Fenced code is kept verbatim, including its blank
    lines, which is why the fence is tracked rather than split on.
    """
    blocks: list[Block] = []
    paragraph: list[str] = []
    code: list[str] = []
    fenced = False

    def close() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(Block(kind="text", text=plain(" ".join(paragraph))))
        paragraph = []

    for raw in markdown.splitlines():
        if _FENCE.match(raw):
            if fenced:
                blocks.append(Block(kind="code", text=chr(10).join(code)))
                code = []
            else:
                close()
            fenced = not fenced
            continue
        if fenced:
            code.append(raw)
            continue

        line = raw.rstrip()
        heading = _HEADING.match(line)
        if heading:
            close()
            blocks.append(
                Block(kind="heading", text=plain(heading.group(2)), level=len(heading.group(1)))
            )
            continue
        if _RULE.match(line):
            close()
            blocks.append(Block(kind="rule"))
            continue
        if not line.strip():
            close()
            continue
        if _TABLE.match(line):
            close()
            # Kept as a row of cells rather than laid out: a table in these records is
            # usually two columns of short text, and a monospaced row reads correctly.
            cells = [plain(cell) for cell in line.strip().strip("|").split("|")]
            if any(set(cell) <= set("-: ") for cell in cells):
                continue
            blocks.append(Block(kind="table", text="   ".join(cell.strip() for cell in cells)))
            continue
        quoted = _QUOTE.match(line)
        if quoted:
            close()
            blocks.append(Block(kind="quote", text=plain(quoted.group(1))))
            continue
        item = _ITEM.match(line)
        if item:
            close()
            blocks.append(Block(kind="item", text=plain(item.group(1))))
            continue
        paragraph.append(line.strip())
    close()
    if fenced and code:
        blocks.append(Block(kind="code", text=chr(10).join(code)))
    return tuple(blocks)


def documentation_near(package: Path) -> Path | None:
    """The `docs/` folder of this repository, if the package is running inside it.

    Walks up from the package rather than taking a path from anybody. Returns nothing when
    there is no repository around it, which is the ordinary case for an installed package
    and is reported rather than guessed at.
    """
    for parent in package.resolve().parents:
        for name in _FOLDERS:
            candidate = parent / name
            if candidate.is_dir():
                return candidate
    return None


def _title_of(path: Path) -> str:
    """The document's own first heading, falling back to its filename."""
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for _ in range(40):
                line = handle.readline()
                if not line:
                    break
                heading = _HEADING.match(line.rstrip())
                if heading:
                    return plain(heading.group(2))
    except OSError:
        pass
    return path.stem.replace("-", " ")


def pages_in(folder: Path) -> tuple[Page, ...]:
    """Every Markdown document under ``folder``, grouped by the folder it sits in.

    Sorted so that the top level comes before what is nested under it, which is the order
    these were written to be read in.
    """
    found: list[Page] = []
    for path in sorted(folder.rglob("*.md")):
        if any(part in _SKIP for part in path.parts):
            continue
        section = path.parent.name if path.parent != folder else ""
        found.append(Page(path=path, title=_title_of(path), section=section))
    return tuple(sorted(found, key=lambda page: (page.section, page.path.name)))


SHOWN_AT_ONCE = 250
"""How many blocks are drawn before a document is cut off.

A corpus here is 284 KB and thousands of blocks, and a widget per block would freeze the
window drawing a file nobody reads to the end anyway. The cut is a **decision** - the number
and the fact that there is one - so it lives with the other decisions, and what is not shown
is counted and said rather than silently dropped (ADR-073).
"""


def opening(blocks: tuple[Block, ...], most: int = SHOWN_AT_ONCE) -> tuple[tuple[Block, ...], int]:
    """The first blocks of a document, and how many were left out.

    Returning the remainder rather than a flag: a reader deciding whether to open the file
    properly wants to know whether it is ten more or ten thousand.
    """
    return blocks[:most], max(len(blocks) - most, 0)
