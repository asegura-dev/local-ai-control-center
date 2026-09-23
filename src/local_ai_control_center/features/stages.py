"""Where the work stands, stage by stage (ADR-080).

`tools/measure.py` reports the project: layers, tests, records. This reports **the work**:
how much of a bibliography has been converted, collected, assembled, resolved and reviewed,
and what each stage is still missing.

Two rules shape it.

**Every figure is counted from the files, now.** Nothing is stored and nothing is estimated -
which is the same stance the measurement tool takes, for the same reason: a number written
down is a number that will be true for a while and then quietly stop being.

**A stage reports what is missing, not only what is done.** "832 quotations" reads like
success; "832 quotations, 2 documents with none" is the same fact with the part that needs
doing still attached. This project has measured what the first kind of sentence costs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.corpus import parse_corpus
from local_ai_control_center.core.references import references_in, without_truncations

CORPUS_MARKS = ("# Collected quotations", "# Claims collected by")
BIBLIOGRAPHY_MARK = "# Bibliography"
REVIEW_MARK = "# Review of"
COVERAGE_MARK = "# How far the nearest quotation is"
"""How a coverage report opens (ADR-088).

Added the day after `coverage` shipped, because `status` counted its own reports as
documents nobody had quoted - three invented pending items. **Every new writer of a file in
the workspace has to be taught to this reader**, and there is no way to notice except by
running `status` after adding one (ADR-082).
"""

_A_CONTROL_TOPIC = re.compile(r"(?m)^!\s*\S")
"""How a topics file is recognised: a line marked as the control.

Not a heading, because a topics file has none worth requiring - it is a list somebody wrote.
The control marker is the one thing `coverage` *refuses to run without*, so every usable
topics file carries it, and a line opening with `!` is not markdown for anything else.

It is looked for anywhere in the opening rather than on the first line, because a person
writes the control **last** - it is the odd one out, and that is where an odd one out goes.
"""
RESOLVED_MARK = "## Resolved"
TAKEN_FROM = ".from.json"
"""Where a section written by `--take` records the document it came from.

Beside the file, the way findings sit beside a report and the registry cache beside a
bibliography. Nothing is written *into* the extract: hundreds of quotations are checked
against these files as they are (ADR-076), and this is a fact **about** the file rather than
part of it.

Without it, `status` called a guideline "with no quotation" while seven sections taken out of
it were collected - a pending item that was not pending (ADR-082).
"""

_SAMPLE = 200

_ENOUGH_FOR_A_LIST = 8_000
"""How much is read when the cheap checks have all missed.

Only reached by a file that is not a corpus, a bibliography, a review, a coverage report or
an extract - so it is read once, to look for a control marker that a person writes at the
end of a short list. A file with nothing of the sort past this is a document.
"""

_SECTION_OPENING = re.compile(r"^\s{0,3}\d{1,2}(?:\.\d{1,2}){0,2}\.?(?:\s|$)")
"""How a file written by `sections --take` opens: with the number of the section it is.

Counted apart from the documents somebody brought, because it is neither - it came out of
one of them. The first reading of this counted six documents "with no quotation" of which
three were extracted sections and one was a page of the user's own notes (ADR-080).
"""


class Stage(BaseModel):
    """One step of the work, with what it produced and what it has not."""

    model_config = ConfigDict(frozen=True)

    name: str
    command: str
    """What to run to move it forward."""

    done: str = ""
    missing: str = ""
    """Empty when nothing is outstanding. Never a reassurance - an empty string is silence."""

    @property
    def settled(self) -> bool:
        """Whether this stage has something to show and nothing outstanding."""
        return bool(self.done) and not self.missing


class Work(BaseModel):
    """The whole of it, in order."""

    model_config = ConfigDict(frozen=True)

    workspace: str
    stages: tuple[Stage, ...] = ()

    @property
    def settled(self) -> int:
        return sum(1 for stage in self.stages if stage.settled)


def _kind(path: Path) -> str:
    """What a file announces itself to be, from its first line."""
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            more = handle.read(_ENOUGH_FOR_A_LIST)
    except OSError:
        return "other"
    opening = more[:_SAMPLE]
    if opening.startswith(CORPUS_MARKS):
        return "corpus"
    if opening.startswith(BIBLIOGRAPHY_MARK):
        return "bibliography"
    if opening.startswith(REVIEW_MARK):
        return "review"
    if opening.startswith(COVERAGE_MARK):
        return "coverage"
    if _A_CONTROL_TOPIC.search(more):
        return "topics"
    if _SECTION_OPENING.match(opening.splitlines()[0] if opening.splitlines() else ""):
        return "extract"
    return "document"


def stages_in(workspace: Path, context_file: str = "") -> Work:
    """Read the workspace and say where each stage of the work stands.

    Counted from files: no model is called, nothing is written, and nothing leaves.

    ``context_file`` is excluded from the documents. A workspace names one in its own
    configuration, and standing context is something every run carries rather than something
    to quote from - counting it as a document with no quotation invents a pending item out
    of a setting the user wrote (ADR-082).
    """
    if not workspace.is_dir():
        return Work(workspace=str(workspace))

    by_kind: dict[str, list[Path]] = {
        "corpus": [],
        "bibliography": [],
        "review": [],
        "coverage": [],
        "topics": [],
        "extract": [],
        "document": [],
    }
    for path in sorted(workspace.glob("*.md")):
        if path.name.startswith("."):
            continue
        if context_file and path.name == context_file:
            continue
        by_kind[_kind(path)].append(path)

    documents = by_kind["document"]
    corpora = by_kind["corpus"]

    # The largest corpus is the one being worked from; the others are parts or backups.
    biggest = max(corpora, key=lambda p: p.stat().st_size, default=None)
    claims = parse_corpus(biggest.read_text(encoding="utf-8", errors="replace")) if biggest else ()
    refused = sum(1 for c in claims if "NOT IN THE DOCUMENT" in c.recorded_verdict)
    covered = {c.document for c in claims}
    # A document whose extracted sections are collected is covered *through* them. The
    # extract says which document it came from, in a file beside it (ADR-082).
    for extract in by_kind["extract"]:
        if extract.name not in covered:
            continue
        beside = extract.with_suffix(extract.suffix + TAKEN_FROM)
        try:
            noted = json.loads(beside.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(noted, dict) and isinstance(noted.get("document"), str):
            covered.add(noted["document"])
    uncovered = [p.name for p in documents if p.name not in covered]

    dois: set[str] = set()
    parsed = 0
    for path in documents:
        found = references_in(path.read_text(encoding="utf-8", errors="replace"))
        parsed += bool(found)
        dois |= {r.doi for r in found if r.doi}
    whole = without_truncations(frozenset(dois))

    # Only the entries under `## Resolved`. Counting every bullet in the file also counted
    # the DOIs the registry does not hold and the documents that carry none, which turned
    # 172 into 236 - a figure that flattered, like most of the wrong ones here (ADR-080).
    resolved = 0
    for path in by_kind["bibliography"]:
        text = path.read_text(encoding="utf-8", errors="replace")
        if RESOLVED_MARK not in text:
            continue
        listed = text.split(RESOLVED_MARK, 1)[1].split("\n## ", 1)[0]
        resolved = max(resolved, listed.count("\n- "))

    return Work(
        workspace=str(workspace),
        stages=(
            Stage(
                name="Documents",
                command="lacc ingest <file> --into <name>.md",
                done=(
                    f"{len(documents)} brought in"
                    + (
                        f", {len(by_kind['extract'])} sections taken out of them"
                        if by_kind["extract"]
                        else ""
                    )
                ),
                missing="" if documents else "nothing to work from yet",
            ),
            Stage(
                name="Quotations",
                command="lacc collect extract_claims <docs> --into corpus.md",
                done=f"{len(claims):,} from {len(covered)} documents" if claims else "",
                missing=(
                    f"{len(uncovered)} with none: {', '.join(name[:34] for name in uncovered[:3])}"
                    if uncovered
                    else ""
                ),
            ),
            Stage(
                name="Corpus",
                command="lacc corpus <corpora> --into citas.md",
                done=(
                    f"{len(claims) - refused:,} citable of {len(claims):,}, in {biggest.name}"
                    if biggest
                    else ""
                ),
                missing=(f"{refused} are no longer in their document" if refused else ""),
            ),
            Stage(
                name="References",
                command="lacc references <docs>",
                # Only when there is something to have parsed. With nothing in the
                # workspace this read "0 of 0 parse" and the stage called itself settled,
                # which is a stage reporting success for having no work (ADR-080).
                done=(
                    f"{parsed} of {len(documents)} parse, {len(whole)} distinct DOIs"
                    if documents
                    else ""
                ),
                missing=(
                    f"{len(documents) - parsed} number their references in a way this cannot read"
                    if parsed < len(documents)
                    else ""
                ),
            ),
            Stage(
                name="Bibliography",
                command="lacc resolve <docs> --cited --into bibliografia.md",
                done=f"{resolved} works resolved" if resolved else "",
                missing=(
                    f"{len(whole) - resolved} DOIs unresolved" if resolved < len(whole) else ""
                ),
            ),
            Stage(
                name="Writing",
                command="lacc review <draft> --against <corpus> --into report.md",
                done=f"{len(by_kind['review'])} drafts reviewed" if by_kind["review"] else "",
                missing="" if by_kind["review"] else "nothing of yours has been read yet",
            ),
        ),
    )
