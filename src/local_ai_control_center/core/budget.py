"""How much of a context window a prompt may use, and how much is held back.

Pure arithmetic over text sizes. It lives in the core because it is a rule rather than a
service: nothing here reads a file, calls an engine or knows what a prompt is for. The
cycle uses it to decide whether to refuse a prompt, and `passes` uses it to decide how much
of a document fits in one reading.
"""

from __future__ import annotations

CHARS_PER_TOKEN = 3
"""How many characters LACC assumes one token holds, when estimating a prompt's size.

Deliberately low. Four is the usual rule of thumb for English prose, and text with
accents, code or unusual words tokenizes worse; assuming three estimates more tokens than
there probably are, so LACC refuses slightly early. The two errors are not symmetric: a
prompt refused that would have fitted is visible and costs one line of configuration,
while a prompt truncated that should have been refused produces a plausible wrong answer
nobody has reason to check (ADR-019).
"""

_MINIMUM_ANSWER_RESERVE = 512
"""Fewest tokens held back for the completion, whatever the window."""


def estimate_tokens(text: str) -> int:
    """Estimate how many tokens ``text`` occupies, erring high.

    An estimate, and called one everywhere it appears: LACC has no tokenizer and will not
    carry one per model family for a number that only decides whether to refuse.
    """
    return -(-len(text) // CHARS_PER_TOKEN)


def answer_reserve(window: int) -> int:
    """Tokens held back from ``window`` so the model has room to answer."""
    return max(window // 4, _MINIMUM_ANSWER_RESERVE)
