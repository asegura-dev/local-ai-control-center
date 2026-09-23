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
from local_ai_control_center.features.ask import Asked, Prepared
from local_ai_control_center.features.commands import Command
from local_ai_control_center.features.prompts import Prompt
from local_ai_control_center.ports.retriever import Passage


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

    context_file: str = ""
    """The standing context a configuration names.

    A document, and what makes it not one to quote from is a setting - so the window is told
    which it is, the way `status` is, rather than a reader of text guessing (ADR-090).
    """

    prepare_question: Callable[[str, str, tuple[Passage, ...]], Prepared] | None = None
    """Rank a corpus against a question and report what would be sent. Sends no prompt.

    The third argument is what a thread has already established - passages whose quotations
    were checked in earlier turns. Empty for a question asked on its own (ADR-091).
    """

    send_question: Callable[[Prepared], Asked] | None = None
    """Run a question that has already been previewed. Never raises (ADR-085).

    Both arrive from `cli.py` for the reason `check_engine` does: a section may reach
    `features/` and `core`, and neither can build a provider or call the cycle. The window
    is handed the ability to run one thing and cannot obtain it for itself. When they are
    absent the section says so and the rest of the window is unaffected.
    """


WIDEST_ROW = 44
"""Characters a sidebar row shows before it is cut.

The tree has one column and no horizontal scrolling, so a longer title was simply severed
mid-word with nothing to say it had been - `Chapter 2 - Roadmap: where LACC is and where it
is headi`. Cut deliberately, with an ellipsis, it at least says so (ADR-084).
"""


def shortened(title: str, widest: int = WIDEST_ROW) -> str:
    """A row's text, cut where it will not fit, with a mark that it was."""
    tidy = " ".join(title.split())
    return tidy if len(tidy) <= widest else tidy[: widest - 1].rstrip() + "…"


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
