"""The fence around a document in a prompt, and what it can and cannot do.

A document is put between markers and the model is told that what sits inside them is
material to work on rather than a request to obey. That instruction is a request, and a
model may ignore it - which was tested rather than assumed, and it did (ADR-038).

What this module provides is the one thing here that is a control rather than a request:
the markers are removed from document content, so a document cannot end its own fence.
Everything else is detection, reported to the person and never acted on alone.

Pure functions over text. Both `skill` and `cycle` use them, so there is one definition of
what a fence is and one place that defends it.
"""

from __future__ import annotations

import re

DOCUMENT_OPEN = "<<<BEGIN DOCUMENT>>>"
"""Marker that opens the fenced document inside a prompt (ADR-015)."""

DOCUMENT_CLOSE = "<<<END DOCUMENT>>>"
"""Marker that closes it.

The markers themselves hold no user-supplied text. That is not the same as a fence being
unforgeable, which is what this docstring claimed until v0.32.0: the *content* between them
is user-supplied, and a document carrying the closing marker ended its own fence, after
which the rest of it read to the model as LACC's instructions. Tested against a real model,
which obeyed. `without_markers` is what actually prevents it (ADR-038).
"""

MARKER_REMOVED = "[marker removed]"
"""What replaces a fence marker found in a document, visibly rather than silently."""

_INSTRUCTION_SHAPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ignores earlier instructions", re.compile(r"ignore\s+(all\s+)?(previous|prior|above)", re.I)),
    (
        "disregards what came before",
        re.compile(r"disregard\s+(the\s+)?(above|previous|prior)", re.I),
    ),
    ("addresses the model directly", re.compile(r"^\s*(system|assistant|user)\s*:", re.I | re.M)),
    ("issues new instructions", re.compile(r"(new|updated)\s+instructions?\s*[:.]", re.I)),
    (
        "claims to speak for the operator",
        re.compile(r"(instruction|message)\s+from\s+the\s+operator", re.I),
    ),
    ("tells the model what it must now do", re.compile(r"you\s+(must|should|will)\s+now\b", re.I)),
)
"""Shapes that a document has no ordinary reason to contain.

Deliberately short. A longer list catches more phrasings and none of the ones nobody
thought of, and every entry costs a false positive on a paper that discusses the subject.
"""


def without_markers(content: str) -> tuple[str, int]:
    """Remove fence markers from ``content``, and report how many were there.

    The control this module exists for. After it, a document cannot close its own fence,
    because the string that would do it is gone - which is true regardless of what any
    model decides to pay attention to (ADR-038).

    The count is returned rather than swallowed: a document carrying a fence marker is
    worth telling someone about, even though it is not worth refusing over.
    """
    found = content.count(DOCUMENT_OPEN) + content.count(DOCUMENT_CLOSE)
    if not found:
        return content, 0
    cleaned = content.replace(DOCUMENT_OPEN, MARKER_REMOVED).replace(DOCUMENT_CLOSE, MARKER_REMOVED)
    return cleaned, found


def instruction_shapes_in(content: str) -> tuple[str, ...]:
    """Name the ways ``content`` reads like an instruction rather than like a document.

    **Detection, not prevention.** A model can obey something no pattern here catches, and
    saying otherwise would repeat the claim ADR-038 exists to correct. What this buys is
    that a person reading an answer knows the document was trying something, at the moment
    they are deciding whether to trust it.

    Returns descriptions rather than the matched text, so that reporting a finding never
    reprints the instruction where someone might read it as one.
    """
    return tuple(
        description for description, pattern in _INSTRUCTION_SHAPES if pattern.search(content)
    )


def content_slot(index: int) -> str:
    """The marker a skill leaves for the document at ``index``.

    One per document, so several can be fenced separately and the model can tell them
    apart. The plan holds the holes; the cycle fills them with what it read.
    """
    return f"<<file_content:{index}>>"


CONTENT_PLACEHOLDER = content_slot(0)
"""Marker a prompt template leaves for the cycle to replace with file contents.

A skill's plan is pure, so it can only leave the hole; filling it is a side
effect's product and belongs to the cycle (ADR-014). A literal marker is replaced,
not formatted, so braces in a path or a file never break the substitution.
"""
