"""What was done in this workspace, read from its audit trail (ADR-104).

Read-only, and it can be nothing else: the trail is append-only and hash-chained, and a window
that could change it would be a window its own chain had to be checked against.

**Nothing on the Tk thread waits.** Walking the chain of the thesis's trail took one to two
seconds, and the trail only grows. The walk runs on a worker, handed in from `cli.py` because a
section may reach neither the audit log nor the chain, and this draws "reading" until it is
done. An answer that arrives after you have left the section is dropped, as ADR-099 does.

It decides nothing: which runs there are, how each ended and whether the chain vouches for it
are all `features/trail.py`'s.
"""

from __future__ import annotations

import queue
import threading

import customtkinter as ctk

from local_ai_control_center.features.appearance import Palette
from local_ai_control_center.features.trail import Run, Said, Trail
from local_ai_control_center.views import paint
from local_ai_control_center.views.section import Panel, Section, Sidebar, State

EVERY = 150
"""Milliseconds between looks at whether the walk is done."""

_LISTED: dict[str, Run] = {}
"""The runs listed last, by key, so choosing one draws it without walking the trail again."""


def _alive(widget: object) -> bool:
    """Whether a widget is still on the screen - false once its section has been left."""
    try:
        return bool(widget.winfo_exists())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - a destroyed widget answers in several ways
        return False


def _colour(tone: str, skin: Palette) -> str:
    """The colour a tone is drawn in."""
    return {
        "good": skin.supported,
        "warn": skin.uncovered,
        "bad": skin.contradicted,
        "plain": skin.ink,
        "quiet": skin.faint,
    }.get(tone, skin.ink)


def _list_trail(side: Sidebar, panel: Panel, state: State) -> None:
    if state.read_trail is None:
        panel.said("Audit is unavailable", "This window was opened without its trail.")
        return
    panel.said("Audit", "Reading the trail, and checking every link in it.")
    waiting = paint.text(panel.body, "reading...", panel.skin.faint, 11)
    answers: queue.Queue[Trail | str] = queue.Queue()
    read = state.read_trail

    def work() -> None:
        # Touches no widget: the answer goes in the queue, and `_watch` draws it.
        try:
            answers.put(read())
        except Exception as error:  # noqa: BLE001 - a worker that dies says nothing at all
            answers.put(f"The trail could not be read: {error}")

    threading.Thread(target=work, daemon=True, name="lacc-trail").start()
    panel.body.after(EVERY, lambda: _watch(answers, waiting, side, panel))


def _watch(
    answers: queue.Queue[Trail | str], waiting: ctk.CTkLabel, side: Sidebar, panel: Panel
) -> None:
    """Draw the walk once it is done, if this section is still the one on the screen."""
    if not _alive(waiting):
        return
    try:
        found = answers.get_nowait()
    except queue.Empty:
        panel.body.after(EVERY, lambda: _watch(answers, waiting, side, panel))
        return
    waiting.destroy()
    if isinstance(found, str):
        panel.said("Audit", found)
        return
    _LISTED.clear()
    days: dict[str, str] = {}
    for run in found.runs:
        if run.day not in days:
            days[run.day] = side.group(run.day, open_now=not days)
        _LISTED[run.key] = run
        mark = "" if run.vouched else "! "
        side.row(run.key, f"{mark}{run.at}  {run.what} - {run.ending}", under=days[run.day])
    listed = (
        f"The latest {len(found.runs)} of {found.total_runs} runs"
        if found.total_runs > len(found.runs)
        else f"{found.total_runs} runs"
    )
    panel.said(
        "Audit",
        f"{listed}, {found.records} records, newest first. Times are this machine's; the trail "
        "keeps UTC. Nothing here can change it.",
    )
    first = found.integrity[0].tone if found.integrity else "plain"
    body = paint.card(panel.body, panel.skin, stripe=_colour(first, panel.skin))
    for said in found.integrity:
        _sentence(body, said, panel.skin)


def _sentence(parent: ctk.CTkFrame, said: Said, skin: Palette) -> None:
    """One sentence about the trail, its first part in the colour of what it says."""
    if said.lead:
        paint.text(parent, said.lead, _colour(said.tone, skin), 12, bold=True)
    size = 10 if said.tone == "quiet" else 12
    paint.text(parent, said.rest, skin.faint if said.tone == "quiet" else skin.dim, size)


def _show_run(key: str, panel: Panel, state: State) -> None:
    run = _LISTED.get(key)
    if run is None:
        return
    took = f", {run.seconds} seconds" if run.seconds else ""
    panel.said(
        f"{run.what} - {run.ending}",
        f"{run.day} {run.at}{took}, {len(run.steps)} records. Run {run.key}.",
    )
    if not run.vouched:
        warned = paint.card(panel.body, panel.skin, stripe=panel.skin.contradicted)
        paint.text(
            warned,
            "Not vouched for by the chain: at least one of these records comes after the "
            "chain breaks, or was written before there was one.",
            panel.skin.contradicted,
            12,
        )
    if run.unkept:
        paint.text(
            paint.card(panel.body, panel.skin),
            "An engine was called and these records hold neither the prompt nor the answer: "
            "they were written under audit_level: standard, which keeps only what happened.",
            panel.skin.dim,
            12,
        )
    for step in run.steps:
        stripe = panel.skin.card if step.vouched else panel.skin.contradicted
        body = paint.card(panel.body, panel.skin, stripe=stripe)
        paint.text(body, f"{step.at}   {step.kind}", panel.skin.faint, 10)
        paint.text(body, step.message, panel.skin.ink, 12)
        for name, value in step.facts:
            paint.fixed(body, f"{name}: {value}", panel.skin.dim, 10)
        for content in step.content:
            left = f"   {content.left:,} more characters in the trail" if content.left else ""
            paint.text(body, f"{content.name}{left}", panel.skin.faint, 10, bold=True)
            paint.fixed(body, content.shown, panel.skin.ink, 10)
            if content.digest:
                paint.fixed(body, f"sha256 {content.digest}", panel.skin.faint, 9)


SECTIONS = (Section("Audit", _list_trail, _show_run, group="YOUR WORK"),)
