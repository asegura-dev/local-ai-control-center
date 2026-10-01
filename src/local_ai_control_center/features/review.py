"""Reading a draft somebody wrote, against the sources they collected (ADR-068).

Pure. Text in, paragraphs out; findings in, a report out. The two parts that are not pure -
ranking the corpus and asking the judge - live where they already lived, and this decides
what is worth asking about and how the answer is written down.

The rule that shapes every sentence printed here: **unsupported is not false.** A paragraph
can be true and well argued while resting on a paper that is not in the corpus, which on a
bibliography of two dozen papers is the ordinary case. The wording says so wherever it
appears, not once in a legend.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.wording import agreeing, counted
from local_ai_control_center.ports.entailment import Judgement

_FENCE = re.compile(r"^```")
_NOT_PROSE = re.compile(r"^(#{1,6}\s|\||!\[|<|\s*[-*+]\s|\s*\d+\.\s|>\s)")
"""Headings, tables, images, HTML, list items and block quotations.

Passed over rather than judged. A heading asserts nothing, a block quotation is somebody
else's sentence, and a table's support is its caption's problem. What is skipped is counted
and reported, so the output says what it looked at instead of implying it looked at all of it.
"""

_ENOUGH_WORDS = 8
"""Below this a paragraph is a caption, a label or a transition, not an assertion.

Eight rather than twelve, and the difference matters: *"PSMA PET/CT is more sensitive than
CT for nodal staging"* is ten words and is exactly the kind of sentence this exists to check.
A threshold that skipped it would skip the strongest claims in a draft, which are usually the
shortest. Headings and list items are excluded by shape rather than by length, so this only
has to catch what is too small to assert anything at all.
"""


class Paragraph(BaseModel):
    """One paragraph of a draft, with where it starts so a person can find it."""

    model_config = ConfigDict(frozen=True)

    text: str
    line: int


class Finding(BaseModel):
    """What was concluded about one paragraph, and on what."""

    model_config = ConfigDict(frozen=True)

    paragraph: Paragraph
    quote: str = ""
    """The quotation the verdict is about, when there is one."""

    document: str = ""
    verdict: str = "nothing"
    """`supported`, `contradicted`, `nothing` or `undecided`.

    `nothing` means what was judged did not hold it, which is not the same as the paragraph
    being wrong. `undecided` means the judge did not answer for something closest to it - an
    engine that did not load - so nothing was concluded at all (ADR-115). It used to be
    reported as `nothing`: a corpus blamed for an engine that was switched off."""

    detail: str = ""

    considered: tuple[tuple[str, str], ...] = ()
    """What was ranked closest and judged, as (document, quotation), whatever the verdict.

    Carried so that "nothing covers this" can be acted on. Without it the finding is opaque
    in exactly the way ADR-034 refused for quotations: a reader cannot tell whether their
    support was never retrieved or was retrieved and rejected, and those call for opposite
    responses - collect more, or rewrite the sentence. Found by running this on a draft whose
    support was in the corpus and was still reported as uncovered (ADR-068).
    """

    @property
    def worth_a_look(self) -> bool:
        """Whether a person should read this paragraph again before submitting it."""
        return self.verdict != "supported"


FINDINGS_SUFFIX = ".findings.json"
"""Where a review leaves what it concluded, for a second view to read (ADR-069).

Beside the report, the way the registry cache sits beside the bibliography. The report is for
a person; this is the same findings as data, so the window can paint them over the draft
without re-running anything - and so that if the window and the CLI ever disagree about what
a finding means, the disagreement is visible in a file both of them read.
"""


class Reviewed(BaseModel):
    """A whole review, as the file that carries it between views."""

    model_config = ConfigDict(frozen=True)

    draft: str
    corpus: str
    findings: tuple[Finding, ...] = ()


def paragraphs_in(text: str) -> tuple[Paragraph, ...]:
    """The paragraphs of a draft that assert something, with their line numbers.

    Fenced blocks are skipped whole: a fence can contain blank lines, so splitting on blank
    lines first would cut code into paragraphs and judge the pieces.
    """
    found: list[Paragraph] = []
    block: list[str] = []
    start = 0
    fenced = False

    def close() -> None:
        nonlocal block
        if block:
            whole = " ".join(line.strip() for line in block).strip()
            if len(whole.split()) >= _ENOUGH_WORDS:
                found.append(Paragraph(text=whole, line=start))
        block = []

    for number, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line.strip()):
            close()
            fenced = not fenced
            continue
        if fenced:
            continue
        if not line.strip():
            close()
            continue
        if not block and _NOT_PROSE.match(line):
            continue
        if not block:
            start = number
        block.append(line)
    close()
    return tuple(found)


def concluded(paragraph: Paragraph, judged: list[tuple[str, str, Judgement]]) -> Finding:
    """Turn what the judge said about several candidates into one finding.

    A contradiction outranks support, and does so deliberately: a paragraph that some
    quotation holds up and another flatly contradicts is the most important thing on the
    page, and reporting only the agreeable half would hide it.
    """
    looked_at = tuple((document, quote) for document, quote, _ in judged)
    for document, quote, judgement in judged:
        if judgement.verdict == "contradicts":
            return Finding(
                paragraph=paragraph,
                quote=quote,
                document=document,
                verdict="contradicted",
                detail=judgement.detail,
                considered=looked_at,
            )
    for document, quote, judgement in judged:
        if judgement.supported:
            return Finding(
                paragraph=paragraph,
                quote=quote,
                document=document,
                verdict="supported",
                detail=judgement.detail,
                considered=looked_at,
            )
    # A candidate the judge could not answer for might have held it: without it, "nothing
    # holds this" is not something anyone knows (ADR-115).
    silent = next((j for _, _, j in judged if j.verdict == "undecided"), None)
    if silent is not None:
        return Finding(
            paragraph=paragraph, verdict="undecided", detail=silent.detail, considered=looked_at
        )
    return Finding(paragraph=paragraph, considered=looked_at)


NOT_TEXT = frozenset({".pdf", ".docx"})
"""What a draft may be brought as but not reviewed as: `ingest` turns these into Markdown."""


def draft_text(name: str, data: bytes) -> str:
    """A draft's bytes as text, or a ValueError saying why they are not text to judge.

    A `.docx` is a zip and a PDF is not prose: read as text, the first "paragraph" began
    `PK...[Content_Types].xml` and a yes would have sent sixty-nine judgements of it to the
    engine. And text that is not UTF-8 is refused rather than read with replacement marks,
    which sent `Dise?o metodol?gico` to be judged without a word (ADR-115). A byte-order mark
    is not a character of the draft, and is dropped.
    """
    suffix = Path(name).suffix.lower()
    if suffix in NOT_TEXT:
        raise ValueError(
            f"{name} is a {suffix} file, not text. Convert it first - "
            f'lacc ingest "{name}" - and review the .md it writes.'
        )
    if b"\x00" in data[:4096]:
        raise ValueError(f"{name} is not text: it holds bytes no text file does.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(
            f"{name} is not UTF-8 text: the byte 0x{data[error.start]:02x} at position "
            f"{error.start} is not a character in it. Save it as UTF-8 and bring it again."
        ) from error


def _shortened(text: str, longest: int = 220) -> str:
    """The opening of a paragraph, for a report that has to stay readable."""
    return text if len(text) <= longest else text[: longest - 1].rstrip() + "…"


def report(findings: list[Finding], draft: str, corpus: str, skipped: int) -> str:
    """The written record of a review, ordered by what needs attention first."""
    held = [f for f in findings if f.verdict == "supported"]
    against = [f for f in findings if f.verdict == "contradicted"]
    nothing = [f for f in findings if f.verdict == "nothing"]
    undecided = [f for f in findings if f.verdict == "undecided"]

    lines = [
        f"# Review of {draft}",
        "",
        f"{counted(len(findings), 'paragraph')} read against {corpus}. "
        f"{len(held)} {agreeing(len(held), 'is', 'are')} held up by a quotation in it, "
        f"{len(against)} {agreeing(len(against), 'is', 'are')} contradicted by one, and "
        f"{len(nothing)} {agreeing(len(nothing), 'is', 'are')} not covered by it either way."
        + (
            f" **{len(undecided)} {agreeing(len(undecided), 'was', 'were')} not judged**: "
            "the engine did not answer."
            if undecided
            else ""
        ),
        "",
        "**Nothing here says a paragraph is wrong.** This reports whether your own sources "
        "hold a sentence up, not whether the sentence is true - a paragraph resting on a "
        "paper that is not in this corpus is reported as uncovered, and is the ordinary "
        "case rather than the exception.",
        "",
    ]
    if skipped:
        lines += [
            f"*{skipped} blocks were not read*: headings, tables, code, block quotations "
            "and anything too short to assert something.",
            "",
        ]
    if against:
        lines += [
            "## Read these first: your corpus says otherwise",
            "",
            "A quotation you collected was judged to contradict what the paragraph says. "
            "This is the one that can put a false statement in a thesis.",
            "",
        ]
        for finding in against:
            lines += [
                f"**Line {finding.paragraph.line}.** {_shortened(finding.paragraph.text)}",
                "",
                f"> {finding.quote}",
                "",
                f"*{finding.document}* - {finding.detail}"
                if finding.detail
                else f"*{finding.document}*",
                "",
            ]
    if undecided:
        lines += [
            "## Not judged: the engine did not answer",
            "",
            "The judge could not answer for these, so nothing was concluded about them - which "
            "is not your corpus failing to hold them. Review the draft again once the engine "
            "answers.",
            "",
        ]
        for finding in undecided:
            lines += [
                f"**Line {finding.paragraph.line}.** {_shortened(finding.paragraph.text)}",
                "",
            ]
    if nothing:
        lines += [
            "## Not covered by your corpus",
            "",
            "Nothing collected was judged to hold these up. That means one of three things, "
            "and the report cannot tell them apart: the source is not in your corpus, the "
            "supporting quotation was never extracted from a document that is, or the "
            "paragraph claims more than your sources do. **Only the third is a problem with "
            "the writing.**",
            "",
        ]
        for finding in nothing:
            lines += [
                f"**Line {finding.paragraph.line}.** {_shortened(finding.paragraph.text)}",
                "",
            ]
            if finding.considered:
                lines.append("*Closest in your corpus, and judged not to hold it:*")
                lines.append("")
                lines += [
                    f"- {document}: {_shortened(quote, 160)}"
                    for document, quote in finding.considered
                ]
                lines.append("")
    if held:
        lines += ["## Held up by your corpus", ""]
        for finding in held:
            lines += [
                f"**Line {finding.paragraph.line}.** {_shortened(finding.paragraph.text)}",
                "",
                f"> {finding.quote}",
                "",
                f"*{finding.document}*",
                "",
            ]
    return chr(10).join(lines)


def reviews_in(folder: Path) -> tuple[Path, ...]:
    """Every review left in ``folder``, newest first.

    Here rather than in a view because finding and ordering them is a decision, and a view
    that made it would be a view containing logic (ADR-066).
    """
    found = sorted(folder.glob(f"*{FINDINGS_SUFFIX}"), key=lambda p: p.stat().st_mtime)
    return tuple(reversed(found))


def reviewed_from(path: Path) -> Reviewed | None:
    """Read one review back, or nothing if the file is not one.

    A damaged findings file is reported as unreadable rather than partially rendered: half a
    review painted over a draft would say some paragraphs are uncovered when nobody checked.
    """
    try:
        return Reviewed.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
