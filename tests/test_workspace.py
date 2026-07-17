"""Tests for the workspace contract and its boundary enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from local_ai_control_center.config import Config
from local_ai_control_center.workspace import Workspace, workspace_from_config


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
