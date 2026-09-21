"""Describing repeated measurements of the same thing (ADR-066).

One function, and its whole content is a refusal. `lacc measure` exists because a model
comparison written in this project's own documentation turned out to be sampling noise, so
the one thing this must not do is answer with a single number.
"""

from __future__ import annotations


def spread(values: list[int]) -> str:
    """Describe a set of measurements by its range and middle, never by its average.

    A mean would reproduce the error this command exists to correct: it reports a single
    number for something whose whole finding is that a single number misleads (ADR-032).
    """
    if not values:
        return "-"
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    if ordered[0] == ordered[-1]:
        return f"{ordered[0]}"
    return f"{ordered[0]} - {ordered[-1]}  (median {median})"
