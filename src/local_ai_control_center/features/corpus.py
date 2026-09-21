"""Writing a corpus, and re-checking one that was written before (ADR-066).

**This is the half of the corpus format that used to live in the view.** `core.corpus` reads
the format; these two functions write it, and while they sat in `cli.py` they were free to
disagree with the reader for as long as nobody looked. They did: `_assembled` put the
paraphrase where the reader expects the standing, so assembling a corpus twice stripped the
meaning from every quotation in it while reporting figures that were all true (ADR-065).

Here, the writers and the reader are one import apart and answer to the same tests. That is
the arrangement the record asked for - it makes the defect impossible rather than merely
detectable.

`recheck` is the one thing here that touches the disk, and it belongs with the writers
because what it decides is what they print: a standing comes from looking in the document
again, never from the label the file being read carried (ADR-042).

`RunResult` is imported here **for typing only**. It lives in `cycle.py` and belongs there:
its `completion` is a `Completion`, the contract crossing the provider port, and the core may
not import a port. Naming a type is not depending on a module, which is why the test of
slices ignores type-only imports.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from local_ai_control_center.core.corpus import CollectedClaim
from local_ai_control_center.core.grounding import Claim, check_claim
from local_ai_control_center.core.workspace import Workspace

if TYPE_CHECKING:  # pragma: no cover - a type, never an import at run time
    from local_ai_control_center.cycle import RunResult

STANDINGS = ((True, "Citable"), (None, "Not re-checked"), (False, "Not in the document"))
"""The three groups an assembled corpus is divided into, in the order they are printed.

Three and not two: a quotation that is in the document and cannot be placed on a page is not
a fabrication, and calling it one is the error ADR-042 exists to correct.
"""


def standing_said(found: bool | None, page: int | None) -> str:
    """What the page line says about a quotation, in the words `collect` uses.

    Decided by the re-check, never by the label the file being read carried. A quotation
    whose document has left the workspace says that instead of claiming either standing.
    """
    if found is None:
        return "not re-checked: the document is no longer in the workspace"
    if not found:
        return "**NOT IN THE DOCUMENT**"
    return "verified" if page else "in the document, page not determined"


def collected_markdown(
    skill_name: str, model: str, gathered: list[tuple[str, RunResult | str]]
) -> str:
    """Assemble the collected claims into a file meant to be worked from.

    The quotation comes before the claim in each block, because the quotation is what
    carries authority: the claim is the model's paraphrase, and a generated file invites
    being treated as a source when it is not (ADR-039).
    """
    lines = [
        f"# Claims collected by {skill_name}",
        "",
        f"From {len(gathered)} documents, using {model or 'the mock provider'}. Every "
        "quotation was checked against the document it came from; the page is the one LACC "
        "located, not the one the model gave.",
        "",
        "This file is generated. It is not a source: each claim is the model's paraphrase, "
        "and the quotation beneath it is what can be cited.",
        "",
    ]
    divided = [
        name for name, outcome in gathered if not isinstance(outcome, str) and outcome.passes > 1
    ]
    if divided:
        many = len(divided) > 1
        lines += [
            f"{len(divided)} of these {'were' if many else 'was'} too large for the window and "
            f"{'were' if many else 'was'} read in several passes over "
            f"{'their' if many else 'its'} pages. Every quotation was still checked against "
            "the whole document, but no reading held all of it, so anything said about such a "
            "document as a whole rests on less than it appears to.",
            "",
        ]
    for name, outcome in gathered:
        lines.append(f"## {name}")
        lines.append("")
        if isinstance(outcome, str):
            lines += [f"**Not collected.** {outcome}", ""]
            continue
        claims = outcome.checked_claims
        held = sum(1 for c in claims if c.found)
        how = (
            f" Read in {outcome.passes} passes, so the model never held all of it at once."
            if outcome.passes > 1
            else ""
        )
        unplaceable = sum(1 for c in claims if c.found and not c.holds)
        aside = f" {unplaceable} are in it with no page determinable." if unplaceable else ""
        lines += [
            f"*{held} of {len(claims)} quotations are in the document.*{aside}{how}",
            "",
        ]
        for checked in claims:
            # Three outcomes, not two. A quotation that is in the document and cannot be
            # placed on a page is not a fabrication, and calling it one is the error
            # ADR-042 exists to correct - which lived on here after the check was fixed.
            # `holds` is what decides the page, not `found_on_page` directly: the two agree
            # by construction in `grounding`, and depending on that here would make this
            # file's output rest on an invariant of another module.
            number = checked.found_on_page if checked.holds else None
            page = f"p. {number}" if number else "page unknown"
            lines += [
                f"> {checked.claim.quote}",
                "",
                f"{page} - {standing_said(checked.found, number)}",
                "",
                checked.claim.claim,
                "",
            ]
            if checked.nearest:
                lines += [f"Closest text in the source: {checked.nearest}", ""]
    return chr(10).join(lines) + chr(10)


def assembled(
    rechecked: list[tuple[CollectedClaim, bool | None]],
    marked: frozenset[str],
    sources: list[Path],
) -> str:
    """Render one corpus, grouped by document, with each quotation's current standing."""
    named = ", ".join(source.name for source in sources)
    real = sum(1 for _, found in rechecked if found)
    lines = [
        "# Collected quotations",
        "",
        f"Assembled from {named}. Every quotation was looked for again in the document it "
        f"names: {real} of {len(rechecked)} are there.",
        "",
        "This file is generated and is not a source. The quotation is what can be cited; "
        "the line under it is the model's paraphrase and was never checked.",
        "",
    ]
    if marked:
        # Counted as entries rather than as distinct quotations: the same sentence can be
        # quoted from two documents, and the number here has to match what a reader counts.
        shown = sum(1 for claim, _ in rechecked if claim.quote in marked)
        lines += [
            f"**{shown} quotations are marked** with a bullet, for mentioning words you "
            "gave. Nothing was removed, and a quotation can be about a subject without "
            "naming it.",
            "",
        ]

    by_document: dict[str, list[tuple[CollectedClaim, bool | None]]] = {}
    for claim, found in rechecked:
        by_document.setdefault(claim.document, []).append((claim, found))

    for document, entries in by_document.items():
        here = sum(1 for _, found in entries if found)
        lines += [f"## {document}", "", f"*{here} of {len(entries)} are in the document.*", ""]
        for standing, heading in STANDINGS:
            group = [c for c, found in entries if found is standing]
            if not group:
                continue
            lines += [f"### {heading}", ""]
            for claim in group:
                bullet = "- " if claim.quote in marked else ""
                where = f"p. {claim.page}" if claim.page else "page unknown"
                # The same shape `collected_markdown` writes: the standing on the page
                # line, the paraphrase on its own line below. Putting the paraphrase on the
                # page line made this file unreadable by the parser that reads the other
                # one - it matched as a verdict, and a verdict is correctly not carried
                # forward - so assembling a corpus twice silently stripped every paraphrase
                # in it while reporting success (ADR-065).
                lines += [
                    f"{bullet}> {claim.quote}",
                    "",
                    f"{where} - {standing_said(standing, claim.page)}",
                    "",
                    claim.claim,
                    "",
                ]
                if claim.nearest and standing is False:
                    lines += [f"Closest text in the source: {claim.nearest}", ""]
    return chr(10).join(lines) + chr(10)


def recheck(
    collected: list[CollectedClaim], workspace: Workspace
) -> tuple[list[tuple[CollectedClaim, bool | None]], list[CollectedClaim]]:
    """Look for every quotation again in the document it names.

    Returns each claim with whether it is really there, or ``None`` when the document is no
    longer in the workspace - which is reported rather than guessed at.
    """
    sources: dict[str, str | None] = {}
    out: list[tuple[CollectedClaim, bool | None]] = []
    missing: list[CollectedClaim] = []
    for claim in collected:
        if claim.document not in sources:
            try:
                path = workspace.resolve_within(Path(claim.document))
                sources[claim.document] = path.read_text(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                sources[claim.document] = None
        text = sources[claim.document]
        if text is None:
            missing.append(claim)
            out.append((claim, None))
            continue
        out.append((claim, check_claim(Claim(claim=claim.claim, quote=claim.quote), text).found))
    return out, missing
