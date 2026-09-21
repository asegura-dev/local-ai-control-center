"""How the window looks, and what it remembers between openings (ADR-069).

**A separate file from the configuration, on purpose.** `Config` declares what LACC may do -
which model, which host, whether anything may leave the machine - and it is frozen and
validated with `extra="forbid"` so that a typo is an error rather than a silent default. A
colour has no business in it.

The split is also a rule about who may write what. **These preferences are the window's own
and the window may save them**; the configuration is the user's and is edited in the file
they wrote, with the same preview and confirmation everything else here gets. A window that
quietly rewrote `model:` would be a window deciding what runs.

Themes are data. A palette named here can be replaced by one written in the YAML, because
somebody who wants their own colours should not need a release.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

WINDOW_PREFERENCES = ".lacc-window.yaml"
"""Where the window keeps its own settings, hidden inside the workspace.

Hidden because they are not the user's documents and should not be listed among
them, and inside the workspace because they belong to that workspace: a different
one is a different set of papers and may well want a different theme.
"""


class Palette(BaseModel):
    """The colours a window is drawn with."""

    model_config = ConfigDict(frozen=True)

    mode: str = "dark"
    """What CustomTkinter calls it: `dark`, `light` or `system`."""

    ink: str = "#e6e9ef"
    dim: str = "#8a9199"
    faint: str = "#6b727a"
    rail: str = "#202225"
    side: str = "#1d1e21"
    surface: str = "#1a1b1e"
    card: str = "#26282c"
    accent: str = "#5b8dd6"

    supported: str = "#4a8a5c"
    contradicted: str = "#c1554a"
    uncovered: str = "#b08040"
    """Amber for uncovered, never red: uncovered is not false, and a colour that said
    otherwise would teach a reader to distrust correct sentences (ADR-068)."""

    def for_verdict(self, verdict: str) -> str:
        """The colour a finding is painted in.

        Here rather than in the window because which colour means which verdict is a
        decision - the amber above is an argument, not a preference - and a view that made
        it would be a view containing logic (ADR-066).
        """
        return {
            "contradicted": self.contradicted,
            "supported": self.supported,
            "nothing": self.uncovered,
        }.get(verdict, self.faint)


THEMES: dict[str, Palette] = {
    "slate": Palette(),
    "carbon": Palette(
        rail="#161719", side="#131416", surface="#0f1011", card="#1c1d20", accent="#7aa2e3"
    ),
    "parchment": Palette(
        mode="light",
        ink="#20242b",
        dim="#5a6169",
        faint="#868d95",
        rail="#e9e5dd",
        side="#f2efe9",
        surface="#faf8f4",
        card="#ffffff",
        accent="#3a6ea5",
        supported="#2f6b46",
        contradicted="#a33c33",
        uncovered="#8a6320",
    ),
}
"""Three to start from. A palette in the file replaces one of these by name."""


class Preferences(BaseModel):
    """What the window remembers: how it looks and where it was last pointed."""

    model_config = ConfigDict(frozen=True)

    theme: str = "slate"
    configuration: str = ""
    """Which configuration file was last chosen, by name."""

    palettes: dict[str, Palette] = Field(default_factory=dict)
    """Palettes written by hand, which override the built-in ones of the same name."""

    def palette(self) -> Palette:
        """The palette in force: the user's by that name, else a built-in, else the default."""
        return self.palettes.get(self.theme) or THEMES.get(self.theme) or Palette()

    def names(self) -> tuple[str, ...]:
        """Every theme that can be chosen, the user's first."""
        return tuple(dict.fromkeys([*self.palettes, *THEMES]))


def preferences_from(path: Path) -> Preferences:
    """Read the window's preferences, falling back to the defaults.

    A file that cannot be read or does not validate yields the defaults rather than an
    error: a broken colour must never stop somebody opening their work. It is the opposite
    of the rule for `Config`, and deliberately - one describes what may run, this describes
    what it looks like.
    """
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return Preferences()
    if not isinstance(loaded, dict):
        return Preferences()
    try:
        return Preferences.model_validate(loaded)
    except ValueError:
        return Preferences()


def remember(path: Path, preferences: Preferences) -> None:
    """Save the window's preferences, quietly failing rather than interrupting.

    Written with `safe_dump`, and holding nothing but appearance and a filename: no path
    outside the workspace, no secret, nothing about what may run.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(preferences.model_dump(exclude_defaults=True), sort_keys=False),
            encoding="utf-8",
        )
    except OSError:
        return
