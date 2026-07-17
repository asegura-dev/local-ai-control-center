"""Workspaces: a bounded area LACC may operate in, with an enforced boundary.

A workspace is a validated contract around a root directory (ADR-003). Its core
job is containment: `is_within` and `resolve_within` decide whether a candidate
path stays inside the workspace, resolving `..` and symlinks first so the check
cannot be tricked. Creation of the root is explicit (`ensure`), never a silent
side effect of construction.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

from local_ai_control_center.config import Config


class Workspace(BaseModel):
    """A validated workspace rooted at a resolved, existing directory.

    Frozen: once validated it does not change. The root is stored resolved
    (absolute, symlink-free) so every boundary check compares against a canonical
    location. Constructing a workspace whose root does not exist is an error; use
    :meth:`ensure` to create it explicitly.
    """

    model_config = ConfigDict(frozen=True)

    root: Path

    @field_validator("root")
    @classmethod
    def _resolve_existing_dir(cls, value: Path) -> Path:
        resolved = value.expanduser().resolve()
        if not resolved.exists():
            raise ValueError(f"Workspace root does not exist: {resolved}")
        if not resolved.is_dir():
            raise ValueError(f"Workspace root is not a directory: {resolved}")
        return resolved

    @classmethod
    def ensure(cls, root: str | Path) -> Workspace:
        """Create the root directory if missing, then return the workspace.

        This is the only path that touches the filesystem. Creation is explicit:
        it happens because the caller asked, not as a side effect of construction.
        """
        path = Path(root).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return cls(root=path)

    def is_within(self, path: str | Path) -> bool:
        """Return whether ``path`` resolves to a location inside this workspace.

        The candidate is resolved (absolute, symlink-free) before comparison, so
        ``..`` segments and symlinks pointing outside are caught, not trusted.
        """
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.expanduser().resolve()
        return resolved == self.root or self.root in resolved.parents

    def resolve_within(self, path: str | Path) -> Path:
        """Return the safe resolved path if inside the workspace, else raise.

        For callers that need the concrete path. Raises ``ValueError`` when the
        candidate resolves outside the boundary.
        """
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.expanduser().resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ValueError(f"Path escapes workspace boundary: {resolved}")
        return resolved


def workspace_from_config(config: Config) -> Workspace:
    """Build a workspace from a configuration's ``workspace_root``.

    Uses explicit creation, so a configured workspace that does not yet exist is
    created deliberately. This is the seam where configuration becomes an
    operational workspace; the core modules stay unaware of each other otherwise.
    """
    return Workspace.ensure(config.workspace_root)
