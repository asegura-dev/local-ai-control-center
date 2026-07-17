"""Tests for the core configuration contract and its YAML loader."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from local_ai_control_center.config import Config, load_config


def test_defaults_are_safe() -> None:
    """Network access is off by default; audit level is standard."""
    config = Config(workspace_root=Path("/tmp/lacc"))
    assert config.network_access is False
    assert config.audit_level == "standard"


def test_workspace_root_is_required() -> None:
    """Omitting workspace_root is a validation error (no universal default)."""
    with pytest.raises(ValidationError):
        Config()  # type: ignore[call-arg]


def test_unknown_field_is_rejected() -> None:
    """An unknown field fails loudly instead of being ignored."""
    with pytest.raises(ValidationError):
        Config(workspace_root=Path("/tmp/lacc"), unknown_field=True)  # type: ignore[call-arg]


def test_invalid_audit_level_is_rejected() -> None:
    """audit_level outside the closed set is rejected at the boundary."""
    with pytest.raises(ValidationError):
        Config(workspace_root=Path("/tmp/lacc"), audit_level="verbose")  # type: ignore[arg-type]


def test_config_is_frozen() -> None:
    """A validated config cannot be mutated afterwards."""
    config = Config(workspace_root=Path("/tmp/lacc"))
    with pytest.raises(ValidationError):
        config.network_access = True  # type: ignore[misc]


def test_load_config_reads_yaml(tmp_path: Path) -> None:
    """A well-formed YAML file loads into a validated Config."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "network_access: true\naudit_level: full\nworkspace_root: /data/lacc\n",
        encoding="utf-8",
    )
    config = load_config(config_file)
    assert config.network_access is True
    assert config.audit_level == "full"
    assert config.workspace_root == Path("/data/lacc")


def test_load_config_absent_field_takes_default(tmp_path: Path) -> None:
    """A field absent from the file takes its default (network stays off)."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("workspace_root: /data/lacc\n", encoding="utf-8")
    config = load_config(config_file)
    assert config.network_access is False


def test_load_config_rejects_non_mapping(tmp_path: Path) -> None:
    """A YAML file that is not a mapping fails with a clear error."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(config_file)
