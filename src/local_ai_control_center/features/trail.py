"""What LACC did in a workspace, as runs a person can read (ADR-104).

Pure. Records in, runs out: grouped by the run they belong to, newest first, each with how it
ended as its own records say. And the sentences that say whether the trail can be trusted,
which `lacc verify` prints and the window draws - one writer for both, because two writers
of the same sentence is the drift ADR-065 measured.

Records are read through the shape they have rather than the class that writes them, so this
slice reaches only for what a slice may (ADR-066). A test writes records with the real log and
reads them back here, which is what keeps the writer and this reader in agreement.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, tzinfo
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

Tone = Literal["good", "warn", "bad", "plain", "quiet"]
"""How a sentence should look: held, worth a look, wrong, plain, or a note in passing."""

RUNS_SHOWN = 300
"""How many runs are listed, newest first. The heading gives the total."""

ANSWER_SHOWN = 4000
PROMPT_SHOWN = 1500
"""Characters of an answer and of a prompt shown before the rest is counted instead.

A single prompt in the thesis's trail is 91,000 characters. The digest beside it is the
whole of it for checking; this much is enough to recognise it."""

FACT_SHOWN = 300
"""Characters of any other recorded detail shown before it is cut."""

_CONTENT = (("completion", "answer", ANSWER_SHOWN), ("prompt", "prompt", PROMPT_SHOWN))
"""The detail keys that hold what was sent and said, what to call each, and how much to show."""

LIMITS = (
    "The chain catches a record edited, removed from the middle, or reordered. It does not "
    "catch records removed from the end - a shorter chain is still a valid chain - nor a "
    "deliberate rewrite, since whatever can write the file can recompute the digests. The "
    "anchor beside the trail catches loss, and sits under the same permissions as the trail, "
    "so it does not catch a person who wants it gone. If you keep your notifications, those "
    "are the only record of this that is not on this machine."
)
"""Two limits, and the one that was never stated is the easier attack (ADR-043)."""


class Recorded(Protocol):
    """One audit record, as far as this reads it."""

    @property
    def timestamp(self) -> str: ...
    @property
    def run_id(self) -> str: ...
    @property
    def kind(self) -> str: ...
    @property
    def message(self) -> str: ...
    @property
    def detail(self) -> dict[str, Any]: ...


class ChainLike(Protocol):
    """What walking a trail's chain found, as far as a sentence needs it."""

    @property
    def intact(self) -> bool: ...
    @property
    def records(self) -> int: ...
    @property
    def first_seen(self) -> str: ...
    @property
    def last_seen(self) -> str: ...
    @property
    def unverifiable(self) -> int: ...
    @property
    def broken_at(self) -> int | None: ...
    @property
    def unreadable_at(self) -> int | None: ...


class AnchorLike(Protocol):
    """What the anchor beside a trail says, as far as a sentence needs it."""

    @property
    def present(self) -> bool: ...
    @property
    def agrees(self) -> bool: ...
    @property
    def expected_records(self) -> int: ...
    @property
    def found_records(self) -> int: ...
    @property
    def head_changed(self) -> bool: ...
    @property
    def lost(self) -> int: ...


class Said(BaseModel):
    """One sentence about a trail: the part to stress, the rest, and how it should look."""

    model_config = ConfigDict(frozen=True)

    tone: Tone
    lead: str
    rest: str


def integrity_of(
    chain: ChainLike, anchor: AnchorLike, where: str, exists: bool = True
) -> tuple[Said, ...]:
    """Whether a trail can be trusted, in the sentences `lacc verify` has always printed.

    A trail that is unreadable or broken is described by that alone, as the command did. A
    workspace where nothing has been recorded has **no trail yet**, which the command used to
    call unreadable at record 1 (ADR-104).
    """
    if not exists:
        return (
            Said(tone="plain", lead="No trail yet.", rest=f"Nothing has been recorded in {where}."),
        )
    if chain.unreadable_at is not None:
        return (
            Said(
                tone="bad",
                lead="The trail cannot be read",
                rest=f"at record {chain.unreadable_at} ({where}).",
            ),
        )
    if not chain.intact:
        return (
            Said(
                tone="bad",
                lead="The trail has been altered.",
                rest=f"The chain first breaks at record {chain.broken_at} of {chain.records} in "
                f"{where}. Every record from there on is no longer vouched for by the ones before "
                "it.",
            ),
        )
    said = [
        Said(
            tone="good",
            lead="The trail holds.",
            rest=f"{chain.records} records in {where}, each linked to the one before it.",
        )
    ]
    if chain.first_seen:
        said.append(
            Said(tone="plain", lead="", rest=f"From {chain.first_seen} to {chain.last_seen}.")
        )
    if chain.unverifiable:
        said.append(
            Said(
                tone="warn",
                lead=f"{chain.unverifiable} of them predate the chain",
                rest="and cannot be vouched for either way.",
            )
        )
    said.append(_anchor_said(anchor))
    said.append(Said(tone="quiet", lead="", rest=LIMITS))
    return tuple(said)


def _anchor_said(anchor: AnchorLike) -> Said:
    """What the sidecar knows. Shorter and a changed last record are different events."""
    if not anchor.present:
        return Said(
            tone="quiet",
            lead="",
            rest="This trail has no anchor beside it - it was written before anchors existed. "
            "One will be written the next time something is recorded.",
        )
    if anchor.agrees:
        return Said(
            tone="good",
            lead="The anchor agrees:",
            rest=f"{anchor.expected_records} records, and the last one is the last one it saw.",
        )
    if anchor.lost:
        return Said(
            tone="bad",
            lead=f"{anchor.lost} records are missing from the end.",
            rest=f"The anchor remembers {anchor.expected_records} and the trail holds "
            f"{anchor.found_records}. A crashed write, a synchronisation conflict or a restored "
            "backup will do this; so will somebody removing them.",
        )
    if anchor.head_changed:
        return Said(
            tone="bad",
            lead="The last record is not the one the anchor saw.",
            rest="The count matches, so nothing was removed - the final record was replaced.",
        )
    return Said(
        tone="warn",
        lead="The trail is longer than the anchor remembers",
        rest=f"({anchor.found_records} against {anchor.expected_records}). Something wrote to "
        "it without going through LACC.",
    )


class Content(BaseModel):
    """What was sent or said, cut, with what was not shown counted and the whole digested."""

    model_config = ConfigDict(frozen=True)

    name: str
    shown: str
    left: int
    digest: str


class Step(BaseModel):
    """One record of a run, as it is read."""

    model_config = ConfigDict(frozen=True)

    at: str
    kind: str
    message: str
    facts: tuple[tuple[str, str], ...]
    content: tuple[Content, ...]
    vouched: bool


class Run(BaseModel):
    """Everything recorded under one run identifier."""

    model_config = ConfigDict(frozen=True)

    key: str
    day: str
    at: str
    what: str
    ending: str
    tone: Tone
    seconds: int | None
    vouched: bool
    """False if any of its records is past a break, or older than the chain."""

    unkept: bool
    """It called an engine and its records hold neither the prompt nor the answer.

    What a run recorded under `audit_level: standard` looks like, and worth saying: an empty
    panel would read as nothing having been sent.
    """

    steps: tuple[Step, ...]


class Trail(BaseModel):
    """A workspace's trail, read: whether it holds, and its runs, newest first."""

    model_config = ConfigDict(frozen=True)

    where: str
    records: int
    total_runs: int
    runs: tuple[Run, ...]
    integrity: tuple[Said, ...]


def _moment(stamp: str, zone: tzinfo | None) -> datetime | None:
    """A record's time, in the zone it is shown in. The trail keeps UTC."""
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).astimezone(zone)
    except ValueError:
        return None


def _shown(value: object) -> str:
    """A recorded detail as one line of text, cut where it is long."""
    written = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    flat = " ".join(written.split())
    return flat if len(flat) <= FACT_SHOWN else flat[: FACT_SHOWN - 1] + "…"


def _step(record: Recorded, vouched: bool, zone: tzinfo | None) -> Step:
    moment = _moment(record.timestamp, zone)
    detail = record.detail
    content = []
    for key, name, most in _CONTENT:
        text = detail.get(key)
        if isinstance(text, str):
            content.append(
                Content(
                    name=name,
                    shown=text[:most],
                    left=max(0, len(text) - most),
                    digest=str(detail.get(f"{key}_sha256", "")),
                )
            )
    hidden = {key for key, _, _ in _CONTENT}
    facts = tuple((key, _shown(value)) for key, value in detail.items() if key not in hidden)
    return Step(
        at=moment.strftime("%H:%M:%S") if moment else record.timestamp,
        kind=record.kind,
        message=record.message,
        facts=facts,
        content=tuple(content),
        vouched=vouched,
    )


_NOTIFYING = frozenset({"notification_sent", "notification_failed"})


def _ending(kinds: set[str]) -> tuple[str, Tone]:
    """How a run ended, from what it recorded and nothing else.

    A run with no end recorded is what a crash or a closed window leaves; nine of the 250 in
    the thesis's trail are that - seven skill runs, and two questions that sent a notification
    and recorded no finish - and they are worth seeing as such rather than as finished.
    """
    if kinds <= _NOTIFYING:
        return (
            ("notification sent", "plain")
            if "notification_sent" in kinds
            else (
                "notification failed",
                "warn",
            )
        )
    if "run_refused" in kinds:
        return "refused", "bad"
    if "prompt_too_large" in kinds:
        return "refused: the prompt did not fit", "warn"
    if "confirmation_declined" in kinds:
        return "declined", "plain"
    if kinds & {"read_failed", "ingestion_failed"}:
        return "failed", "bad"
    if "run_finished" in kinds:
        return "finished", "good"
    return "no end recorded", "warn"


def _what(records: Sequence[Recorded]) -> str:
    """What ran: the action its records name, or what its first record says."""
    for record in records:
        action = record.detail.get("action")
        if isinstance(action, str) and action:
            return action
    if all(record.kind in _NOTIFYING for record in records):
        return "notification"
    return records[0].message


def trail_of(
    records: Sequence[Recorded],
    integrity: tuple[Said, ...],
    where: str,
    vouched: Sequence[bool] | None = None,
    zone: tzinfo | None = None,
    most: int = RUNS_SHOWN,
) -> Trail:
    """The runs in a trail, newest first, at most ``most`` of them.

    ``vouched`` says, record by record, whether the chain vouches for it; absent, every record
    is. ``zone`` is where times are shown, the machine's own when absent.
    """
    grouped: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        grouped.setdefault(record.run_id, []).append(index)

    runs = []
    for key, indexes in grouped.items():
        mine = [records[i] for i in indexes]
        trusted = [vouched[i] if vouched is not None else True for i in indexes]
        first, last = _moment(mine[0].timestamp, zone), _moment(mine[-1].timestamp, zone)
        ending, tone = _ending({record.kind for record in mine})
        steps = tuple(
            _step(r, trusted_one, zone) for r, trusted_one in zip(mine, trusted, strict=True)
        )
        called = any(record.kind == "provider_called" for record in mine)
        runs.append(
            Run(
                key=key,
                day=first.strftime("%Y-%m-%d") if first else mine[0].timestamp[:10],
                at=first.strftime("%H:%M") if first else mine[0].timestamp,
                what=_what(mine),
                ending=ending,
                tone=tone,
                seconds=int((last - first).total_seconds()) if first and last else None,
                vouched=all(trusted),
                unkept=called and not any(step.content for step in steps),
                steps=steps,
            )
        )
    # The trail is appended to and never reordered, so the order runs began in is the order
    # of the file. Their timestamps tie within a second, and a sort on them did not.
    newest = runs[::-1]
    return Trail(
        where=where,
        records=len(records),
        total_runs=len(runs),
        runs=tuple(newest[:most]),
        integrity=integrity,
    )
