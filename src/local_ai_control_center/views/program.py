"""The sections that read the program: its commands, its prompts, its configuration.

These answer *what can this do and what is it about to ask*, which is a different question
from anything in the workspace. None of them runs anything: a plan is pure, a command list is
derived from the application, and a configuration is read (ADR-072, ADR-074).
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from local_ai_control_center.features.overview import settings_of
from local_ai_control_center.features.reading import blocks_in
from local_ai_control_center.views import paint
from local_ai_control_center.views.section import Panel, Section, Sidebar, State


def _list_commands(side: Sidebar, panel: Panel, state: State) -> None:
    for command in state.commands:
        side.row(f"command:{command.name}", command.name)
    panel.said(
        "Commands",
        f"{len(state.commands)} of them, read from the CLI itself rather than listed here - "
        "a second copy of this list would be a second thing to keep true.\n"
        "The window runs none of them. Copy one and type it in a terminal.",
    )


def _show_command(key: str, panel: Panel, state: State) -> None:
    name = key.removeprefix("command:")
    for command in state.commands:
        if command.name != name:
            continue
        panel.said(f"lacc {command.name}", command.summary)
        body = paint.card(panel.body, panel.skin)
        line = ctk.CTkFrame(body, fg_color="transparent")
        line.pack(fill="x")
        ctk.CTkLabel(
            line,
            text=command.usage,
            anchor="w",
            text_color=panel.skin.accent,
            font=ctk.CTkFont(family="Consolas", size=12),
        ).pack(side="left")
        ctk.CTkButton(
            line,
            text="copy",
            width=54,
            height=24,
            corner_radius=6,
            fg_color=panel.skin.rail,
            hover_color=panel.skin.accent,
            text_color=panel.skin.dim,
            font=ctk.CTkFont(size=10),
            command=lambda where=line, words=command.usage: _copy(where, words, panel),
        ).pack(side="left", padx=10)
        required = [p.shown for p in command.parameters if p.required]
        optional = [p.shown for p in command.parameters if not p.required]
        if required:
            paint.text(body, f"required: {', '.join(required)}", panel.skin.dim, 11)
        if optional:
            paint.text(body, f"optional: {', '.join(optional)}", panel.skin.faint, 11)
        for piece in blocks_in(command.detail):
            paint.block(panel.body, panel.skin, piece)
        return


def _copy(widget: ctk.CTkFrame, words: str, panel: Panel) -> None:
    """Put a command on the clipboard. Copying is not running it."""
    widget.clipboard_clear()
    widget.clipboard_append(words)
    panel.said("Copied", words)


def _list_prompts(side: Sidebar, panel: Panel, state: State) -> None:
    for prompt in state.prompts:
        side.row(f"prompt:{prompt.skill}", prompt.skill if prompt.planned else f"! {prompt.skill}")
    panel.said(
        "Prompts",
        f"{len(state.prompts)} skills, and exactly what each one asks - planned against an "
        "example document, with no model called and nothing sent.\n"
        "A plan is pure by design, which is why reading one is free.",
    )


def _show_prompt(key: str, panel: Panel, state: State) -> None:
    name = key.removeprefix("prompt:")
    for prompt in state.prompts:
        if prompt.skill != name:
            continue
        panel.said(prompt.skill, prompt.summary)
        facts = paint.card(panel.body, panel.skin)
        checked = "checked against the source" if prompt.checks_quotes else "not checked"
        paint.text(facts, f"needs        {', '.join(prompt.needs) or 'nothing'}", panel.skin.dim)
        paint.text(facts, f"quotations   {checked}", panel.skin.dim)
        if prompt.fields:
            paint.text(facts, f"asks for     {', '.join(prompt.fields)}", panel.skin.dim)
        if prompt.temperature is not None:
            paint.text(facts, f"temperature  {prompt.temperature}", panel.skin.dim)
        paint.text(
            facts,
            f"instruction  {prompt.words} words before your document",
            panel.skin.faint,
        )
        body = paint.card(panel.body, panel.skin, stripe=panel.skin.accent)
        paint.fixed(
            body,
            prompt.template,
            panel.skin.ink if prompt.planned else panel.skin.contradicted,
        )
        return


def _show_configuration(side: Sidebar, panel: Panel, state: State) -> None:
    """The configuration in force. Its listing is the whole of the section."""
    if not state.chosen_configuration:
        panel.said("No configuration found", f"Nothing ending in .yaml under {state.configs}.")
        return
    panel.said(
        state.chosen_configuration,
        "What this configuration declares. Reading only - nothing here is written.",
    )
    body = paint.card(panel.body, panel.skin)
    for setting in settings_of(Path(state.configs) / state.chosen_configuration):
        paint.row(body, panel.skin, setting)


SECTIONS = (
    Section("Commands", _list_commands, _show_command, group="THE PROGRAM"),
    Section("Prompts", _list_prompts, _show_prompt, group="THE PROGRAM"),
    Section("Configuration", _show_configuration, group="THE PROGRAM"),
)
