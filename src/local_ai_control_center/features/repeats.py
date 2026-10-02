"""What a text says twice: the report, and a model's proposal for each group (ADR-125).

Pure but for one function: `proposed` asks an engine about one group, through the port it is
handed. Everything else takes groups and answers in and gives prompts and Markdown out. LACC's
own words are English, as all of them are; the writer's sentences are quoted as written,
citation marks and all. **Nothing in it calls a repetition a fault**: a table that repeats its
prose may be what the text needs.

A proposal is a model's, and headed as one. What can be checked without a model is checked
beside it - a number it brought in, a citation mark it dropped, a language it changed - and
nothing it proposes is written anywhere but the report: the writer edits from it.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.protocol import CITATION, numbers_in
from local_ai_control_center.core.repetition import Repetition, content_words, numbers
from local_ai_control_center.core.wording import counted
from local_ai_control_center.ports.provider import Provider

RULE = (
    "Found without a model: two sentences in different paragraphs or rows that share two "
    "specific figures, one figure and a fifth of their words, or half their words. A group is "
    "a place to look, not a fault - a table may repeat its prose on purpose."
)
"""The rule, said wherever its groups are shown, so a reader knows what they are (ADR-125)."""

UNCHANGED = "UNCHANGED"
"""What a proposal says of a sentence whose repetition earns its place."""

EDIT_TEMPERATURE = 0.0
"""A proposal is a decision about one group; the same group gets the same answer within a
warmed engine (chapter 05, "The same prompt gives the same answer")."""

_ASKED = """You are an editor. The sentences below come from one text, and they state the same
fact, or nearly. Each is given with its place - a file and a line, for your answer only - and
the chapter it is in.

{sentences}

Choose the one place where the fact should stay whole. For every other place, write how that
sentence should read so that it no longer repeats the fact: shorter, or pointing to the place
kept, or "UNCHANGED" when the repetition earns its place - a table that summarises its prose
may be worth keeping as it is.

Write each sentence in the language it is written in. Do not add a number, a name or a claim
the sentence does not have, and do not take out anything the sentence kept says nowhere else.
Keep every citation mark in square brackets, such as [12], in the sentence that has it. To
point to the place kept, name its chapter as the text would; never write a file name or a line
number into a sentence - a reader of the text cannot follow them."""

_NAMES_A_PLACE = re.compile(r"\.md\b|\b(?:línea|linea|line|líneas|lines)\s+\d+", re.IGNORECASE)
"""A file or a line written into a sentence: the pilot found six, such as `ver línea 29`."""

_SPANISH = frozenset(
    {"el", "la", "los", "las", "de", "del", "que", "en", "y", "para", "con", "por", "una", "un"}
    | {"es", "se", "al", "lo", "como", "su", "sus"}
)
_ENGLISH = frozenset(
    {"the", "of", "and", "to", "in", "is", "for", "with", "that", "on", "are", "by", "an", "be"}
    | {"this", "as", "it", "from", "its"}
)
_LETTERS = re.compile(r"[^\W\d_]+")


def opening(text: str, longest: int = 150) -> str:
    """The start of a sentence, for a line that has to stay readable."""
    return text if len(text) <= longest else text[: longest - 1].rstrip() + "…"


def shared_label(group: Repetition) -> str:
    """What a group's sentences share, in a few words."""
    if group.figures:
        return f"figures {', '.join(group.figures)}"
    return "most of their words"


def places_of(group: Repetition) -> tuple[str, ...]:
    """Each sentence's place, made unique: two sentences of one paragraph can join a group
    through a third, and a model answering about a place has to mean one of them."""
    seen: dict[str, int] = {}
    labels: list[str] = []
    for one in group.sentences:
        seen[one.place] = seen.get(one.place, 0) + 1
        labels.append(one.place if seen[one.place] == 1 else f"{one.place} ({seen[one.place]})")
    return tuple(labels)


def chapter_of(source: str) -> str:
    """The chapter a file holds, in words, from its name: `03_antecedentes (2026-10-01).md` is
    "antecedentes", `compacto_04_estado_del_arte.md` is "estado del arte".

    What a pointer can name: the pilot's model, given only file and line, wrote "ver línea 29"
    into the text, which no reader can follow (ADR-125).
    """
    stem = re.sub(r"\s*\([^)]*\)\s*$", "", source.rsplit(".", 1)[0] if "." in source else source)
    words = [word for word in re.split(r"[_\s]+", stem) if word]
    numbered = [index for index, word in enumerate(words) if word.isdigit()]
    if numbered and numbered[0] + 1 < len(words):
        words = words[numbered[0] + 1 :]
    return " ".join(words) or source


def proposal_prompt(group: Repetition) -> str:
    """What one group's call asks: the group's sentences, their places and their chapters."""
    listed = "\n".join(
        f"{label} (chapter: {chapter_of(one.source)}): {one.text}"
        for label, one in zip(places_of(group), group.sentences, strict=True)
    )
    return _ASKED.format(sentences=listed)


def proposal_schema(group: Repetition) -> dict[str, Any]:
    """The answer's shape, enforced by the engine: a place can only be one of the group's.

    Asking for a valid place is a request; an enumeration is structure (ADR-052).
    """
    places = list(places_of(group))
    return {
        "type": "object",
        "properties": {
            "keep": {"type": "string", "enum": places},
            "others": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "at": {"type": "string", "enum": places},
                        "reads": {"type": "string"},
                    },
                    "required": ["at", "reads"],
                },
            },
        },
        "required": ["keep", "others"],
    }


class Edit(BaseModel):
    """How the model proposes one sentence should read, and what the checks found."""

    model_config = ConfigDict(frozen=True)

    at: str
    reads: str
    """The proposed wording; `UNCHANGED`, or empty for a sentence the model would remove."""

    added: tuple[str, ...] = ()
    """Numbers the proposal brings in that its original did not have."""

    dropped: tuple[str, ...] = ()
    """Citation marks of the original the proposal leaves out, as `[12]`."""

    other_language: bool = False
    """Whether the proposal is written in another language than its original, judged by
    their function words."""

    lost: tuple[str, ...] = ()
    """Words and numbers of the original that no sentence of the group says any longer, once
    the proposal is applied. What the pilot's checks could not see: they looked at what a
    proposal adds, and seven of 21 took out what nothing else said (ADR-125)."""

    names_a_place: bool = False
    """Whether it writes a file or a line into the text, which a reader cannot follow."""

    @property
    def unchanged(self) -> bool:
        """Whether the model would leave this sentence as it is."""
        return self.reads.strip().upper() == UNCHANGED


class Proposal(BaseModel):
    """A model's proposal for one group, checked; or why there is none to use."""

    model_config = ConfigDict(frozen=True)

    keep: str = ""
    """The place where the fact stays whole."""

    edits: tuple[Edit, ...] = ()
    problems: tuple[str, ...] = ()
    """What is wrong with the answer itself - a place it lacks, a place twice, no answer.
    Said in the report, never mended."""

    @property
    def flagged(self) -> bool:
        """Whether any check found something to look at before using it."""
        return bool(self.problems) or any(
            edit.added or edit.dropped or edit.other_language or edit.lost or edit.names_a_place
            for edit in self.edits
        )


def _language(text: str) -> str:
    words = _LETTERS.findall(text.lower())
    spanish = sum(word in _SPANISH for word in words)
    english = sum(word in _ENGLISH for word in words)
    if spanish == english:
        return ""
    return "es" if spanish > english else "en"


def _marks(text: str) -> set[int]:
    return {number for found in CITATION.finditer(text) for number in numbers_in(found.group(1))}


def _said(text: str) -> frozenset[str]:
    """What a sentence says, as far as words can tell: its content words and its numbers."""
    plain = CITATION.sub("", text)
    return content_words(plain) | numbers(plain)


def checked(
    original: str,
    at: str,
    reads: str,
    still: frozenset[str] = frozenset(),
    files: tuple[str, ...] = (),
) -> Edit:
    """One proposed wording, with what can be checked without a model.

    ``still`` is what the group says once the proposal is applied, every sentence of it;
    ``files`` are the names of the files the group's sentences come from, which no sentence
    of the text should carry.
    """
    if reads.strip().upper() == UNCHANGED:
        return Edit(at=at, reads=UNCHANGED)
    added = numbers(CITATION.sub("", reads)) - numbers(CITATION.sub("", original))
    dropped = _marks(original) - _marks(reads)
    before, after = _language(original), _language(reads)
    return Edit(
        at=at,
        reads=reads,
        added=tuple(sorted(added)),
        dropped=tuple(f"[{number}]" for number in sorted(dropped)),
        other_language=bool(before and after and before != after),
        lost=tuple(sorted(_said(original) - still)),
        names_a_place=bool(_NAMES_A_PLACE.search(reads)) or any(name in reads for name in files),
    )


def proposal_from(group: Repetition, answer: str) -> Proposal:
    """What a model's answer proposes for ``group``, checked; never repaired."""
    try:
        said = json.loads(answer.strip())
    except ValueError:
        said = None
    if not isinstance(said, dict):
        return Proposal(problems=("The answer is not in the shape asked.",))
    labels = places_of(group)
    originals = dict(zip(labels, (one.text for one in group.sentences), strict=True))
    keep = str(said.get("keep", "")).strip()
    problems: list[str] = []
    if keep not in originals:
        problems.append(f"It keeps {keep or 'no place'}, which is not one of this group's.")
        keep = ""
    proposed_for: dict[str, str] = {}
    for item in said.get("others") or []:
        if not isinstance(item, dict):
            continue
        at, reads = str(item.get("at", "")).strip(), str(item.get("reads", "")).strip()
        if at not in originals:
            problems.append(f"It rewrites {at or 'no place'}, which is not one of this group's.")
        elif at == keep:
            problems.append(f"It both keeps and rewrites {at}.")
        elif at in proposed_for:
            problems.append(f"It rewrites {at} twice; the first is shown.")
        else:
            proposed_for[at] = reads
    # What the group still says once every proposal is applied: a rewrite may take out what
    # another sentence of the group keeps saying, and nothing else (ADR-125).
    applied = {
        label: (
            proposed_for[label]
            if label in proposed_for and proposed_for[label].upper() != UNCHANGED
            else text
        )
        for label, text in originals.items()
    }
    still = frozenset().union(*(_said(text) for text in applied.values()))
    # A file's name counts only when no sentence would say it by chance: `07_hipotesis` is a
    # file, `draft` could be a word.
    files = tuple(
        sorted(
            stem
            for stem in {one.source.split(" (")[0].rsplit(".", 1)[0] for one in group.sentences}
            if "_" in stem or any(character.isdigit() for character in stem)
        )
    )
    edits = tuple(
        checked(originals[at], at, reads, still, files) for at, reads in proposed_for.items()
    )
    missing = [label for label in labels if label != keep and label not in proposed_for]
    if keep and missing:
        problems.append(f"It says nothing of {', '.join(missing)}.")
    return Proposal(keep=keep, edits=edits, problems=tuple(problems))


def proposed(provider: Provider, group: Repetition) -> tuple[str, str, Proposal]:
    """One group's proposal: what was asked, what came back, and what it proposes.

    The one place here that reaches an engine, carrying the group's sentences and nothing
    else. One group that fails costs that group, as one claim costs the judge one claim
    (ADR-053): an engine that does not answer is said in the report, and the next group is
    asked. The caller records what went and what came back.
    """
    asked = proposal_prompt(group)
    try:
        answer = provider.complete(asked, EDIT_TEMPERATURE, proposal_schema(group)).text
    except Exception as error:  # noqa: BLE001 - one group, not the batch (ADR-125)
        return asked, "", Proposal(problems=(f"The engine did not answer: {error}",))
    return asked, answer, proposal_from(group, answer)


def _checks(edit: Edit) -> str:
    found = []
    if edit.added:
        found.append(f"adds {', '.join(edit.added)}")
    if edit.dropped:
        found.append(f"drops {', '.join(edit.dropped)}")
    if edit.other_language:
        found.append("is written in another language than its original")
    if edit.lost:
        found.append(f"loses what the group no longer says: {', '.join(edit.lost)}")
    if edit.names_a_place:
        found.append("writes a file or a line into the text")
    if found:
        return "; ".join(found)
    return "adds no number, keeps its citation marks, loses nothing the group stops saying"


def _proposal_lines(proposal: Proposal, model: str) -> list[str]:
    lines = [f"**The model's proposal** ({model}) - checked without a model; yours to decide:", ""]
    if proposal.keep:
        lines.append(f"- keep whole: **{proposal.keep}**")
    for edit in proposal.edits:
        if edit.unchanged:
            lines.append(f"- **{edit.at}** - unchanged")
        elif not edit.reads:
            lines.append(f"- **{edit.at}** - removed")
        else:
            lines += [f"- **{edit.at}** - reads:", ""]
            lines += [f"  > {line}" for line in edit.reads.splitlines()]
            lines += ["", f"  *Checks: {_checks(edit)}.*"]
    lines += [f"- *Not usable as given:* {problem}" for problem in proposal.problems]
    return [*lines, ""]


def report_text(
    groups: tuple[Repetition, ...],
    read: tuple[str, ...],
    sentences: int,
    proposals: tuple[Proposal, ...] = (),
    model: str = "",
) -> str:
    """The report, whole: the rule, the counts, then each group, with its proposal if asked."""
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
        for label, stated in zip(places_of(group), group.sentences, strict=True):
            lines += [f"> **{label}**", ">"]
            lines += [f"> {line}" for line in stated.text.splitlines()]
            lines.append("")
        if number <= len(proposals):
            lines += _proposal_lines(proposals[number - 1], model)
    return "\n".join(lines).rstrip() + "\n"
