"""Tests that the directory layout is true, not merely described.

Five directories that mean something are five directories somebody will eventually break.
A layout enforced by a test is a layout; a layout in a document is a wish (ADR-029).
"""

from __future__ import annotations

import ast
import pathlib

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src" / "local_ai_control_center"
PACKAGE = "local_ai_control_center."


def _imports_of(path: pathlib.Path) -> set[str]:
    """Internal modules that ``path`` imports, as dotted names below the package."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.module.removeprefix(PACKAGE)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(PACKAGE)
    }


def _layer(module: str) -> str:
    """Which directory a dotted module name belongs to, or `root` for the top level."""
    parts = module.split(".")
    return parts[0] if len(parts) > 1 else "root"


def _modules_in(layer: str) -> list[pathlib.Path]:
    where = SOURCE / layer if layer != "root" else SOURCE
    pattern = "*.py" if layer == "root" else "**/*.py"
    return [p for p in sorted(where.glob(pattern)) if p.name != "__init__.py"]


def test_core_depends_on_nothing_outside_itself() -> None:
    """The load-bearing rule. Core decides things; it does not reach for anything.

    `workspace` resolves real paths, which is the one exception and is deliberate: "nothing
    outside the workspace is touched" is a rule rather than a service the core consumes
    (ADR-029).
    """
    for module in _modules_in("core"):
        for imported in _imports_of(module):
            assert _layer(imported) == "core", f"{module.name} reaches for {imported}"


def test_a_port_depends_on_nothing_outside_itself() -> None:
    """A port is an abstract class and the contracts crossing it, and nothing else.

    A port that imported an adapter would be a port with an opinion about who satisfies it.
    """
    for module in _modules_in("ports"):
        for imported in _imports_of(module):
            assert _layer(imported) == "ports", f"{module.name} reaches for {imported}"


def test_an_adapter_reaches_only_for_core_and_ports() -> None:
    """It implements a port using the rules, and knows nothing of the cycle or the CLI."""
    for module in _modules_in("adapters"):
        for imported in _imports_of(module):
            assert _layer(imported) in {"core", "ports", "adapters"}, (
                f"{module.name} reaches for {imported}"
            )


def test_nothing_in_core_imports_the_cycle() -> None:
    """The inversion this restructure existed to fix.

    `run_skill` lived in `core.skill` and called into the cycle, so the module holding the
    pure planning logic dragged in everything the cycle touches. It now lives with the other
    orchestration (ADR-029).
    """
    for module in _modules_in("core"):
        assert "cycle" not in _imports_of(module), f"{module.name} imports the cycle"


def test_every_module_lives_in_a_layer_that_has_a_meaning() -> None:
    """A file at the top level is either the application service or the driving adapter.

    Anything else there is a module nobody decided where to put.
    """
    assert {p.name for p in _modules_in("root")} <= {"cycle.py", "cli.py", "window.py"}
    assert _modules_in("features"), "features/ is a layer and is empty"


# --- The converse of the rule above (ADR-066) --------------------------------------------
#
# Every test to this point follows dependencies *inward*: core imports nothing, a port
# imports nothing, an adapter reaches only for core and ports. None of them asks whether
# logic has leaked *outward* into a view, and that is what cost ADR-065: both writers of the
# corpus format lived in `cli.py` while its reader lived in `core`, free to drift apart with
# the suite green. They drifted, and assembling a corpus twice silently stripped the meaning
# from every quotation in it.

_PRESENTATION = frozenset(
    {
        "Console",
        "_console",
        "_show",
        "Progress",
        "Panel",
        "Table",
        "Text",
        "Syntax",
        "Markdown",
        "print",
        "echo",
        "secho",
        "prompt",
        "confirm",
        "_approve",
        "_confirm",
        "style",
        # The window's vocabulary. Tk's is not Rich's, and a rule that only knew one of them
        # would pass a view it had never looked at (ADR-069).
        "CTk",
        "CTkFrame",
        "CTkLabel",
        "CTkButton",
        "CTkTextbox",
        "CTkScrollableFrame",
        "CTkFont",
        "Treeview",
        "insert",
        "configure",
        "grid",
        "pack",
        "tag_config",
        "mainloop",
        "set_appearance_mode",
        "set_default_color_theme",
        # Destroying and enumerating widgets is as much presentation as creating them, and
        # a method that only does that reaches no other name at all.
        "destroy",
        "winfo_children",
        "winfo_width",
        "clipboard_clear",
        "clipboard_append",
        "bind",
        "after",
    }
)
"""The vocabulary that makes a function part of a view.

Concrete names rather than a notion of "output", because a test that cannot be run against
the code is a wish. A helper that only formats a string for a helper that prints it is still
presentation, which is why the check takes the transitive closure over calls.

It covers **both** views. ADR-066 emptied the exception list before a second view existed,
precisely so the window would be bound by the rule from its first line - a second view
doubles whatever the first one got wrong.
"""

_VIEWS = ("cli.py", "window.py")
"""Every driving adapter, so a rule written for one cannot silently miss the other."""

_A_VIEW_MAY_HOLD = frozenset(
    {
        "main",  # the entry point
        "_build_provider",  # composition: the view is the driving adapter (ADR-029)
        "_page_range",  # parsing this view's own argument
        "_words",  # parsing this view's own argument
    }
)
"""What belongs in a view although it never prints. Each is named, never a category."""

_LOGIC_THE_VIEW_STILL_HOLDS: frozenset[str] = frozenset()
"""Logic that has not moved yet, named one by one so the rule binds on everything else.

**It is empty, and that is the point.** It began at four names after the `corpus` slice
landed and reached zero when `ask` and `measure` followed; `ask_once` went to the cycle
instead of a slice, because running an action through the whole system is orchestration and
this project has one place for that (ADR-029).

A baseline that were a *number* would let one function leave and another arrive. A list of
names cannot: anything new fails this test on the day it is written, and while this set is
empty the rule is absolute (ADR-066).
"""


def _functions_in(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    """Every function a view defines, including the methods of its classes.

    Methods were missed at first, and a window is almost entirely methods - so the rule read
    as covering `window.py` while barely touching it. Found by writing the window and then
    asking what the check had actually looked at (ADR-066).
    """
    found = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for inner in node.body:
                if isinstance(inner, ast.FunctionDef) and inner.name != "__init__":
                    found.setdefault(f"{node.name}.{inner.name}", inner)
    return found


def _touches_presentation(module: pathlib.Path) -> dict[str, bool]:
    """For each function and method, whether it reaches the view, directly or through a call."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    functions = _functions_in(tree)

    def mentioned(node: ast.AST) -> set[str]:
        found: set[str] = set()
        for inner in ast.walk(node):
            if isinstance(inner, ast.Name):
                found.add(inner.id)
            elif isinstance(inner, ast.Attribute):
                found.add(inner.attr)
        return found

    plain = {name.split(".")[-1]: name for name in functions}
    reaches = {name: bool(mentioned(fn) & _PRESENTATION) for name, fn in functions.items()}
    # A method calls another as `self.other`, which `mentioned` sees as the attribute
    # `other`. Resolving through the bare name is what lets the closure cross a class.
    calls = {
        name: {plain[called] for called in mentioned(fn) & set(plain)}
        for name, fn in functions.items()
    }
    changed = True
    while changed:  # a helper that feeds a printer is presentation too
        changed = False
        for name in functions:
            if not reaches[name] and any(reaches[called] for called in calls[name]):
                reaches[name] = True
                changed = True
    return reaches


def test_a_view_contains_no_logic() -> None:
    """A function in the view that never touches the presentation is not part of the view.

    "Logic" has no syntax; its opposite does. Run against `cli.py` before the first slice
    existed, this named twelve functions, and the first two it named were the two writers of
    the corpus format - the check derived from the defect finds the defect.
    """
    for view_name in _VIEWS:
        view = SOURCE / view_name
        if not view.exists():
            continue
        tree = ast.parse(view.read_text(encoding="utf-8"))
        commands = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.decorator_list
        }
        # A property or a cached lookup on a class is presentation by position: it belongs
        # to the widget that holds it. Only plain methods are asked about.
        commands |= {
            f"{node.name}.{inner.name}"
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            for inner in node.body
            if isinstance(inner, ast.FunctionDef) and inner.decorator_list
        }
        astray = {
            name
            for name, reaches in _touches_presentation(view).items()
            if not reaches and name not in commands
        }
        unexpected = astray - _A_VIEW_MAY_HOLD - _LOGIC_THE_VIEW_STILL_HOLDS
        assert not unexpected, (
            f"logic in {view_name}: {sorted(unexpected)}. It belongs in a slice under "
            "features/, beside whatever has to agree with it (ADR-066)."
        )


def test_the_named_debt_is_really_still_there() -> None:
    """The exception list shrinks by moving code, never by editing the list.

    Without this, a name could stay after its function left, and the list would quietly
    stop describing anything. It is the same failure as a figure whose tense has aged.
    """
    present: set[str] = set()
    for view_name in _VIEWS:
        view = SOURCE / view_name
        if view.exists():
            present |= set(_touches_presentation(view))
    gone = (_A_VIEW_MAY_HOLD | _LOGIC_THE_VIEW_STILL_HOLDS) - present
    assert not gone, f"named as exceptions but no longer in any view: {sorted(gone)}"


def test_a_slice_reaches_only_for_core_and_ports() -> None:
    """A capability uses the rules; it does not know the cycle, the view, or another slice.

    Type-only imports are not dependencies and are not counted: `features/corpus.py` names
    `RunResult`, which lives in `cycle.py` and should not, and says so in its docstring
    rather than pretending otherwise.
    """
    for module in _modules_in("features"):
        for imported in _runtime_imports_of(module):
            assert _layer(imported) in {"core", "ports"}, f"{module.name} reaches for {imported}"


def _runtime_imports_of(path: pathlib.Path) -> set[str]:
    """Internal modules imported when the program runs, ignoring `if TYPE_CHECKING` blocks."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    typing_only = {
        id(inner)
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "TYPE_CHECKING"
        for inner in ast.walk(node)
    }
    return {
        node.module.removeprefix(PACKAGE)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith(PACKAGE)
        and id(node) not in typing_only
    }
