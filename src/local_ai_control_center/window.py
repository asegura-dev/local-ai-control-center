"""The second view: a window that reads, and runs one thing (ADR-069, ADR-075, ADR-085).

**Eight sections read. One asks.** No skill is run from here, no document written, nothing
converted - the single action the window may take is a question against a corpus that is
already there, which is the only thing this program does that leaves the workspace exactly as
it found it. It happens behind a preview, on a worker thread, and the ability to do it is
handed in rather than obtained: `cli.py` passes the two callables, and without them the
section says so and the rest is unaffected (ADR-085).

**And it decides nothing.** Which reviews exist, what a finding means, which files are
corpora, what a configuration declares, which colours a theme has: all answered in
`features/`. `tests/test_layering.py` enforces that, and enforced it before this file existed
(ADR-066).

**This module is the frame, not the contents.** Three columns, a theme, a configuration
picker and routing. The sections live in `views/` and are **declared** rather than wired: the
window iterates over them and knows nothing about any of them. Adding one used to mean editing
four places, and getting three of the four right produced a section that appeared in the menu
and did nothing at all.

**The one thing it writes is its own appearance**, in a file of its own. The configuration is
the user's: choosing one here changes *which* is read, never what is in it.

Tk cannot be exercised headlessly, so nothing here is covered by a test. That is why it is
this thin.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

import customtkinter as ctk

from local_ai_control_center.features.appearance import Palette, Preferences, remember
from local_ai_control_center.features.ask import Asked, Prepared
from local_ai_control_center.features.commands import Command
from local_ai_control_center.features.overview import configurations_in
from local_ai_control_center.features.prompts import Prompt
from local_ai_control_center.features.status import EngineSeen, Status
from local_ai_control_center.views import asking, paint, program, records, work, workspace
from local_ai_control_center.views.section import Section, State, shortened

WIDTH, HEIGHT = 1280, 820
RAIL, SIDE = 214, 330

MARGIN = 96
"""Room a wrapped label leaves for the padding around it, when nothing better is known.

Wrapping was a fixed number first, so text ran past the edge of a narrow window and stopped
short of a wide one. It is now only the fallback: a label inside a card sits behind two more
layers of padding, and a single figure for the whole panel let that text run out of its card
(ADR-084).
"""

INSET = 28
"""Padding between a label and the edge of whatever holds it."""

LINES_PER_NOTCH = 3
"""How far one notch of the wheel scrolls, which is what the rest of the system does."""

SECTIONS: tuple[Section, ...] = (
    *work.SECTIONS,
    *workspace.SECTIONS,
    *asking.SECTIONS,
    *program.SECTIONS,
    *records.SECTIONS,
)
"""Every section, in the order they appear. The frame knows nothing else about them."""


class Window(ctk.CTk):
    """Sections down the left, a list beside them, and what is selected on the right."""

    def __init__(
        self,
        folder: Path,
        configs: Path,
        preferences: Preferences,
        saved: Path,
        commands: tuple[Command, ...] = (),
        prompts: tuple[Prompt, ...] = (),
        status: Status | None = None,
        check_engine: Callable[[], EngineSeen] | None = None,
        prepare_question: Callable[..., Prepared] | None = None,
        send_question: Callable[[Prepared], Asked] | None = None,
        context_file: str = "",
    ) -> None:
        super().__init__()
        self._pending: str | None = None
        self._rows: set[str] = set()
        self.folder = folder
        self.configs = configs
        self.commands = commands
        self.prompts = prompts
        # Not `self.status`: Tk delegates an unknown attribute to its interpreter, which has
        # one by that name, so the assignment went somewhere else and the read failed.
        self.seen = status
        self.check_engine = check_engine
        self.prepare_question = prepare_question
        self.send_question = send_question
        self.context_file = context_file
        self.engine = EngineSeen()
        self.preferences = preferences
        self.saved = saved
        self.skin: Palette = preferences.palette()

        available = [p.name for p in configurations_in(configs)]
        self.chosen = preferences.configuration or (available[0] if available else "")
        self.section = SECTIONS[0]

        self.title("LACC")
        self.geometry(f"{WIDTH}x{HEIGHT}")
        ctk.set_appearance_mode(self.skin.mode)
        self.configure(fg_color=self.skin.surface)

        self._rail(available)
        self._middle()
        self._panel()
        self._bar()
        self.right.bind("<Configure>", self._reflow)
        # Bound on the whole window, not on the panel and its children. Tk delivers the
        # wheel to the widget under the pointer, and a label neither handles it nor passes
        # it on - so binding per widget left gaps, and a panel scrolled only after being
        # clicked. `bind_all` sees it wherever it lands (ADR-084).
        self.bind_all("<MouseWheel>", self._wheel)
        self._go(SECTIONS[0])

    # --- what a section is handed ----------------------------------------------------------

    @property
    def body(self) -> ctk.CTkFrame:
        """The frame a section draws into."""
        return self.panel_body

    def said(self, title: str, summary: str) -> None:
        """Set the heading and the line under it."""
        self.title_label.configure(text=title)
        self.summary.configure(text=summary)
        self._reflow()

    def row(self, key: str, shown: str, under: str = "") -> str:
        """Add a row to the sidebar, optionally under a group."""
        self.tree.insert(under, "end", iid=key, text=f"  {shortened(shown)}")
        self._rows.add(key)
        return key

    def group(self, shown: str, open_now: bool = False) -> str:
        """Add a group that rows sit under."""
        return str(self.tree.insert("", "end", text=f"  {shown}", open=open_now))

    def _state(self) -> State:
        return State(
            workspace=self.folder,
            configs=self.configs,
            chosen_configuration=self.chosen,
            commands=self.commands,
            prompts=self.prompts,
            prepare_question=self.prepare_question,
            send_question=self.send_question,
            context_file=self.context_file,
        )

    # --- the three columns -----------------------------------------------------------------

    def _rail(self, available: list[str]) -> None:
        """What the application is, where it points, and how it looks."""
        skin = self.skin
        rail = ctk.CTkFrame(self, width=RAIL, corner_radius=0, fg_color=skin.rail)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        top = ctk.CTkFrame(rail, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(20, 14))
        paint.text(top, "LACC", skin.ink, 19, bold=True, wrap=180)
        paint.text(top, "reads what you wrote", skin.faint, 11, wrap=180)

        self.buttons: dict[str, ctk.CTkButton] = {}
        for section in SECTIONS:
            button = ctk.CTkButton(
                rail,
                text=section.name,
                anchor="w",
                height=32,
                corner_radius=8,
                fg_color="transparent",
                hover_color=skin.card,
                text_color=skin.dim,
                font=ctk.CTkFont(size=13),
                command=lambda picked=section: self._go(picked),
            )
            button.pack(fill="x", padx=12, pady=1)
            self.buttons[section.name] = button

        under = ctk.CTkFrame(rail, fg_color="transparent")
        under.pack(fill="x", side="bottom", pady=(0, 16))
        paint.text(under, "  THEME", skin.faint, 10, bold=True, wrap=180)
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

        paint.text(under, "  CONFIGURATION", skin.faint, 10, bold=True, wrap=180)
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
        paint.text(
            under, "  changes which is read,\n  never what is in it", skin.faint, 10, wrap=185
        )
        paint.text(under, f"\n  WORKSPACE\n  {self.folder}", skin.faint, 10, wrap=185)

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
        self.tree.bind("<<TreeviewSelect>>", self._chosen)

    def _panel(self) -> None:
        """A heading, a summary, and whatever the selection calls for."""
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
        self.panel_body = ctk.CTkFrame(self.right, fg_color="transparent")
        self.panel_body.pack(fill="both", expand=True)

    # --- behaviour -------------------------------------------------------------------------

    def _bar(self) -> None:
        """The line along the bottom: what there is, and what may be reached.

        Packed before the columns claim the rest of the window, which is what `side="bottom"`
        on a sibling that comes later would not do.
        """
        skin = self.skin
        bar = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=skin.rail)
        bar.pack(side="bottom", fill="x")
        bar.pack_propagate(False)

        shown = self.seen
        left = shown.material if shown else "no workspace read"
        # The right half is packed first and the left is given what is over. Packed the
        # other way round, a long left half pushed the right one off and the two overlapped
        # into `881 quotationsked` (ADR-084).
        self.engine_said = ctk.CTkLabel(
            bar, text="", anchor="e", text_color=skin.dim, font=ctk.CTkFont(size=11)
        )
        self.engine_said.pack(side="right", padx=(0, 10))
        ctk.CTkLabel(
            bar,
            text=f"  {left}",
            anchor="w",
            text_color=skin.dim,
            font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=(8, 0), fill="x", expand=True)
        if self.check_engine is not None:
            ctk.CTkButton(
                bar,
                text="check",
                width=52,
                height=20,
                corner_radius=5,
                fg_color=skin.card,
                hover_color=skin.accent,
                text_color=skin.dim,
                font=ctk.CTkFont(size=10),
                command=self._ask_the_engine,
            ).pack(side="right", padx=8)
        self._say_the_engine()

    def _say_the_engine(self) -> None:
        """What the bar says on the right: what is allowed, then what was found."""
        shown = self.seen
        allowed = shown.reach if shown else ""
        model = f"{shown.model}   " if shown and shown.model else ""
        self.engine_said.configure(text=f"{model}{allowed}   ·   {self.engine.said}  ")

    def _ask_the_engine(self) -> None:
        """Ask the engine whether it answers. **Only from here**, never on opening."""
        if self.check_engine is None:
            return
        self.engine_said.configure(text="asking the engine...  ")
        self.update_idletasks()
        self.engine = self.check_engine()
        self._say_the_engine()

    def _reflow(self, _event: object = None) -> None:
        """Re-wrap to the width the panel has, debounced against a drag."""
        if self._pending is not None:
            self.after_cancel(self._pending)
        self._pending = self.after(90, self._rewrap)

    def _rewrap(self) -> None:
        """Give every label the current width, and let the wheel work anywhere on it.

        The wheel is bound on every child because Tk delivers it to the widget under the
        pointer and a label does not pass it on - without this a panel scrolled only while
        the pointer was over the gaps between its cards.
        """
        self._pending = None
        # The **viewport**, not the panel frame and not the holder. Inside a scrollable
        # frame a child can be wider than what is on screen, so both of those measure
        # something the reader cannot see - which is why the text still ran off the right
        # edge after being wrapped to its card (ADR-084).
        canvas = getattr(self.right, "_parent_canvas", None)
        seen = getattr(canvas, "winfo_width", lambda: 0)() or self.right.winfo_width()
        room = max(seen - MARGIN, 260)

        def walk(widget: object, inset: int) -> None:
            for child in getattr(widget, "winfo_children", list)():
                if isinstance(child, ctk.CTkLabel):
                    child.configure(wraplength=max(room - inset, 200))
                # Each frame between the viewport and the text costs its own padding.
                walk(child, inset + (INSET if isinstance(child, ctk.CTkFrame) else 0))

        walk(self.right, 0)

    def _wheel(self, event: object) -> str:
        """Scroll from anywhere in the window, and stop the event travelling further.

        Windows sends 120 per notch, and a notch is three lines everywhere else on the
        system. Moving one unit per notch made a long record feel stuck (ADR-084).
        """
        turned = getattr(event, "delta", 0)
        canvas = getattr(self.right, "_parent_canvas", None)
        if canvas is not None and turned:
            canvas.yview_scroll(-int(turned / 120) * LINES_PER_NOTCH, "units")
        return "break"

    def _clear(self) -> None:
        for child in self.panel_body.winfo_children():
            child.destroy()

    def _theme(self, name: str) -> None:
        """Remember the theme. It applies when the window is opened again."""
        self.preferences = self.preferences.model_copy(update={"theme": name})
        remember(self.saved, self.preferences)
        self._clear()
        self.said(
            f"Theme set to {name}",
            "Saved. Colours apply the next time you open the window - Tk builds its widgets "
            "once, and rebuilding them live leaves half a window in the old palette.",
        )

    def _switch(self, name: str) -> None:
        """Read a different configuration. Nothing of yours is written."""
        self.chosen = name
        self.preferences = self.preferences.model_copy(update={"configuration": name})
        remember(self.saved, self.preferences)
        self._go(next(s for s in SECTIONS if s.name == "Configuration"))

    def _go(self, section: Section) -> None:
        """Show one section. The frame does not know what any of them do."""
        self.section = section
        for name, button in self.buttons.items():
            button.configure(
                text_color=self.skin.ink if name == section.name else self.skin.dim,
                fg_color=self.skin.card if name == section.name else "transparent",
            )
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        self._clear()
        section.listing(self, self, self._state())

    def _chosen(self, _event: object) -> None:
        """Hand the selection to the section that made it."""
        selected = self.tree.selection()
        if not selected or selected[0] not in self._rows:
            return
        self._clear()
        self.section.open(selected[0], self, self._state())


def show(
    folder: Path,
    configs: Path,
    preferences: Preferences,
    saved: Path,
    commands: tuple[Command, ...] = (),
    prompts: tuple[Prompt, ...] = (),
    status: Status | None = None,
    check_engine: Callable[[], EngineSeen] | None = None,
    prepare_question: Callable[..., Prepared] | None = None,
    send_question: Callable[[Prepared], Asked] | None = None,
    context_file: str = "",
) -> None:
    """Open the window and hand control to Tk until it closes.

    The engine check is passed in rather than performed here: reaching another machine is an
    adapter's job, and a view that did it would be a view reaching past `features/`
    (ADR-066). It is also never called until somebody presses the button (ADR-077).
    """
    Window(
        folder,
        configs,
        preferences,
        saved,
        commands,
        prompts,
        status,
        check_engine,
        prepare_question,
        send_question,
        context_file,
    ).mainloop()
