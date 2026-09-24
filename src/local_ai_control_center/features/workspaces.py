"""Which workspace a configuration points at, and what it would cost to put one somewhere.

Everything LACC does happens inside one folder. Until this existed, which folder that was sat
at the bottom of the rail in the faintest colour in the palette, and the warnings about it
went to a terminal that somebody using the window never reads (ADR-093).

**Nothing here writes.** `intended` says what a new configuration would contain and
`as_yaml` renders it; putting it on disk is the caller's, so the preview and the act are
separable and the preview can be shown before anything happens.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.config import Config, load_config
from local_ai_control_center.core.workspace import repository_above, sync_folder_suspicion

CONFIGURATION_SUFFIX = ".yaml"


class Points(BaseModel):
    """One configuration, and where it says the work lives."""

    model_config = ConfigDict(frozen=True)

    name: str
    workspace: str = ""
    model: str = ""
    exists: bool = False
    unreadable: str = ""
    """Why it could not be read, when it could not. A broken file is named, never skipped."""


class Risk(BaseModel):
    """What is worth knowing about a folder before work is put in it."""

    model_config = ConfigDict(frozen=True)

    refused: str = ""
    """Why this cannot be used at all. A fact, never a guess."""

    warned: str = ""
    """What is probably true about it and cannot be confirmed."""

    advice: str = ""
    """What to do about the warning. A warning with no answer is one people click past."""

    @property
    def usable(self) -> bool:
        return not self.refused


def points_of(folder: Path) -> tuple[Points, ...]:
    """Every configuration in ``folder``, with the workspace it names.

    A configuration that cannot be read is returned with the reason rather than left out:
    a picker missing an entry looks like a file that was never written.
    """
    found: list[Points] = []
    for path in sorted(folder.glob(f"*{CONFIGURATION_SUFFIX}")):
        try:
            config = load_config(path)
        except Exception as error:  # noqa: BLE001 - a configuration may fail in any way
            found.append(Points(name=path.name, unreadable=str(error)))
            continue
        root = Path(config.workspace_root).expanduser()
        found.append(
            Points(
                name=path.name,
                workspace=str(root),
                model=config.model,
                exists=root.is_dir(),
            )
        )
    return tuple(found)


def risk_of(root: Path) -> Risk:
    """What using ``root`` as a workspace would mean.

    **A git working tree is refused**: private material one `git add -A` from being published
    is not a risk a sentence covers, and LACC cannot ask git whether the path is ignored
    because it does not run git (ADR-022).

    **A synchronising folder is warned about and allowed.** It is a guess from a name - a
    folder called `Dropbox` may sync nothing and one called `work` may sync everything - and
    refusing on a guess teaches people that this program's refusals are noise. The sentence
    says what it costs and leaves the choice where it belongs.
    """
    path = Path(root).expanduser()
    repository = repository_above(path)
    refused = ""
    if repository is not None:
        refused = (
            f"That is inside the git repository at {repository}. Everything LACC reads, "
            "converts and records there would be one 'git add -A' from being committed and "
            "pushed, and LACC cannot ask git whether the path is ignored. Choose a folder "
            "outside it."
        )
    warned = sync_folder_suspicion(path) or ""
    return Risk(refused=refused, warned=warned, advice=WHAT_TO_DO if warned else "")


_BREAK = chr(10)

WHAT_TO_DO = _BREAK.join(
    (
        "Working from more than one machine is a real reason to want this, and for a corpus "
        "of published papers most of what would travel is already public. Two things are "
        "not, and both have an answer:",
        "   ·  the audit log holds every prompt and every answer under audit_level: full, "
        "which this configuration uses. audit_level: standard is the default and records "
        "what ran without the content - one line, and most of the exposure goes.",
        "   ·  your standing context and any draft are yours alone. Keep them outside the "
        "workspace, or accept that they travel.",
        "And pause the synchroniser during a long collect or corpus: files held mid-write "
        "cost this project four failed installs in one day (ADR-084).",
    )
)
"""What to do about a synchronising folder, rather than only what is wrong with it.

A warning that only frightens is a warning people learn to click past. This one names the
setting that removes most of the exposure - one line - and the two files it cannot help with
(ADR-093).
"""


def intended(name: str, root: Path, like: Config) -> Points:
    """What a new configuration would be, taking its engine settings from ``like``.

    A new configuration without a model and an engine is a workspace that cannot do
    anything, so the one in force is copied. Nothing of the old workspace comes with it.
    """
    called = name.strip()
    if called and not called.endswith(CONFIGURATION_SUFFIX):
        called += CONFIGURATION_SUFFIX
    path = Path(root).expanduser()
    return Points(name=called, workspace=str(path), model=like.model, exists=path.is_dir())


def as_yaml(root: Path, like: Config) -> str:
    """The configuration file, as text, carrying over what makes an engine reachable.

    Written rather than dumped from the model: a dump would carry every default the contract
    has, and a configuration a person cannot read is one they cannot correct.
    """
    lines = [
        "# Written by lacc window. An ordinary configuration - edit it freely.",
        f"workspace_root: {Path(root).expanduser().as_posix()}",
        f"model: {like.model}",
    ]
    if like.context_tokens:
        lines.append(f"context_tokens: {like.context_tokens}")
    if like.embedding_model:
        lines.append(f"embedding_model: {like.embedding_model}")
    if like.network_access:
        lines += ["", "network_access: true", f"engine_host: {like.engine_host}"]
    if like.registry_url:
        lines.append(f"registry_url: {like.registry_url}")
    if like.audit_level == "full":
        # Carried over rather than quietly downgraded: a configuration that records less
        # than the one it was copied from would be a decision made on somebody's behalf.
        lines += ["", f"audit_level: {like.audit_level}"]
    return chr(10).join(lines) + chr(10)
