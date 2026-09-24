"""What is true about a workspace right now, for the line along the bottom (ADR-077).

Two kinds of fact, and the difference between them is the decision this module exists for.

**What is on disk** - how many documents, how many corpora, how many quotations in the
largest, what the configuration declares - costs a directory listing and is always shown.

**Whether the engine answers** costs a request to another machine. It is **not** taken when
the window opens. A window that pings on its own is a window that talks to the network
because somebody looked at it, and this project's first rule is that reaching anywhere is
deliberate. The bar says what the configuration *allows* until a person asks, and then it
says what happened.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.config import Config
from local_ai_control_center.core.corpus import parse_corpus
from local_ai_control_center.core.kinds import kind_of


class EngineSeen(BaseModel):
    """What a check of the engine found, as data rather than as a sentence.

    A contract of this project's own, so a view never handles the adapter's type and the
    layer rule holds (ADR-066).
    """

    model_config = ConfigDict(frozen=True)

    asked: bool = False
    """False until somebody asks. The difference between "not reached" and "not tried"."""

    reached: bool = False
    answered: bool = False
    models: int = 0
    held: tuple[str, ...] = ()
    """What the engine says it holds. The check has returned these since ADR-077 and this
    contract kept only the count, so the window could say `4 models` and not which."""

    host: str = ""
    wanted: str = ""
    """The model the configuration names, so a listing can say which of them it is."""

    seconds: float = 0.0
    detail: str = ""

    @property
    def has_it(self) -> bool:
        """Whether the engine holds the model the configuration names."""
        return bool(self.wanted) and self.wanted in self.held

    @property
    def said(self) -> str:
        """One phrase for the bar."""
        if not self.asked:
            return "not checked"
        if not self.reached:
            return "unreachable"
        if not self.answered:
            return f"reached, {self.models} models, no answer"
        return f"answered in {self.seconds:g}s"


class Status(BaseModel):
    """What the bottom of the window says, taken from files alone."""

    model_config = ConfigDict(frozen=True)

    workspace: str
    documents: int = 0
    corpora: int = 0
    quotations: int = 0
    """In the largest corpus found, which is the one being worked from."""

    model: str = ""
    engine: str = ""
    network: bool = False
    registry: bool = False
    embeddings: bool = False

    @property
    def material(self) -> str:
        """The left half: what there is to work with."""
        if not self.corpora:
            return f"{self.documents} documents   no corpus yet"
        return f"{self.documents} documents   {self.quotations:,} quotations"

    @property
    def reach(self) -> str:
        """The right half: what this configuration is allowed to reach, before any check."""
        if not self.network:
            return "network off - nothing leaves this machine"
        parts = [self.engine or "local engine"]
        if self.registry:
            parts.append("registry allowed")
        return "   ".join(parts)


def status_of(workspace: Path, config: Config, context_file: str = "") -> Status:
    """Read the workspace and the configuration. No request is made to anything.

    What each file is comes from `core.kinds`, which is the one place that decides it. This
    counted every Markdown file as a document and said **61** where the same workspace held
    28 - invisible until the left half of this bar was drawn for the first time (ADR-090,
    ADR-092).
    """
    documents = corpora = quotations = 0
    if workspace.is_dir():
        for path in workspace.glob("*.md"):
            if path.name.startswith(".") or (context_file and path.name == context_file):
                continue
            kind = kind_of(path)
            if kind == "document":
                documents += 1
            elif kind == "corpus":
                corpora += 1
                # The largest is the one being worked from; a backup beside it is smaller.
                held = len(parse_corpus(path.read_text(encoding="utf-8", errors="replace")))
                quotations = max(quotations, held)
    return Status(
        workspace=str(workspace),
        documents=documents,
        corpora=corpora,
        quotations=quotations,
        model=config.model,
        engine=config.engine_host,
        network=config.network_access,
        registry=bool(config.registry_url),
        embeddings=bool(config.embedding_model),
    )
