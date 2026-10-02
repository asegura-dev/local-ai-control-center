"""Audit: an append-only record of what LACC did.

Records are JSON Lines inside the workspace, resolved through the workspace
boundary (ADR-006). Detail follows the configured `audit_level`: metadata always,
prompt and completion content only under `full`. When a record cannot be written,
`audit_failure_policy` decides whether execution stops or proceeds unrecorded.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from local_ai_control_center.core.config import Config
from local_ai_control_center.core.run import new_run_id
from local_ai_control_center.core.workspace import Workspace

if sys.platform == "win32":
    import msvcrt

    def _lock(descriptor: int) -> bool:
        """Try once to take the lock file's first byte. True when it was taken."""
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    def _unlock(descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(descriptor: int) -> bool:
        """Try once to take the lock file. True when it was taken."""
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _unlock(descriptor: int) -> None:
        fcntl.flock(descriptor, fcntl.LOCK_UN)


EventKind = Literal[
    "run_started",
    "run_finished",
    "run_refused",
    "confirmation_declined",
    "permission_granted",
    "permission_denied",
    "files_read",
    "read_in_passes",
    "passages_selected",
    "document_converted",
    "revision_written",
    "revision_declined",
    "ingestion_failed",
    "read_failed",
    "prompt_measured",
    "prompt_too_large",
    "provider_called",
    "quotations_checked",
    "prompt_was_truncated",
    "ceiling_underestimated",
    "answer_truncated",
    "fence_markers_removed",
    "instruction_shapes_seen",
    "standing_context_used",
    "readings_judged",
    "notification_sent",
    "notification_failed",
    "registry_asked",
    "texts_embedded",
    "file_written",
    "run_failed",
    "edits_proposed",
]
"""The closed set of events recorded today. It grows as real events appear.

`registry_asked`, `texts_embedded`, `file_written` and `run_failed` arrived with ADR-107, when
`review`, `resolve`, `identify` and `coverage` began to record what they reach and what they
write. `edits_proposed` arrived with ADR-125: what `repeats --propose` asked of a model."""

GENESIS_DIGEST = "0" * 64
"""What the first record folds in, since there is no record before it."""


def digest_of(text: str) -> str:
    """Return the SHA-256 of ``text``, as hex.

    A digest identifies without exposing: it cannot be read back into the thing it
    describes, and it is exactly enough to say whether two things are the same one
    (ADR-023).
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_of_file(path: Path) -> str | None:
    """Return the SHA-256 of the file at ``path``, or ``None`` if it cannot be read.

    Unreadable means unknown. A record that says nothing about a file is honest; one
    that says the wrong thing is not.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


AUDIT_FILENAME = "audit.jsonl"
"""Default log filename inside the workspace."""


class AuditWriteError(Exception):
    """Raised when a record cannot be written and the policy is to abort."""


class AuditEvent(BaseModel):
    """A single audited event.

    Frozen: a record is written once and never revised.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: str
    run_id: str
    kind: EventKind
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)
    previous: str = GENESIS_DIGEST
    """Digest of the record before this one, or the genesis value for the first."""

    digest: str = ""
    """This record's own digest, over its content and the one before it (ADR-023).

    Filled when the record is written. Any later edit changes it, and every record after
    it, so silent tampering becomes detectable and locatable rather than invisible.
    """

    def chained(self, previous: str) -> AuditEvent:
        """Return this record linked to ``previous``, with its own digest computed."""
        linked = self.model_copy(update={"previous": previous, "digest": ""})
        return linked.model_copy(update={"digest": digest_of(linked.model_dump_json())})


class AuditLog:
    """Appends audit events to a JSON Lines file inside a workspace."""

    def __init__(
        self, workspace: Workspace, config: Config, filename: str = AUDIT_FILENAME
    ) -> None:
        """Bind the log to a workspace and configuration.

        The path is resolved through the workspace boundary, so the audit trail is
        contained like anything else LACC touches.
        """
        self._path = workspace.resolve_within(filename)
        self._root = workspace.root
        self._config = config

    @property
    def path(self) -> Path:
        """The resolved path of the log file."""
        return self._path

    def opened(self, action: str) -> str:
        """Open a run for a command that does not go through the cycle, and give its id.

        The same first record every run has, `run_started` naming the action, so the Audit
        section reads these runs the way it reads the rest (ADR-107).
        """
        run_id = new_run_id()
        self.record(run_id, "run_started", f"Starting {action}", {"action": action})
        return run_id

    def wrote(self, run_id: str, action: str, written: Path) -> None:
        """Record a file a command left: where it is in the workspace, and its digest."""
        try:
            where = written.relative_to(self._root).as_posix()
        except ValueError:
            where = written.as_posix()
        self.record(
            run_id,
            "file_written",
            f"Wrote {written.name}",
            {"action": action, "path": where, "sha256": digest_of_file(written)},
        )

    def asked(
        self, run_id: str, action: str, registry: str, sent: Sequence[str], identified: bool
    ) -> None:
        """Record what went to a registry, when anything did.

        The DOIs under `dois`, which only `full` keeps; the registry and how many went, always.
        Whether a contact address went with them, and never the address (ADR-107).
        """
        if not sent:
            return
        self.record(
            run_id,
            "registry_asked",
            f"Asked {registry} about {len(sent)} DOIs",
            {
                "action": action,
                "registry": registry,
                "asked": len(sent),
                "identified": identified,
                "dois": list(sent),
            },
        )

    def embedded(
        self,
        run_id: str,
        action: str,
        model: str,
        reaches: str,
        sent: dict[str, int],
        question: str = "",
    ) -> None:
        """Record what went to an embedding model: which model, where, how many of what.

        A question that went with them is content: its digest always, its words under `full`
        alone, the rule every question follows (ADR-105). Counts are plural - `questions`,
        `quotations` - so none can share a key with the question itself, which the filter
        would drop along with it.
        """
        clash = {"question", "question_sha256"} & set(sent)
        if clash:
            raise ValueError(f"{sorted(clash)} name the question itself, not a count of texts")
        total = sum(sent.values())
        detail: dict[str, Any] = {
            "action": action,
            "model": model,
            "reaches": reaches,
            "texts": total,
            **sent,
        }
        if question:
            detail["question"] = question
            detail["question_sha256"] = digest_of(question)
        self.record(run_id, "texts_embedded", f"Embedded {total} texts with {model}", detail)

    def ranked(
        self,
        before: str,
        model: str,
        reaches: str,
        sent: dict[str, int],
        question: str,
        failed: str = "",
    ) -> None:
        """Record a ranking by meaning as a run of its own, and close it (ADR-108).

        Its own run because it had its own agreement, and because the question it was for may
        never be sent: a Prepare nobody followed with Send is still a question that went to the
        engine. ``before`` is what it ranked for.
        """
        run_id = new_run_id()
        action = "rank_by_meaning"
        self.record(
            run_id,
            "run_started",
            f"Starting {action} for {before}",
            {"action": action, "for": before},
        )
        if failed:
            self.record(
                run_id,
                "run_failed",
                "The embedding model did not answer",
                {"action": action, "error": failed},
            )
            return
        self.embedded(run_id, action, model, reaches, sent, question)
        self.record(run_id, "run_finished", f"Finished {action}", {"action": action})

    def record(
        self,
        run_id: str,
        kind: EventKind,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent | None:
        """Append an event to the log.

        Returns the written event, or ``None`` when writing failed and the policy
        allows continuing. Raises :class:`AuditWriteError` when the policy is to
        abort.
        """
        kept = self._filter_detail(detail or {})
        try:
            # The head is read in the same turn as the append, never remembered: a log that
            # remembered it chained to its own last record while another log - the window's
            # Prepare, a terminal - had written since, and broke the chain (ADR-109).
            with _turn(self._path, writing=True):
                # And the time is taken in the turn too. Taken before it, a writer that waited
                # stamped an earlier time than the record it came after: 48 of 607 steps went
                # backwards with four writers (ADR-116).
                pending = AuditEvent(
                    timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    run_id=run_id,
                    kind=kind,
                    message=message,
                    detail=kept,
                )
                previous = _last_digest(self._path)
                event = pending.chained(previous)
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(event.model_dump_json() + "\n")
                self._anchor(previous, event.digest)
        except OSError as error:
            if self._config.audit_failure_policy == "abort":
                raise AuditWriteError(f"Could not write audit record: {error}") from error
            return None
        return event

    def _anchor(self, previous: str, head: str) -> None:
        """Record how long the trail is now, beside it.

        Best effort and deliberately not fatal: the record itself is already written, and
        failing a run because a note about it could not be written would trade the thing for
        the note about the thing.

        Beside the trail rather than outside the workspace, because nothing outside the
        workspace is touched. That places it under the same permissions as the trail, which
        is why this guards against loss and not against a person (ADR-049).

        **Counted from itself when it describes the record just before**, which it always
        does once writers take turns: one more than it said. It recounted the whole trail on
        every record - 164 of the 199 milliseconds a record took on the thesis's trail of
        8.6 MB - and still recounts when it is missing or says something else (ADR-109).
        """
        beside = self._path.with_suffix(ANCHOR_SUFFIX)
        try:
            said = json.loads(beside.read_text(encoding="utf-8"))
            known = int(said["records"]) if said.get("head") == previous else None
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            known = None
        try:
            if known is None:
                text = self._path.read_text(encoding="utf-8")
                records = sum(1 for line in text.splitlines() if line)
            else:
                records = known + 1
            beside.write_text(
                json.dumps({"records": records, "head": head}) + chr(10), encoding="utf-8"
            )
        except OSError:
            return

    def _filter_detail(self, detail: dict[str, Any]) -> dict[str, Any]:
        """Drop content fields unless the configured level is ``full``.

        Prompts and completions can contain whatever the user was working on, so
        they are recorded only when explicitly opted into.
        """
        if self._config.audit_level == "full":
            return dict(detail)
        return {key: value for key, value in detail.items() if key not in _CONTENT_KEYS}


_FIRST_TAIL = 64 * 1024
"""Bytes read from the end of the trail first, when looking for its last record."""


def _last_digest(path: Path) -> str:
    """The digest of the last readable record in ``path``, or genesis when there is none.

    Read from the end, because this runs before every record and the thesis's trail is
    megabytes long. A record under `full` can be a hundred kilobytes, so the read widens until
    it holds a whole line; the first line of a read that starts mid-file may be cut, and is
    never taken for a record.
    """
    try:
        with path.open("rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            span = _FIRST_TAIL
            while True:
                start = max(0, size - span)
                handle.seek(start)
                lines = handle.read(size - start).split(b"\n")
                for line in reversed(lines if start == 0 else lines[1:]):
                    if not line.strip():
                        continue
                    try:
                        recorded = AuditEvent.model_validate_json(line)
                    except ValueError:
                        continue
                    return recorded.digest or GENESIS_DIGEST
                if start == 0:
                    return GENESIS_DIGEST
                span *= 4
    except OSError:
        return GENESIS_DIGEST


LOCK_SUFFIX = ".lock"
"""The file beside the trail that writers take turns at: `audit.lock` next to `audit.jsonl`."""

_WAIT_SECONDS = 10.0
"""How long a writer waits for its turn before its record fails like any failed write."""

_TURNS: dict[str, threading.Lock] = {}
_TURNS_GUARD = threading.Lock()


def _turn_among_threads(path: Path) -> threading.Lock:
    """The lock this program's own threads take turns at, one per trail."""
    with _TURNS_GUARD:
        return _TURNS.setdefault(str(path), threading.Lock())


def _take(path: Path, writing: bool) -> int | None:
    """Take this trail's turn among programs, and give the lock's descriptor.

    ``None`` when a reader could not have it: there is no lock file - nobody has written here
    since writers began taking turns, and a reader must not create one - or another program
    kept it past the wait. A writer that cannot have it raises, as any failed write does.
    """
    flags = os.O_RDWR | (os.O_CREAT if writing else 0)
    try:
        descriptor = os.open(path.with_suffix(LOCK_SUFFIX), flags)
    except OSError:
        if writing:
            raise
        return None
    deadline = time.monotonic() + _WAIT_SECONDS
    while not _lock(descriptor):
        if time.monotonic() > deadline:
            os.close(descriptor)
            if writing:
                raise OSError(
                    f"{path.name} was held by another writer for {_WAIT_SECONDS:.0f} seconds"
                )
            return None
        time.sleep(0.01)
    return descriptor


@contextmanager
def _turn(path: Path, writing: bool) -> Iterator[None]:
    """This trail's turn: first among this program's threads, then among programs (ADR-109).

    A writer reads the head and appends inside it, so no two writers chain to the same record.
    A reader takes it too, so it never reads a record half written - which would look exactly
    like a trail that cannot be read past that point - and reads anyway when it cannot have it:
    a `verify` that gave up would be a `verify` that cannot answer.
    """
    with _turn_among_threads(path):
        descriptor = _take(path, writing)
        try:
            yield
        finally:
            if descriptor is not None:
                try:
                    _unlock(descriptor)
                finally:
                    os.close(descriptor)


class ChainCheck(BaseModel):
    """What walking an audit trail's hash chain found.

    ``intact`` is True only when every record that carries a digest links correctly to
    the one before it. Records written before the chain existed are counted as
    unverifiable rather than broken: a trail cannot vouch for what predates the
    mechanism, and saying so is honest where an alarm would not be (ADR-023).
    """

    model_config = ConfigDict(frozen=True)

    intact: bool
    records: int
    first_seen: str = ""
    last_seen: str = ""
    """When the trail starts and ends.

    The only signal a person has against records removed from the end, which no hash chain
    can detect from the file alone: a trail whose last record predates your last run is a
    trail that lost something (ADR-043).
    """

    unverifiable: int = 0
    broken_at: int | None = None
    unreadable_at: int | None = None


class Walked(BaseModel):
    """A trail read once: what its chain says, and every record in it that could be read."""

    model_config = ConfigDict(frozen=True)

    chain: ChainCheck
    events: tuple[AuditEvent, ...] = ()
    vouched: tuple[bool, ...] = ()
    """For each record kept, whether the chain vouches for it.

    False from the first break or unreadable line on, and for a record written before the
    chain existed. Records past a break are kept rather than dropped: they are shown, marked,
    because hiding them would hide the evidence (ADR-104).
    """

    exists: bool = True


def walk(path: Path) -> Walked:
    """Read the trail at ``path`` once: check each link, and keep every record that parses.

    Detects modification by anything that does not know the file is a chain. It does not
    detect a deliberate rewrite: whatever can write the file can recompute every digest from
    the point it changed. That limit is the claim's boundary, not a gap in it (ADR-023).

    It replaced `verify_chain`, which walked the chain and kept nothing. The window needs the
    records too, and walking twice - once to vouch for them, once to show them - paid twice for
    the slowest thing here, on a file that only grows (ADR-104). The chain reports exactly what
    it reported before: the first unreadable line or the first break, whichever comes first.
    """
    try:
        with _turn(path, writing=False):
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    except OSError:
        return Walked(
            chain=ChainCheck(intact=False, records=0, unreadable_at=1), exists=path.exists()
        )

    previous = GENESIS_DIGEST
    unverifiable = 0
    stamps: list[str] = []
    events: list[AuditEvent] = []
    vouched: list[bool] = []
    unreadable_at: int | None = None
    broken_at: int | None = None
    for position, line in enumerate(lines, start=1):
        try:
            recorded = AuditEvent.model_validate_json(line)
        except ValueError:
            if unreadable_at is None and broken_at is None:
                unreadable_at = position
            continue
        stamps.append(recorded.timestamp)
        events.append(recorded)
        if unreadable_at is not None or broken_at is not None:
            vouched.append(False)
            continue
        if not recorded.digest:
            unverifiable += 1
            vouched.append(False)
            continue
        expected = recorded.model_copy(update={"digest": ""})
        recomputed = digest_of(expected.model_dump_json())
        if recorded.previous != previous or recomputed != recorded.digest:
            broken_at = position
            vouched.append(False)
            continue
        previous = recorded.digest
        vouched.append(True)

    if unreadable_at is not None:
        chain = ChainCheck(intact=False, records=len(lines), unreadable_at=unreadable_at)
    elif broken_at is not None:
        chain = ChainCheck(
            intact=False, records=len(lines), unverifiable=unverifiable, broken_at=broken_at
        )
    else:
        chain = ChainCheck(
            intact=True,
            records=len(lines),
            unverifiable=unverifiable,
            first_seen=stamps[0] if stamps else "",
            last_seen=stamps[-1] if stamps else "",
        )
    return Walked(chain=chain, events=tuple(events), vouched=tuple(vouched))


_CONTENT_KEYS = frozenset({"prompt", "completion", "question", "dois"})
"""Detail keys treated as user content, omitted unless the level is ``full``.

`question` joined on 27-sep: a question to a corpus was kept word for word under the default
level, because nothing had told the filter it was content (ADR-105). Its digest is recorded
beside it, which says which question without saying what it was.

`dois` joined on 28-sep, by the choice of the person whose trail it is: a DOI is public, and
the list of them sent to a registry is a bibliography, which says what somebody is reading.
The count is always kept (ADR-107).
"""


ANCHOR_SUFFIX = ".anchor"
"""What the sidecar beside the trail is called: `audit.anchor` next to `audit.jsonl`."""


class AnchorCheck(BaseModel):
    """What the sidecar says about a trail, compared with the trail itself.

    Three outcomes rather than two, because "shorter than it was" and "the last record
    changed" are different events with different causes, and a single "broken" would send
    somebody looking for the wrong thing (ADR-049).
    """

    model_config = ConfigDict(frozen=True)

    present: bool = False
    """Whether there is an anchor at all. Trails written before this have none."""

    agrees: bool = False
    expected_records: int = 0
    found_records: int = 0
    head_changed: bool = False
    head: str = ""
    """The digest the trail actually ends on, for a caller that wants to carry it somewhere."""

    @property
    def lost(self) -> int:
        """How many records the trail is short of what the anchor remembers."""
        return max(0, self.expected_records - self.found_records)


def check_anchor(path: Path) -> AnchorCheck:
    """Compare a trail against the sidecar beside it.

    A missing sidecar is reported as absent rather than as a failure: every trail written
    before this decision has none, and treating an old trail as tampered with would be an
    alarm about this project's own history.
    """
    anchor = path.with_suffix(ANCHOR_SUFFIX)
    # The anchor and the trail read in one turn, so a record written between the two reads
    # cannot make them disagree (ADR-109).
    with _turn(path, writing=False):
        try:
            remembered = json.loads(anchor.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return AnchorCheck()
        try:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        except OSError:
            lines = []
        actual_head = _last_digest(path)

    expected = int(remembered.get("records", 0))
    head = str(remembered.get("head", ""))
    return AnchorCheck(
        present=True,
        agrees=len(lines) == expected and actual_head == head,
        expected_records=expected,
        found_records=len(lines),
        head_changed=len(lines) == expected and actual_head != head,
        head=actual_head,
    )
