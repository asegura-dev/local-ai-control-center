"""A note per reference, written for the thesis it serves (ADR-124).

Pure: what was found, judged and read comes in, and Markdown goes out, in the markup an
Obsidian vault reads - frontmatter and callouts. **Each part says what it is.** What LACC
assembled is stated; what a judge decided is labelled with its verdict; what a model read is
headed as its reading. A note that blurred the three would hand a writer a model's opinion
looking like a checked fact.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.corpus import CollectedClaim
from local_ai_control_center.core.protocol import CitingSentence, MasterEntry, Version
from local_ai_control_center.core.skill import FORMULA_PART

NOTES_FOLDER = "notes"
"""Where notes go when no other folder is named: one file per reference, named by its key."""

SentenceVerdict = Literal["supported", "contradicted", "nothing", "undecided"]
"""What the judge concluded about a sentence of the protocol - `review`'s four (ADR-115)."""


class Cited(BaseModel):
    """One sentence of the protocol that cites this reference, and what was concluded."""

    model_config = ConfigDict(frozen=True)

    sentence: CitingSentence
    version: Version
    verdict: SentenceVerdict = "nothing"
    quote: str = ""
    """The quotation the verdict rests on, when there is one."""

    page: int | None = None
    detail: str = ""
    considered: tuple[tuple[str, int | None], ...] = ()
    """The quotations judged for it, nearest first, with their pages.

    Shown when nothing held the sentence up, so "not covered" can be acted on: a reader sees
    whether the reference's support was never collected or was collected and judged not to
    hold it, which call for opposite responses (ADR-068, ADR-124)."""


class Reading(BaseModel):
    """What the model read in this reference for one part of the thesis, and its checks."""

    model_config = ConfigDict(frozen=True)

    part: str
    reading: str
    quote: str
    page: int | None = None
    found: bool = False
    """Whether its quotation is in the document - the check every quotation gets."""

    verdict: str = ""
    """What the judge said of the reading against its quotation, or empty when it was not
    asked: a formula, or a quotation that is not in the document."""

    use: str = ""
    """How the model suggests the thesis could use it. Shown as its suggestion, never judged:
    no quotation of the reference can establish what the thesis should do with it."""

    @property
    def formula(self) -> bool:
        """Whether this block is a formula the model reconstructed."""
        return self.part.strip().lower() == FORMULA_PART.lower()


_VERDICTS: dict[str, tuple[str, str]] = {
    "supported": ("success", "Held up"),
    "contradicted": ("failure", "Contradicted"),
    "nothing": ("question", "Not covered by its quotations"),
    "undecided": ("warning", "Not judged - the engine did not answer"),
}
"""A sentence's verdict as an Obsidian callout. Not covered is a question, never a failure:
the reference may say it in words no quotation caught (ADR-068)."""

_VERSIONS = {"compact": "compact", "extended": "extended"}


def _quoted(text: str) -> list[str]:
    """``text`` as the lines of a callout's body."""
    return [f"> {line}" if line else ">" for line in text.splitlines()] or [">"]


def _yaml(value: str) -> str:
    """A string safe in frontmatter: JSON's quoting is valid YAML and survives any colon."""
    return json.dumps(value, ensure_ascii=False)


def _page(page: int | None) -> str:
    return f"p. {page}" if page is not None else "page unknown"


def note_text(
    entry: MasterEntry,
    cited: tuple[Cited, ...],
    readings: tuple[Reading, ...],
    quotations: tuple[CollectedClaim, ...],
) -> str:
    """The note for one reference, whole."""
    lines = ["---", f"key: {_yaml(entry.key)}"]
    if entry.compact is not None:
        lines.append(f"compact: {entry.compact}")
    if entry.extended is not None:
        lines.append(f"extended: {entry.extended}")
    if entry.doi:
        lines.append(f"doi: {_yaml(entry.doi)}")
    lines += [f"reference: {_yaml(entry.reference)}", "---", "", f"# {entry.key}", ""]

    numbers = " · ".join(
        f"{version} [{number}]"
        for version, number in (("compact", entry.compact), ("extended", entry.extended))
        if number is not None
    )
    lines += ["> [!info] Reference"]
    lines += _quoted(entry.reference or "(not in the master list)")
    lines += [">", f"> Cite as `[@{entry.key}]`" + (f" · {numbers}" if numbers else ""), ""]

    lines += ["## Where the protocol cites it", ""]
    if not cited:
        lines += ["No sentence of either version cites it.", ""]
    for one in cited:
        kind, label = _VERDICTS[one.verdict]
        where = f"{_VERSIONS[one.version]}, {one.sentence.source}, line {one.sentence.line}"
        lines += [f"> [!{kind}] {label} · {where}"]
        lines += _quoted(one.sentence.text)
        if one.quote:
            lines += [">", f"> It rests on ({_page(one.page)}):"]
            lines += [f">> {line}" for line in one.quote.splitlines()]
        elif one.considered:
            lines += [">", "> The nearest of its quotations, none judged to hold it:"]
            for quote, page in one.considered:
                lines += [f">> {_page(page)}: {line}" for line in quote.splitlines()[:1]]
        if one.detail:
            lines += [">", f"> Judge: {one.detail}"]
        lines.append("")

    prose = [r for r in readings if not r.formula]
    formulas = [r for r in readings if r.formula]
    lines += ["## What it gives the thesis - the model's reading", ""]
    lines += [
        "*A model's reading. Each quotation under it was checked against the document, and "
        "each reading judged against its quotation; neither makes the reading true.*",
        "",
    ]
    if not prose:
        lines += ["The model named no part of the thesis this reference bears on.", ""]
    for reading in prose:
        if not reading.found:
            kind, label = "caution", "its quotation is not in the document"
        elif reading.verdict == "follows":
            kind, label = "note", "its quotation supports it"
        elif reading.verdict in ("contradicts", "neither"):
            kind, label = "caution", "its quotation does not support it"
        else:
            kind, label = "note", "not judged"
        lines += [f"> [!{kind}] {reading.part} · {label}"]
        lines += _quoted(reading.reading)
        lines += [">", f"> {_page(reading.page)}:"]
        lines += [f">> {line}" for line in reading.quote.splitlines()]
        if reading.use:
            lines += [">", f"> *How the thesis might use it, as the model suggests:* {reading.use}"]
        lines.append("")

    if formulas:
        lines += ["## Formulas - reconstructed by the model", ""]
        lines += [
            "*Extraction breaks formulas, so these are the model's LaTeX for a line of the text. "
            "The line is checked; the LaTeX can only be checked by a person, against the PDF.*",
            "",
        ]
    for formula in formulas:
        state = "the line is in the document" if formula.found else "the line was not found"
        lines += [f"> [!warning] Reconstruction · {_page(formula.page)} · {state}"]
        lines += [">", "> $$", f"> {formula.reading}", "> $$", ">", "> From the text:"]
        lines += [f">> {line}" for line in formula.quote.splitlines()]
        lines.append("")

    lines += ["## Its verified quotations", ""]
    if not quotations:
        lines += ["None of its quotations is in the corpus.", ""]
    for quotation in quotations:
        lines += [f"> [!quote] {_page(quotation.page)}"]
        lines += _quoted(quotation.quote)
        if quotation.claim:
            lines += [">", f"> — {quotation.claim}"]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
