"""The few shapes every section is drawn out of (ADR-075).

Text, a card, a labelled row, a block of a document, a paragraph with its verdict. Nothing
here decides anything: each takes what to draw and the colours to draw it in.

Kept in one module because a motif repeated in eight places is a motif that will stop being
repeated in one of them.
"""

from __future__ import annotations

import customtkinter as ctk

from local_ai_control_center.features.appearance import Palette
from local_ai_control_center.features.reading import Block
from local_ai_control_center.features.review import Finding

VERDICT_SAID = {
    "contradicted": "your corpus says otherwise",
    "supported": "held up by your corpus",
    "nothing": "not covered - which is not the same as wrong",
}


def text(
    parent: ctk.CTkFrame,
    words: str,
    colour: str,
    size: int = 11,
    bold: bool = False,
    wrap: int = 780,
) -> ctk.CTkLabel:
    """One line or paragraph, left aligned like everything else here."""
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


def fixed(
    parent: ctk.CTkFrame, words: str, colour: str, size: int = 11, wrap: int = 720
) -> ctk.CTkLabel:
    """Monospaced text: code, a command, a table row - anything whose columns matter.

    Wrapped like everything else, and re-wrapped with everything else. It was the one
    painter with no `wraplength`, so a wide table or a long line of code ran off the right
    edge with nothing to scroll sideways with (ADR-084).
    """
    label = ctk.CTkLabel(
        parent,
        text=words,
        anchor="w",
        justify="left",
        wraplength=wrap,
        text_color=colour,
        font=ctk.CTkFont(family="Consolas", size=size),
    )
    label.pack(fill="x")
    return label


def card(parent: ctk.CTkFrame, skin: Palette, stripe: str = "") -> ctk.CTkFrame:
    """A panel with an optional coloured edge, which is this window's only real motif."""
    shell = ctk.CTkFrame(parent, fg_color=skin.card, corner_radius=10)
    shell.pack(fill="x", padx=18, pady=7)
    if stripe:
        edge = ctk.CTkFrame(shell, fg_color=stripe, corner_radius=10, width=4)
        edge.pack(side="left", fill="y", padx=(0, 12), pady=2)
    body = ctk.CTkFrame(shell, fg_color="transparent")
    body.pack(side="left", fill="both", expand=True, padx=(0 if stripe else 14, 14), pady=13)
    return body


def block(parent: ctk.CTkFrame, skin: Palette, piece: Block) -> None:
    """One block of a document, given a font rather than a meaning.

    What each block *is* was decided in `features/reading.py`. This gives it a size and a
    colour, which is the whole of a view's job (ADR-066).
    """
    if piece.kind == "rule":
        line = ctk.CTkFrame(parent, fg_color=skin.card, height=1)
        line.pack(fill="x", padx=18, pady=14)
        return
    if piece.kind == "heading":
        size = {1: 22, 2: 17, 3: 14}.get(piece.level, 13)
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(18 if piece.level < 3 else 12, 4))
        text(holder, piece.text, skin.ink, size, bold=True, wrap=760)
        return
    if piece.kind == "code":
        fixed(card(parent, skin), piece.text, skin.dim)
        return
    holder = ctk.CTkFrame(parent, fg_color="transparent")
    holder.pack(fill="x", padx=18, pady=2)
    if piece.kind == "quote":
        text(holder, f"   │  {piece.text}", skin.dim, 12, wrap=740)
    elif piece.kind == "item":
        text(holder, f"   •  {piece.text}", skin.ink, 12, wrap=740)
    elif piece.kind == "table":
        fixed(holder, piece.text, skin.dim)
    else:
        text(holder, piece.text, skin.ink, 12, wrap=770)


def paragraph(parent: ctk.CTkFrame, skin: Palette, finding: Finding) -> None:
    """One paragraph of a draft, with its verdict painted down the edge."""
    colour = skin.for_verdict(finding.verdict)
    body = card(parent, skin, stripe=colour)
    text(
        body,
        f"Line {finding.paragraph.line}   {VERDICT_SAID.get(finding.verdict, '')}",
        colour,
        11,
        bold=True,
    )
    text(body, finding.paragraph.text, skin.ink, 13, wrap=720)
    if finding.quote:
        text(body, f"“{finding.quote}”\n{finding.document}", skin.dim, 11, wrap=700)
    elif finding.considered:
        text(body, "Closest in your corpus, and judged not to hold it:", skin.faint, 10)
        for document, quote in finding.considered:
            text(body, f"• {quote}\n   {document}", skin.faint, 10, wrap=690)
