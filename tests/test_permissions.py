"""Tests for the permission contract, the configuration ceiling, and checking."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from local_ai_control_center.config import Config
from local_ai_control_center.permissions import (
    CAPABILITIES,
    PermissionDenied,
    Permissions,
    check,
    effective_permissions,
    require,
)


def _config(*, network_access: bool = False) -> Config:
    return Config(workspace_root=Path("/tmp/lacc"), network_access=network_access)


def test_everything_starts_disabled() -> None:
    """An empty Permissions grants nothing."""
    assert Permissions().granted() == frozenset()


def test_granted_reports_only_what_is_enabled() -> None:
    """granted() lists exactly the enabled capabilities."""
    permissions = Permissions(read_files=True, run_commands=True)
    assert permissions.granted() == frozenset({"read_files", "run_commands"})


def test_unknown_capability_field_is_rejected() -> None:
    """An unknown capability is a validation error, not a silent grant."""
    with pytest.raises(ValidationError):
        Permissions(delete_everything=True)  # type: ignore[call-arg]


def test_permissions_are_frozen() -> None:
    """Granted permissions cannot be mutated after construction."""
    permissions = Permissions(read_files=True)
    with pytest.raises(ValidationError):
        permissions.read_files = False  # type: ignore[misc]


def test_config_ceiling_denies_network_when_disabled() -> None:
    """Network stays unavailable when the configuration forbids it."""
    permissions = Permissions(network=True)
    available = effective_permissions(permissions, _config(network_access=False))
    assert "network" not in available


def test_config_ceiling_allows_network_when_enabled() -> None:
    """Network becomes available only when both grant and config allow it."""
    permissions = Permissions(network=True)
    available = effective_permissions(permissions, _config(network_access=True))
    assert "network" in available


def test_config_ceiling_does_not_grant_what_was_not_granted() -> None:
    """Enabling network in config does not grant a capability by itself."""
    available = effective_permissions(Permissions(), _config(network_access=True))
    assert "network" not in available


def test_check_allows_when_everything_is_granted() -> None:
    """A satisfied requirement is allowed with nothing missing."""
    result = check({"read_files"}, Permissions(read_files=True), _config())
    assert result.allowed is True
    assert result.missing == ()


def test_check_reports_missing_capabilities() -> None:
    """A denied check names exactly what is missing, sorted."""
    result = check({"write_files", "read_files"}, Permissions(), _config())
    assert result.allowed is False
    assert result.missing == ("read_files", "write_files")


def test_check_reports_network_missing_under_config_ceiling() -> None:
    """A granted capability the config forbids still shows as missing."""
    result = check({"network"}, Permissions(network=True), _config(network_access=False))
    assert result.allowed is False
    assert result.missing == ("network",)


def test_check_with_no_requirements_is_allowed() -> None:
    """Requiring nothing is allowed even with no permissions."""
    result = check(set(), Permissions(), _config())
    assert result.allowed is True


def test_require_passes_when_allowed() -> None:
    """require() returns quietly when the requirement is satisfied."""
    require({"read_files"}, Permissions(read_files=True), _config())


def test_require_raises_when_denied() -> None:
    """require() raises PermissionDenied naming the missing capabilities."""
    with pytest.raises(PermissionDenied) as excinfo:
        require({"write_files"}, Permissions(), _config())
    assert "write_files" in str(excinfo.value)


def test_capabilities_tuple_matches_model_fields() -> None:
    """The capability set and the model's fields stay in sync."""
    assert set(CAPABILITIES) == set(Permissions.model_fields)
