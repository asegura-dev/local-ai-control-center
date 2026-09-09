"""Tests for the workspace contract and its boundary enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from local_ai_control_center.config import Config
from local_ai_control_center.workspace import (
    Workspace,
    WorkspaceExposed,
    repository_above,
    sync_folder_suspicion,
    workspace_from_config,
)


def test_construction_requires_existing_dir(tmp_path: Path) -> None:
    """Constructing a workspace on a missing root is an error."""
    with pytest.raises(ValidationError):
        Workspace(root=tmp_path / "does-not-exist")


def test_construction_rejects_a_file(tmp_path: Path) -> None:
    """A root that is a file, not a directory, is rejected."""
    a_file = tmp_path / "file.txt"
    a_file.write_text("x", encoding="utf-8")
    with pytest.raises(ValidationError):
        Workspace(root=a_file)


def test_ensure_creates_missing_dir(tmp_path: Path) -> None:
    """ensure() creates the root when missing and returns a workspace."""
    target = tmp_path / "new" / "workspace"
    assert not target.exists()
    workspace = Workspace.ensure(target)
    assert target.is_dir()
    assert workspace.root == target.resolve()


def test_ensure_is_idempotent(tmp_path: Path) -> None:
    """ensure() on an existing dir succeeds without error."""
    workspace = Workspace.ensure(tmp_path)
    assert workspace.root == tmp_path.resolve()


def test_is_within_accepts_inside_path(tmp_path: Path) -> None:
    """A path inside the workspace is within the boundary."""
    workspace = Workspace.ensure(tmp_path)
    assert workspace.is_within(tmp_path / "sub" / "file.txt")


def test_is_within_accepts_the_root_itself(tmp_path: Path) -> None:
    """The root path itself counts as within."""
    workspace = Workspace.ensure(tmp_path)
    assert workspace.is_within(tmp_path)


def test_is_within_rejects_parent_escape(tmp_path: Path) -> None:
    """A path using .. to climb out is rejected."""
    workspace = Workspace.ensure(tmp_path / "ws")
    assert workspace.is_within("../secret.txt") is False


def test_is_within_rejects_absolute_outside(tmp_path: Path) -> None:
    """An absolute path outside the workspace is rejected."""
    workspace = Workspace.ensure(tmp_path / "ws")
    outside = tmp_path / "elsewhere" / "file.txt"
    assert workspace.is_within(outside) is False


def test_resolve_within_returns_safe_path(tmp_path: Path) -> None:
    """resolve_within returns the resolved path when inside."""
    workspace = Workspace.ensure(tmp_path)
    resolved = workspace.resolve_within("sub/file.txt")
    assert resolved == (tmp_path / "sub" / "file.txt").resolve()


def test_resolve_within_raises_on_escape(tmp_path: Path) -> None:
    """resolve_within raises when the path escapes the boundary."""
    workspace = Workspace.ensure(tmp_path / "ws")
    with pytest.raises(ValueError):
        workspace.resolve_within("../../etc/passwd")


def test_workspace_from_config_creates_and_binds(tmp_path: Path) -> None:
    """workspace_from_config builds a workspace from the config's root."""
    target = tmp_path / "configured"
    config = Config(workspace_root=target)
    workspace = workspace_from_config(config)
    assert workspace.root == target.resolve()
    assert target.is_dir()


def test_reserved_device_names_are_refused(tmp_path: Path) -> None:
    """`NUL` swallows a write and reports success, whatever directory precedes it."""
    workspace = Workspace.ensure(tmp_path)
    for name in ("NUL", "con", "COM1", "sources/NUL", "NUL.txt"):
        assert workspace.is_within(name) is False
        with pytest.raises(ValueError):
            workspace.resolve_within(name)


def test_alternate_data_streams_are_refused(tmp_path: Path) -> None:
    """A stream no directory listing shows contradicts LACC being inspectable."""
    workspace = Workspace.ensure(tmp_path)
    assert workspace.is_within("notes.md:hidden") is False
    with pytest.raises(ValueError):
        workspace.resolve_within("notes.md:hidden")


def test_names_ending_in_a_dot_or_space_are_refused(tmp_path: Path) -> None:
    """Windows strips them before resolving, so the file written is not the file named."""
    workspace = Workspace.ensure(tmp_path)
    for name in ("notes.md.", "notes.md ", "folder./notes.md"):
        assert workspace.is_within(name) is False
        with pytest.raises(ValueError):
            workspace.resolve_within(name)


def test_ordinary_names_are_still_accepted(tmp_path: Path) -> None:
    """The new refusals are about shape, and must not catch anything ordinary."""
    workspace = Workspace.ensure(tmp_path)
    for name in ("notes.md", "sources/paper.pdf", "a.b.c/nul_notes.txt", "console.md"):
        assert workspace.is_within(name) is True
        assert workspace.resolve_within(name)


def test_a_repository_above_the_workspace_is_found(tmp_path: Path) -> None:
    """A `.git` in an ancestor is a fact, and facts are what this check reports."""
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "docs" / "thesis"
    nested.mkdir(parents=True)
    assert repository_above(nested) == tmp_path
    assert repository_above(tmp_path.parent) is None


def test_a_workspace_inside_a_repository_is_refused(tmp_path: Path) -> None:
    """Private material one `git add -A` from being published is not a warning's job."""
    (tmp_path / ".git").mkdir()
    workspace_root = tmp_path / "thesis"
    workspace_root.mkdir()
    with pytest.raises(WorkspaceExposed) as excinfo:
        workspace_from_config(Config(workspace_root=workspace_root))
    message = str(excinfo.value)
    assert "git add -A" in message
    assert "workspace_in_repository" in message


def test_the_refusal_is_lifted_by_an_explicit_acknowledgement(tmp_path: Path) -> None:
    """Sometimes it is genuinely safe, and the person who can confirm that says so."""
    (tmp_path / ".git").mkdir()
    workspace_root = tmp_path / "thesis"
    workspace_root.mkdir()
    config = Config(workspace_root=workspace_root, workspace_in_repository=True)
    assert workspace_from_config(config).root == workspace_root.resolve()


def test_a_workspace_outside_any_repository_is_built(tmp_path: Path) -> None:
    """The ordinary case stays ordinary."""
    assert workspace_from_config(Config(workspace_root=tmp_path)).root == tmp_path.resolve()


def test_a_synchronising_folder_is_reported_as_a_suspicion(tmp_path: Path) -> None:
    """A guess from a folder name, and it says so rather than sounding certain."""
    suspect = tmp_path / "OneDrive" / "thesis"
    suspect.mkdir(parents=True)
    warning = sync_folder_suspicion(suspect)
    assert warning is not None
    assert "guess" in warning
    assert "copied to somebody else" in warning


def test_an_ordinary_folder_raises_no_suspicion(tmp_path: Path) -> None:
    """The heuristic must stay quiet where there is nothing to say."""
    assert sync_folder_suspicion(tmp_path / "projects" / "thesis") is None
