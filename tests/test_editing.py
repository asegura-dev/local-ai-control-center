"""What the window may change about a configuration, and what it may not (ADR-094).

**The window may change what LACC does. It may not change what LACC is allowed to do.**
`network_access` and `workspace_in_repository` are not settings - they are refusals being
lifted, and the whole weight of them is that somebody wrote them down deliberately. The first
two tests are the ones that matter.
"""

from __future__ import annotations

import yaml

from local_ai_control_center.core.config import Config
from local_ai_control_center.features.editing import (
    CHANGEABLE,
    FILE_ONLY,
    Wanted,
    ceiling_of,
    changed,
    differences,
    settings_shown,
)

NOW = """workspace_root: ~/lacc-workspace
model: qwen2.5:14b
context_tokens: 32768
network_access: true
engine_host: http://desk:11434
"""


def _config(**over: object) -> Config:
    settings: dict[str, object] = {"workspace_root": "workspace", "model": "qwen2.5:14b"}
    settings.update(over)
    return Config(**settings)  # type: ignore[arg-type]


# --- the line ------------------------------------------------------------------------------


def test_the_ceiling_cannot_be_changed_from_the_window() -> None:
    """A toggle is not a deliberate decision, and these two exist to be deliberate."""
    after, refused = changed(NOW, (Wanted(key="network_access", value="false"),))
    assert after == NOW
    assert [one.key for one in refused] == ["network_access"]
    assert "network_access: true" in after


def test_the_refusal_to_work_inside_a_repository_cannot_be_lifted_here() -> None:
    after, refused = changed(NOW, (Wanted(key="workspace_in_repository", value="true"),))
    assert after == NOW
    assert refused


def test_neither_of_the_two_is_offered_as_a_field() -> None:
    keys = {key for key, _ in CHANGEABLE}
    assert keys.isdisjoint({key for key, _ in FILE_ONLY})
    assert {key for key, _ in FILE_ONLY} == {"network_access", "workspace_in_repository"}


def test_both_are_shown_with_why_they_are_not_here() -> None:
    """Shown, not hidden: a setting you cannot find is a setting you cannot check."""
    shown = ceiling_of(_config(network_access=True))
    assert [key for key, _, _ in shown] == ["network_access", "workspace_in_repository"]
    assert all(why for _, _, why in shown)


def test_the_host_is_changeable_because_the_ceiling_makes_it_inert() -> None:
    """Naming a host LACC may not reach changes nothing."""
    after, refused = changed(NOW, (Wanted(key="engine_host", value="http://other:11434"),))
    assert not refused
    assert yaml.safe_load(after)["engine_host"] == "http://other:11434"


def test_the_audit_level_is_changeable_because_it_records_rather_than_reaches() -> None:
    """Lowering it is how a workspace that synchronises stops carrying your prose."""
    after, refused = changed(NOW, (Wanted(key="audit_level", value="standard"),))
    assert not refused
    assert yaml.safe_load(after)["audit_level"] == "standard"


# --- what a change costs --------------------------------------------------------------------


def test_an_empty_value_removes_the_setting_rather_than_writing_an_empty_one() -> None:
    """Which is how a default is restored."""
    after, refused = changed(NOW, (Wanted(key="context_tokens", value=""),))
    assert not refused
    assert "context_tokens" not in yaml.safe_load(after)


def test_a_value_the_contract_refuses_is_named_and_nothing_is_written() -> None:
    """The same refusal a run would meet, not a second opinion about what is allowed."""
    after, refused = changed(NOW, (Wanted(key="context_tokens", value="not a number"),))
    assert after == NOW
    assert refused


def test_a_file_that_is_not_a_mapping_is_refused_rather_than_replaced() -> None:
    after, refused = changed("- a list\n- of things\n", (Wanted(key="model", value="x"),))
    assert after == "- a list\n- of things\n"
    assert refused


def test_the_diff_says_both_sides_of_every_line_that_changes() -> None:
    after, _ = changed(NOW, (Wanted(key="model", value="qwen2.5:32b"),))
    lines = differences(NOW, after, "denso.yaml")
    assert any(line.startswith("-") and "qwen2.5:14b" in line for line in lines)
    assert any(line.startswith("+") and "qwen2.5:32b" in line for line in lines)


def test_nothing_changing_gives_an_empty_diff() -> None:
    after, refused = changed(NOW, (Wanted(key="model", value="qwen2.5:14b"),))
    assert not refused
    assert not differences(NOW, after, "denso.yaml")


def test_every_field_shown_says_what_it_decides() -> None:
    """A form of names is a form you have to already understand."""
    shown = settings_shown(NOW, _config(context_tokens=32_768))
    assert all(says for _, _, says in shown)
    assert dict((key, value) for key, value, _ in shown)["model"] == "qwen2.5:14b"


def test_a_field_shows_what_the_file_says_not_what_the_contract_parsed() -> None:
    """Filling a box from the parsed value made every untouched box a change."""
    shown = dict((key, value) for key, value, _ in settings_shown(NOW, _config()))
    assert shown["workspace_root"] == "~/lacc-workspace"


def test_a_setting_the_file_never_mentions_is_empty_and_says_its_default() -> None:
    shown = {key: (value, says) for key, value, says in settings_shown(NOW, _config())}
    value, says = shown["output_language"]
    assert value == ""
    assert "the default is English" in says


def test_a_form_nobody_touched_changes_nothing() -> None:
    """The one that matters: Check on an untouched form proposed rewriting three lines."""
    typed = tuple(Wanted(key=key, value=value) for key, value, _ in settings_shown(NOW, _config()))
    after, refused = changed(NOW, typed)
    assert not refused
    assert after == NOW
    assert not differences(NOW, after, "denso.yaml")


def test_a_comment_survives_a_change_to_another_line() -> None:
    """The file is edited line by line; only what changed changes."""
    with_note = "# what this is for\n" + NOW
    after, refused = changed(with_note, (Wanted(key="model", value="qwen2.5:32b"),))
    assert not refused
    assert after.startswith("# what this is for")
    assert "engine_host: http://desk:11434" in after


def test_what_is_written_is_a_configuration_that_loads(tmp_path) -> None:  # type: ignore[no-untyped-def]
    after, refused = changed(NOW, (Wanted(key="model", value="qwen2.5:32b"),))
    assert not refused
    path = tmp_path / "made.yaml"
    path.write_text(after, encoding="utf-8")
    from local_ai_control_center.core.config import load_config

    assert load_config(path).model == "qwen2.5:32b"
