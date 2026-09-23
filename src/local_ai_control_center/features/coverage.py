"""How far the nearest quotation is from each topic you name (ADR-088).

**It tells you what is thin. It never tells you what is missing**, because LACC knows nothing
of your field beyond the documents you brought: a subject absent from both your corpus and
your topics file is invisible here and always will be.

Two instruments were measured and refused before this one. Counting the documents behind a
top-N ranking measures the ranking - it returned eight documents for a topic deliberately
outside the subject. Counting shared words called a topic absent that the corpus speaks to in
other words, which is a false gap reported about somebody's own bibliography. Distance by
meaning put the outside-the-subject control at the floor and ordered the rest the way a person
would, so that is what this uses.

**Nothing here is a verdict.** No threshold, no label, no gap. The topics are ordered by how
close the corpus gets, the control is printed beside them as the floor, and the nearest
quotation is shown so the number can be checked in three seconds rather than believed.
"""

from __future__ import annotations

import math
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.ports.embedder import Embedder
from local_ai_control_center.ports.retriever import Passage

CONTROL_MARK = "!"
"""What marks the topic that is deliberately outside the subject.

Required, and it earns being required. A cosine number means nothing alone - it moves with
the model, the language and the length of what is compared - so a reader without a floor
supplies one, usually the number the corpus would need for everything to be fine.
"""

NEAREST_SHOWN = 240
"""Characters of the closest quotation printed beside a topic's distance."""

REACHES_SUFFIX = ".reaches.json"
"""Where a coverage run leaves its numbers, beside the report it wrote.

The same arrangement `review --into` uses for its findings, for the same reason: the window
paints a measurement without re-running an engine, and it reads **data** rather than parsing
the Markdown back. A reader of a file its own writer generated is how ADR-065 happened.
"""


class Topic(BaseModel):
    """One subject a person wants to know their corpus reaches."""

    model_config = ConfigDict(frozen=True)

    said: str
    control: bool = False
    """True for the topic written to sit outside the subject, which anchors the rest."""


class Reach(BaseModel):
    """How close a corpus gets to one topic, and what got closest."""

    model_config = ConfigDict(frozen=True)

    topic: Topic
    nearest: float = 0.0
    quote: str = ""
    document: str = ""
    page: int | None = None
    within: tuple[tuple[float, int, int], ...] = ()
    """For each level asked about: the level, how many quotations reach it, from how many
    documents. Counts, never a verdict."""


def topics_in(text: str) -> tuple[Topic, ...]:
    """Read a topics file: one subject per line, `!` marking the control.

    Blank lines and lines opening with `#` are skipped, so the file can carry a note about
    what it is for without that note becoming a topic.
    """
    found: list[Topic] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(CONTROL_MARK):
            said = line[len(CONTROL_MARK) :].strip()
            if said:
                found.append(Topic(said=said, control=True))
            continue
        found.append(Topic(said=line))
    return tuple(found)


def missing_control(topics: tuple[Topic, ...]) -> bool:
    """Whether the topics file names nothing to anchor the numbers against."""
    return not any(topic.control for topic in topics)


def _cosine(one: tuple[float, ...], other: tuple[float, ...]) -> float:
    """Similarity of two vectors, or zero if either has no length."""
    dot = sum(a * b for a, b in zip(one, other, strict=False))
    first = math.sqrt(sum(a * a for a in one))
    second = math.sqrt(sum(b * b for b in other))
    return dot / (first * second) if first and second else 0.0


def reach_of(
    topics: tuple[Topic, ...],
    passages: tuple[Passage, ...],
    vectors: tuple[tuple[float, ...], ...],
    embedder: Embedder,
    levels: tuple[float, ...] = (0.55, 0.60, 0.65),
) -> tuple[Reach, ...]:
    """How close the corpus gets to each topic, nearest first.

    ``vectors`` lines up with ``passages`` by position, which is the contract the embedder
    port already enforces by refusing a short or ragged answer: one missing vector would
    mis-attribute every passage after it.

    The topics are embedded here - one small request per topic, and nothing but the topic
    leaves. The passages are not: their vectors were computed when the corpus was last asked
    a question and are handed in.
    """
    if len(vectors) != len(passages):
        raise ValueError(
            f"{len(vectors)} vectors for {len(passages)} passages. Lining them up by "
            "position would mis-attribute every quotation after the first gap."
        )
    if not topics or not passages:
        return ()

    asked = embedder.embed(tuple(topic.said for topic in topics))
    found: list[Reach] = []
    for topic, wanted in zip(topics, asked, strict=True):
        scored = [
            (_cosine(wanted, vector), passage)
            for vector, passage in zip(vectors, passages, strict=True)
        ]
        best, closest = max(scored, key=lambda pair: pair[0])
        within = tuple(
            (
                level,
                sum(1 for score, _ in scored if score >= level),
                len({p.source for score, p in scored if score >= level}),
            )
            for level in levels
        )
        found.append(
            Reach(
                topic=topic,
                nearest=best,
                quote=closest.text[:NEAREST_SHOWN],
                document=closest.source,
                page=closest.page,
                within=within,
            )
        )
    # Nearest first. A person reads from the top, and the top is what is best covered - the
    # bottom is where the work is, which is why the control is printed with them rather than
    # cut off: it is usually there.
    return tuple(sorted(found, key=lambda one: -one.nearest))


class Measured(BaseModel):
    """One coverage run, as data: what was asked, of what, with which model, and when."""

    model_config = ConfigDict(frozen=True)

    corpus: str
    model: str
    taken: str
    reaches: tuple[Reach, ...] = ()

    @property
    def floor(self) -> float:
        """What the control reached, or zero when no control was given.

        Zero is not a floor and is not pretended to be one: a reader with no floor is told
        so rather than shown a number that happens to be small.
        """
        return next((one.nearest for one in self.reaches if one.topic.control), 0.0)


def measurements_in(folder: Path) -> tuple[Path, ...]:
    """Every coverage measurement left in ``folder``, newest first.

    Here rather than in a view, because finding and ordering them is a decision (ADR-066).
    """
    found = sorted(folder.glob(f"*{REACHES_SUFFIX}"), key=lambda p: p.stat().st_mtime)
    return tuple(reversed(found))


def measured_from(path: Path) -> Measured | None:
    """Read one measurement back, or nothing if the file is not one.

    A damaged file is nothing rather than half a measurement: a coverage report missing its
    control would be read as having no floor, which is the one thing it must never claim
    falsely.
    """
    try:
        return Measured.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def report(reaches: tuple[Reach, ...], corpus: str, model: str, taken: str) -> str:
    """The whole file. Orders, counts, shows - and calls nothing a gap."""
    control = next((one for one in reaches if one.topic.control), None)
    lines = [
        "# How far the nearest quotation is",
        "",
        f"{len(reaches)} topics against {corpus}, by meaning, using {model}. Taken {taken}.",
        "",
        "**Nothing here is called a gap.** A similarity is not an interval and has no meaning "
        "on its own: it moves with the model, the language and the length of what is compared. "
        "What this gives you is an ordering, a floor, and the sentence that came closest.",
        "",
    ]
    if control is not None:
        lines += [
            f"**The floor is {control.nearest:.2f}**, reached by *{control.topic.said}* - the "
            "topic written to sit outside this subject. A topic near that number is one your "
            "corpus barely speaks to; how near is your judgement, not this tool's.",
            "",
        ]
    else:
        lines += [
            "**No control topic was given**, so these numbers have no floor. Mark one line of "
            f"your topics file with `{CONTROL_MARK}` - a subject deliberately outside your "
            "field - and take this again.",
            "",
        ]

    lines += ["| nearest | topic | where it came closest |", "|---|---|---|"]
    for one in reaches:
        name = f"**{one.topic.said}** (control)" if one.topic.control else one.topic.said
        where = f"{one.document}, p. {one.page}" if one.page else one.document
        lines.append(f"| {one.nearest:.2f} | {name} | {where} |")
    lines.append("")

    lines += ["## What came closest, topic by topic", ""]
    for one in reaches:
        lines += [f"### {one.topic.said}" + ("  *(control)*" if one.topic.control else ""), ""]
        counted = "   ".join(
            f"{count} quotations from {documents} documents at {level:.2f}"
            for level, count, documents in one.within
        )
        lines += [
            f"Nearest **{one.nearest:.2f}**.   {counted}",
            "",
            f"> {one.quote}",
            "",
            f"*{one.document}" + (f", p. {one.page}*" if one.page else "*"),
            "",
        ]
    lines += [
        "---",
        "",
        "*This says what is thin. It cannot say what is missing: a subject absent from both "
        "your corpus and this file is invisible to it, and naming one would be the model's "
        "memory rather than your sources.*",
        "",
    ]
    return chr(10).join(lines)
