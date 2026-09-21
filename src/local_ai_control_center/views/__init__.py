"""The window's sections, one module each (ADR-075).

A section is the smallest thing this window has that is worth adding or removing on its own:
a name, a list down the side, and what to draw when something in that list is chosen.

**They are declared, not wired.** `Section` carries all three, so adding one is adding a piece
to a tuple rather than editing four places - the menu, the router, the selection handler and a
pair of methods. Getting three of those four right produced a section that appeared in the
menu and did nothing, silently, which is the shape of defect this project keeps finding.

Nothing here decides anything about the material. What a corpus holds, what a finding means,
which files exist: all of that stays in `features/`, and these modules put it on a screen
(ADR-066).
"""

from __future__ import annotations

from local_ai_control_center.views.section import Panel, Section, Sidebar

__all__ = ["Panel", "Section", "Sidebar"]
