"""The configuration, changeable, and the engines, askable (ADR-094).

**The window may change what LACC does. It may not change what LACC is allowed to do.**
`network_access` and `workspace_in_repository` are shown and not edited: they are refusals
being lifted rather than settings, and a toggle is not a deliberate decision.

**Check produces the button**, as everywhere else here. Pressing it writes nothing and draws
every line that would change, before and after. There is no extra ceremony for the riskier
settings - a ritual on some changes teaches people to click through the ritual.

**And nothing is asked of an engine until somebody presses it**, which is the rule the line
along the bottom has kept since it was written (ADR-077).
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

import customtkinter as ctk

from local_ai_control_center.core.config import Config, load_config
from local_ai_control_center.features.editing import (
    KEPT,
    Wanted,
    ceiling_of,
    changed,
    differences,
    settings_shown,
)
from local_ai_control_center.features.status import EngineSeen
from local_ai_control_center.views import paint
from local_ai_control_center.views.section import Panel, Section, Sidebar, State


def _read(state: State) -> tuple[Path, Config | None]:
    path = Path(state.configs) / state.chosen_configuration
    try:
        return path, load_config(path)
    except Exception:  # noqa: BLE001 - a configuration may fail in any way
        return path, None


def _show_configuration(side: Sidebar, panel: Panel, state: State) -> None:
    """Every setting, the changeable ones in a box, the two refusals beside them."""
    path, config = _read(state)
    if config is None:
        panel.said(
            state.chosen_configuration or "No configuration",
            f"{path} could not be read. Nothing is shown rather than half of it.",
        )
        return
    panel.said(
        state.chosen_configuration,
        f"{path}\nChange what LACC does here. What it is **allowed** to do stays in the "
        "file: those two are refusals being lifted, and a toggle is not a deliberate "
        "decision.",
    )

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    body = paint.card(panel.body, panel.skin, stripe=panel.skin.accent)
    fields: dict[str, ctk.CTkEntry] = {}
    for key, value, says in settings_shown(text, config):
        line = ctk.CTkFrame(body, fg_color="transparent")
        line.pack(fill="x", pady=3)
        ctk.CTkLabel(
            line,
            text=key,
            width=140,
            anchor="w",
            text_color=panel.skin.dim,
            font=ctk.CTkFont(size=12),
        ).pack(side="left")
        entry = ctk.CTkEntry(
            line,
            height=28,
            corner_radius=6,
            fg_color=panel.skin.surface,
            text_color=panel.skin.ink,
            border_width=0,
            font=ctk.CTkFont(size=12),
        )
        entry.insert(0, value)
        entry.pack(side="left", fill="x", expand=True)
        fields[key] = entry
        paint.text(body, f"      {says}", panel.skin.faint, 10)

    below = ctk.CTkFrame(panel.body, fg_color="transparent")
    below.pack(fill="both", expand=True)
    ctk.CTkButton(
        body,
        text="Check",
        width=110,
        height=30,
        corner_radius=8,
        fg_color=panel.skin.card,
        hover_color=panel.skin.accent,
        text_color=panel.skin.ink,
        font=ctk.CTkFont(size=12),
        command=lambda: _check(fields, path, below, panel),
    ).pack(anchor="w", pady=(10, 0))

    held = paint.card(panel.body, panel.skin)
    paint.text(held, "Not changed from here", panel.skin.ink, 13, bold=True)
    for key, value, why in ceiling_of(config):
        paint.fixed(held, f"{key}   {value}", panel.skin.dim, 11)
        paint.text(held, f"   {why}", panel.skin.faint, 10)


def _check(fields: dict[str, ctk.CTkEntry], path: Path, below: ctk.CTkFrame, panel: Panel) -> None:
    """Draw every line that would change. Nothing is written."""
    for child in below.winfo_children():
        child.destroy()
    try:
        before = path.read_text(encoding="utf-8")
    except OSError as error:
        paint.text(
            paint.card(below, panel.skin, stripe=panel.skin.contradicted),
            f"{path} could not be read: {error}",
            panel.skin.ink,
            12,
        )
        return

    after, refused = changed(
        before, tuple(Wanted(key=key, value=entry.get()) for key, entry in fields.items())
    )
    if refused:
        card = paint.card(below, panel.skin, stripe=panel.skin.contradicted)
        paint.text(card, "Nothing would be written", panel.skin.contradicted, 13, bold=True)
        for one in refused:
            paint.text(card, f"{one.key}: {one.why}", panel.skin.ink, 12)
        return

    lines = differences(before, after, path.name)
    card = paint.card(below, panel.skin, stripe=panel.skin.accent)
    if not lines:
        paint.text(card, "Nothing would change.", panel.skin.dim, 12)
        return
    paint.text(card, "This is what would change", panel.skin.ink, 13, bold=True)
    for line in lines:
        colour = panel.skin.dim
        if line.startswith("+") and not line.startswith("+++"):
            colour = panel.skin.supported
        elif line.startswith("-") and not line.startswith("---"):
            colour = panel.skin.contradicted
        paint.fixed(card, line, colour, 11)
    paint.text(card, KEPT, panel.skin.faint, 10)
    ctk.CTkButton(
        card,
        text="Save it",
        width=140,
        height=32,
        corner_radius=8,
        fg_color=panel.skin.accent,
        hover_color=panel.skin.accent,
        text_color=panel.skin.ink,
        font=ctk.CTkFont(size=12, weight="bold"),
        command=lambda: _save(path, after, below, panel),
    ).pack(anchor="w", pady=(10, 0))


def _save(path: Path, after: str, below: ctk.CTkFrame, panel: Panel) -> None:
    """Write it. This one replaces a file, which is the whole point of changing it."""
    for child in below.winfo_children():
        child.destroy()
    try:
        path.write_text(after, encoding="utf-8")
    except OSError as error:
        paint.text(
            paint.card(below, panel.skin, stripe=panel.skin.contradicted),
            f"Nothing was written: {error}",
            panel.skin.ink,
            12,
        )
        return
    card = paint.card(below, panel.skin, stripe=panel.skin.supported)
    paint.text(card, f"{path.name} written", panel.skin.supported, 13, bold=True)
    paint.text(
        card,
        "Close and open the window to work with it. Tk builds its widgets once, and what is "
        "already on the screen was drawn from the configuration as it was.",
        panel.skin.dim,
        12,
    )


# --- the engines ----------------------------------------------------------------------------


def _show_engines(side: Sidebar, panel: Panel, state: State) -> None:
    """What the configuration names, what this machine holds, and nothing asked yet."""
    path, config = _read(state)
    if config is None:
        panel.said("Engines", f"{path} could not be read.")
        return
    panel.said(
        "Engines",
        f"The configuration names {config.engine_host or 'this machine'} and asks for "
        f"{config.model}.\nNothing is asked of either until you press it - a window that "
        "reaches the network because somebody looked at it is a window that decides for you.",
    )
    if state.ask_engine is None:
        paint.text(
            paint.card(panel.body, panel.skin),
            "This window was opened without the ability to reach anything.",
            panel.skin.dim,
            12,
        )
        return

    for title, host in (
        ("the host the configuration names", config.engine_host or "http://localhost:11434"),
        ("this machine", "http://localhost:11434"),
    ):
        card = paint.card(panel.body, panel.skin)
        paint.text(card, title, panel.skin.ink, 13, bold=True)
        paint.fixed(card, host, panel.skin.dim, 11)
        answers = ctk.CTkFrame(card, fg_color="transparent")
        answers.pack(fill="x")
        ctk.CTkButton(
            card,
            text="Ask it",
            width=110,
            height=28,
            corner_radius=8,
            fg_color=panel.skin.card,
            hover_color=panel.skin.accent,
            text_color=panel.skin.dim,
            font=ctk.CTkFont(size=11),
            command=lambda where=host, into=answers: _ask(where, into, panel, state),
        ).pack(anchor="w", pady=(6, 0))
    if not config.network_access:
        paint.text(
            paint.card(panel.body, panel.skin),
            "network_access is off, so only this machine is reachable whatever a host says. "
            "It is the ceiling, and it is changed in the file.",
            panel.skin.faint,
            11,
        )


EVERY = 200
"""Milliseconds between looks at a check in flight, as Ask's (ADR-110)."""


def _alive(widget: object) -> bool:
    """Whether a widget is still on the screen - a poll outlives a section left (ADR-099)."""
    try:
        return bool(widget.winfo_exists())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - a destroyed widget answers in several ways
        return False


def _ask(host: str, into: ctk.CTkFrame, panel: Panel, state: State) -> None:
    """Ask one engine what it holds, on a worker, counting the seconds (ADR-118).

    It asked on the window's thread. An engine that accepts a connection and never answers
    held the window for the check's eight seconds, and the tester saw no notice while it
    waited and an empty card after. Now the press returns at once, a line counts, and what
    came back - or why nothing did - is drawn when it arrives. What is needed is read here;
    the worker touches no widget.
    """
    if state.ask_engine is None:
        return
    for child in into.winfo_children():
        child.destroy()
    counting = paint.text(into, f"asking {host}... 0s", panel.skin.faint, 11)
    results: queue.Queue[EngineSeen] = queue.Queue()
    ask = state.ask_engine

    def work() -> None:
        """The worker. Nothing it does can raise into Tk: a failure is drawn as one."""
        try:
            results.put(ask(host))
        except Exception as error:  # noqa: BLE001 - a traceback here has nowhere to go
            results.put(EngineSeen(asked=True, host=host, detail=str(error)))

    began = time.monotonic()
    threading.Thread(target=work, daemon=True, name="lacc-engine").start()
    _await_engine(results, began, counting, host, into, panel)


def _await_engine(
    results: queue.Queue[EngineSeen],
    began: float,
    counting: ctk.CTkLabel,
    host: str,
    into: ctk.CTkFrame,
    panel: Panel,
) -> None:
    """Look for the check's answer from inside `after`, and draw it while its card is there."""
    if not _alive(into):
        return
    try:
        seen = results.get_nowait()
    except queue.Empty:
        if _alive(counting):
            counting.configure(text=f"asking {host}... {time.monotonic() - began:.0f}s")
        panel.body.after(EVERY, lambda: _await_engine(results, began, counting, host, into, panel))
        return
    for child in into.winfo_children():
        child.destroy()
    _draw_seen(seen, into, panel)


def _draw_seen(seen: EngineSeen, into: ctk.CTkFrame, panel: Panel) -> None:
    """What the check found: whether it answered, why not, and what the engine holds."""
    colour = panel.skin.supported if seen.answered else panel.skin.contradicted
    paint.text(into, seen.said, colour, 12, bold=True)
    if seen.detail and not seen.answered:
        paint.text(into, seen.detail, panel.skin.dim, 11)
    if not seen.held:
        return
    paint.text(into, f"{len(seen.held)} models installed there", panel.skin.faint, 10)
    for name in seen.held:
        here = name == seen.wanted
        said = f"  {name}   <- the one this configuration asks for" if here else f"  {name}"
        paint.fixed(into, said, panel.skin.ink if here else panel.skin.dim, 11)
    if seen.wanted and not seen.has_it:
        paint.text(
            into,
            f"{seen.wanted} is not among them. Pull it there with  ollama pull {seen.wanted}",
            panel.skin.contradicted,
            11,
        )


SECTIONS = (
    Section("Configuration", _show_configuration, group="THE PROGRAM"),
    Section("Engines", _show_engines, group="THE PROGRAM"),
)
