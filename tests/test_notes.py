"""A note per reference: assembled, judged and read, each marked as what it is (ADR-124)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from local_ai_control_center.cli import app
from local_ai_control_center.core.corpus import CollectedClaim
from local_ai_control_center.core.protocol import CitingSentence, MasterEntry
from local_ai_control_center.features.notes import Cited, Reading, note_text
from local_ai_control_center.ports.provider import Completion, Provider

runner = CliRunner()

_ENTRY = MasterEntry(
    key="rokuss",
    compact=19,
    extended=31,
    reference="Rokuss M, et al. From FDG to PSMA: a hitchhiker's guide. *arXiv*. 2024.",
    doi="10.48550/arXiv.2409.09478",
)
_SENTENCE = CitingSentence(
    source="compacto_03.md",
    line=7,
    text="El modelo final alcanzó un Dice de 0.600 [19].",
    numbers=(19,),
)
_QUOTE = "The final model reached a Dice of 0.600 on the PSMA cohort."


def test_a_note_says_what_each_part_is() -> None:
    written = note_text(
        _ENTRY,
        (
            Cited(sentence=_SENTENCE, version="compact", verdict="supported", quote=_QUOTE, page=1),
            Cited(
                sentence=_SENTENCE,
                version="extended",
                verdict="nothing",
                considered=(("A sentence near it, but about FDG.", 3),),
            ),
        ),
        (
            Reading(
                part="Objective 2",
                reading="It sets a ceiling.",
                quote=_QUOTE,
                page=1,
                found=True,
                verdict="follows",
            ),
            Reading(
                part="Hypothesis",
                reading="It proves the thesis.",
                quote="Words it never had",
                found=False,
            ),
            Reading(
                part="Formula", reading=r"\mathcal{L}", quote="L = LCE + LKD", page=2, found=True
            ),
        ),
        (CollectedClaim(document="rokuss.md", quote=_QUOTE, claim="the PSMA Dice", page=1),),
    )
    assert written.startswith('---\nkey: "rokuss"\ncompact: 19\nextended: 31\n')
    assert "reference: \"Rokuss M, et al. From FDG to PSMA: a hitchhiker's guide." in written
    assert "Cite as `[@rokuss]` · compact [19] · extended [31]" in written
    assert "> [!success] Held up · compact, compacto_03.md, line 7" in written
    assert "> [!question] Not covered by its quotations · extended" in written, "never a failure"
    assert ">> p. 3: A sentence near it, but about FDG." in written, "what was judged, shown"
    assert "the model's reading" in written
    assert "> [!note] Objective 2 · its quotation supports it" in written
    assert "> [!caution] Hypothesis · its quotation is not in the document" in written
    assert "> [!warning] Reconstruction · p. 2 · the line is in the document" in written
    assert "> [!quote] p. 1" in written


_DOCUMENT = "<!-- page 1 -->\n\n" + _QUOTE + " The loss is L = LCE + LKD over the voxels.\n"
_CORPUS = "\n".join(
    [
        "## rokuss.md",
        "",
        "*1 of 1 quotations are in the document.*",
        "",
        f"> {_QUOTE}",
        "",
        "p. 1 - the PSMA Dice",
        "",
    ]
)
_MASTER = (
    "- **rokuss** | compacto [19] | extenso [31] | verificada contra la fuente | con DOI\n"
    "  Rokuss M, et al. From FDG to PSMA. *arXiv*. 2024. doi:10.48550/arXiv.2409.09478.\n"
)
_CHAPTER = "# Antecedentes\n\nEl modelo final documentó un Dice de 0.600 [19].\n"
_READ = "\n".join(
    [
        "PART: Objective 2",
        "READING: The winning model reached a Dice of 0.600 on PSMA.",
        f"QUOTE: {_QUOTE}",
        "PAGE: 1",
        "USE: It sets a ceiling to compare against.",
        "",
        "PART: Formula",
        r"READING: \mathcal{L} = \mathcal{L}_{CE} + \mathcal{L}_{KD}",
        "QUOTE: The loss is L = LCE + LKD over the voxels.",
        "PAGE: 1",
    ]
)


class _Engine(Provider):
    """Reads for the thesis when asked to, and finds every reading supported when judging."""

    @property
    def name(self) -> str:
        return "engine"

    def complete(
        self, prompt: str, temperature: float = 0.0, schema: dict[str, Any] | None = None
    ) -> Completion:
        if "You are reading one document for a thesis" in prompt:
            return Completion(text=_READ, provider="engine")
        return Completion(text='{"verdict": "follows", "why": "it says so"}', provider="engine")


def _workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    workspace = tmp_path / "ws"
    (workspace / "drafts").mkdir(parents=True)
    (workspace / "rokuss.md").write_text(_DOCUMENT, encoding="utf-8")
    (workspace / "citas.md").write_text(_CORPUS, encoding="utf-8")
    (workspace / "drafts" / "maestras.md").write_text(_MASTER, encoding="utf-8")
    (workspace / "drafts" / "compacto_03.md").write_text(_CHAPTER, encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}\nmodel: qwen2.5:14b\n", encoding="utf-8")
    monkeypatch.setattr(
        "local_ai_control_center.cli._build_provider",
        lambda choice, config, skill="": _Engine(),
    )
    return config


_ARGUMENTS = [
    "notes",
    "rokuss.md",
    "--master",
    "drafts/maestras.md",
    "--against",
    "citas.md",
    "--compact",
    "drafts/compacto_03.md",
]


def test_a_note_is_written_with_its_sentence_judged_and_its_reading_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path, monkeypatch)
    result = runner.invoke(app, [*_ARGUMENTS, "-c", str(config)], input="y\n")
    assert result.exit_code == 0, result.stdout
    note = (tmp_path / "ws" / "notes" / "rokuss.md").read_text(encoding="utf-8")
    assert "> [!success] Held up · compact, compacto_03.md, line 3" in note
    assert "> [!note] Objective 2 · its quotation supports it" in note
    assert "*How the thesis might use it, as the model suggests:* It sets a ceiling" in note
    assert "> [!warning] Reconstruction · p. 1 · the line is in the document" in note
    said = " ".join(result.stdout.split())
    assert "1 note written" in said and "1 held up" in said


def test_the_judge_is_asked_for_by_its_own_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """So `models: {judge: ...}` decides which model judges (ADR-124)."""
    config = _workspace(tmp_path, monkeypatch)
    asked: list[str] = []

    def built(choice: object, config: object, skill: str = "") -> Provider:
        asked.append(skill)
        return _Engine()

    monkeypatch.setattr("local_ai_control_center.cli._build_provider", built)
    runner.invoke(app, [*_ARGUMENTS, "-c", str(config)], input="y\n")
    assert set(asked) == {"read_for_thesis", "judge"}


def test_the_judges_model_is_said_without_calling_it_a_skill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The line said "names a model for this skill" of the judge, which is not one."""
    config = _workspace(tmp_path, monkeypatch)
    config.write_text(
        config.read_text(encoding="utf-8") + "models:\n  judge: gemma4:12b\n", encoding="utf-8"
    )
    result = runner.invoke(app, [*_ARGUMENTS, "-c", str(config)], input="n\n")
    said = " ".join(result.stdout.split())
    assert "judge runs on gemma4:12b, not qwen2.5:14b" in said
    assert "names a model for it." in said and "this skill" not in said


def test_the_note_run_and_the_reading_run_are_both_in_the_trail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path, monkeypatch)
    runner.invoke(app, [*_ARGUMENTS, "-c", str(config)], input="y\n")
    records = [
        json.loads(line)
        for line in (tmp_path / "ws" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    actions = {record["detail"].get("action") for record in records}
    assert {"notes", "read_for_thesis"} <= actions
    notes_kinds = [r["kind"] for r in records if r["detail"].get("action") == "notes"]
    assert notes_kinds[0] == "run_started" and notes_kinds[-1] == "run_finished"
    assert "readings_judged" in notes_kinds and "file_written" in notes_kinds
    judged = next(r["detail"] for r in records if r["kind"] == "readings_judged")
    assert (judged["sentences"], judged["held"], judged["readings_followed"]) == (1, 1, 1)


def test_a_note_already_there_is_refused_before_anything_is_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path, monkeypatch)
    (tmp_path / "ws" / "notes").mkdir()
    (tmp_path / "ws" / "notes" / "rokuss.md").write_text("mine", encoding="utf-8")
    result = runner.invoke(app, [*_ARGUMENTS, "-c", str(config)], input="y\n")
    assert result.exit_code == 1
    assert "already in notes" in " ".join(result.stdout.split())
    assert (tmp_path / "ws" / "notes" / "rokuss.md").read_text(encoding="utf-8") == "mine"
    assert not (tmp_path / "ws" / "audit.jsonl").exists()


def test_a_no_sends_nothing_and_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path, monkeypatch)
    result = runner.invoke(app, [*_ARGUMENTS, "-c", str(config)], input="n\n")
    assert result.exit_code == 0
    assert "Nothing was sent to the engine." in " ".join(result.stdout.split())
    assert not (tmp_path / "ws" / "notes").exists()
    kinds = [
        json.loads(line)["kind"]
        for line in (tmp_path / "ws" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert kinds == ["run_started", "confirmation_declined"]
