"""Where the work stands, and how far the corpus reaches.

Two sections that were only ever a line along the bottom or a file to open by hand. Both draw
data somebody else decided: `features/stages.py` says what a stage is and when it is settled,
and `features/coverage.py` says how close the corpus gets to a topic. Nothing here computes
either (ADR-066).

**Neither runs anything.** `status` counts files, and a coverage measurement is read from the
numbers a run left beside its report - the same arrangement that lets the window paint a
review's findings without an engine (ADR-069).
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from local_ai_control_center.features.coverage import measured_from, measurements_in
from local_ai_control_center.features.stages import Work, stages_in
from local_ai_control_center.views import paint
from local_ai_control_center.views.section import Panel, Section, Sidebar, State

NEAR_THE_FLOOR = 0.06
"""How close to the control a topic sits before it is drawn in the colour of a contradiction.

**Not a threshold that decides anything** - the report calls nothing a gap, and neither does
this. It chooses a colour, so a person's eye reaches the bottom of the list first, which is
where the work is (ADR-088).
"""

QUOTED = 200


def _stand(state: State) -> Work:
    return stages_in(state.workspace, state.context_file)


def _show_work(side: Sidebar, panel: Panel, state: State) -> None:
    """The six stages, each with what it produced and what it has not."""
    work = _stand(state)
    if not work.stages:
        panel.said(
            "No workspace to read",
            f"Nothing at {state.workspace}. Point a configuration at one that exists.",
        )
        return
    panel.said(
        "Where the work stands",
        f"{work.settled} of {len(work.stages)} stages have nothing outstanding.   ·   "
        f"{state.workspace}\nCounted from the files every time. No model is called and "
        "nothing is written.",
    )
    for stage in work.stages:
        edge = panel.skin.supported if stage.settled else panel.skin.accent
        body = paint.card(panel.body, panel.skin, stripe=edge)
        said = "done" if stage.settled else "open"
        paint.text(body, f"{said}   {stage.name}", edge, 13, bold=True)
        if stage.done:
            paint.text(body, stage.done, panel.skin.ink, 12)
        if stage.missing:
            # What is missing is the point of this screen. A stage that reads like success
            # while something is outstanding is the sentence this project has measured the
            # cost of (ADR-080).
            paint.text(body, stage.missing, panel.skin.contradicted, 12)
        paint.fixed(body, stage.command, panel.skin.faint, 11)


def _list_coverage(side: Sidebar, panel: Panel, state: State) -> None:
    found = measurements_in(state.workspace)
    for path in found:
        side.row(str(path), path.name.removesuffix(".reaches.json"))
    if found:
        panel.said(
            "Coverage",
            f"{len(found)} measurements. Choose one to see how far the nearest quotation is "
            "from each topic you named.\nNothing here is called a gap: a similarity is an "
            "ordering, not an interval.",
        )
        return
    panel.said(
        "No coverage measured yet",
        "Write a file of topics - one per line, with one line marked `!` as a subject "
        "deliberately outside your field - and run\n"
        "  lacc coverage <topics> --against <corpus> --into cobertura.md\n"
        "The marked line is the floor the rest are read against.",
    )


def _show_coverage(key: str, panel: Panel, state: State) -> None:
    measured = measured_from(Path(key))
    if measured is None or not measured.reaches:
        panel.said(
            "This measurement could not be read",
            "Nothing is shown rather than half of it: a coverage report missing its control "
            "would read as having no floor.",
        )
        return
    control = next((one for one in measured.reaches if one.topic.control), None)
    panel.said(
        f"{len(measured.reaches)} topics against {measured.corpus}",
        f"{measured.model}   ·   taken {measured.taken}\n"
        + (
            f"The floor is {measured.floor:.2f}, reached by the topic written to sit outside "
            "this subject. A topic near it is one your corpus barely speaks to; how near is "
            "your judgement, not this tool's."
            if control is not None
            else "No control topic was given, so these numbers have no floor. Mark one line "
            "of your topics file with ! and take this again."
        ),
    )
    for one in measured.reaches:
        near = control is not None and one.nearest - measured.floor <= NEAR_THE_FLOOR
        edge = panel.skin.contradicted if near else panel.skin.supported
        if one.topic.control:
            edge = panel.skin.faint
        body = paint.card(panel.body, panel.skin, stripe=edge)
        name = f"{one.topic.said}   (control)" if one.topic.control else one.topic.said
        paint.text(body, f"{one.nearest:.2f}   {name}", edge, 13, bold=True)
        counted = "   ".join(
            f"{count} from {documents} documents at {level:.2f}"
            for level, count, documents in one.within
        )
        if counted:
            paint.text(body, counted, panel.skin.faint, 10)
        where = f"{one.document}, p. {one.page}" if one.page else one.document
        paint.text(body, f"“{one.quote[:QUOTED]}”", panel.skin.ink, 12)
        paint.text(body, where, panel.skin.dim, 10)
    ctk.CTkLabel(
        panel.body,
        text="  This says what is thin. It cannot say what is missing: a subject absent from "
        "both your corpus and your topics file is invisible to it.",
        anchor="w",
        justify="left",
        wraplength=760,
        text_color=panel.skin.faint,
        font=ctk.CTkFont(size=10),
    ).pack(fill="x", padx=18, pady=(8, 14))


SECTIONS = (
    Section("Where it stands", _show_work),
    Section("Coverage", _list_coverage, _show_coverage),
)
