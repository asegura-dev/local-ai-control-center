"""A count and the word it counts, agreeing (ADR-120).

The program said *1 sections*, *1 paragraphs*, *1 drafts brought in* and *1 of 6 stages have*.
Each is small, and each is the program saying something a person reads as careless, in the
lines that are meant to be read most carefully - the ones with the numbers in them.
"""

from __future__ import annotations


def counted(number: int, one: str, many: str = "") -> str:
    """`1 section`, `2 sections`, `1,300 quotations`: the number, marked, and its word.

    ``many`` is for the words whose plural is not ``one`` and an `s` - `entry`, `entries`.
    """
    word = one if number == 1 else (many or f"{one}s")
    return f"{number:,} {word}"
