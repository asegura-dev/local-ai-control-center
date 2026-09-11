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
    assert {p.name for p in _modules_in("root")} == {"cycle.py", "cli.py"}
