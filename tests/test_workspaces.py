"""Which workspace a configuration names, and what it costs to put one somewhere (ADR-093).

The tests that matter are about the difference between a **fact** and a **guess**. A git
working tree is a fact and is refused; a folder whose name looks like a synchroniser is a
guess and is warned about, because refusing on a guess teaches people that this program's
refusals are noise (ADR-022).
"""

from __future__ import annotations

from pathlib import Path

from local_ai_control_center.core.config import Config
from local_ai_control_center.features.workspaces import (
    as_yaml,
    intended,
    points_of,
    risk_of,
)

WRITTEN = """workspace_root: {root}
model: qwen2.5:14b
context_tokens: 32768
"""


def _config(**over: object) -> Config:
    settings: dict[str, object] = {
        "workspace_root": "workspace",
        "model": "qwen2.5:14b",
        "context_tokens": 32_768,
    }
    settings.update(over)
    return Config(**settings)  # type: ignore[arg-type]


# --- what each configuration points at -----------------------------------------------------


def test_each_configuration_is_listed_with_the_workspace_it_names(tmp_path: Path) -> None:
    configs = tmp_path / "configs"
    configs.mkdir()
    work = tmp_path / "somewhere"
    work.mkdir()
    (configs / "one.yaml").write_text(WRITTEN.format(root=work.as_posix()), encoding="utf-8")
    found = points_of(configs)
    assert [one.name for one in found] == ["one.yaml"]
    assert found[0].workspace == str(work)
    assert found[0].model == "qwen2.5:14b"
    assert found[0].exists


def test_a_workspace_that_is_not_there_yet_is_said_to_be_missing(tmp_path: Path) -> None:
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "one.yaml").write_text(
        WRITTEN.format(root=(tmp_path / "not-yet").as_posix()), encoding="utf-8"
    )
    assert not points_of(configs)[0].exists


def test_a_configuration_that_cannot_be_read_is_named_rather_than_skipped(
    tmp_path: Path,
) -> None:
    """A picker missing an entry looks like a file that was never written."""
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "broken.yaml").write_text("this: [is not: valid", encoding="utf-8")
    found = points_of(configs)
    assert len(found) == 1
    assert found[0].name == "broken.yaml"
    assert found[0].unreadable


# --- a fact is refused, a guess is warned about --------------------------------------------


def test_a_git_working_tree_is_refused_because_that_is_a_fact(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    inside = tmp_path / "work"
    inside.mkdir()
    danger = risk_of(inside)
    assert not danger.usable
    assert "git add -A" in danger.refused


def test_a_folder_that_looks_synchronised_is_warned_about_and_allowed(tmp_path: Path) -> None:
    """A folder called Dropbox may sync nothing; a folder called work may sync everything."""
    inside = tmp_path / "OneDrive" / "research"
    inside.mkdir(parents=True)
    danger = risk_of(inside)
    assert danger.usable
    assert danger.warned
    assert danger.advice


def test_the_warning_names_a_setting_that_exists(tmp_path: Path) -> None:
    """It said `audit_level: metadata`, which is not one of the two levels there are."""
    inside = tmp_path / "OneDrive" / "research"
    inside.mkdir(parents=True)
    advice = risk_of(inside).advice
    assert "audit_level: standard" in advice
    assert "metadata" not in advice


def test_an_ordinary_folder_is_neither_refused_nor_warned_about(tmp_path: Path) -> None:
    assert risk_of(tmp_path) == risk_of(tmp_path)
    assert risk_of(tmp_path).usable
    assert not risk_of(tmp_path).warned


# --- what would be written -----------------------------------------------------------------


def test_a_name_without_a_suffix_gets_one(tmp_path: Path) -> None:
    assert intended("another", tmp_path, _config()).name == "another.yaml"
    assert intended("another.yaml", tmp_path, _config()).name == "another.yaml"


def test_the_engine_settings_come_with_it(tmp_path: Path) -> None:
    """A configuration without them is a workspace that cannot do anything."""
    written = as_yaml(
        tmp_path,
        _config(network_access=True, engine_host="http://desk:11434", embedding_model="bge-m3"),
    )
    assert "model: qwen2.5:14b" in written
    assert "context_tokens: 32768" in written
    assert "embedding_model: bge-m3" in written
    assert "network_access: true" in written
    assert "engine_host: http://desk:11434" in written


def test_nothing_of_the_old_workspace_comes_with_it() -> None:
    # Fixed paths, not `tmp_path`: pytest names a temporary directory after the test, so a
    # test looking for "old" in the output finds it in its own directory name.
    written = as_yaml(Path("/fresh/place"), _config(workspace_root="/somewhere/previous"))
    assert "previous" not in written
    assert "/fresh/place" in written


def test_a_full_audit_level_is_carried_rather_than_quietly_lowered() -> None:
    """Recording less than the configuration it was copied from is a decision to make."""
    where = Path("/fresh/place")
    assert "audit_level: full" in as_yaml(where, _config(audit_level="full"))
    assert "audit_level" not in as_yaml(where, _config())


def test_what_is_written_is_a_configuration_that_loads(tmp_path: Path) -> None:
    """The point of writing the keys by hand is that the result is an ordinary file."""
    from local_ai_control_center.core.config import load_config

    path = tmp_path / "made.yaml"
    path.write_text(as_yaml(tmp_path / "work", _config(embedding_model="bge-m3")), encoding="utf-8")
    loaded = load_config(path)
    assert Path(loaded.workspace_root) == tmp_path / "work"
    assert loaded.model == "qwen2.5:14b"
    assert loaded.embedding_model == "bge-m3"
