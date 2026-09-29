"""Bringing one named file into the workspace (ADR-111).

The one command that reads outside the workspace, so these tests are about its width as much
as its work: one file, shown before it is read, copied beside nothing it could replace, and
recorded - and refused for anything else.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from local_ai_control_center.cli import app
from local_ai_control_center.core.drafts import BROUGHT, DRAFTS, drafts_in
from local_ai_control_center.features.bring import MOST_BYTES, copy_name, noted, refusal
from local_ai_control_center.features.stages import stages_in

runner = CliRunner()
TODAY = date(2026, 9, 29)


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A configuration, its workspace, and a folder outside it holding a chapter."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "vault"
    outside.mkdir()
    (outside / "03 Metodología.md").write_text(
        "La destilación de conocimiento transfiere lo que aprendió el profesor." + chr(10),
        encoding="utf-8",
    )
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}{chr(10)}", encoding="utf-8")
    return config, workspace, outside


def _trail(workspace: Path) -> list[dict[str, Any]]:
    log = workspace / "audit.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]


# --- what may be brought, decided before anything is read ------------------------------------


def test_one_markdown_file_outside_may_be_brought() -> None:
    assert refusal(Path("vault/03.md"), inside=False, size=1_000) == ""


def test_a_file_already_inside_is_used_where_it_is() -> None:
    assert "already in the workspace" in refusal(Path("ws/03.md"), inside=True, size=1_000)


def test_a_folder_is_never_brought() -> None:
    """Never a folder, never a pattern: the exception is one path wide."""
    assert "not a file" in refusal(Path("vault"), inside=False, size=None)


def test_a_kind_of_file_lacc_cannot_read_is_refused() -> None:
    assert "cannot read" in refusal(Path("vault/03.rtf"), inside=False, size=1_000)


def test_something_the_size_of_a_library_is_refused() -> None:
    assert "MB" in refusal(Path("vault/all.pdf"), inside=False, size=MOST_BYTES + 1)


def test_a_copy_is_named_after_the_file_and_the_day() -> None:
    assert copy_name(Path("vault/03 Metodología.md"), set(), TODAY) == (
        "03 Metodología (2026-09-29).md"
    )


def test_a_second_copy_the_same_day_is_numbered_never_replacing_the_first() -> None:
    taken = {"03.md", "03 (2026-09-29).md", "03 (2026-09-29) 2.md"}
    assert copy_name(Path("vault/03.md"), taken, TODAY) == "03 (2026-09-29) 3.md"


def test_the_note_beside_a_copy_says_where_it_came_from() -> None:
    said = json.loads(noted(Path("C:/vault/03.md"), TODAY, "ab" * 32))
    assert said == {
        "source": str(Path("C:/vault/03.md")),
        "brought_on": "2026-09-29",
        "sha256": "ab" * 32,
    }


def test_only_copies_that_say_where_they_came_from_are_drafts(tmp_path: Path) -> None:
    """A file put in the folder by hand was not brought, and is not counted as if it were."""
    folder = tmp_path / DRAFTS
    folder.mkdir()
    (folder / "brought.md").write_text("x", encoding="utf-8")
    (folder / ("brought.md" + BROUGHT)).write_text("{}", encoding="utf-8")
    (folder / "by hand.md").write_text("y", encoding="utf-8")
    assert [path.name for path in drafts_in(tmp_path)] == ["brought.md"]
    assert drafts_in(tmp_path / "nowhere") == ()


# --- the command ------------------------------------------------------------------------------


def test_bring_copies_the_named_file_in_and_leaves_the_original_alone(tmp_path: Path) -> None:
    config, workspace, outside = _workspace(tmp_path)
    source = outside / "03 Metodología.md"
    before = source.read_bytes()
    result = runner.invoke(app, ["bring", str(source), "-c", str(config)], input="y\n")
    assert result.exit_code == 0, result.stdout
    said = " ".join(result.stdout.split())
    assert "Would read" in said and "Bring it? [y/N]" in said
    copies = drafts_in(workspace)
    assert len(copies) == 1
    assert copies[0].name.startswith("03 Metodología (") and copies[0].suffix == ".md"
    assert copies[0].read_bytes() == before
    assert source.read_bytes() == before, "the original is read, never written"
    note = json.loads(copies[0].with_name(copies[0].name + BROUGHT).read_text(encoding="utf-8"))
    assert note["source"] == str(source.resolve())
    assert note["sha256"] == hashlib.sha256(before).hexdigest()


def test_what_bring_read_and_wrote_is_in_the_trail(tmp_path: Path) -> None:
    config, workspace, outside = _workspace(tmp_path)
    source = outside / "03 Metodología.md"
    runner.invoke(app, ["bring", str(source), "-c", str(config)], input="y\n")
    trail = _trail(workspace)
    kinds = [record["kind"] for record in trail]
    assert kinds == ["run_started", "files_read", "file_written", "file_written", "run_finished"]
    read = trail[1]["detail"]["files"][0]
    assert read["path"] == str(source.resolve())
    assert read["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_no_reads_nothing_and_says_so_in_the_trail(tmp_path: Path) -> None:
    """Before the yes only the size is read; after a no, nothing of it at all."""
    config, workspace, outside = _workspace(tmp_path)
    result = runner.invoke(
        app, ["bring", str(outside / "03 Metodología.md"), "-c", str(config)], input="\n"
    )
    assert result.exit_code == 0, result.stdout
    assert drafts_in(workspace) == ()
    assert not (workspace / DRAFTS).exists()
    assert [record["kind"] for record in _trail(workspace)] == [
        "run_started",
        "confirmation_declined",
    ]


def test_a_folder_is_refused_before_anything_is_asked(tmp_path: Path) -> None:
    config, workspace, outside = _workspace(tmp_path)
    result = runner.invoke(app, ["bring", str(outside), "-c", str(config)], input="y\n")
    assert result.exit_code == 1
    assert "not a file" in " ".join(result.stdout.split())
    assert "Bring it?" not in result.stdout
    assert _trail(workspace) == []


def test_a_file_already_in_the_workspace_is_not_copied_into_it(tmp_path: Path) -> None:
    config, workspace, _ = _workspace(tmp_path)
    inside = workspace / "notes.md"
    inside.write_text("mine" + chr(10), encoding="utf-8")
    result = runner.invoke(app, ["bring", str(inside), "-c", str(config)], input="y\n")
    assert result.exit_code == 1
    assert "already in the workspace" in " ".join(result.stdout.split())
    assert drafts_in(workspace) == ()


def test_bringing_the_same_chapter_twice_keeps_both(tmp_path: Path) -> None:
    config, workspace, outside = _workspace(tmp_path)
    source = outside / "03 Metodología.md"
    runner.invoke(app, ["bring", str(source), "-c", str(config)], input="y\n")
    source.write_text("Una versión más nueva." + chr(10), encoding="utf-8")
    runner.invoke(app, ["bring", str(source), "-c", str(config)], input="y\n")
    copies = drafts_in(workspace)
    assert len(copies) == 2
    assert {copy.read_text(encoding="utf-8").strip() for copy in copies} == {
        "La destilación de conocimiento transfiere lo que aprendió el profesor.",
        "Una versión más nueva.",
    }


def test_status_counts_what_was_brought_and_names_the_way_in(tmp_path: Path) -> None:
    config, workspace, outside = _workspace(tmp_path)
    empty = next(stage for stage in stages_in(workspace).stages if stage.name == "Writing")
    assert "lacc bring" in empty.missing
    runner.invoke(
        app, ["bring", str(outside / "03 Metodología.md"), "-c", str(config)], input="y\n"
    )
    writing = next(stage for stage in stages_in(workspace).stages if stage.name == "Writing")
    assert writing.done == "1 drafts brought in"
    assert "none of them reviewed" in writing.missing
