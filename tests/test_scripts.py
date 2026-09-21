"""The launchers, and the digests that say they are what was recorded (ADR-071).

A checksum nobody checks is decoration. This is what makes the file beside the scripts mean
something: the gate fails if a script changes without its digest changing, so the two cannot
drift apart the way two writers of the corpus format once did (ADR-065).

What it proves is narrow and worth stating: the files on this disk are the ones the digests
were taken over. It does not prove the digests are honest - whoever could edit a script could
edit the list beside it. What makes it worth something is that both are in Git, so
`git log scripts/` shows when either changed.
"""

from __future__ import annotations

import hashlib
import pathlib

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
SUMS = SCRIPTS / "SHA256SUMS.txt"


def _recorded() -> dict[str, str]:
    """What the file says each script should hash to."""
    found: dict[str, str] = {}
    for line in SUMS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        found[name.strip()] = digest.lower()
    return found


def test_every_script_matches_the_digest_recorded_for_it() -> None:
    """Edit a script without recording it and the gate fails, which is the whole point."""
    recorded = _recorded()
    for path in sorted(SCRIPTS.glob("*.bat")):
        assert path.name in recorded, (
            f"{path.name} has no digest in SHA256SUMS.txt. Regenerate it, and let the diff "
            "show what changed."
        )
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == recorded[path.name], (
            f"{path.name} is not what was recorded. Either the change is intended and the "
            "digest needs updating in the same commit, or it is not."
        )


def test_nothing_is_recorded_that_is_not_there() -> None:
    """A digest for a file that no longer exists describes nothing, like a stale figure."""
    present = {p.name for p in SCRIPTS.glob("*.bat")}
    assert set(_recorded()) <= present, (
        f"recorded but missing: {sorted(set(_recorded()) - present)}"
    )


def test_the_scripts_reach_nothing_and_download_nothing() -> None:
    """A launcher that fetched something would be a supply chain in a .bat file.

    Read as text rather than reasoned about: these are small enough that the check is exact.
    """
    forbidden = (
        "curl",
        "powershell -c iwr",
        "invoke-webrequest",
        "bitsadmin",
        "certutil -urlcache",
    )
    for path in sorted(SCRIPTS.glob("*.bat")):
        words = path.read_text(encoding="utf-8", errors="replace").lower()
        for banned in forbidden:
            assert banned not in words, f"{path.name} reaches the network with {banned!r}"


def test_the_engine_launcher_binds_to_loopback_by_default() -> None:
    """A default that listened on every interface would expose this machine silently."""
    words = (SCRIPTS / "serve-ollama.bat").read_text(encoding="utf-8")
    assert "OLLAMA_HOST=127.0.0.1:11434" in words
    assert "OLLAMA_KV_CACHE_TYPE=q8_0" in words
