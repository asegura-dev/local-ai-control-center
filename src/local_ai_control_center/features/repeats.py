"""A report of what a text says twice, for the writer to edit from (ADR-125).

Pure: the groups come in, Markdown goes out. LACC's own words are English, as all of them are;
the writer's sentences are quoted as written, citation marks and all. **Nothing in it calls a
repetition a fault**: a table that repeats its prose may be what the text needs, and the
report says where the same fact is so the writer can decide.
"""

from __future__ import annotations

from local_ai_control_center.core.repetition import Repetition
from local_ai_control_center.core.wording import counted

RULE = (
    "Found without a model: two sentences in different paragraphs or rows that share two "
    "specific figures, one figure and a fifth of their words, or half their words. A group is "
    "a place to look, not a fault - a table may repeat its prose on purpose."
)
"""The rule, said wherever its groups are shown, so a reader knows what they are (ADR-125)."""


def opening(text: str, longest: int = 150) -> str:
    """The start of a sentence, for a line that has to stay readable."""
    return text if len(text) <= longest else text[: longest - 1].rstrip() + "…"


def shared_label(group: Repetition) -> str:
    """What a group's sentences share, in a few words."""
    if group.figures:
        return f"figures {', '.join(group.figures)}"
    return "most of their words"


def report_text(groups: tuple[Repetition, ...], read: tuple[str, ...], sentences: int) -> str:
    """The report, whole: the rule, the counts, then each group with its sentences."""
    within = sum(len(group.sentences) for group in groups)
    lines = ["# What these files say twice", "", f"*{RULE}*", ""]
    lines += [
        f"{counted(len(groups), 'group')}, holding {counted(within, 'sentence')} of "
        f"{sentences:,} read in {counted(len(read), 'file')}:",
        "",
    ]
    lines += [f"- {name}" for name in read] + [""]
    if not groups:
        lines += ["Nothing in them is said twice, by this rule.", ""]
    for number, group in enumerate(groups, start=1):
        lines += [
            f"## {number} · {counted(len(group.sentences), 'sentence')} · {shared_label(group)}",
            "",
        ]
        for stated in group.sentences:
            lines += [f"> **{stated.place}**", ">"]
            lines += [f"> {line}" for line in stated.text.splitlines()]
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
