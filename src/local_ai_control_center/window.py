"""The second view: a window that reads (ADR-069).

**It reads and runs nothing.** No skill, no model call, no document written. A review takes
minutes and an engine; a window that ran one would need threads, progress, cancellation and a
way to report an engine that went away - four new ways to be wrong, in a view, on day one.
Running stays in the CLI.

**And it decides nothing.** Which reviews exist, what a finding means, which files are
corpora, what a configuration declares, which colours a theme has: all answered in
`features/`. What is here is widgets, layout and the wiring between them.
`tests/test_layering.py` enforces that, and enforced it before this file existed (ADR-066).

**The one thing it writes is its own appearance.** A theme and the name of the configuration
last chosen, in a file of its own. The configuration itself is the user's: choosing one here
changes *which* is read, never what is in it, because editing is writing and writing has a
preview and a confirmation everywhere else in this project.

Tk cannot be exercised headlessly, so nothing here is covered by a test. That is why it is
this thin.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import ttk

import customtkinter as ctk

from local_ai_control_center.features.appearance import Palette, Preferences, remember
from local_ai_control_center.features.overview import (
    Setting,
    configurations_in,
    corpus_seen,
    documents_in,
    settings_of,
)
from local_ai_control_center.features.review import (
    Finding,
    Reviewed,
    reviewed_from,
    reviews_in,
)

WIDTH, HEIGHT = 1280, 820
RAIL, SIDE = 214, 330

VERDICT_SAID = {
    "contradicted": "your corpus says otherwise",
    "supported": "held up by your corpus",
    "nothing": "not covered - which is not the same as wrong",
}

SECTIONS = ("Reviews", "Corpora", "Documents", "Configuration")


def _text(
    parent: ctk.CTkFrame,
    words: str,
    colour: str,
    size: int = 11,
    bold: bool = False,
    wrap: int = 780,
) -> ctk.CTkLabel:
    """One line or paragraph of text in the panel, left aligned like everything else."""
    label = ctk.CTkLabel(
        parent,
        text=words,
        anchor="w",
        justify="left",
        wraplength=wrap,
        text_color=colour,
        font=ctk.CTkFont(size=size, weight="bold" if bold else "normal"),
    )
    label.pack(fill="x")
    return label


def _card(parent: ctk.CTkFrame, skin: Palette, stripe: str = "") -> ctk.CTkFrame:
    """A panel with an optional coloured edge, which is the window's only real motif."""
    shell = ctk.CTkFrame(parent, fg_color=skin.card, corner_radius=10)
    shell.pack(fill="x", padx=18, pady=7)
    if stripe:
        edge = ctk.CTkFrame(shell, fg_color=stripe, corner_radius=10, width=4)
        edge.pack(side="left", fill="y", padx=(0, 12), pady=2)
    body = ctk.CTkFrame(shell, fg_color="transparent")
    body.pack(side="left", fill="both", expand=True, padx=(0 if stripe else 14, 14), pady=13)
    return body


def _row(parent: ctk.CTkFrame, skin: Palette, setting: Setting) -> None:
    """One label-and-value line of a configuration."""
    line = ctk.CTkFrame(parent, fg_color="transparent")
    line.pack(fill="x", pady=3)
    ctk.CTkLabel(
        line,
        text=setting.label,
        width=150,
        anchor="w",
        text_color=skin.dim,
        font=ctk.CTkFont(size=12),
    ).pack(side="left")
    ctk.CTkLabel(
        line,
        text=setting.value,
        anchor="w",
        text_color=skin.ink,
        font=ctk.CTkFont(size=12, weight="bold"),
    ).pack(side="left")
    if setting.note:
        ctk.CTkLabel(
            line,
            text=f"   {setting.note}",
            anchor="w",
            text_color=skin.faint,
            font=ctk.CTkFont(size=11),
        ).pack(side="left")


def _paragraph_card(parent: ctk.CTkFrame, skin: Palette, finding: Finding) -> None:
    """One paragraph of the draft, with its verdict painted down the edge."""
    colour = skin.for_verdict(finding.verdict)
    body = _card(parent, skin, stripe=colour)
    _text(
        body,
        f"Line {finding.paragraph.line}   {VERDICT_SAID.get(finding.verdict, '')}",
        colour,
        11,
        bold=True,
    )
    _text(body, finding.paragraph.text, skin.ink, 13, wrap=720)
    if finding.quote:
        _text(body, f"“{finding.quote}”\n{finding.document}", skin.dim, 11, wrap=700)
    elif finding.considered:
        _text(body, "Closest in your corpus, and judged not to hold it:", skin.faint, 10)
        for document, quote in finding.considered:
            _text(body, f"• {quote}\n   {document}", skin.faint, 10, wrap=690)


class Window(ctk.CTk):
    """Sections on the left, a list beside them, and what is selected on the right."""

    def __init__(self, folder: Path, configs: Path, preferences: Preferences, saved: Path) -> None:
        super().__init__()
        self.folder = folder
        self.configs = configs
        self.preferences = preferences
        self.saved = saved
        self.skin = preferences.palette()
        self.section = SECTIONS[0]

        available = [p.name for p in configurations_in(configs)]
        self.chosen = preferences.configuration or (available[0] if available else "")

        self.title("LACC")
        self.geometry(f"{WIDTH}x{HEIGHT}")
        ctk.set_appearance_mode(self.skin.mode)
        self.configure(fg_color=self.skin.surface)

        self._rail(available)
        self._middle()
        self._panel()
        self._go(SECTIONS[0])

    # --- the three columns ---------------------------------------------------------------

    def _rail(self, available: list[str]) -> None:
        """The far left: what the application is, where it is pointed, and how it looks."""
        skin = self.skin
        rail = ctk.CTkFrame(self, width=RAIL, corner_radius=0, fg_color=skin.rail)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        _pad = ctk.CTkFrame(rail, fg_color="transparent", height=18)
        _pad.pack(fill="x")
        holder = ctk.CTkFrame(rail, fg_color="transparent")
        holder.pack(fill="x", padx=18)
        _text(holder, "LACC", skin.ink, 19, bold=True, wrap=180)
        _text(holder, "reads what you wrote", skin.faint, 11, wrap=180)

        self.buttons: dict[str, ctk.CTkButton] = {}
        spacer = ctk.CTkFrame(rail, fg_color="transparent", height=14)
        spacer.pack(fill="x")
        for name in SECTIONS:
            button = ctk.CTkButton(
                rail,
                text=name,
                anchor="w",
                height=34,
                corner_radius=8,
                fg_color="transparent",
                hover_color=skin.card,
                text_color=skin.dim,
                font=ctk.CTkFont(size=13),
                command=lambda picked=name: self._go(picked),
            )
            button.pack(fill="x", padx=12, pady=2)
            self.buttons[name] = button

        under = ctk.CTkFrame(rail, fg_color="transparent")
        under.pack(fill="x", side="bottom", pady=(0, 16))

        _text(under, "  THEME", skin.faint, 10, bold=True, wrap=180)
        themes = ctk.CTkOptionMenu(
            under,
            values=list(self.preferences.names()),
            height=30,
            corner_radius=8,
            fg_color=skin.card,
            button_color=skin.card,
            button_hover_color=skin.accent,
            text_color=skin.ink,
            font=ctk.CTkFont(size=11),
            command=self._theme,
        )
        themes.set(self.preferences.theme)
        themes.pack(fill="x", padx=12, pady=(2, 12))

        _text(under, "  CONFIGURATION", skin.faint, 10, bold=True, wrap=180)
        self.picker = ctk.CTkOptionMenu(
            under,
            values=available or ["none found"],
            height=30,
            corner_radius=8,
            fg_color=skin.card,
            button_color=skin.card,
            button_hover_color=skin.accent,
            text_color=skin.ink,
            font=ctk.CTkFont(size=11),
            command=self._switch,
        )
        self.picker.set(self.chosen or "none found")
        self.picker.pack(fill="x", padx=12, pady=2)
        _text(under, "  changes which is read,\n  never what is in it", skin.faint, 10, wrap=185)

        _text(under, "\n  WORKSPACE", skin.faint, 10, bold=True, wrap=180)
        _text(under, f"  {self.folder}", skin.dim, 10, wrap=185)

    def _middle(self) -> None:
        """The list for the current section."""
        skin = self.skin
        side = ctk.CTkFrame(self, width=SIDE, corner_radius=0, fg_color=skin.side)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Side.Treeview",
            background=skin.side,
            fieldbackground=skin.side,
            foreground=skin.ink,
            borderwidth=0,
            rowheight=30,
            font=("Segoe UI", 10),
        )
        style.map("Side.Treeview", background=[("selected", skin.accent)])
        self.tree = ttk.Treeview(side, show="tree", style="Side.Treeview", selectmode="browse")
        self.tree.pack(fill="both", expand=True, padx=10, pady=12)
        self.tree.bind("<<TreeviewSelect>>", self._chosen_in_tree)

    def _panel(self) -> None:
        """The right: a heading, a summary and whatever the selection calls for."""
        skin = self.skin
        self.right = ctk.CTkScrollableFrame(self, fg_color=skin.surface)
        self.right.pack(side="left", fill="both", expand=True)
        self.title_label = ctk.CTkLabel(
            self.right,
            text="",
            anchor="w",
            text_color=skin.ink,
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.title_label.pack(fill="x", padx=18, pady=(20, 2))
        self.summary = ctk.CTkLabel(
            self.right,
            text="",
            anchor="w",
            wraplength=800,
            justify="left",
            text_color=skin.dim,
            font=ctk.CTkFont(size=12),
        )
        self.summary.pack(fill="x", padx=18, pady=(0, 12))
        self.body = ctk.CTkFrame(self.right, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

    # --- what the controls do ------------------------------------------------------------

    def _clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def _said(self, title: str, summary: str) -> None:
        self.title_label.configure(text=title)
        self.summary.configure(text=summary)

    def _theme(self, name: str) -> None:
        """Remember the theme. It applies when the window is opened again."""
        self.preferences = self.preferences.model_copy(update={"theme": name})
        remember(self.saved, self.preferences)
        self._clear()
        self._said(
            f"Theme set to {name}",
            "Saved. Colours apply the next time you open the window - Tk builds its widgets "
            "once, and rebuilding them live is the kind of thing that leaves half a window "
            "in the old palette.",
        )

    def _switch(self, name: str) -> None:
        """Read a different configuration. Nothing of yours is written."""
        self.chosen = name
        self.preferences = self.preferences.model_copy(update={"configuration": name})
        remember(self.saved, self.preferences)
        self._go("Configuration")

    def _go(self, section: str) -> None:
        """Show one section: fill the list, empty the panel."""
        self.section = section
        for name, button in self.buttons.items():
            button.configure(
                text_color=self.skin.ink if name == section else self.skin.dim,
                fg_color=self.skin.card if name == section else "transparent",
            )
        self.tree.delete(*self.tree.get_children())
        self._clear()
        if section == "Reviews":
            self._list_reviews()
        elif section == "Corpora":
            self._list_files("corpus", "Corpora", "Choose one to count what it holds.")
        elif section == "Documents":
            self._list_files("document", "Documents", "Everything else in the workspace.")
        else:
            self._show_configuration()

    def _list_reviews(self) -> None:
        found = reviews_in(self.folder)
        for path in found:
            self.tree.insert("", "end", iid=str(path), text=f"  {path.name}")
        if found:
            self._said("Reviews", "Choose one to see your draft with its verdicts.")
        else:
            self._said(
                "No reviews yet",
                "Run  lacc review <draft> --against <corpus> --into report.md  and the "
                "findings appear beside the report. This window reads them; it does not run "
                "anything.",
            )

    def _list_files(self, kind: str, title: str, said: str) -> None:
        for seen in documents_in(self.folder):
            if seen.kind == kind:
                self.tree.insert("", "end", iid=str(seen.path), text=f"  {seen.name}")
        self._said(title, said)

    def _show_configuration(self) -> None:
        if not self.chosen:
            self._said("No configuration found", f"Nothing ending in .yaml under {self.configs}.")
            return
        self._said(
            self.chosen, "What this configuration declares. Reading only - nothing is written."
        )
        body = _card(self.body, self.skin)
        for setting in settings_of(self.configs / self.chosen):
            _row(body, self.skin, setting)

    def _chosen_in_tree(self, _event: object) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        path = Path(selected[0])
        self._clear()
        if self.section == "Reviews":
            self._show_review(path)
        elif self.section == "Corpora":
            self._show_corpus(path)
        else:
            self._show_document(path)

    def _show_review(self, path: Path) -> None:
        reviewed = reviewed_from(path)
        if reviewed is None:
            self._said("This file could not be read", "Nothing is shown rather than half of it.")
            return
        self._paint(reviewed)

    def _paint(self, reviewed: Reviewed) -> None:
        counted = {
            verdict: sum(1 for f in reviewed.findings if f.verdict == verdict)
            for verdict in ("contradicted", "nothing", "supported")
        }
        self._said(
            reviewed.draft,
            f"{len(reviewed.findings)} paragraphs against {reviewed.corpus}   ·   "
            f"{counted['supported']} held up, {counted['contradicted']} contradicted, "
            f"{counted['nothing']} not covered\n"
            "Not covered means nothing collected holds it - not that it is wrong.",
        )
        order = {"contradicted": 0, "nothing": 1, "supported": 2}
        for finding in sorted(reviewed.findings, key=lambda f: order.get(f.verdict, 3)):
            _paragraph_card(self.body, self.skin, finding)

    def _show_corpus(self, path: Path) -> None:
        seen = corpus_seen(path)
        self._said(
            path.name,
            f"{seen.quotations} quotations   ·   {seen.with_a_page} with a page   ·   "
            f"from {len(seen.documents)} documents",
        )
        body = _card(self.body, self.skin)
        _text(body, "Where they came from", self.skin.ink, 13, bold=True)
        for name, count in seen.documents:
            _text(body, f"{count:>5}   {name}", self.skin.dim, 11)

    def _show_document(self, path: Path) -> None:
        for seen in documents_in(self.folder):
            if seen.path != path:
                continue
            size = f"{seen.bytes_on_disk / 1024:,.0f} KB"
            tokens = f"{seen.tokens:,} tokens (estimated)" if seen.tokens else "not text"
            self._said(seen.name, f"{size}   ·   {tokens}")
            return


def show(folder: Path, configs: Path, preferences: Preferences, saved: Path) -> None:
    """Open the window and hand control to Tk until it closes."""
    Window(folder, configs, preferences, saved).mainloop()
