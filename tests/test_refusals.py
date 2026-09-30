"""A refusal, not a traceback (ADR-114).

Each case here was a decision the program made correctly and showed as a crash: a broken
configuration, an engine the configuration forbids, a destination it may not write, a folder
that is a file. The decision stays; what changes is that it is said, before any work, and that
nothing is left behind - no folder, no file, no run without an end.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from local_ai_control_center.cli import app
from local_ai_control_center.core.config import load_config

runner = CliRunner()
REMOTE = "http://100.64.0.1:11434"


def _config(tmp_path: Path, *extra: str, workspace: str = "ws") -> Path:
    config = tmp_path / "config.yaml"
    lines = [f"workspace_root: {tmp_path / workspace}", *extra]
    config.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    return config


def _said(result: object) -> str:
    return " ".join(getattr(result, "stdout", "").split())


def _refused(result: object) -> None:
    """Ended with 1 and a sentence - not with an exception the runner caught."""
    assert getattr(result, "exit_code", None) == 1, getattr(result, "stdout", "")
    exception = getattr(result, "exception", None)
    assert exception is None or isinstance(exception, SystemExit), repr(exception)


# --- a configuration that is not YAML ----------------------------------------------------------


def test_a_broken_configuration_is_named_with_where_it_breaks(tmp_path: Path) -> None:
    config = tmp_path / "roto.yaml"
    config.write_text("model: [qwen2.5:14b" + chr(10), encoding="utf-8")
    with pytest.raises(ValueError, match="roto.yaml is not valid YAML at line"):
        load_config(config)
    result = runner.invoke(app, ["status", "-c", str(config)])
    _refused(result)
    assert "roto.yaml is not valid YAML at line" in _said(result)


# --- an engine the configuration forbids --------------------------------------------------------


def _forbidden_engine(tmp_path: Path) -> Path:
    """Everything each command needs to reach the point where it would call the engine."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    quote = "The sensitivity for pelvic lymph nodes was 82 per cent."
    (workspace / "paper.md").write_text(quote + chr(10), encoding="utf-8")
    (workspace / "citas.md").write_text(
        chr(10).join(
            [
                "## paper.md",
                "",
                "*1 of 1 quotations are in the document.*",
                "",
                f"> {quote}",
                "",
                "p. 1 - detection sensitivity",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "borrador.md").write_text(
        "La sensibilidad del PET con PSMA para los ganglios pélvicos fue de 82 por ciento en "
        "la cohorte que se describe, y eso sostiene el resto del capítulo." + chr(10),
        encoding="utf-8",
    )
    (workspace / "temas.md").write_text(
        "un tema" + chr(10) + "! control" + chr(10), encoding="utf-8"
    )
    return _config(tmp_path, f"engine_host: {REMOTE}", "embedding_model: bge-m3")


@pytest.mark.parametrize(
    "arguments",
    [
        ["ask", "¿qué dice?", "--from", "citas.md"],
        ["review", "borrador.md", "--against", "citas.md"],
        ["coverage", "temas.md", "--against", "citas.md"],
        ["engine", "test"],
    ],
)
def test_an_engine_off_this_machine_with_the_network_off_is_refused_in_words(
    tmp_path: Path, arguments: list[str]
) -> None:
    config = _forbidden_engine(tmp_path)
    result = runner.invoke(app, [*arguments, "-c", str(config)], input="y\ny\n")
    _refused(result)
    assert "network_access is off" in _said(result)
    assert not (tmp_path / "ws" / "audit.jsonl").exists(), "nothing was started"


# --- a destination the command may not write ---------------------------------------------------


def test_a_destination_outside_is_refused_before_any_work(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.md").write_text("x" + chr(10), encoding="utf-8")
    config = _config(tmp_path)
    for arguments in (
        ["corpus", "a.md", "--into", "../fuera.md"],
        ["review", "a.md", "--against", "a.md", "--into", "../fuera.md"],
        ["coverage", "a.md", "--against", "a.md", "--into", "../fuera.md"],
    ):
        result = runner.invoke(app, [*arguments, "-c", str(config)], input="y\n")
        _refused(result)
        said = _said(result)
        assert "escapes workspace boundary" in said and "Nothing was done" in said
    assert not (tmp_path / "fuera.md").exists()
    assert not (workspace / "audit.jsonl").exists()


def test_a_destination_already_there_is_refused_before_the_engine_is_asked(
    tmp_path: Path,
) -> None:
    """`review` used to find this out after judging every paragraph."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.md").write_text("x" + chr(10), encoding="utf-8")
    (workspace / "informe.md").write_text("mío" + chr(10), encoding="utf-8")
    config = _config(tmp_path)
    result = runner.invoke(
        app, ["review", "a.md", "--against", "a.md", "--into", "informe.md", "-c", str(config)]
    )
    _refused(result)
    assert "informe.md already exists" in _said(result)
    assert (workspace / "informe.md").read_text(encoding="utf-8") == "mío" + chr(10)
    assert not (workspace / "audit.jsonl").exists()


# --- where bring would put the copy ------------------------------------------------------------


def _outside_draft(tmp_path: Path) -> Path:
    outside = tmp_path / "boveda"
    outside.mkdir()
    draft = outside / "03.md"
    draft.write_text("Un capítulo." + chr(10), encoding="utf-8")
    return draft


def test_bring_refuses_a_drafts_that_is_a_file_before_asking(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "drafts").write_text("no soy una carpeta", encoding="utf-8")
    config = _config(tmp_path)
    result = runner.invoke(
        app, ["bring", str(_outside_draft(tmp_path)), "-c", str(config)], input="y\n"
    )
    _refused(result)
    assert "drafts is a file here" in _said(result)
    assert "Bring it?" not in result.stdout
    assert not (workspace / "audit.jsonl").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="a junction is a Windows folder link")
def test_bring_refuses_a_drafts_that_leads_outside_before_asking(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(workspace / "drafts"), str(elsewhere)],
        check=True,
        capture_output=True,
    )
    config = _config(tmp_path)
    result = runner.invoke(
        app, ["bring", str(_outside_draft(tmp_path)), "-c", str(config)], input="y\n"
    )
    _refused(result)
    assert "leads outside the workspace" in _said(result)
    assert list(elsewhere.iterdir()) == []


# --- a workspace that does not exist -----------------------------------------------------------


def test_a_command_that_only_reads_does_not_create_the_workspace(tmp_path: Path) -> None:
    config = _config(tmp_path, workspace="no-existe/a/b")
    for arguments in (["status"], ["verify"]):
        result = runner.invoke(app, [*arguments, "-c", str(config)])
        _refused(result)
        assert "does not exist" in _said(result)
    assert not (tmp_path / "no-existe").exists()


def test_a_command_that_writes_creates_the_workspace_and_says_so(tmp_path: Path) -> None:
    config = _config(tmp_path, workspace="nuevo")
    result = runner.invoke(
        app, ["bring", str(_outside_draft(tmp_path)), "-c", str(config)], input="n\n"
    )
    assert result.exit_code == 0, result.stdout
    assert "Created the workspace" in _said(result)
    assert (tmp_path / "nuevo").is_dir()
