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


CALLED_FROM_OUTSIDE = frozenset({"main"})
"""Definitions the program does not reference because something outside it does.

`main` is the console entry point named in `pyproject.toml`. Each entry is a claim that
something outside the source calls this, and it should be checkable by opening that thing.
"""


def _public_definitions(trees: dict[pathlib.Path, ast.Module]) -> dict[str, str]:
    """Public functions and classes, and the file each is defined in.

    A decorated definition is excluded: a decorator is a reference, and it is how every CLI
    command is registered.
    """
    found: dict[str, str] = {}
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and not node.name.startswith("_")
                and not node.decorator_list
            ):
                found.setdefault(node.name, path.name)
    return found


def _every_name_the_source_mentions(trees: dict[pathlib.Path, ast.Module]) -> set[str]:
    """Every identifier the source refers to, by any of the four routes it uses.

    String constants count, because `getattr(converter, "furniture_dropped", 0)` is a real
    reference and reading only the syntax would call it dead.
    """
    mentioned: set[str] = set()
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                mentioned.add(node.id)
            elif isinstance(node, ast.Attribute):
                mentioned.add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                mentioned.add(node.value)
            elif isinstance(node, ast.alias):
                mentioned.add(node.asname or node.name.rsplit(".", 1)[-1])
    return mentioned


def test_nothing_public_is_defined_that_only_a_test_reaches() -> None:
    """A capability the program never touches is a capability its users do not have.

    This found two on the day it was written. `AskingJudge` - the judge of readings from
    ADR-053, graded and published with a table - was constructed by nothing: no command, no
    flag, no configuration, so nobody could run it. And `require` was dead while its module
    docstring said the execution path used it *"so an ignored return value can never become
    an unnoticed grant"* (ADR-058).
    """
    trees = _sources()
    mentioned = _every_name_the_source_mentions(trees)
    orphaned = sorted(
        f"{name} ({where})"
        for name, where in _public_definitions(trees).items()
        if name not in mentioned and name not in CALLED_FROM_OUTSIDE
    )
    assert not orphaned, (
        "Defined in the source and referred to nowhere in it: "
        + ", ".join(orphaned)
        + ". Either the program cannot reach it, or something outside calls it and belongs "
        "in CALLED_FROM_OUTSIDE with a reason."
    )


PAIRED = (("check_answer", "without_repeats"),)
"""Calls that must appear together, as `(call, what must accompany it)`.

Not a general rule about the language - a short, argued list. `check_answer` turns an answer
into checked claims, and every one of those reaches a person or a corpus, so every one must
have its repeats dropped (ADR-054). That held on one of the four call sites for a year,
because ADR-045 wrote the rule in terms of *how* a repeat arises rather than what it costs
(ADR-058).

A pair belongs here when the same reasoning applies at every site, so a new site that forgets
it is a defect rather than a choice. Adding one is an argument; it is not a style rule.
"""


def _functions_containing(trees: dict[pathlib.Path, ast.Module], call: str) -> list[ast.AST]:
    """Every function body in which ``call`` is called.

    Functions only. A whole module would satisfy the pairing whenever the companion appears
    anywhere in it, which is weaker than the question being asked - and there are no
    top-level calls here for that looseness to buy anything.
    """
    holders: list[ast.AST] = []
    for tree in trees.values():
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Name)
                    and inner.func.id == call
                ):
                    holders.append(node)
                    break
    return holders


def _calls_in(node: ast.AST) -> set[str]:
    return {
        inner.func.id
        for inner in ast.walk(node)
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
    }


def test_controls_that_must_travel_together_do() -> None:
    """A control applied at three of four call sites is not a control, it is a habit.

    The reachability checks above ask whether something can be reached at all. This asks the
    narrower question that caught deduplication: wherever this happens, does that happen too?
    """
    trees = _sources()
    missing: list[str] = []
    for call, companion in PAIRED:
        for holder in _functions_containing(trees, call):
            if companion not in _calls_in(holder):
                where = getattr(holder, "name", "<module level>")
                missing.append(f"{call} in {where}() without {companion}")
    assert not missing, (
        "These call sites break a pairing the records rely on: "
        + "; ".join(sorted(missing))
        + ". Either call it, or argue the pair out of PAIRED."
    )


def test_the_pairing_check_notices_a_site_that_forgets() -> None:
    """Guards the guard, the way the reachability check guards itself.

    Deduplication as it stood: one function pairing correctly, another calling `check_answer`
    alone. The check must name the second and not the first.
    """
    both, alone = "in_passes", "ordinary"
    source = ast.parse(
        "def "
        + both
        + "():"
        + chr(10)
        + "    return without_repeats(check_answer(a, b))"
        + chr(10)
        + "def "
        + alone
        + "():"
        + chr(10)
        + "    return check_answer(a, b)"
        + chr(10)
    )
    trees = {pathlib.Path("cycle.py"): source}
    forgetful = [
        node
        for node in _functions_containing(trees, "check_answer")
        if "without_repeats" not in _calls_in(node)
    ]
    assert [getattr(node, "name", "") for node in forgetful] == [alone]
