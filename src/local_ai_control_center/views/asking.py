"""The one section that runs something, as a thread of questions (ADR-085, ADR-091).

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

**And the thread carries what was checked, never what was said.** A conversation puts the
previous answer into the next prompt, which would let an invented quotation verify one turn
later - the check would confirm it, because it really would be in what was sent. What
accumulates here is the passages whose quotations were found.

It decides nothing. What a prepared question is, what a turn establishes and what a thread
carries are all in `features/`; running it is the cycle's, handed in because a section may
reach neither (ADR-066, ADR-075).
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

import customtkinter as ctk

from local_ai_control_center.features.ask import Asked, Prepared
from local_ai_control_center.features.overview import documents_in
from local_ai_control_center.features.thread import Thread, Turn, established_by
from local_ai_control_center.views import paint
from local_ai_control_center.views.section import Panel, Section, Sidebar, State

EVERY = 200
"""Milliseconds between looks at the queue. Slow enough to cost nothing, fast enough that
the elapsed seconds move."""

BOX_HEIGHT = 92
QUOTED = 220
"""Characters of a quotation shown before it is cut. A passage can be a paragraph."""

_THREADS: dict[str, Thread] = {}
"""The threads open in this window, by corpus.

**Not saved, and deliberately.** A thread is a way of working rather than a record; the
record is the audit log, which holds every question, every prompt and every answer and is
hash-chained. Closing the window ends them (ADR-091).
"""


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


def _thread_for(corpus: str) -> Thread:
    return _THREADS.setdefault(corpus, Thread(corpus=corpus))


def _list_corpora(side: Sidebar, panel: Panel, state: State) -> None:
    found = [
        seen for seen in documents_in(state.workspace, state.context_file) if seen.kind == "corpus"
    ]
    for seen in found:
        open_now = _THREADS.get(seen.name)
        turns = f"   ({len(open_now.turns)})" if open_now and open_now.turns else ""
        side.row(str(seen.path), f"{seen.name}{turns}")
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
        f"{len(found)} corpora. Choose one and write a question; ask again and the thread "
        "carries what the answers established.\nIt is not a conversation: what carries is "
        "the passages whose quotations were found, never what the model said.",
    )


def _open_corpus(key: str, panel: Panel, state: State) -> None:
    """The box to write in, then the thread so far, newest first."""
    if state.prepare_question is None or state.send_question is None:
        panel.said("Questions are unavailable", "This window was opened without them.")
        return
    corpus = Path(key).name
    thread = _thread_for(corpus)
    carried = thread.carried
    panel.said(
        corpus,
        f"{len(thread.turns)} questions so far   ·   {len(carried)} passages established\n"
        "Nothing is sent until you have seen what would be. A follow-up has to be a whole "
        "question: the ranking reads your words, not the thread.",
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
    said = (
        "The ranking is by the words you use. It does not cross languages unless an "
        "embedding model is configured."
    )
    if carried:
        said += (
            f"   {len(carried)} passages established earlier go with every question in this thread."
        )
    paint.text(body, said, panel.skin.faint, 10)

    below = ctk.CTkFrame(panel.body, fg_color="transparent")
    below.pack(fill="both", expand=True)

    line = ctk.CTkFrame(body, fg_color="transparent")
    line.pack(fill="x", pady=(8, 0))
    ctk.CTkButton(
        line,
        text="Prepare",
        width=110,
        height=30,
        corner_radius=8,
        fg_color=panel.skin.card,
        hover_color=panel.skin.accent,
        text_color=panel.skin.ink,
        font=ctk.CTkFont(size=12),
        command=lambda: _prepare(box, corpus, below, panel, state),
    ).pack(side="left")
    if thread.turns:
        ctk.CTkButton(
            line,
            text="Start over",
            width=110,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            hover_color=panel.skin.card,
            text_color=panel.skin.faint,
            font=ctk.CTkFont(size=11),
            command=lambda: _forget(corpus, key, panel, state),
        ).pack(side="left", padx=10)

    _draw_thread(thread, below, panel)


def _forget(corpus: str, key: str, panel: Panel, state: State) -> None:
    """Drop the thread and draw the section again, empty."""
    _THREADS[corpus] = Thread(corpus=corpus)
    for child in panel.body.winfo_children():
        child.destroy()
    _open_corpus(key, panel, state)


def _draw_thread(thread: Thread, below: ctk.CTkFrame, panel: Panel) -> None:
    """The turns so far, newest first, so the last answer sits under the box."""
    for turn in reversed(thread.turns):
        card = paint.card(
            below,
            panel.skin,
            stripe=panel.skin.accent if turn.worked else panel.skin.contradicted,
        )
        paint.text(card, turn.question, panel.skin.ink, 13, bold=True)
        if not turn.worked:
            paint.text(card, turn.failure or "No answer came back.", panel.skin.dim, 12)
            continue
        paint.text(card, turn.answer, panel.skin.ink, 12)
        invented = (
            f"   ·   {turn.invented} quotations not in what was sent" if turn.invented else ""
        )
        paint.text(
            card,
            f"{turn.seconds:.0f}s   ·   {turn.selected} of {turn.considered} passages   ·   "
            f"{len(turn.established)} established{invented}",
            panel.skin.contradicted if turn.invented else panel.skin.faint,
            10,
        )


def _prepare(
    box: ctk.CTkTextbox, corpus: str, below: ctk.CTkFrame, panel: Panel, state: State
) -> None:
    """Rank the corpus and draw what would be sent. The prompt itself goes nowhere."""
    if state.prepare_question is None:
        return
    for child in below.winfo_children():
        child.destroy()
    thread = _thread_for(corpus)
    prepared = state.prepare_question(box.get("1.0", "end"), corpus, thread.carried)
    if prepared.refusal:
        refused = paint.card(below, panel.skin, stripe=panel.skin.contradicted)
        paint.text(refused, prepared.refusal, panel.skin.ink, 12)
        _draw_thread(thread, below, panel)
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
    if prepared.established:
        paint.fixed(
            card,
            f"of those   {prepared.established} established earlier in this thread",
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
        command=lambda: _send(prepared, corpus, below, panel, state),
    ).pack(anchor="w", pady=(10, 0))
    _draw_thread(thread, below, panel)


def _send(prepared: Prepared, corpus: str, below: ctk.CTkFrame, panel: Panel, state: State) -> None:
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
    _watch(answers, stopped, time.monotonic(), waiting, below, panel, corpus)


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
    corpus: str,
) -> None:
    """Count the seconds, and put the answer in the thread when it arrives.

    **The only place in this feature that writes to a widget after a send**, and it runs on
    the Tk thread because `after` puts it there. The worker never reaches past the queue.

    What goes into the thread is the turn, and what the turn carries forward is
    `established_by` - the passages whose quotations were **found**. An invention contributes
    nothing to the next question, which is the whole of ADR-091.
    """
    if stopped.is_set() or not _alive(below):
        return
    try:
        answered = answers.get_nowait()
    except queue.Empty:
        if _alive(waiting):
            waiting.configure(text=f"Asking the engine... {time.monotonic() - began:.0f}s")
        below.after(EVERY, lambda: _watch(answers, stopped, began, waiting, below, panel, corpus))
        return

    _THREADS[corpus] = _thread_for(corpus).after(
        Turn(
            question=answered.prepared.question,
            answer=answered.answer,
            failure=answered.failure,
            seconds=answered.seconds,
            selected=answered.prepared.selected,
            considered=answered.prepared.considered,
            # Only the quotations that were **found**. An invention contributes nothing
            # to the next question, which is the whole of ADR-091.
            established=established_by(
                answered.prepared.chosen,
                tuple(r.quote for r in answered.readings if r.found) if answered.worked else (),
            ),
            invented=answered.invented,
        )
    )
    for child in below.winfo_children():
        child.destroy()
    _draw(answered, below, panel)
    _draw_thread(_THREADS[corpus], below, panel)


def _draw(answered: Asked, below: ctk.CTkFrame, panel: Panel) -> None:
    """What the check found. The answer itself is drawn with its turn, below this."""
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

    if not answered.readings:
        note = paint.card(below, panel.skin)
        paint.text(
            note,
            "No quotations to check: the answer did not use the format, so nothing in it "
            "was verified - and this turn establishes nothing for the next one.",
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
            "the document - and they establish nothing for the next question.",
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
