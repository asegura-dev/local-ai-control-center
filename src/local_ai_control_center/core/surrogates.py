"""Characters a conversion delivered in halves, made writable and counted (ADR-122).

A character beyond the first 65,536 - the mathematical letters from U+1D400 on, which papers
use for their symbols - can reach an extractor as two halves, and sometimes as one. A Python
string holds a half; UTF-8 cannot encode it. `lckd.pdf` carried ten lone halves, and its
conversion ended a batch of 65 documents in a traceback and left an empty file behind.

**Joined where they can be, replaced where they cannot, and always counted.** Converted text
is what every quotation is checked against, so nothing about it changes without a number that
says so. A lone half becomes U+FFFD rather than nothing, so the place where something was lost
can be found by searching for it.
"""

from __future__ import annotations

import re

REPLACEMENT = "�"
"""What a half with no partner is written as: the character that means one was lost."""

_HALF = re.compile("[\ud800-\udfff]")
_HIGH_FIRST, _HIGH_LAST = 0xD800, 0xDBFF
_LOW_FIRST, _LOW_LAST = 0xDC00, 0xDFFF


def whole_characters(text: str) -> tuple[str, int]:
    """``text`` with each pair of halves joined and each lone half replaced, and the count.

    Returns the text and how many halves were replaced. A pair is not counted: joined, it is
    the character the document meant. Text with no halves comes back as it was, untouched,
    which is every document of the thesis's 65 but one.
    """
    if _HALF.search(text) is None:
        return text, 0
    pieces: list[str] = []
    replaced = 0
    position = 0
    while position < len(text):
        code = ord(text[position])
        following = ord(text[position + 1]) if position + 1 < len(text) else 0
        if _HIGH_FIRST <= code <= _HIGH_LAST and _LOW_FIRST <= following <= _LOW_LAST:
            pieces.append(chr(0x10000 + ((code - _HIGH_FIRST) << 10) + (following - _LOW_FIRST)))
            position += 2
            continue
        if _HIGH_FIRST <= code <= _LOW_LAST:
            pieces.append(REPLACEMENT)
            replaced += 1
        else:
            pieces.append(text[position])
        position += 1
    return "".join(pieces), replaced
