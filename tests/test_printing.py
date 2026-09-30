"""What the terminal prints is what was written (ADR-113).

Rich reads anything shaped like `[word]` in what it prints as a style and drops it, and raises
on a stray `[/word]`. A file's name, a quotation, an error and an engine's answer are not the
program's words, so none of them may be read that way: what this program puts into a printed
line goes through `_plain`, and what it prints whole is printed with markup off.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from typer.testing import CliRunner

from local_ai_control_center import cli
from local_ai_control_center.adapters.mock import MockProvider
from local_ai_control_center.cli import app

runner = CliRunner()
CLI = Path(cli.__file__)

_PRINTERS = {"_show", "console.print", "Panel", "add_row"}
_STYLES = {"colour", "style"}
"""Variables holding a style's name, put between brackets on purpose."""
_NUMERIC_CALLS = {"len", "sum", "max", "min"}
_NUMERIC_SPEC = set("fdeg%,bxXo")
_ESCAPED = {"_plain", "escape"}
_RENDERABLES = {"table", "rendered"}
"""Names holding a Rich object the program built, printed as it is."""


def _called(node: ast.Call) -> str:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        if function.attr == "add_row":
            return "add_row"
        owner = function.value.id if isinstance(function.value, ast.Name) else ""
        return f"{owner}.{function.attr}"
    return ""


def _is_safe(part: ast.FormattedValue) -> bool:
    """Escaped, a style's name, a constant the program wrote, or a number."""
    value = part.value
    if (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id in _ESCAPED | _NUMERIC_CALLS
    ):
        return True
    if isinstance(value, ast.Name) and (value.id in _STYLES or value.id.isupper()):
        return True
    written = "".join(
        piece.value
        for piece in getattr(part.format_spec, "values", [])
        if isinstance(piece, ast.Constant)
    )
    return bool(set(written) & _NUMERIC_SPEC)


def _unescaped(tree: ast.AST) -> list[str]:
    """Every value put into a printed line without passing through `_plain`."""
    found: list[str] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if isinstance(part, ast.FormattedValue) and not _is_safe(part):
                    found.append(ast.unparse(part.value))
        elif isinstance(node, ast.IfExp):
            visit(node.body)
            visit(node.orelse)
        elif isinstance(node, ast.BinOp):
            for side in (node.left, node.right):
                if isinstance(side, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.IfExp)):
                    visit(side)
                elif not (isinstance(side, ast.Call) and _called(side) in _ESCAPED):
                    found.append(ast.unparse(side))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _called(node) in _PRINTERS:
            for argument in node.args:
                visit(argument)
    return found


def _printed_whole(tree: ast.AST) -> list[str]:
    """What is printed whole rather than as a string the program wrote, without markup off."""
    written = (ast.Constant, ast.JoinedStr, ast.IfExp, ast.BinOp)
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        kind, first = _called(node), node.args[0]
        if kind in {"_show", "console.print"}:
            if any(keyword.arg == "markup" for keyword in node.keywords):
                continue
            if isinstance(first, written):
                continue
            if isinstance(first, ast.Name) and first.id in _RENDERABLES:
                continue
            if isinstance(first, ast.Call) and _called(first) in {"Panel", "Table", "Text"}:
                continue
            found.append(ast.unparse(first))
        elif kind == "Panel":
            if isinstance(first, written) or (
                isinstance(first, ast.Name) and first.id in _RENDERABLES
            ):
                continue
            if isinstance(first, ast.Call) and _called(first) == "Text":
                continue
            found.append(ast.unparse(first))
    return found


def _cli_tree() -> ast.Module:
    return ast.parse(CLI.read_text(encoding="utf-8"))


def test_nothing_is_put_into_a_printed_line_unescaped() -> None:
    assert _unescaped(_cli_tree()) == []


def test_nothing_the_program_did_not_write_is_printed_whole_as_markup() -> None:
    assert _printed_whole(_cli_tree()) == []


def test_the_rules_catch_what_they_are_for() -> None:
    """Each zero above is worth something only if the same check fails on the defect."""
    bad = ast.parse(
        '_show(f"[red]{name}[/red]")\n'
        'console.print(f"{path}: " + ", ".join(names))\n'
        "_show(result.completion.text)\n"
        "console.print(Panel(models_text))\n"
    )
    assert _unescaped(bad) == ["name", "path", "', '.join(names)"]
    assert _printed_whole(bad) == ["result.completion.text", "models_text"]
    good = ast.parse(
        '_show(f"[{colour}]{_plain(name)}[/{colour}] {total:,} {len(x)} {DRAFTS}")\n'
        "_show(result.completion.text, markup=False)\n"
        "console.print(Panel(Text(models_text)))\n"
        "console.print(table)\n"
    )
    assert _unescaped(good) == []
    assert _printed_whole(good) == []


def test_a_stray_closing_tag_is_printed_not_raised(capsys: pytest.CaptureFixture[str]) -> None:
    """Before, `[/b]` in an engine's answer raised after the answer had arrived (ADR-062)."""
    cli._show("el modelo escribió [/b] y siguió")
    assert "el modelo escribió [/b] y siguió" in capsys.readouterr().out


def test_an_answer_is_printed_as_the_engine_wrote_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "notes.txt").write_text("A short note." + chr(10), encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}{chr(10)}", encoding="utf-8")
    answer = "Dice [v2], luego [/b] y [sic]."
    monkeypatch.setattr(MockProvider, "_derive", staticmethod(lambda prompt: answer))
    result = runner.invoke(
        app,
        ["run", "summarize_file", "notes.txt", "-c", str(config), "--provider", "mock"],
        input="y\n",
    )
    assert result.exit_code == 0, result.stdout
    assert answer in " ".join(result.stdout.split())


def test_a_name_with_brackets_is_printed_as_it_is(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "nota [v2].md").write_text("x", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}{chr(10)}", encoding="utf-8")
    result = runner.invoke(app, ["metadata", "nota [v2].md", "-c", str(config)])
    assert result.exit_code == 0, result.stdout
    assert "nota [v2].md" in result.stdout
