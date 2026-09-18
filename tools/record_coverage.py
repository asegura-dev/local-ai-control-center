"""Report, for every decision record, the code it names and where that code is used.

**This detects nothing.** It answers no question on its own, and a symbol low in its output
is not a defect. What it does is turn *read the source looking for controls that do not cover
what their record claims* into a finite list - fifty-nine records, ninety-seven symbols -
that a person can walk in an afternoon (ADR-059).

The question it is for, asked of each row: **what does the record claim this does, and does
the code do it in every place it should?** That question found deduplication running on one
of four call sites, and no test would have.

Run it with `.\run.ps1 run python tools/record_coverage.py`. The output is meant to be read,
not committed: a report in the repository would be stale by the next commit, and a stale
inventory is worse than none because it reads like a current one.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "local_ai_control_center"
SUITE = ROOT / "tests"
RECORDS = ROOT / "docs" / "adr"

BACKTICKED = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")
"""Identifiers a record names. Prose in backticks is how every record cites code."""

PROSE = frozenset(
    {
        "true",
        "false",
        "none",
        "null",
        "yes",
        "no",
        "on",
        "off",
        "and",
        "or",
        "not",
        "if",
        "is",
        "in",
        "the",
        "a",
        "an",
        "it",
        "this",
        "that",
        "one",
        "two",
    }
)
"""Backticked words that are English rather than code, so the report does not cry wolf."""


DELIBERATE = {
    ("ADR-004-permissions", "require"): "removed in v1.5.0; the record carries the correction",
    ("ADR-059-checking-that-a-control-covers-what-it-claims", "require"): "records its removal",
    ("ADR-046-how-much-to-show-at-once", "_GENERATE_TIMEOUT_SECONDS"): (
        "describes what was there before this record changed it; now _MINIMUM_GENERATE_TIMEOUT"
    ),
}
"""Citations of code that is gone, kept on purpose, with why.

A record that corrects itself still names the thing it corrected, and a record about a
removal names what was removed. Both are right to, and both would otherwise sit in the
report forever - which is how a reader learns to skip the section.

An entry is a claim that the record already tells the reader what happened. It is worth
opening the record to check, and it is not a place to put something still to fix.
"""


def _not_our_code() -> frozenset[str]:
    """Names a record may cite that are not symbols: our modules, and other people's tools.

    A record saying `cycle` means the module, and one saying `pypdf` means the package. Both
    are legitimate citations and neither is a symbol this source defines, so reporting them
    as missing would bury the two that matter under twenty that do not.
    """
    modules = {p.stem for p in SOURCE.rglob("*.py")} | {
        p.name for p in SOURCE.iterdir() if p.is_dir()
    }
    outside = set(
        re.findall(r"[A-Za-z][A-Za-z0-9_-]+", (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    )
    return frozenset(modules | outside | {"local_ai_control_center", "lacc"})


def _trees(where: pathlib.Path) -> dict[pathlib.Path, ast.Module]:
    return {p: ast.parse(p.read_text(encoding="utf-8")) for p in sorted(where.rglob("*.py"))}


def _definitions(
    trees: dict[pathlib.Path, ast.Module], root: pathlib.Path = SOURCE
) -> dict[str, str]:
    """Every name the source defines, and the file it is defined in."""
    found: dict[str, str] = {}
    for path, tree in trees.items():
        where = str(path.relative_to(root))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                found.setdefault(node.name, where)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                found.setdefault(node.target.id, where)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        found.setdefault(target.id, where)
    return found


def _sites(trees: dict[pathlib.Path, ast.Module]) -> dict[str, list[str]]:
    """Where each name is referred to: `file.py:line`, one entry per mention.

    A definition line counts as a site and is marked, so a symbol with one site and that
    site being its own definition reads as what it is.
    """
    found: dict[str, list[str]] = defaultdict(list)
    for path, tree in trees.items():
        where = str(path.relative_to(SOURCE))
        for node in ast.walk(tree):
            line = getattr(node, "lineno", None)
            if line is None:
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                found[node.name].append(f"{where}:{line} (def)")
            elif isinstance(node, ast.Name):
                found[node.id].append(f"{where}:{line}")
            elif isinstance(node, ast.Attribute):
                found[node.attr].append(f"{where}:{line}")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.isidentifier():
                    found[node.value].append(f"{where}:{line} (by name)")
    return found


def _mentioned_anywhere(trees: dict[pathlib.Path, ast.Module]) -> set[str]:
    names: set[str] = set()
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                names.add(node.value)
            elif isinstance(node, ast.alias):
                names.add(node.asname or node.name.rsplit(".", 1)[-1])
    return names


def main() -> int:
    """Print the inventory, records first, then what the source never mentions."""
    trees = _trees(SOURCE)
    defined, sites, mentioned = _definitions(trees), _sites(trees), _mentioned_anywhere(trees)
    # The suite defines things a record may cite - the allowlists in ADR-059, for one - and
    # citing a test constant is not the same as citing a control, so they are kept apart.
    in_the_suite = _mentioned_anywhere(_trees(SUITE)) | set(_definitions(_trees(SUITE), SUITE))
    not_a_symbol = _not_our_code()

    records = sorted(RECORDS.glob("ADR-*.md"))
    rows: dict[str, list[tuple[str, str, list[str]]]] = {}
    absent: dict[str, set[str]] = {}

    for record in records:
        text = record.read_text(encoding="utf-8")
        named = {m for m in BACKTICKED.findall(text) if m.lower() not in PROSE}
        resolved = []
        for name in sorted(named):
            if name in defined:
                elsewhere = [s for s in sites.get(name, []) if "(def)" not in s]
                resolved.append((name, defined[name], elsewhere))
        rows[record.name] = resolved
        missing = {
            n
            for n in named
            if n not in defined
            and n not in mentioned
            and n not in in_the_suite
            and n not in not_a_symbol
        }
        missing -= {name for (which, name) in DELIBERATE if which == record.name[:-3]}
        if missing:
            absent[record.name] = missing

    print("=" * 78)
    print("WHAT EACH RECORD NAMES, AND WHERE THE SOURCE USES IT")
    print("=" * 78)
    print()
    print("Thin is not wrong. Ask of each row: what does the record claim this does, and")
    print("does the code do it everywhere it should? (ADR-059)")
    print()

    for name, resolved in rows.items():
        if not resolved:
            continue
        thinnest = min(len(where) for _, _, where in resolved)
        print(f"--- {name[:-3]}   (thinnest symbol: {thinnest} use{'' if thinnest == 1 else 's'})")
        for symbol, defined_in, where in sorted(resolved, key=lambda r: len(r[2])):
            shown = ", ".join(where[:4]) + (f", +{len(where) - 4} more" if len(where) > 4 else "")
            print(f"    {symbol:30} {defined_in:22} {len(where):>3} use(s)  {shown or '(none)'}")
        print()

    if absent:
        print("=" * 78)
        print("NAMED BY A RECORD, AND THE SOURCE NEVER MENTIONS IT")
        print("=" * 78)
        print("Module names, packages and test-side symbols are filtered out. What is left is")
        print("a renamed symbol, a plan that was not built, or prose that looks like code -")
        print("and the first two mean a record describes something that is not there.")
        print()
        for name, missing in absent.items():
            print(f"    {name[:-3]:58} {', '.join(sorted(missing))}")
        print()

    if DELIBERATE:
        print(
            f"({len(DELIBERATE)} citations of removed code are listed as deliberate in "
            "DELIBERATE, with a reason each.)"
        )
        print()

    counted = sum(len(r) for r in rows.values())
    with_code = sum(1 for r in rows.values() if r)
    print(f"{len(records)} records, {with_code} naming code, {counted} record-to-symbol links.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
