"""Bringing one named file into the workspace (ADR-111).

The one command that reads outside the workspace, so these tests are about its width as much
as its work: one file, shown before it is read, copied beside nothing it could replace, and
recorded - and refused for anything else.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from local_ai_control_center import cli
from local_ai_control_center.cli import app, main
from local_ai_control_center.core.drafts import BROUGHT, DRAFTS, drafts_in
from local_ai_control_center.features.bring import (
    MOST_BYTES,
    copy_name,
    not_on_this_machine,
    noted,
    on_the_network,
    refusal,
)
from local_ai_control_center.features.stages import stages_in
from local_ai_control_center.system.profiler import drive_is_remote

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
    assert writing.done == "1 draft brought in", "the count and its word agree (ADR-120)"
    assert "none of them reviewed" in writing.missing


# --- the file named is the file read (ADR-112) -------------------------------------------------


def test_arguments_reach_lacc_as_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Windows, Click would match `[1]`, `*` and `?` against the folder and expand `%VAR%`."""
    seen: dict[str, Any] = {}
    monkeypatch.setattr(cli, "app", lambda **kwargs: seen.update(kwargs))
    main()
    assert seen == {"windows_expand_args": False}


@pytest.mark.skipif(sys.platform != "win32", reason="the expansion exists only on Windows")
def test_brackets_in_a_name_are_the_name_not_a_pattern(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The case the tester found: beside `cap 1.md`, `cap [1].md` proposed to read the other."""
    config, _, outside = _workspace(tmp_path)
    (outside / "cap 1.md").write_text("otro" + chr(10), encoding="utf-8")
    named = outside / "cap [1].md"
    named.write_text("este" + chr(10), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lacc", "bring", str(named), "-c", str(config)])
    monkeypatch.setattr(sys, "stdin", io.StringIO("n" + chr(10)))
    with pytest.raises(SystemExit) as ended:
        main()
    said = " ".join(capsys.readouterr().out.split())
    assert ended.value.code in (0, None)
    assert "cap [1].md" in said
    assert "cap 1.md" not in said


def test_the_shapes_of_a_share_are_known_by_their_text() -> None:
    assert on_the_network(chr(92) * 2 + r"archivos\tesis\03.md")
    assert on_the_network("//archivos/tesis/03.md")
    assert on_the_network(chr(92) * 2 + r"?\UNC\archivos\tesis\03.md")
    assert on_the_network(chr(92) * 2 + r".\unc\archivos\tesis\03.md")
    assert not on_the_network(r"C:\Users\Aleja\tesis\03.md")
    assert not on_the_network(chr(92) * 2 + r"?\C:\Users\Aleja\tesis\03.md")
    assert not on_the_network("tesis/03.md")


def test_a_drive_on_this_machine_is_not_remote(tmp_path: Path) -> None:
    assert drive_is_remote(str(tmp_path)) is False
    assert drive_is_remote("//archivos/tesis/03.md") is False


@pytest.mark.skipif(sys.platform != "win32", reason="a share is a Windows path")
def test_a_share_is_refused_before_anything_asks_about_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the network off or on: bring reads files on this machine, and asking reaches it."""
    config, workspace, _ = _workspace(tmp_path)
    asked: list[str] = []
    resolve = Path.resolve

    def watched(self: Path, strict: bool = False) -> Path:
        asked.append(str(self))
        return resolve(self, strict)

    monkeypatch.setattr(Path, "resolve", watched)
    for shared in (chr(92) * 2 + r"archivos.invalid\tesis\03.md", "//archivos.invalid/tesis/03.md"):
        result = runner.invoke(app, ["bring", shared, "-c", str(config)], input="y\n")
        assert result.exit_code == 1
        assert "is on another machine" in " ".join(result.stdout.split())
        assert "Bring it?" not in result.stdout
    assert [path for path in asked if "archivos.invalid" in path] == []
    assert _trail(workspace) == []


def test_a_drive_windows_calls_remote_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, workspace, outside = _workspace(tmp_path)
    monkeypatch.setattr(cli, "drive_is_remote", lambda path: True)
    source = outside / "03 Metodología.md"
    result = runner.invoke(app, ["bring", str(source), "-c", str(config)], input="y\n")
    assert result.exit_code == 1
    assert "is on another machine" in " ".join(result.stdout.split())
    assert drafts_in(workspace) == ()
    assert "never a file share" in not_on_this_machine("Z:/03.md")


def test_a_missing_file_is_called_missing_and_a_folder_a_folder(tmp_path: Path) -> None:
    assert "There is no file at" in refusal(Path("vault/no.md"), False, None, exists=False)
    assert "never a folder" in refusal(Path("vault"), False, None, exists=True)
    config, _, outside = _workspace(tmp_path)
    result = runner.invoke(app, ["bring", str(outside / "no.md"), "-c", str(config)], input="y\n")
    assert result.exit_code == 1
    said = " ".join(result.stdout.split())
    assert "There is no file at" in said and "never a folder" not in said


def test_a_name_with_brackets_is_shown_as_it_is(tmp_path: Path) -> None:
    """Rich reads `[v2]` as a style: the preview dropped it, and the command it suggested failed."""
    config, workspace, outside = _workspace(tmp_path)
    named = outside / "Metodología [v2].md"
    named.write_text("Una versión." + chr(10), encoding="utf-8")
    result = runner.invoke(app, ["bring", str(named), "-c", str(config)], input="y\n")
    assert result.exit_code == 0, result.stdout
    said = " ".join(result.stdout.split())
    assert "Metodología [v2].md" in said
    assert 'lacc review "drafts/Metodología [v2] (' in said
    assert [copy.name.startswith("Metodología [v2] (") for copy in drafts_in(workspace)] == [True]


def test_a_pattern_is_not_a_file_bring_will_read(tmp_path: Path) -> None:
    """`capit*.md` was accepted when it matched one file. Now it is a name, and nothing has it."""
    config, workspace, outside = _workspace(tmp_path)
    result = runner.invoke(app, ["bring", str(outside / "03*.md"), "-c", str(config)], input="y\n")
    assert result.exit_code == 1
    said = " ".join(result.stdout.split())
    assert "There is no file at" in said and "not patterns" in said
    assert drafts_in(workspace) == ()
