"""What the bottom of the window says, and what it does not do to find out (ADR-077)."""

from __future__ import annotations

from pathlib import Path

from local_ai_control_center.core.config import Config
from local_ai_control_center.features.status import EngineSeen, status_of


def _config(root: Path, **fields: object) -> Config:
    return Config(workspace_root=root, **fields)


def test_a_corpus_is_not_also_counted_as_a_document(tmp_path: Path) -> None:
    """This asserted 2 documents for one paper and one corpus, and the bar said so.

    Every Markdown file counted as a document, so a real workspace read **61 documents**
    where the same workspace held 28 - and nobody saw it, because the half of the bar that
    says it was packed off the right edge of the window (ADR-092).
    """
    (tmp_path / "a-paper.md").write_text("Some prose.", encoding="utf-8")
    (tmp_path / "corpus.md").write_text(
        "# Collected quotations\n\n## a.md\n\n> a quotation here\n\np. 1 - verified\n\na claim\n",
        encoding="utf-8",
    )
    seen = status_of(tmp_path, _config(tmp_path))
    assert seen.documents == 1
    assert seen.corpora == 1
    assert seen.quotations == 1
    assert "1 documents" in seen.material


def test_the_standing_context_is_not_a_document_here_either(tmp_path: Path) -> None:
    """What makes it not one to count is a setting, so the caller says which it is."""
    (tmp_path / "a-paper.md").write_text("Some prose.", encoding="utf-8")
    (tmp_path / "contexto.md").write_text("what this thesis argues", encoding="utf-8")
    assert status_of(tmp_path, _config(tmp_path)).documents == 2
    assert status_of(tmp_path, _config(tmp_path), "contexto.md").documents == 1


def test_with_no_corpus_it_says_so_rather_than_showing_a_zero(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("prose", encoding="utf-8")
    assert "no corpus yet" in status_of(tmp_path, _config(tmp_path)).material


def test_the_reach_is_what_the_configuration_allows(tmp_path: Path) -> None:
    """Read from the file. Nothing is asked of anything."""
    off = status_of(tmp_path, _config(tmp_path))
    assert "nothing leaves this machine" in off.reach

    on = status_of(
        tmp_path,
        _config(
            tmp_path,
            network_access=True,
            engine_host="http://10.0.0.2:11434",
            registry_url="https://api.crossref.org",
        ),
    )
    assert "10.0.0.2" in on.reach
    assert "registry allowed" in on.reach


def test_not_checked_is_not_the_same_as_unreachable() -> None:
    """The window never asks on opening, so the bar has to say which it is."""
    assert EngineSeen().said == "not checked"
    assert EngineSeen(asked=True).said == "unreachable"
    assert EngineSeen(asked=True, reached=True, models=4).said == "reached, 4 models, no answer"
    assert "1.2s" in EngineSeen(asked=True, reached=True, answered=True, seconds=1.2).said


def test_a_workspace_that_is_not_there_says_nothing_and_does_not_raise(tmp_path: Path) -> None:
    seen = status_of(tmp_path / "nowhere", _config(tmp_path))
    assert seen.documents == 0
