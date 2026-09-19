"""Remembering vectors beside the corpus they were made from (ADR-061).

**This is a cache, not a document.** The corpus stays Markdown a person can read; nobody
reads six hundred thousand floats. So the file is compact and regenerable rather than
inspectable, and losing it costs the time to make it again and nothing else.

That time is what justifies the file at all, measured on the real corpus: embedding 654
quotations takes 48 seconds against a warm model and 91 against a cold one, while loading
them back takes 72 milliseconds. The format saves another second over JSON and eighty per
cent of the size, which is not why it exists - the 48 seconds is.

A vector is keyed by the digest of the text it came from, so a corpus that gained two
documents embeds two documents' worth and reuses the rest.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

SUFFIX = ".vectors"
"""What the cache is called, beside the corpus it belongs to."""

_HEADER = "header"


def key_for(text: str) -> str:
    """The digest a vector is stored under: the text it was made from."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def remembered(path: Path, embedder: str) -> dict[str, tuple[float, ...]]:
    """Vectors already computed for ``embedder``, by text digest.

    Returns nothing rather than raising for a missing, unreadable, truncated or
    foreign file. **A cache that fails loudly is worse than one that fails quietly**:
    every one of those cases is answered correctly by computing again, and the only thing
    an exception would add is a run that stops for a file the run could rebuild.

    The one case that must not be quiet is a file made by a **different model**. Vectors
    from one embedding space mean nothing in another, and comparing them returns confident
    nonsense rather than an error - so the embedder's name is checked, and a mismatch is
    treated as no cache at all.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return {}

    split = raw.find(b"\n")
    if split < 0:
        return {}
    try:
        header = json.loads(raw[:split].decode("utf-8"))
        width = int(header["dim"])
        keys = list(header["keys"])
    except (ValueError, KeyError, TypeError):
        return {}
    if header.get("embedder") != embedder or width <= 0:
        return {}

    body = raw[split + 1 :]
    if len(body) != len(keys) * width * 4:
        return {}
    return {
        key: struct.unpack_from(f"<{width}f", body, index * width * 4)
        for index, key in enumerate(keys)
    }


def remember(path: Path, embedder: str, vectors: dict[str, tuple[float, ...]]) -> None:
    """Write ``vectors`` beside the corpus, replacing whatever was there.

    Replaced rather than appended: the file describes one embedder and one set of texts,
    and a half-written one is rebuilt in under a minute. Failure to write is swallowed for
    the same reason `remembered` swallows a failure to read - the answer the run produced
    is already correct, and a cache is not worth ending it over.
    """
    if not vectors:
        return
    keys = list(vectors)
    width = len(vectors[keys[0]])
    header = json.dumps({"embedder": embedder, "dim": width, "keys": keys})
    body = b"".join(struct.pack(f"<{width}f", *vectors[key]) for key in keys)
    try:
        path.write_bytes(header.encode("utf-8") + b"\n" + body)
    except OSError:
        return
