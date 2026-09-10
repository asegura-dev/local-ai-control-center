"""Tests for the execution preview: what it reports and what it must not do."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from local_ai_control_center.config import Config
from local_ai_control_center.permissions import Permissions
from local_ai_control_center.preview import IntendedAction, preview_action
from local_ai_control_center.workspace import Workspace


def _setup(tmp_path: Path, **config_kwargs: object) -> tuple[Config, Workspace]:
    workspace = Workspace.ensure(tmp_path)
    config = Config(workspace_root=tmp_path, **config_kwargs)  # type: ignore[arg-type]
    return config, workspace


def test_allowed_when_capabilities_are_granted(tmp_path: Path) -> None:
    """An action whose requirements are met would run."""
    config, workspace = _setup(tmp_path)
    action = IntendedAction(
        name="summarize",
        summary="Summarize a file",
        required=frozenset({"read_files"}),
    )
    result = preview_action(action, Permissions(read_files=True), config, workspace)
    assert result.allowed is True
    assert result.missing_capabilities == ()
    assert result.out_of_bounds == ()


def test_refused_when_capability_is_missing(tmp_path: Path) -> None:
    """A missing capability is reported by name."""
    config, workspace = _setup(tmp_path)
    action = IntendedAction(
        name="write-report",
        summary="Write a report",
        required=frozenset({"write_files"}),
    )
    result = preview_action(action, Permissions(), config, workspace)
    assert result.allowed is False
    assert result.missing_capabilities == ("write_files",)


def test_refused_when_target_escapes_the_workspace(tmp_path: Path) -> None:
    """A target outside the boundary is reported."""
    config, workspace = _setup(tmp_path / "ws")
    outside = tmp_path / "elsewhere" / "file.txt"
    action = IntendedAction(name="read", summary="Read a file", targets=(outside,))
    result = preview_action(action, Permissions(), config, workspace)
    assert result.allowed is False
    assert result.out_of_bounds == (outside,)


def test_inside_targets_are_not_reported(tmp_path: Path) -> None:
    """A target within the workspace raises no boundary complaint."""
    config, workspace = _setup(tmp_path)
    action = IntendedAction(
        name="read",
        summary="Read a file",
        targets=(tmp_path / "sub" / "file.txt",),
    )
    result = preview_action(action, Permissions(), config, workspace)
    assert result.out_of_bounds == ()
    assert result.allowed is True


def test_both_refusal_reasons_are_reported_together(tmp_path: Path) -> None:
    """A person sees every problem at once, not one per round trip."""
    config, workspace = _setup(tmp_path / "ws")
    outside = tmp_path / "elsewhere" / "file.txt"
    action = IntendedAction(
        name="export",
        summary="Write outside the workspace",
        required=frozenset({"write_files"}),
        targets=(outside,),
    )
    result = preview_action(action, Permissions(), config, workspace)
    assert result.allowed is False
    assert result.missing_capabilities == ("write_files",)
    assert result.out_of_bounds == (outside,)


def test_configuration_ceiling_applies_to_previews(tmp_path: Path) -> None:
    """A capability the configuration forbids shows as missing in the preview."""
    config, workspace = _setup(tmp_path, network_access=False)
    action = IntendedAction(
        name="fetch",
        summary="Fetch something",
        required=frozenset({"network"}),
    )
    result = preview_action(action, Permissions(network=True), config, workspace)
    assert result.allowed is False
    assert result.missing_capabilities == ("network",)


def test_action_requiring_nothing_is_allowed(tmp_path: Path) -> None:
    """An action with no requirements and no targets would run."""
    config, workspace = _setup(tmp_path)
    action = IntendedAction(name="noop", summary="Do nothing")
    result = preview_action(action, Permissions(), config, workspace)
    assert result.allowed is True


def test_preview_writes_nothing(tmp_path: Path) -> None:
    """Building a preview creates no files: it has no side effects."""
    config, workspace = _setup(tmp_path)
    before = set(tmp_path.iterdir())
    action = IntendedAction(
        name="write-report",
        summary="Write a report",
        required=frozenset({"write_files"}),
        targets=(tmp_path / "report.txt",),
    )
    preview_action(action, Permissions(write_files=True), config, workspace)
    assert set(tmp_path.iterdir()) == before


def test_render_shows_the_action_and_status(tmp_path: Path) -> None:
    """The rendered block names the action and says it would run."""
    config, workspace = _setup(tmp_path)
    action = IntendedAction(name="summarize", summary="Summarize a file")
    rendered = preview_action(action, Permissions(), config, workspace).render()
    assert "summarize" in rendered
    assert "Summarize a file" in rendered
    assert "would run" in rendered


def test_render_explains_a_refusal(tmp_path: Path) -> None:
    """A refused preview renders the reason."""
    config, workspace = _setup(tmp_path)
    action = IntendedAction(
        name="write-report",
        summary="Write a report",
        required=frozenset({"write_files"}),
    )
    rendered = preview_action(action, Permissions(), config, workspace).render()
    assert "would be refused" in rendered
    assert "write_files" in rendered


def test_action_is_frozen() -> None:
    """An intended action cannot be mutated after creation."""
    action = IntendedAction(name="x", summary="y")
    with pytest.raises(ValidationError):
        action.name = "changed"  # type: ignore[misc]


def _reading(tmp_path: Path) -> IntendedAction:
    return IntendedAction(
        name="summarize_file",
        summary="Summarize notes.txt",
        required=frozenset({"read_files"}),
        targets=(tmp_path / "notes.txt",),
    )


def test_a_remote_engine_is_named_before_anyone_confirms(tmp_path: Path) -> None:
    """The fact the confirmation screen used to omit: the document is leaving the machine.

    Every guarantee around it still held - the host is named in a file the user wrote, and
    the run is audited - but a control nobody can see is a control nobody exercises.
    """
    config, workspace = _setup(tmp_path, network_access=True, engine_host="http://desk:11434")
    preview = preview_action(
        _reading(tmp_path),
        Permissions(read_files=True),
        config,
        workspace,
        config.remote_engine,
    )
    assert preview.sends_to == "http://desk:11434"
    assert "Sends:" in preview.render()
    assert "http://desk:11434" in preview.render()


def test_an_engine_on_this_machine_adds_no_line(tmp_path: Path) -> None:
    """Absence carries meaning: no destination shown means nothing leaves the computer.

    A line that appears on every run is a line nobody reads, which would defeat it.
    """
    config, workspace = _setup(tmp_path, engine_host="http://127.0.0.1:11434")
    preview = preview_action(
        _reading(tmp_path),
        Permissions(read_files=True),
        config,
        workspace,
        config.remote_engine,
    )
    assert preview.sends_to == ""
    assert "Sends:" not in preview.render()


def test_the_default_configuration_names_no_destination(tmp_path: Path) -> None:
    """Nothing configured means nothing leaves, and the preview says so by silence."""
    config, workspace = _setup(tmp_path)
    preview = preview_action(
        _reading(tmp_path),
        Permissions(read_files=True),
        config,
        workspace,
        config.remote_engine,
    )
    assert "Sends:" not in preview.render()


def test_a_caller_that_sends_nothing_shows_nothing_however_the_engine_is_configured(
    tmp_path: Path,
) -> None:
    """Converting a document never contacts an engine, so it must not claim to.

    This is why the destination is passed in rather than inferred from the action:
    a guess from its capabilities would be wrong exactly here (ADR-028).
    """
    config, workspace = _setup(tmp_path, network_access=True, engine_host="http://desk:11434")
    converting = IntendedAction(
        name="ingest_document",
        summary="Convert paper.pdf",
        required=frozenset({"read_files", "write_files"}),
        targets=(tmp_path / "paper.pdf",),
        writes=(tmp_path / "paper.md",),
    )
    preview = preview_action(
        converting, Permissions(read_files=True, write_files=True), config, workspace
    )
    assert preview.sends_to == ""
    assert "Sends:" not in preview.render()
