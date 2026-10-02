"""What a text says twice, found without a model (ADR-125).

Two sentences state the same fact when they share the figures that make it that fact - a Dice
of 0.517, 549 patients, 28% fewer - or most of their words. Finding that is arithmetic, and it
is done here: nothing is asked of anyone, and **nothing is called a defect**. A table that
repeats the prose it summarises may be what a document needs; this says where the same fact
is, and the writer decides.

Measured on the thesis's protocol against a reading of every pair (2 October). A first rule
took any two shared numbers for a shared fact, and 39 of its 64 pairs were not one: 33 shared
only the numbers in a tracer's name, `[68Ga]PSMA-11`. This rule finds 29 pairs, 21 the same
fact and 8 arguable, and none that is not. It was shaped on that one text.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from .protocol import CITATION, sentences_in, units

SHORTEST = 25
"""Characters a sentence needs to be compared: a heading's leftovers state no fact."""

FEWEST_WORDS = 8
"""Content words each sentence needs before sharing half of them counts: two short sentences
share half their words by accident."""

_NUMBER = re.compile(r"(?<![\w\-\[/.,])\d+(?:[.,]\d+)*(?![\w\-\]/])")
"""A number standing alone - not inside `PSMA-11`, `[18F]`, `T1` or `10-20`."""

_YEAR = re.compile(r"(?:19|20)\d\d")

_POINTERS = frozenset(
    {
        "sección",
        "secciones",
        "section",
        "sections",
        "tabla",
        "table",
        "figura",
        "figure",
        "fase",
        "phase",
        "capítulo",
        "chapter",
        "ecuación",
        "equation",
        "anexo",
        "apartado",
    }
)
"""Words whose number points somewhere rather than measuring anything: `sección 3.4`."""

_WORD = re.compile(r"[^\W_]+(?:[.,][^\W_]+)*")

_FUNCTION_WORDS = frozenset(
    [
        "para",
        "como",
        "con",
        "sin",
        "por",
        "sobre",
        "entre",
        "desde",
        "hasta",
        "este",
        "esta",
        "estos",
        "estas",
        "ese",
        "esa",
        "esos",
        "esas",
        "que",
        "del",
        "las",
        "los",
        "una",
        "uno",
        "unos",
        "unas",
        "más",
        "menos",
        "pero",
        "cada",
        "todo",
        "toda",
        "todos",
        "todas",
        "también",
        "solo",
        "sólo",
        "donde",
        "cuando",
        "según",
        "hacia",
        "ante",
        "tras",
        "mismo",
        "misma",
        "ella",
        "ellos",
        "ellas",
        "sus",
        "nos",
        "les",
        "porque",
        "aunque",
        "mientras",
        "durante",
        "cual",
        "cuales",
        "cuyo",
        "cuya",
        "puede",
        "pueden",
        "será",
        "serán",
        "está",
        "están",
        "fue",
        "fueron",
        "son",
        "ser",
        "hay",
        "había",
        "tiene",
        "tienen",
        "otro",
        "otra",
        "otros",
        "otras",
        "that",
        "this",
        "these",
        "those",
        "with",
        "from",
        "have",
        "were",
        "been",
        "their",
        "there",
        "which",
        "into",
        "than",
        "then",
        "also",
        "such",
        "only",
        "more",
        "most",
        "other",
        "some",
        "what",
        "when",
        "where",
        "while",
        "about",
        "after",
        "before",
        "between",
        "both",
        "each",
        "over",
        "under",
        "very",
        "will",
        "would",
        "could",
        "should",
        "might",
        "must",
    ]
)
"""Spanish and English words that carry no fact. Short words never count anyway."""


def specific_figures(text: str) -> frozenset[str]:
    """The numbers in ``text`` that could identify a fact.

    A decimal, a percentage, or a whole number of two or more digits not ending in zero:
    `0.517`, `28%`, `549`, `2,616`. Not a year, not the number of a section, table, figure or
    phase, and not a whole number after a name in capitals, such as `RTX 5080`. Round numbers
    are left out because they are more often settings than findings - 1000 epochs, 10 mm -
    and the measurement found them pairing sentences that state different things.
    """
    found: set[str] = set()
    for match in _NUMBER.finditer(text):
        number = match.group()
        digits = re.sub(r"\D", "", number)
        whole = "." not in number and "," not in number
        if _YEAR.fullmatch(number) or (whole and len(digits) < 2):
            continue
        before = text[: match.start()].split()
        previous = before[-1] if before else ""
        if previous.lower().strip("(") in _POINTERS:
            continue
        if whole and len(previous) >= 2 and previous.isalpha() and previous.isupper():
            continue
        percentage = text[match.end() : match.end() + 1] == "%"
        if not whole or percentage or not digits.endswith("0"):
            found.add(number)
    return frozenset(found)


def numbers(text: str) -> frozenset[str]:
    """Every number standing alone in ``text``, round ones and years included.

    What a rewritten sentence is checked against: a proposal may not bring in a number its
    original lacked, and a round one is as much an addition as any other (ADR-125). A number
    inside a name, `PSMA-11`, or a citation mark, `[12]`, is not one.
    """
    return frozenset(_NUMBER.findall(text))


def content_words(text: str) -> frozenset[str]:
    """The words of ``text`` that can carry a fact: four letters or more, or holding a digit."""
    return frozenset(
        word
        for word in _WORD.findall(text.lower())
        if word not in _FUNCTION_WORDS and (len(word) >= 4 or any(c.isdigit() for c in word))
    )


class Stated(BaseModel):
    """One sentence of a text, with where it is and what it could share."""

    model_config = ConfigDict(frozen=True)

    source: str
    line: int
    """Where its paragraph, list item or table row starts."""

    text: str
    """As written, citation marks and all."""

    figures: frozenset[str] = frozenset()
    words: frozenset[str] = frozenset()

    @property
    def place(self) -> str:
        """`file:line`, how a reader finds it."""
        return f"{self.source}:{self.line}"


def stated_in(text: str, source: str) -> tuple[Stated, ...]:
    """Every sentence of ``text`` long enough to state a fact, with its figures and words.

    Display formulas are left out: two formulas share symbols, not facts.
    """
    found: list[Stated] = []
    for line, unit in units(text):
        if unit.lstrip().startswith("$$"):
            continue
        for sentence in sentences_in(unit):
            plain = CITATION.sub("", sentence).replace("**", "").replace("*", "").strip()
            if len(plain) < SHORTEST:
                continue
            found.append(
                Stated(
                    source=source,
                    line=line,
                    text=sentence.strip(),
                    figures=specific_figures(plain),
                    words=content_words(plain),
                )
            )
    return tuple(found)


def same_fact(first: Stated, second: Stated) -> bool:
    """Whether two sentences in different units state the same fact.

    Two shared figures; or one, with a fifth of their words; or half their words. Words count
    only when each sentence has enough of them to make sharing more than an accident.
    """
    if (first.source, first.line) == (second.source, second.line):
        return False
    shared = len(first.figures & second.figures)
    enough = min(len(first.words), len(second.words)) >= FEWEST_WORDS
    overlap = len(first.words & second.words) / len(first.words | second.words) if enough else 0.0
    return shared >= 2 or (shared == 1 and overlap >= 0.2) or overlap >= 0.5


class Repetition(BaseModel):
    """Sentences that state the same fact, and the figures they share."""

    model_config = ConfigDict(frozen=True)

    sentences: tuple[Stated, ...]
    figures: tuple[str, ...] = ()
    """The figures shared by at least two of them, sorted."""


def repetitions(sentences: Sequence[Stated]) -> tuple[Repetition, ...]:
    """The groups of sentences that state the same fact, largest first.

    Pairs that share a sentence join one group: an introduction that repeats two rows of a
    table is one place to look, not two.
    """
    parent = list(range(len(sentences)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    shared: dict[tuple[int, int], frozenset[str]] = {}
    for i, first in enumerate(sentences):
        for j in range(i + 1, len(sentences)):
            second = sentences[j]
            if same_fact(first, second):
                parent[root(i)] = root(j)
                shared[(i, j)] = first.figures & second.figures

    members: dict[int, list[int]] = {}
    for index in range(len(sentences)):
        members.setdefault(root(index), []).append(index)
    groups: list[Repetition] = []
    for indices in members.values():
        if len(indices) < 2:
            continue
        inside = set(indices)
        common: set[str] = set().union(
            *(found for (i, j), found in shared.items() if i in inside and j in inside)
        )
        groups.append(
            Repetition(
                sentences=tuple(sentences[index] for index in indices),
                figures=tuple(sorted(common)),
            )
        )
    return tuple(sorted(groups, key=lambda group: -len(group.sentences)))
