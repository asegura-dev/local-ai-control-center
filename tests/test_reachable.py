"""Tests that a setting the program declares is a setting the program can reach (ADR-055).

`enforce_shape` was decided, built, released, documented and cited, and nothing could turn
it on: no flag, no configuration key, no declaration. Six tests passed because they built
`SkillPlan` by hand, which the program never does. It was the second instance of that shape
after `ask_corpus`, so it is checked here rather than remembered.

**Coverage of a type is not coverage of a path.** The question this file asks is the one
neither suite asked: *what in the program sets this?*
"""

from __future__ import annotations

import ast
import pathlib

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src" / "local_ai_control_center"

FROM_A_FILE = frozenset(
    {
        "Config",
        "Permissions",
        "NotifierSettings",
        "NtfySettings",
        "DeclaredSkill",
        "DeclaredField",
        "AuditEvent",
    }
)
"""Models a user's file or a stored record fills in, so nothing in the source need set them.

Deserialisation is the path, and it reaches every field by name. Anything not listed here is
built in code and only in code, which is where a field with nobody to set it can hide.
"""

ALWAYS_DEFAULT: frozenset[tuple[str, str]] = frozenset()
"""Fields deliberately left at their default everywhere, as `(class, field)` pairs.

Empty, and a new entry should be argued for rather than added to make this pass. A field
the program never sets is usually a switch nobody can reach.
"""


def _sources() -> dict[pathlib.Path, ast.Module]:
    return {p: ast.parse(p.read_text(encoding="utf-8")) for p in sorted(SOURCE.rglob("*.py"))}


def _fields_with_a_default(trees: dict[pathlib.Path, ast.Module]) -> set[tuple[str, str]]:
    """Annotated class attributes that have a default, outside the deserialised models."""
    found: set[tuple[str, str]] = set()
    for tree in trees.values():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name in FROM_A_FILE:
                continue
            for entry in node.body:
                if (
                    isinstance(entry, ast.AnnAssign)
                    and isinstance(entry.target, ast.Name)
                    and entry.value is not None
                    and not entry.target.id.startswith("_")
                    and entry.target.id != "model_config"
                ):
                    found.add((node.name, entry.target.id))
    return found


def _names_the_source_sets(trees: dict[pathlib.Path, ast.Module]) -> set[str]:
    """Every keyword argument and string dict key the source writes.

    Both forms count: a model is built with `Thing(field=...)` or validated from a literal.
    """
    written: set[str] = set()
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                written.update(keyword.arg for keyword in node.keywords if keyword.arg)
            elif isinstance(node, ast.Dict):
                written.update(
                    key.value
                    for key in node.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                )
    return written


def test_every_setting_has_something_in_the_program_that_sets_it() -> None:
    """A field only a test can set is not a feature, whatever the changelog says."""
    trees = _sources()
    written = _names_the_source_sets(trees)
    unreachable = sorted(
        (owner, field)
        for owner, field in _fields_with_a_default(trees)
        if field not in written and (owner, field) not in ALWAYS_DEFAULT
    )
    assert not unreachable, (
        "Nothing in the program ever sets: "
        + ", ".join(f"{owner}.{field}" for owner, field in unreachable)
        + ". A field only a test sets is unreachable, however well it is covered (ADR-055)."
    )


def test_the_check_would_have_caught_the_defect_it_exists_for() -> None:
    """Guards the guard: a check that cannot fail is decoration.

    `enforce_shape` as released - declared on `SkillPlan`, read by `output_schema`, written
    by nothing - must be what this reports.
    """
    released = ast.parse("class SkillPlan:" + chr(10) + "    enforce_shape: bool = False" + chr(10))
    trees = {pathlib.Path("skill.py"): released}
    assert ("SkillPlan", "enforce_shape") in _fields_with_a_default(trees)
    assert "enforce_shape" not in _names_the_source_sets(trees)
