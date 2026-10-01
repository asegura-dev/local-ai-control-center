"""Characters a conversion delivered in halves (ADR-122).

`lckd.pdf` carried ten lone halves of mathematical letters. Its conversion ended a batch of 65
in a traceback, left the run without an end and left an empty `lckd.md` behind. These tests
hold each of the four.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from local_ai_control_center import cli
from local_ai_control_center.adapters.documents import converter_for
from local_ai_control_center.cli import app
from local_ai_control_center.core.surrogates import REPLACEMENT, whole_characters
from local_ai_control_center.cycle import write_new_file
from local_ai_control_center.ports.converter import ConversionError, Converter

runner = CliRunner()
HIGH, LOW = "\ud835", "\udc31"
"""The two halves of U+1D431, a bold small x, as an extractor can hand them over."""


def test_a_pair_of_halves_is_joined_into_its_character() -> None:
    assert whole_characters(f"x {HIGH}{LOW} y") == ("x \U0001d431 y", 0)


def test_a_lone_half_is_replaced_and_counted() -> None:
    assert whole_characters(f"a{HIGH}b{LOW}c") == (f"a{REPLACEMENT}b{REPLACEMENT}c", 2)


def test_text_without_halves_is_returned_as_it_was() -> None:
    text = "Dice of 0.517, 0.583 and 0.600 in PSMA."
    joined, replaced = whole_characters(text)
    assert joined is text and replaced == 0


def test_a_file_is_created_only_when_its_text_can_be_written(tmp_path: Path) -> None:
    """It used to be created first, and left at 0 bytes when the write failed."""
    target = tmp_path / "lckd.md"
    with pytest.raises(ConversionError, match="cannot be written as UTF-8"):
        write_new_file(target, f"text {HIGH} more")
    assert not target.exists()


class _Halves(Converter):
    """A converter that hands over a lone half, as `lckd.pdf` did."""

    @property
    def name(self) -> str:
        return "halves"

    @property
    def suffixes(self) -> frozenset[str]:
        return frozenset({".pdf"})

    def extract_text(self, path: Path) -> str:
        return f"The loss {HIGH} is minimised over the training set."


class _Broken(Converter):
    """A converter that fails in a way nobody wrote a sentence for."""

    @property
    def name(self) -> str:
        return "broken"

    @property
    def suffixes(self) -> frozenset[str]:
        return frozenset({".pdf"})

    def extract_text(self, path: Path) -> str:
        raise RuntimeError("an unforeseen failure inside the converter")


def _workspace_with(tmp_path: Path, make_pdf: Callable[..., Path], *names: str) -> Path:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    for name in names:
        (workspace / name).write_bytes(make_pdf(f"The text of {name}.").read_bytes())
    config = tmp_path / "config.yaml"
    config.write_text(f"workspace_root: {workspace}{chr(10)}", encoding="utf-8")
    return config


def test_halves_are_written_as_replacement_and_said(
    tmp_path: Path, make_pdf: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace_with(tmp_path, make_pdf, "lckd.pdf")
    monkeypatch.setattr(cli, "converter_for", lambda path: _Halves())
    result = runner.invoke(app, ["ingest", "lckd.pdf", "-c", str(config)], input="y\n")
    assert result.exit_code == 0, result.stdout
    written = (tmp_path / "ws" / "lckd.md").read_text(encoding="utf-8")
    assert REPLACEMENT in written and "minimised" in written
    said = " ".join(result.stdout.split())
    assert "1 character arrived in halves and was written as" in said
    trail = (tmp_path / "ws" / "audit.jsonl").read_text(encoding="utf-8")
    assert '"halves_replaced": 1' in trail or '"halves_replaced":1' in trail


def test_one_document_failing_unexpectedly_costs_that_document(
    tmp_path: Path, make_pdf: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """It cost the batch: 25 documents after `lckd.pdf` were never converted."""
    config = _workspace_with(tmp_path, make_pdf, "bad.pdf", "good.pdf")
    monkeypatch.setattr(
        cli,
        "converter_for",
        lambda path: _Broken() if path.name == "bad.pdf" else converter_for(path),
    )
    result = runner.invoke(app, ["ingest", "bad.pdf", "good.pdf", "-c", str(config)], input="y\n")
    assert result.exit_code == 0, result.stdout
    assert result.exception is None or isinstance(result.exception, SystemExit)
    workspace = tmp_path / "ws"
    assert "The text of good.pdf" in (workspace / "good.md").read_text(encoding="utf-8")
    assert not (workspace / "bad.md").exists(), "no empty file is left behind"
    said = " ".join(result.stdout.split())
    assert "1 of 2 documents converted" in said and "RuntimeError" in said


def test_a_run_that_fails_unexpectedly_still_ends(
    tmp_path: Path, make_pdf: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """It was left with `run_started` and `permission_granted`, and nothing after."""
    import json

    config = _workspace_with(tmp_path, make_pdf, "bad.pdf")
    monkeypatch.setattr(cli, "converter_for", lambda path: _Broken())
    runner.invoke(app, ["ingest", "bad.pdf", "-c", str(config)], input="y\n")
    lines = (tmp_path / "ws" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    kinds = [json.loads(line)["kind"] for line in lines]
    assert kinds[-1] == "ingestion_failed"
    assert json.loads(lines[-1])["detail"]["unexpected"] is True
