"""The indexes of `src/` and `tests/` name every file, and nothing that is gone.

An index somebody has to remember to update is an index that ages, and this project has
recorded published figures that aged into falsehoods. Structure is kept; requests are
negotiated. So the two pages that say where each thing lives are held by the files themselves:
a module or a test file added without its line fails here, and so does a line left after its
file was removed.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "local_ai_control_center"
TESTS = ROOT / "tests"

_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)
_LAYER = re.compile(r"^## `([a-z]+)/`", re.MULTILINE)


def _named_in_src_index() -> set[str]:
    """Every module `src/README.md` lists, as a path inside the package."""
    text = (ROOT / "src" / "README.md").read_text(encoding="utf-8")
    named: set[str] = set()
    for part in re.split(r"(?=^## )", text, flags=re.MULTILINE):
        layer = _LAYER.match(part)
        if layer is None and not part.startswith("## The root"):
            continue
        prefix = f"{layer.group(1)}/" if layer else ""
        named |= {prefix + name for name in _ROW.findall(part) if name.endswith(".py")}
    return named


def test_the_source_index_names_every_module_and_nothing_else() -> None:
    present = {
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*.py")
        if "__pycache__" not in path.parts
    }
    named = _named_in_src_index()
    assert not present - named, f"modules with no line in src/README.md: {sorted(present - named)}"
    assert not named - present, f"lines in src/README.md with no module: {sorted(named - present)}"


def test_the_tests_index_names_every_test_file_and_nothing_else() -> None:
    text = (TESTS / "README.md").read_text(encoding="utf-8")
    named = {name for name in _ROW.findall(text) if name.endswith(".py")}
    present = {path.name for path in TESTS.glob("*.py")}
    assert not present - named, (
        f"test files with no line in tests/README.md: {sorted(present - named)}"
    )
    assert not named - present, f"lines in tests/README.md with no file: {sorted(named - present)}"
