"""The sections that read the workspace: reviews, what LACC wrote, corpora, documents.

All four answer questions about the material rather than about the program, and all four read
files that are already on disk. Nothing here runs a skill or calls a model (ADR-069).
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from local_ai_control_center.features.overview import corpus_seen, documents_in
from local_ai_control_center.features.reading import blocks_in, opening
from local_ai_control_center.features.review import reviewed_from, reviews_in
from local_ai_control_center.views import paint
from local_ai_control_center.views.section import Listing, Panel, Section, Sidebar, State

ORDER = {"contradicted": 0, "nothing": 1, "supported": 2}
"""Worst first. A person reads from the top, so what can put a false claim in a thesis
goes there (ADR-068)."""


def read_markdown(path: Path, said: str, panel: Panel) -> None:
    """Read any Markdown with the engine the records are read with.

    Long files are cut and say by how much: a widget per block over a corpus of 284 KB
    freezes the window drawing what nobody reads to the end (ADR-073).
    """
    if path.suffix != ".md":
        panel.said(path.name, said or "Not a text file.")
        return
    blocks = blocks_in(path.read_text(encoding="utf-8", errors="replace"))
    shown, left = opening(blocks)
    first = next((b.text for b in shown if b.kind == "heading"), path.stem)
    note = f"   ·   showing the first {len(shown)} blocks of {len(blocks)}" if left else ""
    panel.said(first if first != path.stem else path.name, f"{said}{note}")
    for piece in shown:
        if piece.kind == "heading" and piece.text == first:
            continue
        paint.block(panel.body, panel.skin, piece)
    if left:
        paint.text(
            panel.body,
            f"   {left} more blocks are in the file and are not drawn here.",
            panel.skin.faint,
            11,
        )


# --- reviews --------------------------------------------------------------------------------


def _list_reviews(side: Sidebar, panel: Panel, state: State) -> None:
    found = reviews_in(state.workspace)
    for path in found:
        side.row(str(path), path.name)
    if found:
        panel.said("Reviews", "Choose one to see your draft with its verdicts.")
    else:
        panel.said(
            "No reviews yet",
            "Run  lacc review <draft> --against <corpus> --into report.md  and the findings "
            "appear beside the report. This window reads them; it does not run anything.",
        )


def _show_review(key: str, panel: Panel, state: State) -> None:
    reviewed = reviewed_from(Path(key))
    if reviewed is None:
        panel.said("This file could not be read", "Nothing is shown rather than half of it.")
        return
    counted = {
        verdict: sum(1 for f in reviewed.findings if f.verdict == verdict) for verdict in ORDER
    }
    panel.said(
        reviewed.draft,
        f"{len(reviewed.findings)} paragraphs against {reviewed.corpus}   ·   "
        f"{counted['supported']} held up, {counted['contradicted']} contradicted, "
        f"{counted['nothing']} not covered\n"
        "Not covered means nothing collected holds it - not that it is wrong.",
    )
    for finding in sorted(reviewed.findings, key=lambda f: ORDER.get(f.verdict, 3)):
        paint.paragraph(panel.body, panel.skin, finding)


# --- files of a kind ------------------------------------------------------------------------


def _files_of(kind: str, title: str, said: str) -> Listing:
    """A listing for one kind of file. Three sections differ only by these words."""

    def listing(side: Sidebar, panel: Panel, state: State) -> None:
        for seen in documents_in(state.workspace):
            if seen.kind == kind:
                side.row(str(seen.path), seen.name)
        panel.said(title, said)

    return listing


def _show_written(key: str, panel: Panel, state: State) -> None:
    read_markdown(Path(key), "", panel)


def _show_document(key: str, panel: Panel, state: State) -> None:
    path = Path(key)
    for seen in documents_in(state.workspace):
        if seen.path != path:
            continue
        size = f"{seen.bytes_on_disk / 1024:,.0f} KB"
        tokens = f"{seen.tokens:,} tokens (estimated)" if seen.tokens else "not text"
        read_markdown(path, f"{size}   ·   {tokens}", panel)
        return


def _show_corpus(key: str, panel: Panel, state: State) -> None:
    path = Path(key)
    seen = corpus_seen(path)
    panel.said(
        path.name,
        f"{seen.quotations} quotations   ·   {seen.with_a_page} with a page   ·   "
        f"from {len(seen.documents)} documents",
    )
    body = paint.card(panel.body, panel.skin)
    paint.text(body, "Where they came from", panel.skin.ink, 13, bold=True)
    for name, count in seen.documents:
        paint.text(body, f"{count:>5}   {name}", panel.skin.dim, 11)
    ctk.CTkButton(
        panel.body,
        text="read the file",
        width=130,
        height=28,
        corner_radius=8,
        fg_color=panel.skin.card,
        hover_color=panel.skin.accent,
        text_color=panel.skin.dim,
        font=ctk.CTkFont(size=11),
        command=lambda: read_markdown(path, "", panel),
    ).pack(anchor="w", padx=18, pady=(4, 10))


SECTIONS = (
    Section("Reviews", _list_reviews, _show_review),
    Section(
        "Written",
        _files_of("written", "Written by LACC", "Bibliographies and review reports."),
        _show_written,
    ),
    Section(
        "Corpora",
        _files_of("corpus", "Corpora", "Choose one to count what it holds and read it."),
        _show_corpus,
    ),
    Section(
        "Documents",
        _files_of("document", "Documents", "Everything else in the workspace."),
        _show_document,
    ),
)
