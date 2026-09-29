"""Where brought drafts live in a workspace, and how one is told from a file put there by hand.

A fact about files, like `core.kinds`: the command that brings a draft writes it here, and the
stages that say where the work stands read it here, and neither may reach the other's slice
(ADR-066, ADR-111).
"""

from __future__ import annotations

from pathlib import Path

DRAFTS = "drafts"
"""The folder inside the workspace where brought copies land.

Apart from the documents a library is read from: a draft is not a source to collect
quotations out of, and the stages that count the library look only at the workspace's top.
"""

BROUGHT = ".brought.json"
"""What sits beside a copy and says where it came from, when, and its digest."""


def drafts_in(workspace: Path) -> tuple[Path, ...]:
    """The copies brought into this workspace, by name.

    Only files that say where they came from: a file somebody put in the folder by hand is not
    one that was brought, and counting it would say something that did not happen.
    """
    folder = workspace / DRAFTS
    if not folder.is_dir():
        return ()
    return tuple(
        path
        for path in sorted(folder.iterdir())
        if path.is_file()
        and not path.name.endswith(BROUGHT)
        and path.with_name(path.name + BROUGHT).is_file()
    )
