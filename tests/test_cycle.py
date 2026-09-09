"""Integration tests for the execution cycle.

Unlike the other test modules, these exercise configuration, workspace,
permissions, provider, preview, and audit together rather than in isolation.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from local_ai_control_center.audit import AuditLog
from local_ai_control_center.config import Config
from local_ai_control_center.converter import ConversionError, converter_for
from local_ai_control_center.cycle import (
    CONTENT_PLACEHOLDER,
    ExecutionPreview,
    PromptTooLargeError,
    ReadError,
    RunResult,
    answer_reserve,
    estimate_tokens,
    run_action,
    run_conversion,
)
from local_ai_control_center.permissions import PermissionDenied, Permissions
from local_ai_control_center.preview import IntendedAction
from local_ai_control_center.provider import Completion, MockProvider
from local_ai_control_center.workspace import Workspace


def _accept(_preview: ExecutionPreview) -> bool:
    return True


def _decline(_preview: ExecutionPreview) -> bool:
    return False


def _run(
    tmp_path: Path,
    action: IntendedAction,
    permissions: Permissions,
    confirm: object = _accept,
    prompt_template: str = "the prompt",
    **config_kwargs: object,
) -> tuple[RunResult, AuditLog]:
    workspace = Workspace.ensure(tmp_path)
    config = Config(workspace_root=tmp_path, **config_kwargs)  # type: ignore[arg-type]
    audit = AuditLog(workspace, config)
    result = run_action(
        action,
        prompt_template,
        permissions,
        config,
        workspace,
        MockProvider({"the prompt": "the answer"}),
        audit,
        "run-1",
        confirm,  # type: ignore[arg-type]
    )
    return result, audit


def _sha256_of(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _events(audit: AuditLog) -> list[dict[str, object]]:
    text = audit.path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def _kinds(audit: AuditLog) -> list[object]:
    return [event["kind"] for event in _events(audit)]


def test_allowed_and_confirmed_action_runs(tmp_path: Path) -> None:
    """An action that is permitted and confirmed executes and returns a completion."""
    action = IntendedAction(
        name="summarize",
        summary="Summarize something",
        required=frozenset({"read_files"}),
    )
    result, _ = _run(tmp_path, action, Permissions(read_files=True))
    assert result.outcome == "completed"
    assert result.executed is True
    assert result.completion is not None
    assert result.completion.text == "the answer"


def test_completed_run_records_the_full_sequence(tmp_path: Path) -> None:
    """A successful run leaves the expected trail of events."""
    action = IntendedAction(name="summarize", summary="Summarize", required=frozenset())
    _, audit = _run(tmp_path, action, Permissions())
    assert _kinds(audit) == [
        "run_started",
        "permission_granted",
        "prompt_measured",
        "provider_called",
        "run_finished",
    ]


def test_missing_capability_refuses_before_asking(tmp_path: Path) -> None:
    """A refused preview stops the run without calling the confirmation function."""

    def _explode(_preview: ExecutionPreview) -> bool:
        raise AssertionError("confirmation must not be requested for a refused action")

    action = IntendedAction(
        name="write-report",
        summary="Write a report",
        required=frozenset({"write_files"}),
    )
    result, audit = _run(tmp_path, action, Permissions(), confirm=_explode)
    assert result.outcome == "refused"
    assert result.executed is False
    assert result.completion is None
    assert _kinds(audit) == ["run_started", "run_refused"]


def test_refusal_records_what_was_missing(tmp_path: Path) -> None:
    """The refusal event names the missing capability."""
    action = IntendedAction(
        name="write-report",
        summary="Write a report",
        required=frozenset({"write_files"}),
    )
    _, audit = _run(tmp_path, action, Permissions())
    refusal = _events(audit)[-1]
    assert refusal["detail"] == {
        "action": "write-report",
        "missing": ["write_files"],
        "out_of_bounds": [],
    }


def test_target_outside_the_workspace_is_refused(tmp_path: Path) -> None:
    """Boundary violations stop the run, integrating workspace with the cycle."""
    outside = tmp_path / "elsewhere.txt"
    workspace_root = tmp_path / "ws"
    action = IntendedAction(name="read", summary="Read a file", targets=(outside,))
    result, _ = _run(workspace_root, action, Permissions())
    assert result.outcome == "refused"


def test_declining_stops_the_run_and_is_recorded(tmp_path: Path) -> None:
    """A declined confirmation executes nothing and leaves a record."""
    action = IntendedAction(name="summarize", summary="Summarize", required=frozenset())
    result, audit = _run(tmp_path, action, Permissions(), confirm=_decline)
    assert result.outcome == "declined"
    assert result.completion is None
    assert _kinds(audit) == ["run_started", "permission_granted", "confirmation_declined"]


def test_configuration_ceiling_refuses_the_run(tmp_path: Path) -> None:
    """A capability the configuration forbids refuses the run end to end."""
    action = IntendedAction(
        name="fetch",
        summary="Fetch something",
        required=frozenset({"network"}),
    )
    result, _ = _run(tmp_path, action, Permissions(network=True), network_access=False)
    assert result.outcome == "refused"


def test_configuration_ceiling_lifted_allows_the_run(tmp_path: Path) -> None:
    """With the configuration allowing it, the same action runs."""
    action = IntendedAction(
        name="fetch",
        summary="Fetch something",
        required=frozenset({"network"}),
    )
    result, _ = _run(tmp_path, action, Permissions(network=True), network_access=True)
    assert result.outcome == "completed"


def test_standard_audit_level_omits_prompt_and_completion(tmp_path: Path) -> None:
    """By default the trail records that a provider was called, not what was said."""
    action = IntendedAction(name="summarize", summary="Summarize", required=frozenset())
    _, audit = _run(tmp_path, action, Permissions())
    call = next(event for event in _events(audit) if event["kind"] == "provider_called")
    detail = call["detail"]
    assert isinstance(detail, dict)
    assert "prompt" not in detail
    assert "completion" not in detail
    assert detail["provider"] == "mock"


def test_full_audit_level_records_prompt_and_completion(tmp_path: Path) -> None:
    """Under `full`, the content is recorded as an explicit opt-in."""
    action = IntendedAction(name="summarize", summary="Summarize", required=frozenset())
    _, audit = _run(tmp_path, action, Permissions(), audit_level="full")
    call = next(event for event in _events(audit) if event["kind"] == "provider_called")
    detail = call["detail"]
    assert isinstance(detail, dict)
    assert detail["prompt"] == "the prompt"
    assert detail["completion"] == "the answer"


def test_every_event_carries_the_run_id(tmp_path: Path) -> None:
    """The whole trail is tied to one execution."""
    action = IntendedAction(name="summarize", summary="Summarize", required=frozenset())
    _, audit = _run(tmp_path, action, Permissions())
    assert {event["run_id"] for event in _events(audit)} == {"run-1"}


_TEMPLATE = f"Summarize this:\n\n{CONTENT_PLACEHOLDER}"


def _reading_action(*, declares_read: bool = True) -> IntendedAction:
    """An action naming a file to read, optionally without declaring the permission."""
    return IntendedAction(
        name="summarize",
        summary="Summarize a note",
        required=frozenset({"read_files"}) if declares_read else frozenset(),
        targets=(Path("notes.txt"),),
    )


def _note(tmp_path: Path, body: str = "The note body.") -> Path:
    path = tmp_path / "notes.txt"
    path.write_text(body, encoding="utf-8")
    return path


def _recorded_prompt(audit: AuditLog) -> object:
    call = next(event for event in _events(audit) if event["kind"] == "provider_called")
    detail = call["detail"]
    assert isinstance(detail, dict)
    return detail["prompt"]


def test_declared_files_are_read_into_the_prompt(tmp_path: Path) -> None:
    """The cycle fills the template with what it read, and sends that to the provider."""
    _note(tmp_path)
    _, audit = _run(
        tmp_path,
        _reading_action(),
        Permissions(read_files=True),
        prompt_template=_TEMPLATE,
        audit_level="full",
    )
    assert _recorded_prompt(audit) == "Summarize this:\n\nThe note body."


def test_reading_is_recorded_with_the_path_not_the_contents(tmp_path: Path) -> None:
    """The read leaves a trail naming the file; the contents are not in that event."""
    note = _note(tmp_path)
    _, audit = _run(
        tmp_path,
        _reading_action(),
        Permissions(read_files=True),
        prompt_template=_TEMPLATE,
    )
    read = next(event for event in _events(audit) if event["kind"] == "files_read")
    detail = read["detail"]
    assert isinstance(detail, dict)
    recorded = detail["files"]
    assert recorded == [{"path": str(note.resolve()), "sha256": _sha256_of(note)}]


def test_standard_audit_level_omits_the_file_contents(tmp_path: Path) -> None:
    """A read must not leak what the file said into a standard-level trail."""
    _note(tmp_path, "SECRET BODY")
    _, audit = _run(
        tmp_path,
        _reading_action(),
        Permissions(read_files=True),
        prompt_template=_TEMPLATE,
    )
    assert "SECRET BODY" not in audit.path.read_text(encoding="utf-8")


def test_targets_are_not_read_without_a_declared_read_files(tmp_path: Path) -> None:
    """Reading follows the declaration the preview checked, not the granted permission.

    An action that names targets but declares no `read_files` passes the preview,
    since the preview only checks what was declared. It must still not be read.
    """
    _note(tmp_path, "SECRET BODY")
    _, audit = _run(
        tmp_path,
        _reading_action(declares_read=False),
        Permissions(read_files=True),
        prompt_template=_TEMPLATE,
        audit_level="full",
    )
    assert _recorded_prompt(audit) == _TEMPLATE
    assert "files_read" not in _kinds(audit)


def test_unreadable_file_fails_clearly_and_is_recorded(tmp_path: Path) -> None:
    """A target that cannot be read raises a clear error and leaves a record."""
    with pytest.raises(ReadError) as excinfo:
        _run(
            tmp_path,
            _reading_action(),
            Permissions(read_files=True),
            prompt_template=_TEMPLATE,
        )
    assert "notes.txt" in str(excinfo.value)
    trail = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["kind"] for line in trail] == [
        "run_started",
        "permission_granted",
        "read_failed",
    ]


def test_a_file_that_is_not_text_fails_clearly(tmp_path: Path) -> None:
    """A binary target is refused with a message about text, not a decode traceback."""
    (tmp_path / "notes.txt").write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(ReadError) as excinfo:
        _run(
            tmp_path,
            _reading_action(),
            Permissions(read_files=True),
            prompt_template=_TEMPLATE,
        )
    assert "not UTF-8 text" in str(excinfo.value)


def test_declining_reads_nothing(tmp_path: Path) -> None:
    """The read happens after confirmation, never before.

    The note is never created: had the cycle read before asking, this would fail
    with a `ReadError` instead of declining quietly.
    """
    result, audit = _run(
        tmp_path,
        _reading_action(),
        Permissions(read_files=True),
        confirm=_decline,
        prompt_template=_TEMPLATE,
    )
    assert result.outcome == "declined"
    assert "files_read" not in _kinds(audit)


_INGEST_CAPS = frozenset({"read_files", "write_files"})


def _ingest(
    tmp_path: Path,
    source: Path,
    destination: Path,
    *,
    required: frozenset[str] = _INGEST_CAPS,
    confirm: object = _accept,
    **config_kwargs: object,
) -> tuple[RunResult, AuditLog]:
    workspace = Workspace.ensure(tmp_path)
    config = Config(workspace_root=tmp_path, **config_kwargs)  # type: ignore[arg-type]
    audit = AuditLog(workspace, config)
    action = IntendedAction(
        name="ingest",
        summary=f"Extract the text of {source} into {destination}",
        required=required,  # type: ignore[arg-type]
        targets=(source, destination),
    )
    result = run_conversion(
        action,
        source,
        destination,
        converter_for(source),
        Permissions(read_files=True, write_files=True),
        config,
        workspace,
        audit,
        "run-1",
        confirm,  # type: ignore[arg-type]
    )
    return result, audit


def test_conversion_writes_the_extracted_text(
    tmp_path: Path, make_pdf: Callable[..., Path]
) -> None:
    """The run produces a file, and completes without ever reaching a provider."""
    make_pdf("Attention is all you need")
    result, _ = _ingest(tmp_path, Path("document.pdf"), Path("document.md"))
    assert result.outcome == "completed"
    assert result.completion is None
    assert "Attention is all you need" in (tmp_path / "document.md").read_text(encoding="utf-8")


def test_conversion_records_what_it_did(tmp_path: Path, make_pdf: Callable[..., Path]) -> None:
    """A converted document leaves the same shape of trail as any other run."""
    make_pdf("Some text")
    _, audit = _ingest(tmp_path, Path("document.pdf"), Path("document.md"))
    assert _kinds(audit) == [
        "run_started",
        "permission_granted",
        "document_converted",
        "run_finished",
    ]


def test_conversion_records_paths_but_never_the_text(
    tmp_path: Path, make_pdf: Callable[..., Path]
) -> None:
    """The extracted text is already a file the record names; the trail does not repeat it."""
    make_pdf("SECRET RESEARCH FINDING")
    _, audit = _ingest(tmp_path, Path("document.pdf"), Path("document.md"), audit_level="full")
    trail = audit.path.read_text(encoding="utf-8")
    assert "SECRET RESEARCH FINDING" not in trail
    assert "document.pdf" in trail and "document.md" in trail


def test_declining_a_conversion_writes_nothing(
    tmp_path: Path, make_pdf: Callable[..., Path]
) -> None:
    """The effects come after confirmation here too."""
    make_pdf("Some text")
    result, _ = _ingest(tmp_path, Path("document.pdf"), Path("document.md"), confirm=_decline)
    assert result.outcome == "declined"
    assert not (tmp_path / "document.md").exists()


def test_conversion_never_overwrites(tmp_path: Path, make_pdf: Callable[..., Path]) -> None:
    """A destination the user may have corrected by hand is not replaced."""
    make_pdf("Some text")
    existing = tmp_path / "document.md"
    existing.write_text("corrected by hand", encoding="utf-8")
    with pytest.raises(ConversionError) as excinfo:
        _ingest(tmp_path, Path("document.pdf"), Path("document.md"))
    assert "already exists" in str(excinfo.value)
    assert existing.read_text(encoding="utf-8") == "corrected by hand"


def test_conversion_into_a_missing_folder_fails_clearly(
    tmp_path: Path, make_pdf: Callable[..., Path]
) -> None:
    """A folder that is not there is named, rather than created behind the user's back."""
    make_pdf("Some text")
    with pytest.raises(ConversionError) as excinfo:
        _ingest(tmp_path, Path("document.pdf"), Path("nowhere/document.md"))
    assert "does not exist" in str(excinfo.value)


def test_conversion_failure_is_recorded(tmp_path: Path, make_pdf: Callable[..., Path]) -> None:
    """A failed ingestion leaves a record saying so."""
    make_pdf(" ")
    with pytest.raises(ConversionError):
        _ingest(tmp_path, Path("document.pdf"), Path("document.md"))
    audit = AuditLog(Workspace.ensure(tmp_path), Config(workspace_root=tmp_path))
    assert _kinds(audit) == ["run_started", "permission_granted", "ingestion_failed"]


def test_conversion_refuses_a_destination_outside_the_workspace(
    tmp_path: Path, make_pdf: Callable[..., Path]
) -> None:
    """The boundary applies to what is written, not only to what is read."""
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    make_pdf("Some text", name="ws/document.pdf")
    result, _ = _ingest(workspace_root, Path("document.pdf"), Path("../escaped.md"))
    assert result.outcome == "refused"
    assert not (tmp_path / "escaped.md").exists()


def test_conversion_will_not_write_without_the_action_declaring_it(
    tmp_path: Path, make_pdf: Callable[..., Path]
) -> None:
    """Writing follows the declaration the preview checked, not the permission granted.

    The permissions here grant `write_files`; the action does not ask for it. The preview
    checks only what is declared, so an undeclared write would never have been checked.
    """
    make_pdf("Some text")
    with pytest.raises(PermissionDenied) as excinfo:
        _ingest(
            tmp_path,
            Path("document.pdf"),
            Path("document.md"),
            required=frozenset({"read_files"}),
        )
    assert "write_files" in str(excinfo.value)
    assert not (tmp_path / "document.md").exists()


def test_conversion_will_not_read_without_the_action_declaring_it(
    tmp_path: Path, make_pdf: Callable[..., Path]
) -> None:
    """Reading is an effect too, and the same rule covers it.

    An action declaring only `write_files` is checked only for `write_files`, so the
    preview the human confirmed would not have mentioned the read at all.
    """
    make_pdf("Some text")
    with pytest.raises(PermissionDenied) as excinfo:
        _ingest(
            tmp_path,
            Path("document.pdf"),
            Path("document.md"),
            required=frozenset({"write_files"}),
        )
    assert "read_files" in str(excinfo.value)
    assert not (tmp_path / "document.md").exists()


def test_conversion_declaring_nothing_names_both_effects(
    tmp_path: Path, make_pdf: Callable[..., Path]
) -> None:
    """An action that declares neither is told about both, not just the first."""
    make_pdf("Some text")
    with pytest.raises(PermissionDenied) as excinfo:
        _ingest(tmp_path, Path("document.pdf"), Path("document.md"), required=frozenset())
    message = str(excinfo.value)
    assert "read_files" in message and "write_files" in message


def test_a_file_over_the_ceiling_is_not_read(tmp_path: Path) -> None:
    """The ceiling is checked before the file is opened, not after it is in memory."""
    _note(tmp_path, "x" * 500)
    with pytest.raises(ReadError) as excinfo:
        _run(
            tmp_path,
            _reading_action(),
            Permissions(read_files=True),
            prompt_template=_TEMPLATE,
            max_input_bytes=100,
        )
    message = str(excinfo.value)
    assert "notes.txt" in message and "max_input_bytes" in message


def test_a_document_over_the_ceiling_is_not_converted(
    tmp_path: Path, make_pdf: Callable[..., Path]
) -> None:
    """The same ceiling covers ingestion, and the refusal is recorded."""
    make_pdf("Some text")
    with pytest.raises(ConversionError) as excinfo:
        _ingest(tmp_path, Path("document.pdf"), Path("document.md"), max_input_bytes=100)
    assert "max_input_bytes" in str(excinfo.value)
    assert not (tmp_path / "document.md").exists()
    audit = AuditLog(Workspace.ensure(tmp_path), Config(workspace_root=tmp_path))
    assert _kinds(audit)[-1] == "ingestion_failed"


def test_the_token_estimate_errs_toward_refusing() -> None:
    """Three characters per token estimates more tokens than there probably are."""
    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("abcd") == 2
    assert estimate_tokens("x" * 3000) == 1000


def test_the_answer_reserve_never_falls_below_its_floor() -> None:
    """The window must hold the answer too, and a small window still leaves room."""
    assert answer_reserve(32768) == 8192
    assert answer_reserve(1024) == 512


def test_a_prompt_over_the_window_is_refused_before_the_provider(tmp_path: Path) -> None:
    """Nothing is sent, because an engine given too much does not fail - it truncates."""
    _note(tmp_path, "palabra " * 4000)
    with pytest.raises(PromptTooLargeError) as excinfo:
        _run(
            tmp_path,
            _reading_action(),
            Permissions(read_files=True),
            prompt_template=_TEMPLATE,
            context_tokens=4096,
        )
    message = str(excinfo.value)
    assert "estimated" in message and "context_tokens" in message


def test_an_oversized_prompt_is_recorded_as_refused(tmp_path: Path) -> None:
    """The trail says the prompt was measured and then refused, and nothing was called."""
    _note(tmp_path, "palabra " * 4000)
    with pytest.raises(PromptTooLargeError):
        _run(
            tmp_path,
            _reading_action(),
            Permissions(read_files=True),
            prompt_template=_TEMPLATE,
            context_tokens=4096,
        )
    audit = AuditLog(Workspace.ensure(tmp_path), Config(workspace_root=tmp_path))
    kinds = _kinds(audit)
    assert kinds[-2:] == ["prompt_measured", "prompt_too_large"]
    assert "provider_called" not in kinds


def test_a_prompt_within_the_window_runs(tmp_path: Path) -> None:
    """The ceiling refuses what does not fit and stays out of the way of what does."""
    _note(tmp_path, "una nota corta")
    result, _ = _run(
        tmp_path,
        _reading_action(),
        Permissions(read_files=True),
        prompt_template=_TEMPLATE,
        context_tokens=32768,
    )
    assert result.outcome == "completed"


def test_every_prompt_is_measured_even_without_a_ceiling(tmp_path: Path) -> None:
    """How large a prompt was is a fact about the run, recorded whether or not it matters."""
    _note(tmp_path, "una nota corta")
    _, audit = _run(
        tmp_path,
        _reading_action(),
        Permissions(read_files=True),
        prompt_template=_TEMPLATE,
    )
    measured = next(event for event in _events(audit) if event["kind"] == "prompt_measured")
    detail = measured["detail"]
    assert isinstance(detail, dict)
    assert detail["estimated_tokens"] > 0
    assert detail["requested_window"] is None


class _MeasuringProvider(MockProvider):
    """A mock that reports engine counts, so the measurement path can be exercised."""

    def __init__(self, prompt_tokens: int | None = None, finish_reason: str | None = None) -> None:
        super().__init__()
        self._prompt_tokens = prompt_tokens
        self._finish_reason = finish_reason

    def complete(self, prompt: str) -> Completion:
        base = super().complete(prompt)
        return Completion(
            text=base.text,
            provider=base.provider,
            prompt_tokens=self._prompt_tokens,
            answer_tokens=7,
            finish_reason=self._finish_reason,
        )


def _run_measured(tmp_path: Path, provider: MockProvider, **config_kwargs: object) -> AuditLog:
    workspace = Workspace.ensure(tmp_path)
    config = Config(workspace_root=tmp_path, **config_kwargs)  # type: ignore[arg-type]
    audit = AuditLog(workspace, config)
    _note(tmp_path, "una nota corta")
    run_action(
        _reading_action(),
        _TEMPLATE,
        Permissions(read_files=True),
        config,
        workspace,
        provider,
        audit,
        "run-1",
        _accept,
    )
    return audit


def test_the_estimate_and_the_measurement_are_recorded_together(tmp_path: Path) -> None:
    """The trail can say whether the estimate was any good, without re-deriving it."""
    audit = _run_measured(tmp_path, _MeasuringProvider(prompt_tokens=120))
    call = next(event for event in _events(audit) if event["kind"] == "provider_called")
    detail = call["detail"]
    assert isinstance(detail, dict)
    assert detail["estimated_tokens"] > 0
    assert detail["measured_prompt_tokens"] == 120


def test_a_prompt_that_filled_the_window_is_named_as_truncated(tmp_path: Path) -> None:
    """A count that reaches the window means the engine answered from part of the document."""
    audit = _run_measured(tmp_path, _MeasuringProvider(prompt_tokens=4095), context_tokens=4096)
    assert "prompt_was_truncated" in _kinds(audit)
    assert "ceiling_underestimated" not in _kinds(audit)


def test_an_underestimate_is_not_reported_as_truncation(tmp_path: Path) -> None:
    """Different things, told apart: the prompt fitted, the arithmetic was off.

    A window of 32768 reserves 8192 for the answer, leaving 24576. A prompt the engine
    counted at 25000 went over that budget while sitting nowhere near the window.
    """
    audit = _run_measured(tmp_path, _MeasuringProvider(prompt_tokens=25_000), context_tokens=32768)
    assert "ceiling_underestimated" in _kinds(audit)
    assert "prompt_was_truncated" not in _kinds(audit)


def test_a_count_far_below_the_estimate_raises_no_alarm(tmp_path: Path) -> None:
    """The estimate runs high by design, so measuring less than it is the ordinary case.

    Comparing the count against the estimate rather than against the window would flag
    every healthy run on text that tokenizes well (ADR-024).
    """
    audit = _run_measured(tmp_path, _MeasuringProvider(prompt_tokens=10), context_tokens=32768)
    assert "prompt_was_truncated" not in _kinds(audit)
    assert "ceiling_underestimated" not in _kinds(audit)


def test_an_accurate_estimate_raises_no_alarm(tmp_path: Path) -> None:
    """The signal only fires when the engine's count actually exceeded the budget."""
    audit = _run_measured(tmp_path, _MeasuringProvider(prompt_tokens=100), context_tokens=32768)
    assert "ceiling_underestimated" not in _kinds(audit)


def test_an_answer_cut_short_is_recorded(tmp_path: Path) -> None:
    """An answer that ran out of room ends mid-thought and looks like an answer."""
    audit = _run_measured(tmp_path, _MeasuringProvider(finish_reason="length"))
    assert "answer_truncated" in _kinds(audit)


def test_an_answer_that_finished_is_not_flagged(tmp_path: Path) -> None:
    """Stopping because the model was done is the ordinary case."""
    audit = _run_measured(tmp_path, _MeasuringProvider(finish_reason="stop"))
    assert "answer_truncated" not in _kinds(audit)
