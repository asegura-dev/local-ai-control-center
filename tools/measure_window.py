"""Drive the window and report what cannot be read and what cannot be reached.

Two defects of the same family have now been found by looking at a picture rather than by a
test: text running off the right edge (ADR-092) and a rail too long for its column
(ADR-095). Both are questions a machine can ask of every widget at once, and neither can be
asked by `pytest`, because a window needs a display.

**What runs off the right.** `reqwidth > width` on a label *is* "the text is cut". ADR-092
reported zero over 656 labels and left the script that said so outside the repository, so
the figure could not be re-taken. It can now.

**What cannot be reached at the bottom.** A section the rail does not draw, and does not
scroll to, is a section that does not exist for whoever is using this. Asked at several
window heights, because it is the short window that loses them and the machine this was
written on has a tall one - which is why the defect was reported by somebody else.

**What a notch of the wheel does.** Every scrolling figure before ADR-096 was taken by moving
a list in code, and the wheel moved three pixels a notch past both ends of the panel for as
long as that stood. The wheel is now driven here: pixels per notch in each column, whether
the panel stops where its content does, whether a section that fits moves at all, whether a
new section starts at the top, and what four quarter-notches add up to.

It reports. It concludes nothing: a label wider than its box may be a heading that is meant
to clip, and a rail showing a fifth of itself is a small window, not a defect. The figures
are for a person to read.

Run it with `.\run.ps1 run --extra gui python tools/measure_window.py -c configs/denso.yaml`,
and pass `--heights 1025,775,575` to ask at other sizes. The scaling is this display's and no
other (ADR-092): a defect at 150% is not caught by running at 125%.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import customtkinter as ctk  # noqa: E402

from local_ai_control_center.cli import (  # noqa: E402
    _asking_for_the_window,
    _engine_at,
    _known_skills,
    _load,
    app,
)
from local_ai_control_center.features.appearance import (  # noqa: E402
    WINDOW_PREFERENCES,
    preferences_from,
)
from local_ai_control_center.features.commands import commands_of  # noqa: E402
from local_ai_control_center.features.prompts import prompts_of  # noqa: E402
from local_ai_control_center.features.status import status_of  # noqa: E402
from local_ai_control_center.window import SECTIONS, Window  # noqa: E402

SETTLE = 8
"""Redraws to allow before measuring. Tk reports the geometry it last drew, not the one it
intends, so a measurement taken too early is the previous window's."""


def _settle(window: Window, times: int = SETTLE) -> None:
    for _ in range(times):
        window.update()
        time.sleep(0.05)
    window.update_idletasks()


def _descendants(widget: Any, kind: type, found: list[Any] | None = None) -> list[Any]:
    found = [] if found is None else found
    for child in widget.winfo_children():
        if isinstance(child, kind):
            found.append(child)
        _descendants(child, kind, found)
    return found


def _cut_off(widget: Any) -> list[tuple[str, int, int]]:
    """Labels whose text needs more width than they were given, with both figures."""
    cut = []
    for label in _descendants(widget, ctk.CTkLabel):
        said = str(label.cget("text")).strip()
        width, needs = label.winfo_width(), label.winfo_reqwidth()
        if said and width > 1 and needs > width + 1:
            cut.append((said[:60], needs, width))
    return cut


def _open(config_path: pathlib.Path) -> Window:
    config, workspace = _load(config_path)
    saved = workspace.root / WINDOW_PREFERENCES
    preferences = preferences_from(saved).model_copy(update={"configuration": config_path.name})
    return Window(
        workspace.root,
        config_path.parent,
        preferences,
        saved,
        commands_of(app),
        prompts_of(_known_skills(config_path), config),
        status_of(workspace.root, config, config.context_file or ""),
        lambda: _engine_at(config, config.engine_host),
        lambda host: _engine_at(config, host),
        *_asking_for_the_window(config, workspace),
        config.context_file or "",
    )


def _rail_at(window: Window, height: int) -> None:
    """What the rail shows, and whether its last section can be got to, at one height."""
    window.geometry(f"1280x{height}")
    _settle(window)
    rail = window.rail
    canvas = getattr(window.list, "_parent_canvas", None)
    first, last = canvas.yview() if canvas is not None else (0.0, 1.0)
    # Asked in logical pixels, reported in physical ones: the toolkit scales `geometry` by
    # the display scaling, and a screen too short for the request caps it.
    print(
        f"  asked {height}, got {window.winfo_height()} physical, rail {rail.winfo_height()} tall"
    )
    print(f"     shows {last - first:>5.0%} of the rail's content")

    # At *some* scroll position, not at one: asked only at the end, every section above the
    # fold counts as out of reach, which is what a scrolled list is for. The first draft of
    # this check reported the top two sections missing and the window was right.
    unreachable = set(window.buttons)
    for stop in (0.0, 0.25, 0.5, 0.75, 1.0):
        if canvas is not None:
            canvas.yview_moveto(stop)
            _settle(window, 2)
        for name, button in window.buttons.items():
            if 0 <= button.winfo_rooty() - rail.winfo_rooty() < rail.winfo_height():
                unreachable.discard(name)
        if canvas is None:
            break
    if canvas is not None:
        canvas.yview_moveto(0.0)
        _settle(window, 2)
    print(f"     out of reach at every scroll position: {sorted(unreachable) or 'none'}")

    clipped = [
        (type(child).__name__, child.winfo_height(), child.winfo_reqheight())
        for child in rail.winfo_children()
        if child.winfo_reqheight() > child.winfo_height() + 1
    ]
    for kind, has, needs in clipped:
        print(f"     {kind} drawn at {has} of the {needs} it asked for")


def _notches(window: Window, widget: Any, count: int, delta: int = -120) -> None:
    """Turn the wheel ``count`` times with the pointer over the middle of ``widget``."""
    x = widget.winfo_rootx() + widget.winfo_width() // 2
    y = widget.winfo_rooty() + widget.winfo_height() // 2
    for _ in range(count):
        widget.event_generate("<MouseWheel>", delta=delta, rootx=x, rooty=y)
    _settle(window, 2)


def _to_the_end(window: Window, widget: Any, canvas: Any, delta: int) -> float:
    """Turn until the column stops moving, and say where it stopped."""
    last = None
    for _ in range(400):
        _notches(window, widget, 10, delta)
        here = canvas.canvasy(0)
        if here == last:
            break
        last = here
    return float(canvas.canvasy(0))


def _wheel(window: Window) -> None:
    """What a notch does, and whether the panel stops where its content does (ADR-096)."""
    window.geometry("1280x820")
    _settle(window)
    panel = window.right._parent_canvas
    tall = panel.winfo_height()

    # The height the content asks for, after the re-wrap has run. `bbox` read four redraws
    # after opening a section still held the previous section's, and the first run of this
    # check measured the wheel on a section that fitted.
    lengths = {}
    for section in SECTIONS:
        window._go(section)
        _settle(window)
        lengths[section.name] = window.right.winfo_reqheight()
    longest = max(lengths, key=lambda name: lengths[name])
    shortest = min(lengths, key=lambda name: lengths[name])
    print(
        f"  the panel is {tall} tall; {longest} holds {lengths[longest]}, {shortest} holds "
        f"{lengths[shortest]}"
    )

    window._go(next(s for s in SECTIONS if s.name == longest))
    _settle(window)
    print(f"     scroll region: {panel.cget('scrollregion') or 'none'}")
    start = panel.canvasy(0)
    _notches(window, window.right, 1)
    one = panel.canvasy(0) - start
    _notches(window, window.right, 9)
    ten = panel.canvasy(0) - start
    print(f"     one notch moves {one:.0f} px, ten move {ten:.0f}")

    bottom = _to_the_end(window, window.right, panel, -120)
    print(
        f"     turned down to the end: stops at {bottom:.0f}, content ends at "
        f"{lengths[longest]} ({'stops' if bottom + tall <= lengths[longest] + 1 else 'PASSES'})"
    )
    top = _to_the_end(window, window.right, panel, 120)
    print(f"     turned up to the end: stops at {top:.0f} ({'stops' if top >= 0 else 'PASSES'})")

    _notches(window, window.right, 1)
    after_one = panel.canvasy(0)
    _notches(window, window.right, 4, -30)
    quarters = panel.canvasy(0) - after_one
    print(f"     four quarter-notches move {quarters:.0f} px, against {one:.0f} for one notch")

    _notches(window, window.right, 10)
    window._go(SECTIONS[0])
    _settle(window)
    print(f"     opening {SECTIONS[0].name} after scrolling: starts at {panel.canvasy(0):.0f}")

    window._go(next(s for s in SECTIONS if s.name == shortest))
    _settle(window)
    _notches(window, window.right, 20, 120)
    up = panel.canvasy(0)
    _notches(window, window.right, 40, -120)
    down = panel.canvasy(0)
    print(f"     {shortest}, which fits: 20 notches up leave it at {up:.0f}, 40 down at {down:.0f}")

    window.geometry("1280x575")
    _settle(window)
    rail = window.list._parent_canvas
    rail_start, panel_start = rail.canvasy(0), panel.canvasy(0)
    _notches(window, window.list, 1)
    print(
        f"  at 575: one notch over the rail moves the rail {rail.canvasy(0) - rail_start:.0f} "
        f"px and the panel {panel.canvasy(0) - panel_start:.0f}"
    )
    rail.yview_moveto(0.0)
    _settle(window, 2)


def main() -> int:
    parsed = argparse.ArgumentParser(description=__doc__)
    parsed.add_argument("-c", "--config", default="configs/config.yaml", type=pathlib.Path)
    parsed.add_argument(
        "--heights",
        default="1025,775,575",
        help="Window heights to ask the rail about, comma separated.",
    )
    args = parsed.parse_args()

    window = _open(args.config)
    _settle(window)

    print(f"{len(SECTIONS)} sections, at this display's scaling")
    print()
    print("The rail, by window height")
    for height in (int(one) for one in args.heights.split(",")):
        _rail_at(window, height)
    print()

    print("Text wider than the space it was given, section by section")
    total = 0
    for section in SECTIONS:
        window._go(section)
        _settle(window, 4)
        cut = _cut_off(window.right)
        total += len(cut)
        print(f"  {section.name:<20} {len(cut)}")
        for said, needs, width in cut:
            print(f"       needs {needs} in {width}: {said}")
    print()
    print(f"{total} cut off, over {len(SECTIONS)} sections")
    print()
    print("The wheel")
    _wheel(window)
    window.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
