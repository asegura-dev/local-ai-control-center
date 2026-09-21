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
from local_ai_control_center.features.commands import Command
from local_ai_control_center.features.overview import (
    DocumentSeen,
    Setting,
    configurations_in,
    corpus_seen,
    documents_in,
    settings_of,
)
from local_ai_control_center.features.prompts import Prompt
from local_ai_control_center.features.reading import (
    Block,
    blocks_in,
    documentation_near,
    opening,
    pages_in,
)
from local_ai_control_center.features.review import (
    Finding,
    Reviewed,
    reviewed_from,
    reviews_in,
)

WIDTH, HEIGHT = 1280, 820
RAIL, SIDE = 214, 330

MARGIN = 96
"""Room a wrapped label leaves for the padding around it.

Wrapping was a fixed number first, so text ran past the edge of a narrow window and stopped
short of a wide one. A reading application that cannot be resized without spoiling what is in
it is not a reading application.
"""

VERDICT_SAID = {
    "contradicted": "your corpus says otherwise",
    "supported": "held up by your corpus",
    "nothing": "not covered - which is not the same as wrong",
}

SECTIONS = (
    "Reviews",
    "Written",
    "Corpora",
    "Documents",
    "Commands",
    "Prompts",
    "Documentation",
    "Configuration",
)


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


def _block(parent: ctk.CTkFrame, skin: Palette, block: Block) -> None:
    """One block of a document, given a font rather than a meaning.

    What each block *is* was decided in `features/reading.py`. This gives it a size and a
    colour, which is the whole of a view's job (ADR-066).
    """
    if block.kind == "rule":
        line = ctk.CTkFrame(parent, fg_color=skin.card, height=1)
        line.pack(fill="x", padx=18, pady=14)
        return
    if block.kind == "heading":
        size = {1: 22, 2: 17, 3: 14}.get(block.level, 13)
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(18 if block.level < 3 else 12, 4))
        _text(holder, block.text, skin.ink, size, bold=True, wrap=760)
        return
    if block.kind == "code":
        body = _card(parent, skin)
        ctk.CTkLabel(
            body,
            text=block.text,
            anchor="w",
            justify="left",
            text_color=skin.dim,
            font=ctk.CTkFont(family="Consolas", size=11),
        ).pack(fill="x")
        return
    holder = ctk.CTkFrame(parent, fg_color="transparent")
    holder.pack(fill="x", padx=18, pady=2)
    if block.kind == "quote":
        _text(holder, f"   │  {block.text}", skin.dim, 12, wrap=740)
    elif block.kind == "item":
        _text(holder, f"   •  {block.text}", skin.ink, 12, wrap=740)
    elif block.kind == "table":
        ctk.CTkLabel(
            holder,
            text=block.text,
            anchor="w",
            justify="left",
            text_color=skin.dim,
            font=ctk.CTkFont(family="Consolas", size=11),
        ).pack(fill="x")
    else:
        _text(holder, block.text, skin.ink, 12, wrap=770)


class Window(ctk.CTk):
    """Sections on the left, a list beside them, and what is selected on the right."""

    def __init__(
        self,
        folder: Path,
        configs: Path,
        preferences: Preferences,
        saved: Path,
        commands: tuple[Command, ...] = (),
        prompts: tuple[Prompt, ...] = (),
    ) -> None:
        super().__init__()
        self._pending: str | None = None
        self._seen: tuple[DocumentSeen, ...] = ()
        self.commands = commands
        self.prompts = prompts
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
        self.right.bind("<Configure>", self._reflow)
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

    def _reflow(self, _event: object = None) -> None:
        """Re-wrap every label to the width the panel actually has.

        Debounced: Tk sends a configure event for every pixel of a drag, and re-wrapping a
        long record on each of them makes the window crawl.
        """
        if self._pending is not None:
            self.after_cancel(self._pending)
        self._pending = self.after(90, self._rewrap)

    def _rewrap(self) -> None:
        """Walk the panel and give every label the width it now has."""
        self._pending = None
        width = max(self.right.winfo_width() - MARGIN, 280)

        def walk(widget: object) -> None:
            for child in getattr(widget, "winfo_children", list)():
                if isinstance(child, ctk.CTkLabel):
                    child.configure(wraplength=width)
                walk(child)

        walk(self.right)

    def _copy(self, words: str) -> None:
        """Put a command on the clipboard. Copying is not running it.

        The honest middle while the window still runs nothing: remembering the flags and
        typing the paths stops being the tedious part (ADR-072).
        """
        self.clipboard_clear()
        self.clipboard_append(words)
        self.summary.configure(text=f"Copied:  {words}")

    def _clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def _said(self, title: str, summary: str) -> None:
        self.title_label.configure(text=title)
        self.summary.configure(text=summary)
        self._reflow()

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
        elif section == "Written":
            self._list_files(
                "written",
                "Written by LACC",
                "Bibliographies and review reports. Choose one to read it.",
            )
        elif section == "Corpora":
            self._list_files("corpus", "Corpora", "Choose one to count what it holds and read it.")
        elif section == "Documents":
            self._list_files("document", "Documents", "Everything else in the workspace.")
        elif section == "Commands":
            self._list_commands()
        elif section == "Prompts":
            self._list_prompts()
        elif section == "Documentation":
            self._list_documentation()
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
        # Read once per listing rather than once per selection: `documents_in` opens every
        # Markdown file to estimate its tokens, and a corpus here is 284 KB.
        self._seen = documents_in(self.folder)
        for seen in self._seen:
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
        elif self.section == "Written":
            self._read_markdown(path, "")
        elif self.section == "Commands":
            self._show_command(selected[0])
        elif self.section == "Prompts":
            self._show_prompt(selected[0])
        elif self.section == "Documentation":
            self._show_page(path)
        else:
            self._show_document(path)

    def _list_commands(self) -> None:
        """Everything the CLI answers to, read from the application that registers it."""
        for command in self.commands:
            self.tree.insert("", "end", iid=f"command:{command.name}", text=f"  {command.name}")
        self._said(
            "Commands",
            f"{len(self.commands)} of them, read from the CLI itself rather than listed here "
            "- a second copy of this list would be a second thing to keep true.\n"
            "The window runs none of them. Type them in a terminal.",
        )

    def _show_command(self, chosen: str) -> None:
        """One command: what to type, what it does, and why it behaves that way."""
        name = chosen.removeprefix("command:")
        for command in self.commands:
            if command.name != name:
                continue
            self._said(f"lacc {command.name}", command.summary)
            body = _card(self.body, self.skin)
            line = ctk.CTkFrame(body, fg_color="transparent")
            line.pack(fill="x")
            ctk.CTkLabel(
                line,
                text=command.usage,
                anchor="w",
                justify="left",
                text_color=self.skin.accent,
                font=ctk.CTkFont(family="Consolas", size=12),
            ).pack(side="left")
            ctk.CTkButton(
                line,
                text="copy",
                width=54,
                height=24,
                corner_radius=6,
                fg_color=self.skin.rail,
                hover_color=self.skin.accent,
                text_color=self.skin.dim,
                font=ctk.CTkFont(size=10),
                command=lambda words=command.usage: self._copy(words),
            ).pack(side="left", padx=10)
            if command.parameters:
                required = [p.shown for p in command.parameters if p.required]
                optional = [p.shown for p in command.parameters if not p.required]
                if required:
                    _text(body, f"required: {', '.join(required)}", self.skin.dim, 11)
                if optional:
                    _text(body, f"optional: {', '.join(optional)}", self.skin.faint, 11)
            for block in blocks_in(command.detail):
                _block(self.body, self.skin, block)
            return

    def _list_prompts(self) -> None:
        """What each skill would ask, planned against one example document."""
        for prompt in self.prompts:
            mark = "  " if prompt.planned else "  ! "
            self.tree.insert("", "end", iid=f"prompt:{prompt.skill}", text=f"{mark}{prompt.skill}")
        self._said(
            "Prompts",
            f"{len(self.prompts)} skills, and exactly what each one asks - planned against an "
            "example document, with no model called and nothing sent.\n"
            "A plan is pure by design, which is why reading one is free.",
        )

    def _show_prompt(self, chosen: str) -> None:
        """One prompt in full, with what it would need and what it checks."""
        name = chosen.removeprefix("prompt:")
        for prompt in self.prompts:
            if prompt.skill != name:
                continue
            self._said(prompt.skill, prompt.summary)
            facts = _card(self.body, self.skin)
            _text(facts, f"needs        {', '.join(prompt.needs) or 'nothing'}", self.skin.dim, 11)
            _text(
                facts,
                f"quotations   {'checked against the source' if prompt.checks_quotes else 'not checked'}",
                self.skin.dim,
                11,
            )
            if prompt.fields:
                _text(facts, f"asks for     {', '.join(prompt.fields)}", self.skin.dim, 11)
            if prompt.temperature is not None:
                _text(facts, f"temperature  {prompt.temperature}", self.skin.dim, 11)
            _text(
                facts,
                f"instruction  {prompt.words} words before your document",
                self.skin.faint,
                11,
            )

            body = _card(self.body, self.skin, stripe=self.skin.accent)
            ctk.CTkLabel(
                body,
                text=prompt.template,
                anchor="w",
                justify="left",
                wraplength=700,
                text_color=self.skin.ink if prompt.planned else self.skin.contradicted,
                font=ctk.CTkFont(family="Consolas", size=11),
            ).pack(fill="x")
            return

    def _list_documentation(self) -> None:
        """Group this project's own records the way the folders group them."""
        folder = documentation_near(Path(__file__).parent)
        if folder is None:
            self._said(
                "No documentation here",
                "The records live in the repository. Installed as a package on its own, "
                "there is nothing local to read - which is said rather than guessed at.",
            )
            return
        pages = pages_in(folder)
        groups: dict[str, str] = {}
        for page in pages:
            where = page.section or "overview"
            if where not in groups:
                groups[where] = self.tree.insert(
                    "", "end", text=f"  {where}", open=where == "overview"
                )
            self.tree.insert(groups[where], "end", iid=str(page.path), text=f"  {page.title}")
        self._said(
            "Documentation",
            f"{len(pages)} documents in {folder}. Decision records, chapters, guides - and "
            "the book, which is in .gitignore and is why nobody has read it.",
        )

    def _show_page(self, path: Path) -> None:
        """Paint one document, block by block."""
        if not path.is_file():
            return
        blocks = blocks_in(path.read_text(encoding="utf-8", errors="replace"))
        first = next((b.text for b in blocks if b.kind == "heading"), path.stem)
        self._said(first, str(path.name))
        for block in blocks:
            if block.kind == "heading" and block.text == first:
                continue
            _block(self.body, self.skin, block)

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
        ctk.CTkButton(
            self.body,
            text="read the file",
            width=130,
            height=28,
            corner_radius=8,
            fg_color=self.skin.card,
            hover_color=self.skin.accent,
            text_color=self.skin.dim,
            font=ctk.CTkFont(size=11),
            command=lambda where=path: self._open_corpus(where),
        ).pack(anchor="w", padx=18, pady=(4, 10))

    def _open_corpus(self, path: Path) -> None:
        """Read a corpus as text, after its counts have been seen."""
        self._clear()
        self._read_markdown(path, "")

    def _show_document(self, path: Path) -> None:
        """A document of the user's own, with its size and then its text."""
        for seen in self._seen:
            if seen.path != path:
                continue
            size = f"{seen.bytes_on_disk / 1024:,.0f} KB"
            tokens = f"{seen.tokens:,} tokens (estimated)" if seen.tokens else "not text"
            self._read_markdown(path, f"{size}   ·   {tokens}")
            return

    def _read_markdown(self, path: Path, said: str) -> None:
        """Read any Markdown in the workspace with the engine the records are read with.

        The same parser, so a corpus, a bibliography and a decision record all look like what
        they are. Long files are cut and say by how much: a widget per block over a corpus of
        284 KB freezes the window drawing what nobody reads to the end (ADR-073).
        """
        if path.suffix != ".md":
            self._said(path.name, said or "Not a text file.")
            return
        blocks = blocks_in(path.read_text(encoding="utf-8", errors="replace"))
        shown, left = opening(blocks)
        first = next((b.text for b in shown if b.kind == "heading"), path.stem)
        note = f"   ·   showing the first {len(shown)} blocks of {len(blocks)}" if left else ""
        self._said(first if first != path.stem else path.name, f"{said}{note}")
        for block in shown:
            if block.kind == "heading" and block.text == first:
                continue
            _block(self.body, self.skin, block)
        if left:
            _text(
                self.body,
                f"   {left} more blocks are in the file and are not drawn here.",
                self.skin.faint,
                11,
            )


def show(
    folder: Path,
    configs: Path,
    preferences: Preferences,
    saved: Path,
    commands: tuple[Command, ...] = (),
    prompts: tuple[Prompt, ...] = (),
) -> None:
    """Open the window and hand control to Tk until it closes.

    The commands are passed in rather than read here, so that a view never imports another
    view and the list has exactly one source: the application the CLI builds (ADR-072).
    """
    Window(folder, configs, preferences, saved, commands, prompts).mainloop()
