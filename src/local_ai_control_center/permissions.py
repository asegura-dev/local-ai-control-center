"""Permissions: what a skill is allowed to do, restrictive by default.

Every capability starts disabled (ADR-004). A skill declares what it needs, and a
check decides whether that is granted, with the configuration acting as a ceiling:
what the configuration forbids, no permission can grant. Checking returns a result
so a preview can report what is missing; `require` raises for the execution path.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.config import Config

Capability = Literal["read_files", "write_files", "network", "run_commands"]
"""The closed set of things a skill can ask for. Unknown values fail validation."""

CAPABILITIES: tuple[Capability, ...] = get_args(Capability)
"""All capabilities, for iteration and display."""


class PermissionDenied(Exception):
    """Raised when required capabilities are not available."""


class Permissions(BaseModel):
    """Capabilities granted to a skill. Everything starts disabled.

    Frozen: once built it does not change. An empty ``Permissions()`` grants
    nothing, which is the restrictive-by-default stance made concrete.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    read_files: bool = False
    write_files: bool = False
    network: bool = False
    run_commands: bool = False

    def granted(self) -> frozenset[Capability]:
        """Return the set of capabilities this object grants."""
        return frozenset(cap for cap in CAPABILITIES if getattr(self, cap))


class PermissionCheck(BaseModel):
    """The outcome of a permission check.

    ``allowed`` is True only when nothing is missing. ``missing`` lists the
    capabilities that were required but not available, sorted for stable display.
    """

    model_config = ConfigDict(frozen=True)

    allowed: bool
    missing: tuple[Capability, ...] = ()


def effective_permissions(permissions: Permissions, config: Config) -> frozenset[Capability]:
    """Return the capabilities actually available.

    The intersection of what the permissions grant and what the configuration
    allows. The configuration is a ceiling: with ``network_access`` off, the
    ``network`` capability is unavailable however the permissions are set.
    """
    available = set(permissions.granted())
    if not config.network_access:
        available.discard("network")
    return frozenset(available)


def check(
    required: frozenset[Capability] | set[Capability],
    permissions: Permissions,
    config: Config,
) -> PermissionCheck:
    """Decide whether ``required`` is available, reporting what is missing.

    Returns a result rather than raising so callers building an execution preview
    can show precisely which capabilities are denied.
    """
    available = effective_permissions(permissions, config)
    missing = tuple(sorted(set(required) - available))
    return PermissionCheck(allowed=not missing, missing=missing)


def require(
    required: frozenset[Capability] | set[Capability],
    permissions: Permissions,
    config: Config,
) -> None:
    """Raise :class:`PermissionDenied` unless every required capability is available.

    The execution path uses this form so an ignored return value can never become
    an unnoticed grant.
    """
    result = check(required, permissions, config)
    if not result.allowed:
        raise PermissionDenied(f"Missing required capabilities: {', '.join(result.missing)}")
