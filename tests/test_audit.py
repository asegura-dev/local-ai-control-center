"""Tests for the audit log: record format, privacy levels, and failure policy."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from local_ai_control_center.core.config import Config
from local_ai_control_center.core.workspace import Workspace
from local_ai_control_center.system import audit
from local_ai_control_center.system.audit import (
    AUDIT_FILENAME,
    GENESIS_DIGEST,
    LOCK_SUFFIX,
    AuditLog,
    AuditWriteError,
    ChainCheck,
    check_anchor,
    digest_of,
    digest_of_file,
    walk,
)


def _log(tmp_path: Path, **config_kwargs: object) -> AuditLog:
    workspace = Workspace.ensure(tmp_path)
    config = Config(workspace_root=tmp_path, **config_kwargs)  # type: ignore[arg-type]
    return AuditLog(workspace, config)


def _lines(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def test_log_path_is_inside_the_workspace(tmp_path: Path) -> None:
    """The log resolves to a path within the workspace."""
    log = _log(tmp_path)
    assert log.path == (tmp_path / AUDIT_FILENAME).resolve()


def test_record_writes_one_json_line(tmp_path: Path) -> None:
    """A recorded event becomes exactly one JSON line."""
    log = _log(tmp_path)
    log.record("run-1", "run_started", "started")
    records = _lines(log.path)
    assert len(records) == 1
    assert records[0]["run_id"] == "run-1"
    assert records[0]["kind"] == "run_started"
    assert records[0]["message"] == "started"


def test_records_append_never_overwrite(tmp_path: Path) -> None:
    """Successive records accumulate; earlier lines are preserved."""
    log = _log(tmp_path)
    log.record("run-1", "run_started", "first")
    log.record("run-1", "run_finished", "second")
    records = _lines(log.path)
    assert [record["message"] for record in records] == ["first", "second"]


def test_record_returns_the_written_event(tmp_path: Path) -> None:
    """A successful record returns the event it wrote."""
    event = _log(tmp_path).record("run-1", "provider_called", "called")
    assert event is not None
    assert event.kind == "provider_called"


def test_timestamp_is_utc_formatted(tmp_path: Path) -> None:
    """The timestamp is an ISO-like UTC string."""
    event = _log(tmp_path).record("run-1", "run_started", "started")
    assert event is not None
    assert event.timestamp.endswith("Z")


def test_standard_level_omits_content(tmp_path: Path) -> None:
    """Under the default level, prompt and completion are not written."""
    log = _log(tmp_path)
    log.record(
        "run-1",
        "provider_called",
        "called",
        {"prompt": "secret question", "completion": "secret answer", "provider": "mock"},
    )
    detail = _lines(log.path)[0]["detail"]
    assert detail == {"provider": "mock"}


def test_a_judged_reading_leaves_its_digests_and_not_its_words(tmp_path: Path) -> None:
    """The judge records what it judged, and its reasoning follows the same content rule.

    The judge makes one engine call per claim and those calls are not `provider_called` -
    the adapter builds those prompts and the audit lives above it - so this record is what
    says a run judged anything at all. Losing which claim got which verdict would make a
    check that marks claims for a person useless the moment the terminal scrolls (ADR-059).

    The reasoning arrives as a list rather than a string, and the filter works on the key,
    so this pins that a shape change does not quietly start publishing content.
    """
    log = _log(tmp_path)
    rows = [
        {
            "quote_sha256": "a" * 64,
            "claim_sha256": "b" * 64,
            "asked_sha256": "c" * 64,
            "verdict": "neither",
        }
    ]
    log.record(
        "run-1",
        "readings_judged",
        "judged 1 reading",
        {
            "judge": "asking:mock",
            "judged": 1,
            "judged_readings": rows,
            "completion": [{"verdict": "neither", "why": "it names a different drug"}],
        },
    )
    detail = _lines(log.path)[0]["detail"]
    assert detail["judged_readings"] == rows, "which reading got which verdict survives"
    assert "completion" not in detail, "the judge's words are content, like any other"


def test_full_level_records_content(tmp_path: Path) -> None:
    """Under `full`, content is recorded as an explicit opt-in."""
    log = _log(tmp_path, audit_level="full")
    log.record(
        "run-1",
        "provider_called",
        "called",
        {"prompt": "the question", "completion": "the answer"},
    )
    detail = _lines(log.path)[0]["detail"]
    assert detail == {"prompt": "the question", "completion": "the answer"}


def test_standard_level_keeps_non_content_detail(tmp_path: Path) -> None:
    """Metadata survives the content filter."""
    log = _log(tmp_path)
    log.record("run-1", "permission_denied", "denied", {"missing": ["write_files"]})
    assert _lines(log.path)[0]["detail"] == {"missing": ["write_files"]}


def test_abort_policy_raises_on_write_failure(tmp_path: Path) -> None:
    """With the default policy, a write failure stops execution."""
    log = _log(tmp_path)
    log.path.mkdir()  # a directory where the file should be: writing will fail
    with pytest.raises(AuditWriteError):
        log.record("run-1", "run_started", "started")


def test_continue_policy_returns_none_on_write_failure(tmp_path: Path) -> None:
    """With `continue`, a write failure is swallowed and reported as None."""
    log = _log(tmp_path, audit_failure_policy="continue")
    log.path.mkdir()
    assert log.record("run-1", "run_started", "started") is None


def test_event_is_frozen(tmp_path: Path) -> None:
    """A written event cannot be revised."""
    event = _log(tmp_path).record("run-1", "run_started", "started")
    assert event is not None
    with pytest.raises(ValidationError):
        event.message = "tampered"  # type: ignore[misc]


def test_a_record_links_to_the_one_before_it(tmp_path: Path) -> None:
    """Each record folds in the previous digest, so the file is a chain and not a heap."""
    log = AuditLog(Workspace.ensure(tmp_path), Config(workspace_root=tmp_path))
    first = log.record("run-1", "run_started", "one")
    second = log.record("run-1", "run_finished", "two")
    assert first is not None and second is not None
    assert first.previous == GENESIS_DIGEST
    assert second.previous == first.digest
    assert second.digest and second.digest != first.digest


def test_an_intact_trail_verifies(tmp_path: Path) -> None:
    """The ordinary case: nothing touched it, and the walk says so."""
    log = AuditLog(Workspace.ensure(tmp_path), Config(workspace_root=tmp_path))
    for index in range(4):
        log.record("run-1", "run_started", f"record {index}")
    result = walk(log.path).chain
    assert result.intact is True
    assert result.records == 4
    assert result.broken_at is None


def test_an_edited_record_breaks_the_chain_where_it_was_edited(tmp_path: Path) -> None:
    """Silent tampering stops being silent, and the report says which record."""
    log = AuditLog(Workspace.ensure(tmp_path), Config(workspace_root=tmp_path))
    for index in range(4):
        log.record("run-1", "run_started", f"record {index}")

    lines = log.path.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace("record 1", "something else")
    log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = walk(log.path).chain
    assert result.intact is False
    assert result.broken_at == 2


def test_a_removed_record_breaks_the_chain(tmp_path: Path) -> None:
    """Deleting a line is the tampering people actually do, and it is caught too."""
    log = AuditLog(Workspace.ensure(tmp_path), Config(workspace_root=tmp_path))
    for index in range(4):
        log.record("run-1", "run_started", f"record {index}")

    lines = log.path.read_text(encoding="utf-8").splitlines()
    del lines[2]
    log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert walk(log.path).chain.intact is False


def test_the_chain_survives_the_log_being_reopened(tmp_path: Path) -> None:
    """A chain that restarted on every launch would be a chain in name only."""
    workspace, config = Workspace.ensure(tmp_path), Config(workspace_root=tmp_path)
    AuditLog(workspace, config).record("run-1", "run_started", "before")
    AuditLog(workspace, config).record("run-2", "run_started", "after")
    assert walk(tmp_path / "audit.jsonl").chain.intact is True


def test_records_written_before_the_chain_are_unverifiable_not_broken(tmp_path: Path) -> None:
    """A trail cannot vouch for what predates the mechanism, and does not pretend to."""
    path = tmp_path / "audit.jsonl"
    path.write_text(
        '{"timestamp":"2026-01-01T00:00:00Z","run_id":"old","kind":"run_started",'
        '"message":"from before","detail":{}}\n',
        encoding="utf-8",
    )
    result = walk(path).chain
    assert result.intact is True
    assert result.unverifiable == 1


def test_a_digest_identifies_without_exposing(tmp_path: Path) -> None:
    """The point of a digest: the same content hashes the same, and cannot be read back."""
    secret = tmp_path / "thesis.md"
    secret.write_text("A private finding.", encoding="utf-8")
    fingerprint = digest_of_file(secret)
    assert fingerprint == digest_of("A private finding.")
    assert "private" not in (fingerprint or "")

    secret.write_text("A different finding.", encoding="utf-8")
    assert digest_of_file(secret) != fingerprint


def test_an_unreadable_file_has_no_digest(tmp_path: Path) -> None:
    """Unreadable means unknown; a record saying the wrong thing is worse than silence."""
    assert digest_of_file(tmp_path / "absent.md") is None


def _tampered(tmp_path: Path, mutate: Callable[[list[str]], list[str]]) -> ChainCheck:
    """Write a short valid trail, alter it, and report what the check concluded."""
    workspace = Workspace.ensure(tmp_path)
    log = AuditLog(workspace, Config(workspace_root=tmp_path))
    for index in range(5):
        log.record("run", "run_started", f"event {index}")
    lines = log.path.read_text(encoding="utf-8").splitlines()
    log.path.write_text("\n".join(mutate(lines)) + "\n", encoding="utf-8")
    return walk(log.path).chain


def test_an_edited_record_breaks_the_chain(tmp_path: Path) -> None:
    """The case the chain was built for, and it holds."""

    def edit(lines: list[str]) -> list[str]:
        record = json.loads(lines[2])
        record["message"] = "something else"
        lines[2] = json.dumps(record)
        return lines

    assert _tampered(tmp_path, edit).intact is False


def test_a_record_removed_from_the_middle_breaks_the_chain(tmp_path: Path) -> None:
    """The link from the record after it no longer matches."""
    assert _tampered(tmp_path, lambda lines: lines[:2] + lines[3:]).intact is False


def test_reordering_records_breaks_the_chain(tmp_path: Path) -> None:
    """Order is part of what the chain vouches for."""
    reordered = _tampered(tmp_path, lambda lines: lines[:1] + [lines[2], lines[1]] + lines[3:])
    assert reordered.intact is False


def test_records_removed_from_the_end_are_not_detected(tmp_path: Path) -> None:
    """Documented because it is true, and because it is the easiest tampering of all.

    A shorter chain is still a valid chain: every remaining record still links correctly to
    the one before it. No hash chain can catch this from the file alone, and the message
    `lacc verify` prints says so rather than implying otherwise (ADR-043).
    """
    result = _tampered(tmp_path, lambda lines: lines[:-2])
    assert result.intact is True
    assert result.records == 3


def test_the_trail_reports_when_it_starts_and_ends(tmp_path: Path) -> None:
    """The only signal a person has against a truncated tail.

    A trail whose last record predates your last run has lost something, and that is
    checkable by a human without any external state.
    """
    result = _tampered(tmp_path, lambda lines: lines)
    assert result.first_seen
    assert result.last_seen
    assert result.first_seen <= result.last_seen


def test_a_question_is_content_and_is_kept_only_under_full(tmp_path: Path) -> None:
    """ADR-105: `question` is dropped below `full`, like the prompt and the answer."""
    detail = {"question": "what does the corpus say?", "question_sha256": "abc"}
    standard = _log(tmp_path / "s")
    full = _log(tmp_path / "f", audit_level="full")
    kept_standard = standard.record("r", "passages_selected", "Selected", detail)
    kept_full = full.record("r", "passages_selected", "Selected", detail)
    assert kept_standard is not None and kept_full is not None
    assert "question" not in kept_standard.detail
    assert kept_standard.detail["question_sha256"] == "abc"
    assert kept_full.detail["question"] == "what does the corpus say?"


# --- the commands outside the cycle (ADR-107) ----------------------------------------------


def test_the_dois_sent_are_counted_always_and_listed_only_under_full(tmp_path: Path) -> None:
    """A DOI is public; the list of them is a bibliography - the choice made on 28-sep."""
    sent = ("10.1000/one", "10.1000/two")
    standard = _log(tmp_path / "s")
    full = _log(tmp_path / "f", audit_level="full")
    standard.asked("r", "resolve", "https://api.crossref.org", sent, identified=False)
    full.asked("r", "resolve", "https://api.crossref.org", sent, identified=False)
    kept_standard = _lines(standard.path)[0]["detail"]
    kept_full = _lines(full.path)[0]["detail"]
    assert isinstance(kept_standard, dict) and isinstance(kept_full, dict)
    assert kept_standard["asked"] == 2
    assert "dois" not in kept_standard
    assert kept_full["dois"] == list(sent)


def test_a_contact_address_is_recorded_as_sent_and_never_written(tmp_path: Path) -> None:
    """The method is not handed the address at all: only whether one went."""
    log = _log(tmp_path, audit_level="full")
    log.asked("r", "resolve", "https://api.crossref.org", ("10.1000/one",), identified=True)
    detail = _lines(log.path)[0]["detail"]
    assert isinstance(detail, dict)
    assert detail["identified"] is True
    assert "@" not in log.path.read_text(encoding="utf-8")


def test_nothing_sent_to_a_registry_records_nothing(tmp_path: Path) -> None:
    """Every answer came from what was kept: nothing left, so there is nothing to say."""
    log = _log(tmp_path)
    log.asked("r", "resolve", "https://api.crossref.org", (), identified=False)
    assert not log.path.exists()


def test_a_run_outside_the_cycle_opens_the_way_every_run_does(tmp_path: Path) -> None:
    log = _log(tmp_path)
    run = log.opened("review")
    first = _lines(log.path)[0]
    assert first["run_id"] == run
    assert first["kind"] == "run_started"
    assert first["detail"] == {"action": "review"}


def test_a_file_written_is_recorded_by_where_it_is_and_its_digest(tmp_path: Path) -> None:
    log = _log(tmp_path)
    # Beside the log, which is resolved through the workspace the way a command's file is.
    written = log.path.parent / "reports" / "coverage.md"
    written.parent.mkdir()
    written.write_text("a report", encoding="utf-8")
    log.wrote("r", "coverage", written)
    detail = _lines(log.path)[0]["detail"]
    assert detail == {
        "action": "coverage",
        "path": "reports/coverage.md",
        "sha256": digest_of_file(written),
    }


# --- a ranking by meaning (ADR-108) ---------------------------------------------------------


def test_a_ranking_by_meaning_is_a_run_of_its_own(tmp_path: Path) -> None:
    """Its own agreement, and often no question after it: so its own run, closed at once."""
    log = _log(tmp_path)
    log.ranked(
        "ask_corpus",
        "ollama:bge-m3",
        "http://desk:11434",
        {"questions": 1, "quotations": 2},
        "which model found the lesions",
    )
    records = _lines(log.path)
    assert [record["kind"] for record in records] == [
        "run_started",
        "texts_embedded",
        "run_finished",
    ]
    assert records[0]["detail"] == {"action": "rank_by_meaning", "for": "ask_corpus"}
    embedded = records[1]["detail"]
    assert isinstance(embedded, dict)
    assert (embedded["questions"], embedded["quotations"], embedded["texts"]) == (1, 2, 3)
    assert embedded["question_sha256"] == digest_of("which model found the lesions")
    assert "question" not in embedded, "the words are kept only under full"


def test_a_ranking_that_did_not_come_back_is_a_failed_run(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.ranked(
        "sections",
        "ollama:bge-m3",
        "http://desk:11434",
        {"questions": 1, "section_openings": 3},
        "nodal staging",
        failed="Cannot reach http://desk:11434 to embed",
    )
    assert [record["kind"] for record in _lines(log.path)] == ["run_started", "run_failed"]


def test_a_count_cannot_take_the_key_of_the_question_itself(tmp_path: Path) -> None:
    """A count named `question` would be overwritten by the words, and dropped with them."""
    with pytest.raises(ValueError, match="question"):
        _log(tmp_path).embedded("r", "ask_corpus", "m", "h", {"question": 1}, "which model")


# --- one chain, however many writers (ADR-109) ---------------------------------------------


def test_two_logs_on_one_trail_keep_one_chain(tmp_path: Path) -> None:
    """The window's Send records across its wait; a Prepare records its ranking meanwhile.

    Before ADR-109 the second record from Send chained to its own last record rather than to
    the ranking's, and the chain broke at the fourth record.
    """
    send = _log(tmp_path)
    send.record("send", "run_started", "Starting ask_corpus")
    prepare = _log(tmp_path)
    prepare.record("rank", "run_started", "Starting rank_by_meaning")
    prepare.record("rank", "run_finished", "Finished rank_by_meaning")
    send.record("send", "provider_called", "Called the engine")
    chain = walk(send.path).chain
    assert chain.intact, f"broken at record {chain.broken_at}"
    assert chain.records == 4


def test_four_threads_keep_one_chain(tmp_path: Path) -> None:
    logs = [_log(tmp_path) for _ in range(4)]

    def write(log: AuditLog, name: str) -> None:
        for number in range(25):
            log.record(name, "run_started", f"{name} {number}")

    threads = [
        threading.Thread(target=write, args=(log, f"thread-{index}"))
        for index, log in enumerate(logs)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    chain = walk(logs[0].path).chain
    assert chain.intact, f"broken at record {chain.broken_at}"
    assert chain.records == 100


_ANOTHER_PROGRAM = """
import time
from pathlib import Path
from local_ai_control_center.core.config import Config
from local_ai_control_center.core.workspace import Workspace
from local_ai_control_center.system.audit import AuditLog
root = Path({root!r})
log = AuditLog(Workspace.ensure(root), Config(workspace_root=root))
Path({ready!r}).write_text("ready", encoding="utf-8")
while not Path({go!r}).exists():
    time.sleep(0.01)
for number in range(40):
    log.record("there", "run_started", f"there {{number}}")
"""


def test_a_second_program_keeps_the_same_chain(tmp_path: Path) -> None:
    """A terminal and the window on one workspace: another process, one trail."""
    ready, go = tmp_path / "ready", tmp_path / "go"
    script = _ANOTHER_PROGRAM.format(root=str(tmp_path), ready=str(ready), go=str(go))
    child = subprocess.Popen([sys.executable, "-c", script])
    deadline = time.monotonic() + 60
    while not ready.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    go.write_text("go", encoding="utf-8")
    log = _log(tmp_path)
    for number in range(40):
        log.record("here", "run_started", f"here {number}")
    assert child.wait(timeout=60) == 0
    chain = walk(log.path).chain
    assert chain.intact, f"broken at record {chain.broken_at}"
    assert chain.records == 80


def test_the_head_is_found_past_a_record_longer_than_the_first_read(tmp_path: Path) -> None:
    """The head is read from the end of the trail; a record under `full` can be a hundred
    kilobytes, so the read has to widen until it holds a whole line."""
    log = _log(tmp_path, audit_level="full")
    log.record("big", "provider_called", "called", {"prompt": "p" * 300_000})
    log.record("next", "run_finished", "finished")
    assert walk(log.path).chain.intact


def test_writers_take_their_turn_at_a_lock_beside_the_trail(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.record("r", "run_started", "started")
    assert log.path.with_suffix(LOCK_SUFFIX).exists()


def test_a_reader_never_creates_the_lock(tmp_path: Path) -> None:
    """A reader that created a file would be a reader that writes."""
    Workspace.ensure(tmp_path)
    trail = tmp_path / AUDIT_FILENAME
    walk(trail)
    check_anchor(trail)
    assert not trail.with_suffix(LOCK_SUFFIX).exists()


def test_a_writer_that_cannot_have_its_turn_fails_like_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another program holding the turn past the wait: the record fails under the policy."""
    monkeypatch.setattr(audit, "_WAIT_SECONDS", 0.3)
    log = _log(tmp_path, audit_failure_policy="abort")
    held = audit._take(log.path, writing=True)
    assert held is not None
    try:
        with pytest.raises(AuditWriteError, match="another writer"):
            log.record("r", "run_started", "started")
    finally:
        audit._unlock(held)
        os.close(held)
