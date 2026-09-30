"""Every run the trail opens has an end (ADR-116).

ADR-107 promised that a run is recorded however it ends, a no included. The test of 29
September found the ways it still was not: a question interrupted with Ctrl+C or the end of the
input left the run open, a refusal `measure` met before the cycle was never recorded, and a
writer that waited for its turn stamped a time earlier than the record before it.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from local_ai_control_center import cli
from local_ai_control_center.cli import app
from local_ai_control_center.system import audit

runner = CliRunner()


def _kinds(workspace: Path) -> list[str]:
    log = workspace / "audit.jsonl"
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return [json.loads(line)["kind"] for line in lines if line]


def _functions_calling(tree: ast.AST, owner: str, attribute: str) -> list[str]:
    """The functions that call ``owner.attribute(...)``, by name."""
    found: list[str] = []
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == attribute
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == owner
            ):
                found.append(function.name)
                break
    return found


def test_every_question_goes_through_the_one_that_answers_an_interruption() -> None:
    """A prompt that is not `_asked` is one whose Ctrl+C can leave a run open."""
    tree = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    assert _functions_calling(tree, "typer", "confirm") == ["_asked"]


def test_an_interrupted_question_is_taken_as_no_and_the_run_ends(tmp_path: Path) -> None:
    """The end of the input at `Bring it?` raised past the path that records a no."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "boveda"
    outside.mkdir()
    (outside / "03.md").write_text("Un capítulo." + chr(10), encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}{chr(10)}", encoding="utf-8")
    result = runner.invoke(app, ["bring", str(outside / "03.md"), "-c", str(config)], input="")
    assert result.exit_code == 0, result.stdout
    assert "Interrupted: taken as no." in result.stdout
    assert _kinds(workspace) == ["run_started", "confirmation_declined"]


def test_a_refusal_measure_meets_before_the_cycle_is_in_the_trail(tmp_path: Path) -> None:
    """`run` and `ask` record `run_refused` through the cycle; `measure` recorded nothing."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}{chr(10)}", encoding="utf-8")
    result = runner.invoke(
        app,
        ["measure", "summarize_file", "../fuera.txt", "-c", str(config), "--provider", "mock"],
    )
    assert result.exit_code == 1
    assert "Refused" in result.stdout
    assert _kinds(workspace) == ["run_started", "run_refused"]


def test_a_record_takes_its_time_in_its_turn() -> None:
    """Taken before the turn, a writer that waited stamped an earlier time than the record it
    followed: 48 of 607 steps went backwards with four writers. The event, and so its time, is
    made inside `with _turn(...)`."""
    tree = ast.parse(Path(audit.__file__).read_text(encoding="utf-8"))
    record = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "record"
    )
    turns = [
        node
        for node in ast.walk(record)
        if isinstance(node, ast.With)
        and any(
            isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Name)
            and item.context_expr.func.id == "_turn"
            for item in node.items
        )
    ]
    assert len(turns) == 1
    made: list[Any] = [
        node
        for node in ast.walk(record)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AuditEvent"
    ]
    inside = {id(node) for node in ast.walk(turns[0])}
    assert made and all(id(node) in inside for node in made)
