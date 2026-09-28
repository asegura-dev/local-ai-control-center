"""A binding in the window never replaces one it did not make (ADR-096).

Tkinter's `bind` without `add` **replaces** whatever the widget already had for that event.
CustomTkinter's own widgets refuse to let that happen; a `CTkScrollableFrame` is a plain Tk
frame underneath and does not. One `bind("<Configure>", ...)` on the panel removed the
binding that told its canvas how tall the content was, and for as long as it stood the panel
had no scroll region: a full scrollbar, and a wheel with nothing to stop against at either
end. Nothing in the call said it was replacing anything, which is why every `.bind(` has to
say `add`.

`bind_all` is left out on purpose. The wheel handler replaces CustomTkinter's own two on
purpose, because with all three in place every notch would move a column twice.
"""

from __future__ import annotations

import ast
import pathlib

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src" / "local_ai_control_center"
WINDOW = [SOURCE / "window.py", *sorted((SOURCE / "views").glob("*.py"))]


def _replacing_binds(source: str, name: str) -> list[str]:
    """Every `.bind(` call in ``source`` that does not pass `add`, as `name:line`."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "bind"
            and len(node.args) < 3
            and not any(keyword.arg == "add" for keyword in node.keywords)
        ):
            found.append(f"{name}:{node.lineno}")
    return found


def test_no_binding_in_the_window_replaces_one_it_did_not_make() -> None:
    found = [
        where
        for path in WINDOW
        for where in _replacing_binds(path.read_text(encoding="utf-8"), path.name)
    ]
    assert not found, f"`.bind(` without `add` replaces the toolkit's own binding: {found}"


def test_the_check_sees_the_bind_that_emptied_the_scroll_region() -> None:
    """The exact line from before ADR-096 is caught, and its repair is not."""
    before = 'self.right.bind("<Configure>", self._reflow)\n'
    after = 'self.right.bind("<Configure>", self._reflow, add="+")\n'
    assert _replacing_binds(before, "window.py") == ["window.py:1"]
    assert _replacing_binds(after, "window.py") == []


def test_the_wheel_handler_is_allowed_to_replace() -> None:
    """`bind_all` is not a `.bind(` call, so the deliberate replacement stays legal."""
    assert _replacing_binds('self.bind_all("<MouseWheel>", self._wheel)\n', "window.py") == []
