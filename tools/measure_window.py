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

**What Ask keeps.** An answer that arrived while somebody was in another section used to be
lost (ADR-099). Ask is driven here against a stand-in engine that answers after a delay - no
model, no network - through the same buttons a person presses.

**What the Audit section reads.** The real trail, walked on a worker (ADR-104): how long until
the runs are listed, what is listed, whether leaving before the walk is done leaves anything
behind, and how long the second opening takes.

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
    _trail_for_the_window,
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
        _trail_for_the_window(config, workspace),
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


def _stand_in(delay: float) -> tuple[Any, Any]:
    """A prepare and a send that reach nothing: the send answers after ``delay`` seconds."""
    from local_ai_control_center.features.ask import Asked, Prepared, Reading

    def prepare(question: str, corpus: str, carried: tuple[Any, ...], agreed: int = 0) -> Prepared:
        return Prepared(
            question=question.strip() or "a question",
            corpus=corpus,
            selected=3,
            considered=10,
            set_aside=7,
            how="a stand-in",
            model="a stand-in",
            reaches="nothing",
            tokens=100,
        )

    def send(prepared: Prepared) -> Asked:
        time.sleep(delay)
        return Asked(
            prepared=prepared,
            answer='POINT: a stand-in\nQUOTE: "x"\nSOURCE: y',
            readings=(Reading(claim="a stand-in", quote="x", found=True),),
            seconds=delay,
        )

    return prepare, send


def _press(window: Window, text: str) -> bool:
    """Press the first button in the panel labelled ``text``, as a click would."""
    for button in _descendants(window.panel_body, ctk.CTkButton):
        if button.cget("text") == text and button.cget("state") != "disabled":
            button.invoke()
            _settle(window, 4)
            return True
    return False


def _shows(window: Window, words: str) -> bool:
    return any(
        words in str(label.cget("text")) for label in _descendants(window.right, ctk.CTkLabel)
    )


def _ask_flow(window: Window) -> None:
    """Ask, driven against a stand-in engine: what survives a change of section (ADR-099)."""
    from local_ai_control_center.views import asking

    delay = 1.0
    window.prepare_question, window.send_question = _stand_in(delay)
    ask = next(s for s in SECTIONS if s.name == "Ask")
    elsewhere = SECTIONS[0]
    window._go(ask)
    _settle(window, 4)
    rows = window.tree.get_children()
    if not rows:
        print("  no corpus to ask; nothing driven")
        return
    key = rows[0]
    corpus = pathlib.Path(key).name

    def open_corpus() -> None:
        window._go(ask)
        _settle(window, 4)
        window.tree.selection_set(key)
        _settle(window, 4)

    def ask_it(question: str) -> None:
        box = _descendants(window.panel_body, ctk.CTkTextbox)[0]
        box.delete("1.0", "end")
        box.insert("1.0", question)
        _press(window, "Prepare")
        _press(window, "Send to the engine")

    def wait(seconds: float) -> None:
        _settle(window, max(1, int(seconds / 0.05)))

    def turns() -> int:
        thread = asking._THREADS.get(corpus)
        return len(thread.turns) if thread is not None else 0

    open_corpus()
    ask_it("first")
    window._go(elsewhere)
    wait(delay + 1)
    print(
        f"  answered while in another section: kept {turns() == 1}, marked unseen "
        f"{corpus in asking._UNSEEN}"
    )
    open_corpus()
    start_over = any(
        button.cget("text") == "Start over"
        for button in _descendants(window.panel_body, ctk.CTkButton)
    )
    print(
        f"     back in Ask: heading counts it {window.summary.cget('text').startswith('1 ')}, "
        f"says it arrived elsewhere {_shows(window, 'arrived while you were')}, "
        f"Start over there {start_over}"
    )

    ask_it("second")
    box = _descendants(window.panel_body, ctk.CTkTextbox)[0]
    box.delete("1.0", "end")
    box.insert("1.0", "a draft")
    wait(delay + 1)
    box = _descendants(window.panel_body, ctk.CTkTextbox)[0]
    counted = window.summary.cget("text").startswith("2 ")
    kept = box.get("1.0", "end").strip() == "a draft"
    print(f"  answered while looking: heading counts it {counted}, draft kept {kept}")

    # Slower, because opening another section counts the whole workspace and can take longer
    # than a one-second stand-in: the first run of this check came back to an answer already
    # in, and reported the waiting card missing. Opened again after the swap, because a
    # corpus's buttons keep the callables it was drawn with - the second run sent through the
    # fast one and reported the same thing.
    slow = 5.0
    window.prepare_question, window.send_question = _stand_in(slow)
    open_corpus()
    ask_it("third")
    window._go(elsewhere)
    open_corpus()
    print(
        f"  in flight after a change of section: still waiting on the screen "
        f"{_shows(window, 'Asking the engine')}"
    )
    _press(window, "Prepare")
    refused = _press(window, "Send to the engine") and _shows(window, "already with the engine")
    print(f"     a second send while it waits is refused {refused}")
    wait(slow + 1)
    print(f"     then answered: {turns() == 3}")
    window.prepare_question, window.send_question = _stand_in(delay)
    open_corpus()

    before = turns()
    ask_it("fourth")
    _press(window, "Stop waiting")
    wait(delay + 1)
    print(
        f"  stopped waiting: answer discarded {turns() == before}, nothing left in flight "
        f"{corpus not in asking._PENDING}"
    )

    _press(window, "Start over")
    print(f"  Start over: thread empty {turns() == 0}")
    _agreeing_flow(window, open_corpus)


def _agreeing_flow(window: Window, open_corpus: Any) -> None:
    """Prepare with quotations never embedded: nothing ranked until their own button (ADR-106).

    The stand-in asks for five quotations with no stored vector until it is told five may go,
    which is what the real `prepare` does with an embedding model and a corpus that grew.
    """
    from local_ai_control_center.features.ask import Prepared
    from local_ai_control_center.ports.retriever import Outgoing

    prepare, send = _stand_in(1.0)
    agreements: list[int] = []

    def asking_first(
        question: str, corpus: str, carried: tuple[Any, ...], agreed: int = 0
    ) -> Prepared:
        agreements.append(agreed)
        if agreed < 5:
            waiting = Outgoing(model="a stand-in embedder", unembedded=5)
            return Prepared(question=question, corpus=corpus, reaches="nothing", awaiting=waiting)
        return prepare(question, corpus, carried, agreed)

    window.prepare_question, window.send_question = asking_first, send
    window.before_preparing = "Prepare sends your question to a stand-in embedder."
    open_corpus()
    line = _shows(window, "Prepare sends your question")
    box = _descendants(window.panel_body, ctk.CTkTextbox)[0]
    box.delete("1.0", "end")
    box.insert("1.0", "fifth")
    _press(window, "Prepare")
    card = _shows(window, "Ranking needs more than your question")
    no_send = not any(
        button.cget("text") == "Send to the engine"
        for button in _descendants(window.panel_body, ctk.CTkButton)
    )
    _press(window, "Send them and rank")
    preview = _shows(window, "This is what would be sent")
    print(
        f"  quotations never embedded: the line beside Prepare {line}, a card instead of a "
        f"preview {card}, no send button yet {no_send}; its own button ranks {preview}, "
        f"agreed to {agreements}"
    )


def _listed_after(window: Window, section: Any, most: float = 30.0) -> float:
    """Open a section and wait until its list has something in it; the seconds it took."""
    started = time.perf_counter()
    window._go(section)
    while time.perf_counter() - started < most and not window.tree.get_children():
        _settle(window, 2)
    return time.perf_counter() - started


def _audit(window: Window) -> None:
    """The trail, read on a worker: how long, what is listed, what leaving early does."""
    audit = next(s for s in SECTIONS if s.name == "Audit")
    elsewhere = SECTIONS[0]

    window._go(audit)
    window._go(elsewhere)
    _settle(window, 60)
    left_clean = not window.tree.get_children() and not window.side.winfo_ismapped()
    print(f"  left before the walk was done: nothing drawn into the next section {left_clean}")

    took = _listed_after(window, audit)
    days = window.tree.get_children()
    runs = [key for day in days for key in window.tree.get_children(day)]
    print(
        f"  first opening: listed after {took:.1f} s, {len(runs)} runs under {len(days)} days, "
        f"list column shown {bool(window.side.winfo_ismapped())}"
    )
    print(f"  heading: {window.summary.cget('text')[:110]}")
    print(
        f"  says the trail holds {_shows(window, 'The trail holds.')}, "
        f"the anchor agrees {_shows(window, 'The anchor agrees')}"
    )
    endings: dict[str, int] = {}
    for key in runs:
        ending = str(window.tree.item(key, "text")).rsplit(" - ", 1)[-1].strip()
        endings[ending] = endings.get(ending, 0) + 1
    print(f"  how the listed runs ended: {endings}")
    if runs:
        window.tree.selection_set(runs[0])
        _settle(window, 8)
        cards = len(_descendants(window.panel_body, ctk.CTkLabel))
        print(f"  the newest run: {window.title_label.cget('text')} ({cards} labels drawn)")
    again = _listed_after(window, audit)
    print(f"  second opening, the trail unchanged: listed after {again:.2f} s")


def _where_it_opened(window: Window) -> None:
    """Where the window opened against the work area, before anything moved it (ADR-100)."""
    from local_ai_control_center.system.profiler import work_area

    area = work_area()
    x, y = window.winfo_rootx(), window.winfo_rooty()
    wide, tall = window.winfo_width(), window.winfo_height()
    print("Where it opened")
    if area is None:
        print(f"  at {x},{y}, {wide} by {tall}; the system does not say what its work area is")
        return
    left, top, right, bottom = area
    inside = left <= x and x + wide <= right and top <= y and y + tall <= bottom
    print(
        f"  client area at {x},{y}, {wide} by {tall}; work area {left},{top} to {right},{bottom}: "
        f"{'inside' if inside else 'NOT inside'}"
    )


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
    _where_it_opened(window)
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
    print()
    print("Ask, against a stand-in engine")
    _ask_flow(window)
    print()
    print("Audit, against the real trail")
    _audit(window)
    window.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
