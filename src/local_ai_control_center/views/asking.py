"""The one section that runs something (ADR-085).

Every other section reads. This one types a question, shows what would be sent, and - on a
second press - sends it. The reasons that kept the window read-only for eight sections are
answered here rather than dismissed:

**The preview is not a dialog, it is what produces the button.** `Prepare` draws what would
go; the control that sends is created by that drawing, so there is no path from typing to an
engine call that skips it. That is `_confirm`'s guarantee in the only grammar a window has.

**Nothing on the Tk thread waits.** The call runs on a worker that touches no widget: it puts
its result in a queue, and `_watch` - the one function here that writes to the screen after a
send - reads it from inside `after`.

**Cancel stops the waiting, and says so.** The request is already with the engine and keeps
running there. Nothing here pretends otherwise.

It decides nothing. What a prepared question is, whether it can be sent, and how an answer
reads are all in `features/ask.py`; running it is the cycle's, handed in as two callables
because a section may reach neither (ADR-066, ADR-075).
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

import customtkinter as ctk

from local_ai_control_center.features.ask import Asked, Prepared
from local_ai_control_center.features.overview import documents_in
from local_ai_control_center.views import paint
from local_ai_control_center.views.section import Panel, Section, Sidebar, State

EVERY = 200
"""Milliseconds between looks at the queue. Slow enough to cost nothing, fast enough that
the elapsed seconds move."""

BOX_HEIGHT = 92
QUOTED = 220
"""Characters of a quotation shown before it is cut. A passage can be a paragraph."""


def _alive(widget: object) -> bool:
    """Whether a widget is still on the screen.

    A poll scheduled with `after` outlives the section that scheduled it: change section
    while a question is in flight and the callback arrives to write into widgets that were
    destroyed. Tk answers that with an exception from inside the event loop, which is the
    hardest place in this program to see one.
    """
    try:
        return bool(widget.winfo_exists())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - a destroyed widget answers in several ways
        return False


def _list_corpora(side: Sidebar, panel: Panel, state: State) -> None:
    found = [seen for seen in documents_in(state.workspace) if seen.kind == "corpus"]
    for seen in found:
        side.row(str(seen.path), seen.name)
    if state.prepare_question is None or state.send_question is None:
        panel.said(
            "Ask",
            "This window was opened without the ability to run anything, so questions are "
            "unavailable. Everything else still reads.",
        )
        return
    if not found:
        panel.said(
            "No corpus to ask",
            "A question is answered from passages that were already checked against the "
            "documents they name. Build one with  lacc collect  and  lacc corpus.",
        )
        return
    panel.said(
        "Ask",
        f"{len(found)} corpora. Choose one, write a question, and see what would be sent "
        "before anything is.\nThe answer's own quotations are checked against the passages "
        "it was given.",
    )


def _open_corpus(key: str, panel: Panel, state: State) -> None:
    """A corpus, a box to write in, and a button that prepares rather than sends."""
    if state.prepare_question is None or state.send_question is None:
        panel.said("Questions are unavailable", "This window was opened without them.")
        return
    corpus = Path(key).name
    panel.said(
        corpus,
        "Nothing is sent until you have seen what would be. Press Prepare first: it reads "
        "this corpus and ranks it against your words.",
    )

    body = paint.card(panel.body, panel.skin)
    box = ctk.CTkTextbox(
        body,
        height=BOX_HEIGHT,
        corner_radius=8,
        fg_color=panel.skin.surface,
        text_color=panel.skin.ink,
        border_width=0,
        font=ctk.CTkFont(size=13),
    )
    box.pack(fill="x", pady=(2, 8))
    paint.text(
        body,
        "The ranking is by the words you use. It does not cross languages unless an "
        "embedding model is configured.",
        panel.skin.faint,
        10,
    )
    below = ctk.CTkFrame(panel.body, fg_color="transparent")
    below.pack(fill="both", expand=True)

    ctk.CTkButton(
        body,
        text="Prepare",
        width=110,
        height=30,
        corner_radius=8,
        fg_color=panel.skin.card,
        hover_color=panel.skin.accent,
        text_color=panel.skin.ink,
        font=ctk.CTkFont(size=12),
        command=lambda: _prepare(box, corpus, below, panel, state),
    ).pack(anchor="w", pady=(8, 0))


def _prepare(
    box: ctk.CTkTextbox, corpus: str, below: ctk.CTkFrame, panel: Panel, state: State
) -> None:
    """Rank the corpus and draw what would be sent. The prompt itself goes nowhere."""
    if state.prepare_question is None:
        return
    for child in below.winfo_children():
        child.destroy()
    prepared = state.prepare_question(box.get("1.0", "end"), corpus)
    if prepared.refusal:
        refused = paint.card(below, panel.skin, stripe=panel.skin.contradicted)
        paint.text(refused, prepared.refusal, panel.skin.ink, 12)
        return

    card = paint.card(below, panel.skin, stripe=panel.skin.accent)
    paint.text(card, "This is what would be sent", panel.skin.ink, 13, bold=True)
    paint.fixed(card, f"question   {prepared.question}", panel.skin.dim, 11)
    paint.fixed(
        card,
        f"passages   {prepared.selected} of {prepared.considered}, {prepared.set_aside} set aside",
        panel.skin.dim,
        11,
    )
    paint.fixed(card, f"ranked by  {prepared.how}", panel.skin.dim, 11)
    paint.fixed(card, f"material   about {prepared.tokens:,} tokens", panel.skin.dim, 11)
    paint.fixed(card, f"model      {prepared.model}", panel.skin.dim, 11)
    paint.fixed(card, f"reaches    {prepared.reaches}", panel.skin.dim, 11)
    paint.text(
        card,
        "An answer drawn from a selection is an answer about that selection: "
        f"{prepared.set_aside} passages will not be seen by the model.",
        panel.skin.faint,
        10,
    )
    ctk.CTkButton(
        card,
        text="Send to the engine",
        width=170,
        height=32,
        corner_radius=8,
        fg_color=panel.skin.accent,
        hover_color=panel.skin.accent,
        text_color=panel.skin.ink,
        font=ctk.CTkFont(size=12, weight="bold"),
        command=lambda: _send(prepared, below, panel, state),
    ).pack(anchor="w", pady=(10, 0))


def _send(prepared: Prepared, below: ctk.CTkFrame, panel: Panel, state: State) -> None:
    """Start the run on a worker thread and begin watching for its result."""
    if state.send_question is None:
        return
    for child in below.winfo_children():
        child.destroy()
    card = paint.card(below, panel.skin, stripe=panel.skin.accent)
    waiting = paint.text(card, "Asking the engine...", panel.skin.ink, 13, bold=True)
    paint.text(
        card,
        f"{prepared.selected} passages went with your question. A 14B model over a window "
        "this size took 28 seconds when this was measured; yours depends on your machine.",
        panel.skin.faint,
        11,
    )

    answers: queue.Queue[Asked] = queue.Queue()
    stopped = threading.Event()
    send = state.send_question

    def work() -> None:
        """The worker. It touches no widget - that is the whole of its contract."""
        answers.put(send(prepared))

    ctk.CTkButton(
        card,
        text="Stop waiting",
        width=130,
        height=28,
        corner_radius=8,
        fg_color=panel.skin.card,
        hover_color=panel.skin.contradicted,
        text_color=panel.skin.dim,
        font=ctk.CTkFont(size=11),
        command=lambda: _give_up(stopped, waiting, panel),
    ).pack(anchor="w", pady=(10, 0))
    paint.text(
        card,
        "Stopping stops this window waiting. The engine keeps generating and the run is "
        "already in the audit log - the answer is discarded unread.",
        panel.skin.faint,
        10,
    )

    threading.Thread(target=work, daemon=True, name="lacc-asking").start()
    _watch(answers, stopped, time.monotonic(), waiting, below, panel)


def _give_up(stopped: threading.Event, waiting: ctk.CTkLabel, panel: Panel) -> None:
    """Stop watching. Say exactly what that did and what it did not do."""
    stopped.set()
    if _alive(waiting):
        waiting.configure(
            text="Stopped waiting. The engine was not told - it is still generating.",
            text_color=panel.skin.dim,
        )


def _watch(
    answers: queue.Queue[Asked],
    stopped: threading.Event,
    began: float,
    waiting: ctk.CTkLabel,
    below: ctk.CTkFrame,
    panel: Panel,
) -> None:
    """Look at the queue, count the seconds, and draw the answer when one arrives.

    **The only place in this feature that writes to a widget after a send**, and it runs on
    the Tk thread because `after` puts it there. The worker never reaches past the queue.
    """
    if stopped.is_set() or not _alive(below):
        return
    try:
        answered = answers.get_nowait()
    except queue.Empty:
        if _alive(waiting):
            waiting.configure(text=f"Asking the engine... {time.monotonic() - began:.0f}s")
        below.after(EVERY, lambda: _watch(answers, stopped, began, waiting, below, panel))
        return
    for child in below.winfo_children():
        child.destroy()
    _draw(answered, below, panel)


def _draw(answered: Asked, below: ctk.CTkFrame, panel: Panel) -> None:
    """The result, and a failure in the same place and the same shape as an answer."""
    if not answered.worked:
        failed = paint.card(below, panel.skin, stripe=panel.skin.contradicted)
        paint.text(failed, "Nothing came back", panel.skin.ink, 13, bold=True)
        paint.text(failed, answered.failure or "The engine returned no text.", panel.skin.dim, 12)
        paint.text(
            failed,
            "Check the engine from the button at the bottom right. Nothing was written and "
            "the corpus is untouched.",
            panel.skin.faint,
            10,
        )
        return

    card = paint.card(below, panel.skin, stripe=panel.skin.accent)
    paint.text(card, "Answer", panel.skin.ink, 13, bold=True)
    paint.text(card, answered.answer, panel.skin.ink, 12)
    paint.text(
        card,
        f"{answered.seconds:.0f}s   ·   {answered.prepared.selected} of "
        f"{answered.prepared.considered} passages   ·   {answered.prepared.model}",
        panel.skin.faint,
        10,
    )

    if not answered.readings:
        note = paint.card(below, panel.skin)
        paint.text(
            note,
            "No quotations to check: the answer did not use the format, so nothing in it "
            "was verified.",
            panel.skin.dim,
            11,
        )
        return
    good = len(answered.readings) - answered.invented
    check = paint.card(
        below,
        panel.skin,
        stripe=panel.skin.contradicted if answered.invented else panel.skin.supported,
    )
    if answered.invented:
        paint.text(
            check,
            f"{answered.invented} of {len(answered.readings)} quotations are not in what was sent",
            panel.skin.contradicted,
            13,
            bold=True,
        )
        paint.text(
            check,
            "The model quoted something it was not shown. Do not cite these without opening "
            "the document.",
            panel.skin.dim,
            11,
        )
        for reading in answered.readings:
            if not reading.found:
                paint.text(check, f"  x  {reading.quote[:QUOTED]}", panel.skin.contradicted, 11)
    else:
        paint.text(
            check,
            f"All {good} quotations are in the passages that were sent",
            panel.skin.supported,
            13,
            bold=True,
        )
    paint.text(
        check,
        "Checked against what the model was shown, not against the documents - those were "
        "checked when the corpus was built.",
        panel.skin.faint,
        10,
    )


SECTIONS = (Section("Ask", _list_corpora, _open_corpus),)
