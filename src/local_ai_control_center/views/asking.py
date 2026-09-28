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
from dataclasses import dataclass
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


@dataclass
class _Pending:
    """A question with the engine, and where its answer is drawn if anybody is looking."""

    key: str
    state: State
    prepared: Prepared
    answers: queue.Queue[Asked]
    stopped: threading.Event
    began: float


_PENDING: dict[str, _Pending] = {}
"""Questions in flight, by corpus.

A change of section destroys every widget in the panel and none of these. Keeping the answer
used to happen only while its widgets were alive, so an answer that arrived while somebody
was looking at another section was lost - in the audit, and nowhere on the screen (ADR-099).
"""

_LAST: dict[str, Asked] = {}
"""The last answer each corpus received, so its check is still there after a change of
section."""

_UNSEEN: set[str] = set()
"""Corpora whose last answer arrived while nobody was looking at them."""

_DRAWN: dict[str, tuple[ctk.CTkLabel, ctk.CTkButton]] = {}
"""Where each corpus's waiting is on the screen right now - the label counting the seconds
and the button that stops it. Kept apart from the question: they change with every redraw,
and the question does not."""

_BOXES: dict[str, ctk.CTkTextbox] = {}
"""The box each open corpus is written in, so a redraw keeps what was being typed."""


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


def _open_corpus(key: str, panel: Panel, state: State, draft: str = "") -> None:
    """The box to write in, then the thread so far, newest first.

    Also what is still waiting, or the last answer's check with a line saying it arrived while
    you were elsewhere - both survive a change of section (ADR-099).
    """
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
    if draft:
        box.insert("1.0", draft)
    _BOXES[corpus] = box
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
        command=lambda: _prepare(box, key, below, panel, state),
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

    pending = _PENDING.get(corpus)
    if pending is not None and not pending.stopped.is_set():
        _draw_waiting(pending, below, panel)
    elif corpus in _LAST:
        if corpus in _UNSEEN:
            _UNSEEN.discard(corpus)
            paint.text(
                below,
                "This answer arrived while you were in another section.",
                panel.skin.dim,
                11,
            )
        _draw(_LAST[corpus], below, panel)
    _draw_thread(thread, below, panel)


def _forget(corpus: str, key: str, panel: Panel, state: State) -> None:
    """Drop the thread and draw the section again, empty.

    Anything still in flight is stopped too: its answer belonged to the thread just ended
    (ADR-099).
    """
    pending = _PENDING.get(corpus)
    if pending is not None:
        pending.stopped.set()
    _THREADS[corpus] = Thread(corpus=corpus)
    _LAST.pop(corpus, None)
    _UNSEEN.discard(corpus)
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
    box: ctk.CTkTextbox, key: str, below: ctk.CTkFrame, panel: Panel, state: State
) -> None:
    """Rank the corpus and draw what would be sent. The prompt itself goes nowhere."""
    if state.prepare_question is None:
        return
    corpus = Path(key).name
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
        command=lambda: _send(prepared, key, below, panel, state),
    ).pack(anchor="w", pady=(10, 0))
    _draw_thread(thread, below, panel)


def _send(prepared: Prepared, key: str, below: ctk.CTkFrame, panel: Panel, state: State) -> None:
    """Start the run on a worker thread and begin watching for its result.

    One question per corpus at a time: a second answer would have taken the first one's
    place in the thread (ADR-099).
    """
    if state.send_question is None:
        return
    corpus = Path(key).name
    waiting_already = _PENDING.get(corpus)
    if waiting_already is not None and not waiting_already.stopped.is_set():
        refused = paint.card(below, panel.skin, stripe=panel.skin.contradicted)
        paint.text(
            refused,
            "A question on this corpus is already with the engine. Wait for its answer, or "
            "stop waiting for it, before sending another.",
            panel.skin.ink,
            12,
        )
        return
    for child in below.winfo_children():
        child.destroy()

    pending = _Pending(
        key=key,
        state=state,
        prepared=prepared,
        answers=queue.Queue(),
        stopped=threading.Event(),
        began=time.monotonic(),
    )
    _PENDING[corpus] = pending
    send = state.send_question
    answers = pending.answers

    def work() -> None:
        """The worker. It touches no widget - that is the whole of its contract."""
        answers.put(send(prepared))

    _draw_waiting(pending, below, panel)
    threading.Thread(target=work, daemon=True, name="lacc-asking").start()
    _watch(corpus, panel)


def _draw_waiting(pending: _Pending, below: ctk.CTkFrame, panel: Panel) -> None:
    """The card that counts the seconds, and the button that stops the waiting."""
    card = paint.card(below, panel.skin, stripe=panel.skin.accent)
    waiting = paint.text(
        card,
        f"Asking the engine... {time.monotonic() - pending.began:.0f}s",
        panel.skin.ink,
        13,
        bold=True,
    )
    paint.text(
        card,
        f"{pending.prepared.selected} passages went with your question. A 14B model over a "
        "window this size took 28 seconds when this was measured; yours depends on your "
        "machine.",
        panel.skin.faint,
        11,
    )
    stop = ctk.CTkButton(
        card,
        text="Stop waiting",
        width=130,
        height=28,
        corner_radius=8,
        fg_color=panel.skin.card,
        hover_color=panel.skin.contradicted,
        text_color=panel.skin.dim,
        font=ctk.CTkFont(size=11),
        command=lambda: _give_up(pending, panel),
    )
    stop.pack(anchor="w", pady=(10, 0))
    _DRAWN[Path(pending.key).name] = (waiting, stop)
    paint.text(
        card,
        "Stopping stops this window waiting. The engine keeps generating and the run is "
        "already in the audit log - the answer is discarded unread. Changing section does not "
        "stop it: the answer is kept, and shown when you come back.",
        panel.skin.faint,
        10,
    )


def _give_up(pending: _Pending, panel: Panel) -> None:
    """Stop watching. Say exactly what that did and what it did not do."""
    pending.stopped.set()
    drawn = _DRAWN.get(Path(pending.key).name)
    if drawn is None:
        return
    waiting, stop = drawn
    if _alive(waiting):
        waiting.configure(
            text="Stopped waiting. The engine was not told and may still be generating; "
            "whatever it returns is discarded unread.",
            text_color=panel.skin.dim,
        )
    if _alive(stop):
        stop.configure(state="disabled")


def _watch(corpus: str, panel: Panel) -> None:
    """Count the seconds, and keep the answer when it arrives - whoever is looking.

    **Scheduled on the panel's frame, which lives as long as the window.** It used to be
    scheduled on the widgets it drew into, and stopped when they were destroyed - so a change
    of section threw the answer away (ADR-099). Keeping is separate from drawing now: the turn
    is recorded in any case, and drawn only if its corpus is on the screen.

    What goes into the thread is the turn, and what the turn carries forward is
    `established_by` - the passages whose quotations were **found**. An invention contributes
    nothing to the next question, which is the whole of ADR-091.
    """
    pending = _PENDING.get(corpus)
    if pending is None:
        return
    if pending.stopped.is_set():
        # Whatever the worker puts in the queue later is never read.
        _PENDING.pop(corpus, None)
        _DRAWN.pop(corpus, None)
        return
    drawn = _DRAWN.get(corpus)
    try:
        answered = pending.answers.get_nowait()
    except queue.Empty:
        if drawn is not None and _alive(drawn[0]):
            drawn[0].configure(text=f"Asking the engine... {time.monotonic() - pending.began:.0f}s")
        panel.body.after(EVERY, lambda: _watch(corpus, panel))
        return

    _PENDING.pop(corpus, None)
    _DRAWN.pop(corpus, None)
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
    _LAST[corpus] = answered
    if drawn is None or not _alive(drawn[0]):
        _UNSEEN.add(corpus)
        return
    # On the screen: drawn again whole, so the heading counts the new turn and Start over is
    # there - and whatever was being typed in the box is put back.
    box = _BOXES.get(corpus)
    draft = box.get("1.0", "end").strip() if box is not None and _alive(box) else ""
    for child in panel.body.winfo_children():
        child.destroy()
    _open_corpus(pending.key, panel, pending.state, draft)


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


SECTIONS = (Section("Ask", _list_corpora, _open_corpus, group="YOUR WORK"),)
