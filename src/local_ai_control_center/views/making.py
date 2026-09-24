"""Making a workspace, and saying what it would cost before it is made (ADR-093).

The second thing this window writes, after its own appearance - and only ever a **new**
configuration. It never edits one of yours: the configuration is the user's, and a window
that edits it is a window that can be wrong about what the user meant (ADR-069).

**Check produces the button**, the way `Prepare` does in the asking section. Pressing it
writes nothing: it says what would be created, whether the folder is already there, and every
warning that applies. The control that creates is drawn by that drawing (ADR-085).

**A warning is a warning.** A synchronising folder is a guess from a name and is allowed, with
what to do about it beside it; a git working tree is a fact and is refused.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from local_ai_control_center.core.config import Config, load_config
from local_ai_control_center.features.workspaces import (
    as_yaml,
    intended,
    points_of,
    risk_of,
)
from local_ai_control_center.views import paint
from local_ai_control_center.views.section import Panel, Section, Sidebar, State


def _list_workspaces(side: Sidebar, panel: Panel, state: State) -> None:
    """Every configuration and the workspace it names, with the one in force first."""
    found = points_of(state.configs)
    panel.said(
        "Workspaces",
        f"{len(found)} configurations in {state.configs}. Each names one workspace, and the "
        "picker at the top of the rail chooses which is read.\nNothing here changes a "
        "configuration you wrote. Creating one writes a new file and refuses an existing "
        "name.",
    )
    for one in found:
        here = one.name == state.chosen_configuration
        edge = panel.skin.accent if here else panel.skin.card
        body = paint.card(panel.body, panel.skin, stripe=edge)
        said = f"{one.name}   (in force)" if here else one.name
        paint.text(body, said, panel.skin.ink if here else panel.skin.dim, 13, bold=True)
        if one.unreadable:
            paint.text(body, f"could not be read: {one.unreadable}", panel.skin.contradicted, 11)
            continue
        paint.fixed(body, one.workspace, panel.skin.dim, 11)
        there = "the folder is there" if one.exists else "the folder does not exist yet"
        paint.text(body, f"{one.model}   ·   {there}", panel.skin.faint, 10)
        danger = risk_of(Path(one.workspace))
        if danger.refused:
            paint.text(body, danger.refused, panel.skin.contradicted, 10)
        elif danger.warned:
            paint.text(body, danger.warned, panel.skin.contradicted, 10)

    _form(panel, state)


def _form(panel: Panel, state: State) -> None:
    """A folder, a name, and a button that checks rather than creates."""
    body = paint.card(panel.body, panel.skin, stripe=panel.skin.supported)
    paint.text(body, "Make another workspace", panel.skin.ink, 14, bold=True)
    paint.text(
        body,
        "A folder for the material and a configuration naming it. The engine settings are "
        "copied from the one in force, because a configuration without them is a workspace "
        "that cannot do anything.",
        panel.skin.faint,
        11,
    )

    paint.text(body, "folder", panel.skin.dim, 11, bold=True)
    folder = ctk.CTkEntry(
        body,
        height=32,
        corner_radius=8,
        fg_color=panel.skin.surface,
        text_color=panel.skin.ink,
        border_width=0,
        font=ctk.CTkFont(size=12),
    )
    folder.insert(0, str(Path(state.workspace).parent / "another-workspace"))
    folder.pack(fill="x", pady=(2, 8))

    paint.text(body, "call the configuration", panel.skin.dim, 11, bold=True)
    called = ctk.CTkEntry(
        body,
        height=32,
        corner_radius=8,
        fg_color=panel.skin.surface,
        text_color=panel.skin.ink,
        border_width=0,
        font=ctk.CTkFont(size=12),
    )
    called.insert(0, "another")
    called.pack(fill="x", pady=(2, 8))

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
        command=lambda: _check(folder, called, below, panel, state),
    ).pack(anchor="w", pady=(6, 0))


def _check(
    folder: ctk.CTkEntry,
    called: ctk.CTkEntry,
    below: ctk.CTkFrame,
    panel: Panel,
    state: State,
) -> None:
    """Say what would happen. Nothing is written."""
    for child in below.winfo_children():
        child.destroy()
    where = folder.get().strip()
    name = called.get().strip()
    if not where or not name:
        card = paint.card(below, panel.skin, stripe=panel.skin.contradicted)
        paint.text(card, "A folder and a name are both needed.", panel.skin.ink, 12)
        return

    config = _config_in_force(state)
    if config is None:
        card = paint.card(below, panel.skin, stripe=panel.skin.contradicted)
        paint.text(
            card,
            "The configuration in force could not be read, so there is nothing to copy the "
            "engine settings from.",
            panel.skin.ink,
            12,
        )
        return

    root = Path(where).expanduser()
    plan = intended(name, root, config)
    destination = Path(state.configs) / plan.name
    danger = risk_of(root)

    card = paint.card(
        below,
        panel.skin,
        stripe=panel.skin.contradicted if not danger.usable else panel.skin.accent,
    )
    paint.text(card, "This is what would be made", panel.skin.ink, 13, bold=True)
    paint.fixed(card, f"folder        {root}", panel.skin.dim, 11)
    paint.fixed(
        card,
        f"              {'already there' if plan.exists else 'created, empty'}",
        panel.skin.dim,
        11,
    )
    paint.fixed(card, f"configuration {destination}", panel.skin.dim, 11)
    paint.fixed(card, f"model         {plan.model}", panel.skin.dim, 11)

    if destination.exists():
        paint.text(
            card,
            f"{plan.name} already exists, and nothing here replaces a file of yours. Choose "
            "another name.",
            panel.skin.contradicted,
            12,
        )
        return
    if danger.refused:
        paint.text(card, danger.refused, panel.skin.contradicted, 12)
        return
    if danger.warned:
        paint.text(card, danger.warned, panel.skin.contradicted, 12)
        paint.text(card, danger.advice, panel.skin.dim, 11)

    paint.text(card, "what the configuration would say", panel.skin.faint, 10, bold=True)
    paint.fixed(paint.card(below, panel.skin), as_yaml(root, config), panel.skin.dim)
    ctk.CTkButton(
        card,
        text="Create it",
        width=140,
        height=32,
        corner_radius=8,
        fg_color=panel.skin.accent,
        hover_color=panel.skin.accent,
        text_color=panel.skin.ink,
        font=ctk.CTkFont(size=12, weight="bold"),
        command=lambda: _create(root, destination, below, panel, state),
    ).pack(anchor="w", pady=(10, 0))


def _create(root: Path, destination: Path, below: ctk.CTkFrame, panel: Panel, state: State) -> None:
    """Make the folder and write the configuration, refusing an existing file."""
    config = _config_in_force(state)
    if config is None:
        return
    for child in below.winfo_children():
        child.destroy()
    try:
        root.mkdir(parents=True, exist_ok=True)
        # Exclusive creation: an existing file is refused rather than replaced, which is how
        # everything this program writes reaches disk (ADR-039).
        with destination.open("x", encoding="utf-8") as handle:
            handle.write(as_yaml(root, config))
    except OSError as error:
        card = paint.card(below, panel.skin, stripe=panel.skin.contradicted)
        paint.text(card, f"Nothing was made: {error}", panel.skin.ink, 12)
        return

    card = paint.card(below, panel.skin, stripe=panel.skin.supported)
    paint.text(card, f"{destination.name} written", panel.skin.supported, 13, bold=True)
    paint.fixed(card, str(root), panel.skin.dim, 11)
    paint.text(
        card,
        "Choose it in the picker at the top of the rail to work there. From a terminal, name "
        f"it with  -c {destination}",
        panel.skin.dim,
        11,
    )


def _config_in_force(state: State) -> Config | None:
    """The configuration the window is reading, or nothing if it cannot be read."""
    try:
        return load_config(Path(state.configs) / state.chosen_configuration)
    except Exception:  # noqa: BLE001 - a configuration may fail in any way
        return None


SECTIONS = (Section("Workspaces", _list_workspaces, group="YOUR WORK"),)
