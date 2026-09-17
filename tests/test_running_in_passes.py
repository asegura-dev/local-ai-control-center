"""Tests for reading one document in several passes (ADR-045)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_ai_control_center.core.config import Config
from local_ai_control_center.core.fence import CONTENT_PLACEHOLDER
from local_ai_control_center.core.grounding import CheckedClaim, Claim, without_repeats
from local_ai_control_center.core.permissions import Permissions
from local_ai_control_center.core.preview import ExecutionPreview, IntendedAction
from local_ai_control_center.core.workspace import Workspace
from local_ai_control_center.cycle import CannotReadInPasses, RunResult, run_in_passes
from local_ai_control_center.ports.provider import Completion, Provider
from local_ai_control_center.system.audit import AuditLog

NL = chr(10)
_TEMPLATE = f"Read this and list what it claims:{NL}{NL}{CONTENT_PLACEHOLDER}"


class _Recorder(Provider):
    """A provider that remembers every prompt and answers with a scripted claim."""

    def __init__(self, answers: list[str] | None = None) -> None:
        self.prompts: list[str] = []
        self._answers = answers or []

    @property
    def name(self) -> str:
        return "recorder"

    def complete(self, prompt: str, temperature: float = 0.0) -> Completion:
        self.prompts.append(prompt)
        index = len(self.prompts) - 1
        text = self._answers[index] if index < len(self._answers) else "nothing to report"
        return Completion(text=text, provider=self.name, answer_tokens=7)


def _paper(tmp_path: Path, pages: list[str]) -> Path:
    body = NL.join(f"<!-- page {n} -->{NL}{NL}{text}" for n, text in enumerate(pages, start=1))
    path = tmp_path / "paper.md"
    path.write_text(body, encoding="utf-8")
    return path


def _action(targets: tuple[Path, ...] = (Path("paper.md"),)) -> IntendedAction:
    return IntendedAction(
        name="extract_claims",
        summary="Extract what a paper claims",
        required=frozenset({"read_files"}),
        targets=targets,
    )


def _accept(_preview: ExecutionPreview) -> bool:
    return True


def _go(
    tmp_path: Path,
    provider: Provider,
    action: IntendedAction | None = None,
    verify_quotes: bool = False,
    progress: object = None,
    **config_kwargs: object,
) -> tuple[RunResult, AuditLog]:
    workspace = Workspace.ensure(tmp_path)
    config = Config(workspace_root=tmp_path, **config_kwargs)  # type: ignore[arg-type]
    audit = AuditLog(workspace, config)
    result = run_in_passes(
        action or _action(),
        _TEMPLATE,
        Permissions(read_files=True),
        config,
        workspace,
        provider,
        audit,
        "run-1",
        _accept,  # type: ignore[arg-type]
        verify_quotes=verify_quotes,
        progress=progress,  # type: ignore[arg-type]
    )
    return result, audit


def _events(audit: AuditLog) -> list[dict[str, object]]:
    text = audit.path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def _long_pages(count: int) -> list[str]:
    return [f"page {n} says " + "word " * 200 for n in range(1, count + 1)]


def test_a_small_document_is_one_pass(tmp_path: Path) -> None:
    """Nothing about dividing should change a document that never needed it."""
    _paper(tmp_path, ["alpha", "beta", "gamma"])
    provider = _Recorder()
    result, _ = _go(tmp_path, provider, context_tokens=32768)
    assert result.passes == 1
    assert len(provider.prompts) == 1


def test_a_large_document_is_asked_once_per_pass(tmp_path: Path) -> None:
    _paper(tmp_path, _long_pages(10))
    provider = _Recorder()
    result, _ = _go(tmp_path, provider, context_tokens=2048)
    assert result.passes > 2
    assert len(provider.prompts) == result.passes


def test_every_pass_carries_the_skill_instructions(tmp_path: Path) -> None:
    """A pass is a prompt, not a fragment: the wrapper goes with each one."""
    _paper(tmp_path, _long_pages(10))
    provider = _Recorder()
    _go(tmp_path, provider, context_tokens=2048)
    assert all(
        prompt.startswith("Read this and list what it claims:") for prompt in provider.prompts
    )
    assert len({prompt for prompt in provider.prompts}) == len(provider.prompts)


def test_a_quotation_is_checked_against_the_whole_document_not_its_pass(tmp_path: Path) -> None:
    """The line ADR-045 draws. A late pass quoting an early page still verifies."""
    pages = _long_pages(10)
    pages[0] = pages[0] + " The sensitivity was ninety four per cent."
    _paper(tmp_path, pages)

    quote = "The sensitivity was ninety four per cent."

    class _QuotesWhatItCannotSee(_Recorder):
        """Answers with the quotation only from passes that do not contain it."""

        def complete(self, prompt: str, temperature: float = 0.0) -> Completion:
            self.prompts.append(prompt)
            if quote in prompt:
                return Completion(text="nothing", provider=self.name)
            return Completion(
                text=f"CLAIM: it was accurate{NL}QUOTE: {quote}{NL}PAGE: 1",
                provider=self.name,
            )

    provider = _QuotesWhatItCannotSee()
    result, _ = _go(tmp_path, provider, verify_quotes=True, context_tokens=2048)

    assert result.passes > 2
    blind = [prompt for prompt in provider.prompts if quote not in prompt]
    assert blind, "the point of the test is a pass that never saw the sentence"
    assert [c.claim.quote for c in result.checked_claims] == [quote]
    assert result.checked_claims[0].found, "checked against the document, not the pass"


def test_the_same_quotation_from_the_overlap_is_reported_once(tmp_path: Path) -> None:
    pages = _long_pages(6)
    pages[2] = pages[2] + " A repeated finding of note."
    _paper(tmp_path, pages)

    block = f"CLAIM: repeated{NL}QUOTE: A repeated finding of note.{NL}PAGE: 3"
    provider = _Recorder([block] * 20)
    result, _ = _go(tmp_path, provider, verify_quotes=True, context_tokens=2048)

    assert result.passes > 1, "the overlap has to exist for this to mean anything"
    assert len(result.checked_claims) == 1


def test_the_audit_says_how_many_readings_there_were(tmp_path: Path) -> None:
    _paper(tmp_path, _long_pages(10))
    provider = _Recorder()
    result, audit = _go(tmp_path, provider, context_tokens=2048)

    divided = [e for e in _events(audit) if e["kind"] == "read_in_passes"]
    assert len(divided) == 1
    detail = divided[0]["detail"]
    assert isinstance(detail, dict)
    assert detail["passes"] == result.passes
    assert len(detail["pages"]) == result.passes


def test_a_document_without_page_markers_is_refused_rather_than_guessed_at(
    tmp_path: Path,
) -> None:
    (tmp_path / "paper.md").write_text("no markers here at all " * 500, encoding="utf-8")
    with pytest.raises(CannotReadInPasses, match="no page markers"):
        _go(tmp_path, _Recorder(), context_tokens=2048)


def test_reading_several_documents_in_passes_is_refused(tmp_path: Path) -> None:
    _paper(tmp_path, ["alpha"])
    (tmp_path / "other.md").write_text("<!-- page 1 -->" + NL + "beta", encoding="utf-8")
    action = _action((Path("paper.md"), Path("other.md")))
    with pytest.raises(CannotReadInPasses, match="reads one"):
        _go(tmp_path, _Recorder(), action=action, context_tokens=2048)


def test_without_a_window_there_is_nothing_to_divide_against(tmp_path: Path) -> None:
    _paper(tmp_path, ["alpha"])
    with pytest.raises(CannotReadInPasses, match="context_tokens"):
        _go(tmp_path, _Recorder())


def test_repeats_are_dropped_on_the_quotation_however_it_is_spaced() -> None:
    def checked(quote: str) -> CheckedClaim:
        return CheckedClaim(claim=Claim(claim="c", quote=quote), verdict="verified")

    kept = without_repeats(
        (checked("The sensitivity was high."), checked("The s e n s i t i v i t y was high."))
    )
    assert len(kept) == 1


def test_a_run_reports_where_it_has_got_to(tmp_path: Path) -> None:
    """Seventeen passes used to say nothing between starting and finishing."""
    from local_ai_control_center.core.run import Progress

    _paper(tmp_path, _long_pages(10))
    seen: list[Progress] = []
    result, _ = _go(
        tmp_path, _Recorder(), verify_quotes=True, context_tokens=2048, progress=seen.append
    )

    asked = [p for p in seen if p.stage == "asking"]
    assert len(asked) == result.passes
    assert [p.done for p in asked] == list(range(result.passes))
    assert all(p.total == result.passes for p in asked)
    assert [p.stage for p in seen if p.stage == "dividing"] == ["dividing"]
    assert any(p.stage == "checking" for p in seen)
    assert asked[0].fraction == 0.0
    assert asked[-1].fraction < 1.0


def test_a_watcher_that_breaks_does_not_take_the_run_with_it(tmp_path: Path) -> None:
    """A document half read must not be lost to a broken progress bar."""

    def explode(_where: object) -> None:
        raise RuntimeError("the bar is on fire")

    _paper(tmp_path, _long_pages(6))
    result, _ = _go(tmp_path, _Recorder(), context_tokens=2048, progress=explode)
    assert result.outcome == "completed"
    assert result.passes > 1


def test_a_run_nobody_watches_behaves_the_same(tmp_path: Path) -> None:
    _paper(tmp_path, _long_pages(6))
    watched, _ = _go(tmp_path, _Recorder(), context_tokens=2048, progress=lambda _w: None)
    unwatched, _ = _go(tmp_path, _Recorder(), context_tokens=2048)
    assert watched.passes == unwatched.passes
    assert watched.completion is not None and unwatched.completion is not None
    assert watched.completion.text == unwatched.completion.text


def test_a_stage_with_no_total_reports_no_fraction() -> None:
    """An empty bar is honest where a wrong one is not."""
    from local_ai_control_center.core.run import Progress

    assert Progress(stage="checking").fraction == 0.0
    assert Progress(stage="asking", done=3, total=12).fraction == 0.25
