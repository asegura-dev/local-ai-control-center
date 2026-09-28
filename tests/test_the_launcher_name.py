"""The launcher's name is never split in two (ADR-097).

Written through a tool that reads a backslash as the start of an escape, `.\\run.ps1` lost
its backslash and its `r` together: the pair became a carriage return. In a launcher that
printed `.un.ps1 sync --extra gui`; in a chapter, where the carriage return had become an
ordinary line break, it printed a lone dot and a line beginning `un.ps1`. The second went
unseen because the search that declared the first "the only case" looked for carriage
returns, and there was none left to find.

So this asks both questions of every text file in the repository: does any line begin with
`un.ps1`, and is there a carriage return that does not end a line.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEXT = {".md", ".py", ".bat", ".ps1", ".txt", ".toml", ".yaml", ".yml", ".cff", ".cfg", ".json"}
SKIP = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "lacc-workspace",
    "node_modules",
    "build",
    "dist",
}


def _text_files() -> list[pathlib.Path]:
    return [
        path
        for path in sorted(ROOT.rglob("*"))
        if path.is_file() and path.suffix in TEXT and not SKIP & set(path.parts)
    ]


def _split_names(content: bytes) -> list[int]:
    """The lines, numbered from one, that begin with the launcher's name minus its start."""
    lines = content.decode("utf-8", errors="replace").splitlines()
    return [number for number, line in enumerate(lines, 1) if line.startswith("un.ps1")]


def _lone_carriage_returns(content: bytes) -> int:
    return content.count(b"\r") - content.count(b"\r\n")


def test_no_line_begins_with_the_launcher_name_cut_short() -> None:
    found = {
        str(path.relative_to(ROOT)): lines
        for path in _text_files()
        if (lines := _split_names(path.read_bytes()))
    }
    assert not found, f"a line begins with `un.ps1`, where `.\\run.ps1` was split: {found}"


def test_no_carriage_return_stands_alone() -> None:
    found = {
        str(path.relative_to(ROOT)): count
        for path in _text_files()
        if (count := _lone_carriage_returns(path.read_bytes()))
    }
    assert not found, f"a carriage return that ends no line: {found}"


def test_both_shapes_of_the_defect_are_caught() -> None:
    """The launcher's shape and the chapter's, exactly as they were before ADR-097."""
    launcher = b"  echo     ." + b"\r" + b"un.ps1 sync --extra gui\r\n"
    chapter = b"    ." + b"\r\n" + b"un.ps1 run python tools/measure.py\r\n"
    assert _split_names(launcher) == [2]
    assert _lone_carriage_returns(launcher) == 1
    assert _split_names(chapter) == [2]
    assert _split_names(b"    ." + bytes([92]) + b"run.ps1 run python\r\n") == []
