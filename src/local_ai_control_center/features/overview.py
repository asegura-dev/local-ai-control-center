"""What can be known about a workspace without running anything (ADR-069).

Every answer here comes from reading files: what configurations exist and what they declare,
what documents are in the workspace and roughly how large they are, and what a corpus
contains. No model is called, nothing is written, and nothing leaves the machine.

It lives in a slice rather than in the window because each of these is a **decision** - which
files count as a corpus, what "how big" means, which settings are worth showing - and a view
that made those would be a view containing logic (ADR-066).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.budget import estimate_tokens
from local_ai_control_center.core.config import Config, load_config
from local_ai_control_center.core.corpus import parse_corpus
from local_ai_control_center.core.kinds import kind_of

FINDINGS = ".findings.json"
"""What a review leaves beside its report. Recognised by name because it is not Markdown,
and `core.kinds` reads text rather than filenames (ADR-090)."""


class DocumentSeen(BaseModel):
    """One file in the workspace, as much as can be said without opening a model."""

    model_config = ConfigDict(frozen=True)

    path: Path
    name: str
    bytes_on_disk: int
    tokens: int
    kind: str
    """`corpus`, `review`, `document` or `other` - what the file announces itself to be."""


class CorpusSeen(BaseModel):
    """What a corpus holds, counted rather than estimated."""

    model_config = ConfigDict(frozen=True)

    path: Path
    quotations: int = 0
    with_a_page: int = 0
    refused: int = 0
    documents: tuple[tuple[str, int], ...] = ()
    """Each source document and how many quotations came from it, most first."""


class Setting(BaseModel):
    """One line of a configuration, as a person should read it."""

    model_config = ConfigDict(frozen=True)

    label: str
    value: str
    note: str = ""


def configurations_in(folder: Path) -> tuple[Path, ...]:
    """Every configuration file in ``folder``, by name."""
    if not folder.is_dir():
        return ()
    return tuple(sorted(p for p in folder.glob("*.yaml") if p.is_file()))


def settings_shown(config: Config) -> tuple[Setting, ...]:
    """What a configuration declares, in the order somebody choosing one would ask.

    The model first, because that is the question. The two switches that let anything leave
    the machine last, because they are the ones worth noticing.
    """
    window = f"{config.context_tokens:,} tokens" if config.context_tokens else "not declared"
    return (
        Setting(label="Model", value=config.model or "the mock provider"),
        Setting(
            label="Embeddings",
            value=config.embedding_model or "off",
            note="" if config.embedding_model else "ranking falls back to shared words",
        ),
        Setting(label="Engine", value=config.engine_host or "this machine"),
        Setting(label="Context window", value=window),
        Setting(label="Workspace", value=str(config.workspace_root)),
        Setting(label="Answers in", value=config.output_language),
        Setting(label="Audit", value=config.audit_level),
        Setting(
            label="Network",
            value="allowed" if config.network_access else "off",
            note="the ceiling: with this off, nothing reaches anywhere",
        ),
        Setting(
            label="Registry",
            value=config.registry_url or "none",
            note="" if config.registry_url else "no DOI is ever resolved",
        ),
    )


def settings_of(path: Path) -> tuple[Setting, ...]:
    """Read one configuration and describe it, or say it could not be read.

    A configuration that fails validation is a thing a person needs to see named, not a
    window that shows nothing.
    """
    try:
        return settings_shown(load_config(path))
    except (OSError, ValueError) as error:
        return (Setting(label="Unreadable", value=str(error).split(chr(10))[0]),)


def documents_in(workspace: Path, context_file: str = "") -> tuple[DocumentSeen, ...]:
    """Everything in the workspace worth listing, largest first.

    Token counts are the same estimate the rest of the project budgets with, so a number
    here and a number in a refusal mean the same thing.

    What each file *is* comes from `core.kinds`, which is the one place that decides it. This
    module used to decide it again, and the two had drifted nine files apart by the time
    anybody counted them (ADR-090).

    ``context_file`` is the standing context a configuration names. It is a document, and
    what makes it not one to quote from is a setting - so it is excluded here, by the caller
    who read that setting, rather than by a reader of text (ADR-082).
    """
    seen: list[DocumentSeen] = []
    for path in sorted(workspace.glob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if context_file and path.name == context_file:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        # A review's findings sit beside its report as JSON, which is not text this reader
        # looks at - so it is recognised here, by name, where the listing is assembled.
        kind = "review" if path.name.endswith(FINDINGS) else kind_of(path)
        tokens = 0
        if path.suffix == ".md":
            # The estimate, not a tokeniser: the same arithmetic the window budget uses.
            tokens = estimate_tokens(path.read_text(encoding="utf-8", errors="replace"))
        seen.append(
            DocumentSeen(path=path, name=path.name, bytes_on_disk=size, tokens=tokens, kind=kind)
        )
    return tuple(sorted(seen, key=lambda d: -d.bytes_on_disk))


def corpus_seen(path: Path) -> CorpusSeen:
    """Count what a corpus holds, by reading it the way every other reader does.

    Counted, never estimated: the numbers a person plans with should be the numbers the
    parser sees, and this project has been wrong before by carrying a figure taken some
    other way (ADR-042).
    """
    try:
        claims = parse_corpus(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return CorpusSeen(path=path)
    per_document: dict[str, int] = {}
    for claim in claims:
        per_document[claim.document] = per_document.get(claim.document, 0) + 1
    return CorpusSeen(
        path=path,
        quotations=len(claims),
        with_a_page=sum(1 for c in claims if c.page),
        refused=sum(1 for c in claims if "NOT IN THE DOCUMENT" in c.recorded_verdict),
        documents=tuple(sorted(per_document.items(), key=lambda pair: -pair[1])),
    )
