"""What a section is, and the two things the window hands it (ADR-075).

The contract between the window and its sections. Deliberately small: a section is given a
way to put rows in the sidebar and a way to put widgets in the panel, and it is given the
state it needs. It never reaches back for the window.

`Sidebar` and `Panel` are protocols rather than the Tk objects, so a section can be described
- and its listing checked - without a display. Tk cannot be exercised headlessly, and the way
round that is to keep the part that can be tested free of it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from local_ai_control_center.features.appearance import Palette
from local_ai_control_center.features.commands import Command
from local_ai_control_center.features.prompts import Prompt


class Sidebar(Protocol):
    """Where a section puts what can be chosen."""

    def row(self, key: str, shown: str, under: str = "") -> str:
        """Add a row, optionally beneath a group, and return its key."""

    def group(self, shown: str, open_now: bool = False) -> str:
        """Add a group that rows can sit under, and return its key."""


class Panel(Protocol):
    """Where a section draws what was chosen."""

    def said(self, title: str, summary: str) -> None:
        """Set the heading and the line under it."""

    @property
    def body(self) -> Any:
        """The frame to draw into."""

    @property
    def skin(self) -> Palette:
        """The colours in force."""


@dataclass(frozen=True)
class State:
    """Everything a section is allowed to know.

    Passed rather than reached for: a section that could reach the window could reach
    anything on it, and the point of this arrangement is that a section is a piece rather
    than a part of a whole.
    """

    workspace: Path
    configs: Path
    chosen_configuration: str
    commands: tuple[Command, ...] = ()
    prompts: tuple[Prompt, ...] = ()


Listing = Callable[["Sidebar", "Panel", "State"], None]
"""What fills the sidebar for a section and writes its heading."""


@dataclass(frozen=True)
class Section:
    """One part of the window: a name, a listing, and what to show for a selection.

    `listing` fills the sidebar and writes the heading for the section itself. `show` is
    called with whatever key the sidebar returned, and only for keys this section made.
    """

    name: str
    listing: Listing
    show: Callable[[str, Panel, State], None] | None = None
    """Absent for a section whose listing is the whole of it."""

    def open(self, key: str, panel: Panel, state: State) -> None:
        """Show one row, if this section has anything to show."""
        if self.show is not None:
            self.show(key, panel, state)
