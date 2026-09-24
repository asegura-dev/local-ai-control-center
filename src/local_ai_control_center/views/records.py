"""The section that reads this project's own records (ADR-070).

Seventy-four decision records, the chapters, the guides and the book that sits in
`.gitignore`. The folder is found by walking up from the package, never taken from a setting.
"""

from __future__ import annotations

from pathlib import Path

from local_ai_control_center.features.reading import blocks_in, documentation_near, pages_in
from local_ai_control_center.views import paint
from local_ai_control_center.views.section import Panel, Section, Sidebar, State

HERE = Path(__file__).parent.parent
"""The package, which is what `documentation_near` walks up from."""


def _list_records(side: Sidebar, panel: Panel, state: State) -> None:
    folder = documentation_near(HERE)
    if folder is None:
        panel.said(
            "No documentation here",
            "The records live in the repository. Installed as a package on its own there is "
            "nothing local to read - which is said rather than guessed at.",
        )
        return
    pages = pages_in(folder)
    groups: dict[str, str] = {}
    for page in pages:
        where = page.section or "overview"
        if where not in groups:
            groups[where] = side.group(where, open_now=where == "overview")
        side.row(str(page.path), page.title, under=groups[where])
    panel.said(
        "Documentation",
        f"{len(pages)} documents in {folder}. Decision records, chapters, guides - and the "
        "book, which is in .gitignore and is why nobody has read it.",
    )


def _show_record(key: str, panel: Panel, state: State) -> None:
    path = Path(key)
    if not path.is_file():
        return
    blocks = blocks_in(path.read_text(encoding="utf-8", errors="replace"))
    first = next((b.text for b in blocks if b.kind == "heading"), path.stem)
    panel.said(first, path.name)
    for piece in blocks:
        if piece.kind == "heading" and piece.text == first:
            continue
        paint.block(panel.body, panel.skin, piece)


SECTIONS = (Section("Documentation", _list_records, _show_record, group="THE PROGRAM"),)
