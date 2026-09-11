"""Tests for the core configuration contract and its YAML loader."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from local_ai_control_center.adapters.ollama import resolve_engine_host
from local_ai_control_center.core.config import Config, load_config, load_dotenv, parse_dotenv
from local_ai_control_center.ports.provider import ProviderError


@pytest.fixture
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give the test its own copy of the environment.

    `load_dotenv` mutates `os.environ`, which is what a dotenv is for and also what makes
    it hazardous in a suite: one test setting OLLAMA_HOST leaked into every provider test
    that reads it. Swapping in a copy contains the mutation without pretending it is not
    global.
    """
    monkeypatch.setattr(os, "environ", dict(os.environ))


def test_defaults_are_safe() -> None:
    """Network access is off by default; audit level is standard."""
    config = Config(workspace_root=Path("/tmp/lacc"))
    assert config.network_access is False
    assert config.audit_level == "standard"


def test_workspace_root_is_required() -> None:
    """Omitting workspace_root is a validation error (no universal default)."""
    with pytest.raises(ValidationError):
        Config()  # type: ignore[call-arg]


def test_unknown_field_is_rejected() -> None:
    """An unknown field fails loudly instead of being ignored."""
    with pytest.raises(ValidationError):
        Config(workspace_root=Path("/tmp/lacc"), unknown_field=True)  # type: ignore[call-arg]


def test_invalid_audit_level_is_rejected() -> None:
    """audit_level outside the closed set is rejected at the boundary."""
    with pytest.raises(ValidationError):
        Config(workspace_root=Path("/tmp/lacc"), audit_level="verbose")  # type: ignore[arg-type]


def test_config_is_frozen() -> None:
    """A validated config cannot be mutated afterwards."""
    config = Config(workspace_root=Path("/tmp/lacc"))
    with pytest.raises(ValidationError):
        config.network_access = True  # type: ignore[misc]


def test_load_config_reads_yaml(tmp_path: Path) -> None:
    """A well-formed YAML file loads into a validated Config."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "network_access: true\naudit_level: full\nworkspace_root: /data/lacc\n",
        encoding="utf-8",
    )
    config = load_config(config_file)
    assert config.network_access is True
    assert config.audit_level == "full"
    assert config.workspace_root == Path("/data/lacc")


def test_load_config_absent_field_takes_default(tmp_path: Path) -> None:
    """A field absent from the file takes its default (network stays off)."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("workspace_root: /data/lacc\n", encoding="utf-8")
    config = load_config(config_file)
    assert config.network_access is False


def test_load_config_rejects_non_mapping(tmp_path: Path) -> None:
    """A YAML file that is not a mapping fails with a clear error."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(config_file)


def test_output_language_defaults_to_english() -> None:
    """The answer's language is named, not left to the model. English by default."""
    assert Config(workspace_root=Path("/tmp/lacc")).output_language == "English"


def test_blank_output_language_is_rejected() -> None:
    """An empty language is a clear error, not a fallback to whatever the model picks."""
    for blank in ("", "   ", "\t\n"):
        with pytest.raises(ValidationError):
            Config(workspace_root=Path("/tmp/lacc"), output_language=blank)


def test_output_language_is_normalized() -> None:
    """Whitespace is stripped once at the boundary, so a prompt never carries it."""
    config = Config(workspace_root=Path("/tmp/lacc"), output_language="  Spanish  ")
    assert config.output_language == "Spanish"


def test_max_input_bytes_has_a_generous_default() -> None:
    """A ceiling exists without anyone configuring one."""
    assert Config(workspace_root=Path("/tmp/lacc")).max_input_bytes == 32 * 1024 * 1024


def test_max_input_bytes_must_be_a_real_ceiling() -> None:
    """Zero or negative would refuse every file: a way to switch LACC off by accident."""
    for value in (0, -1):
        with pytest.raises(ValidationError):
            Config(workspace_root=Path("/tmp/lacc"), max_input_bytes=value)


def test_context_tokens_is_unset_by_default() -> None:
    """A guessed window is worse than none, so there is no default."""
    assert Config(workspace_root=Path("/tmp/lacc")).context_tokens is None


def test_context_tokens_must_be_a_usable_window() -> None:
    """Unknown is a state LACC handles; zero is not a smaller window, it is a broken one."""
    for value in (0, -4096):
        with pytest.raises(ValidationError):
            Config(workspace_root=Path("/tmp/lacc"), context_tokens=value)


def test_no_engine_host_means_nothing_leaves_the_machine(tmp_path: Path) -> None:
    """The default. Reported as empty rather than as a loopback address."""
    assert Config(workspace_root=tmp_path).remote_engine == ""


def test_a_loopback_engine_is_not_a_remote_one(tmp_path: Path) -> None:
    """Talking to an engine here is inter-process communication, not a departure."""
    for host in ("localhost:11434", "http://127.0.0.1:11434", "http://[::1]:11434"):
        config = Config(workspace_root=tmp_path, engine_host=host)
        assert config.remote_engine == "", host


def test_a_host_elsewhere_is_reported_with_its_scheme(tmp_path: Path) -> None:
    """What the preview shows a person before they confirm (ADR-028)."""
    config = Config(workspace_root=tmp_path, engine_host="desk:11434")
    assert config.remote_engine == "http://desk:11434"


def test_remote_engine_reports_without_judging(tmp_path: Path) -> None:
    """It answers "is this machine" and nothing else.

    Whether reaching that host is permitted is `network_access`, and refusing an
    unpermitted one stays the provider's job. Two questions, deliberately not merged: a
    reporter that also refused could not be used to tell someone what is about to happen.
    """
    config = Config(workspace_root=tmp_path, engine_host="http://desk:11434")
    assert config.network_access is False
    assert config.remote_engine == "http://desk:11434"


def test_a_value_written_where_a_variable_name_belongs_is_refused(tmp_path: Path) -> None:
    """The misreading that put a live token into a file, caught at load instead.

    Before this, LACC looked for a variable with that literal name, found none, and
    reported itself unconfigured. A silence that follows a plausible misreading is a
    design problem, not a user error.
    """
    for field, value in [
        ("server_url_env", "http://100.76.182.73:8080"),
        ("topic_env", "lacc-tesis"),
    ]:
        with pytest.raises(ValidationError):
            Config(
                workspace_root=tmp_path,
                notifier={"ntfy": {"enabled": True, field: value}},
            )


def test_a_token_shaped_like_an_identifier_is_still_refused(tmp_path: Path) -> None:
    """The case a shape check misses, and the one that matters most.

    `tk_f0yn7rfgs48l94eq41y5u7ddh2irw` is a valid identifier, so requiring "looks like a
    name" would accept the very thing this field exists to keep out of files. Upper case
    is what separates the name of a variable from the value of one.
    """
    with pytest.raises(ValidationError):
        Config(
            workspace_root=tmp_path,
            notifier={"ntfy": {"enabled": True, "token_env": "tk_f0yn7rfgs48l94eq41y5u7"}},
        )


def test_the_error_says_what_to_put_there_instead(tmp_path: Path) -> None:
    """A refusal that does not teach the fix just moves the confusion."""
    with pytest.raises(ValidationError) as caught:
        Config(workspace_root=tmp_path, notifier={"ntfy": {"topic_env": "lacc-tesis"}})
    message = str(caught.value)
    assert "NTFY_TOPIC" in message
    assert "upper case" in message


def test_ordinary_variable_names_are_accepted(tmp_path: Path) -> None:
    """The defaults, and anything else spelled the way variables are spelled."""
    config = Config(
        workspace_root=tmp_path,
        notifier={"ntfy": {"server_url_env": "MY_SERVER", "topic_env": "LACC_TOPIC_2"}},
    )
    assert config.notifier.ntfy.server_url_env == "MY_SERVER"


def test_a_dotenv_supplies_the_variables_the_configuration_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_environment: None
) -> None:
    """The point: values live beside the configuration without living inside it."""
    monkeypatch.delenv("NTFY_TOKEN", raising=False)
    (tmp_path / ".env").write_text("NTFY_TOKEN=tk_secret\n", encoding="utf-8")
    assert load_dotenv(tmp_path) == ("NTFY_TOKEN",)
    assert os.environ["NTFY_TOKEN"] == "tk_secret"


def test_the_real_environment_always_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A server, a CI job or a deliberate export keeps the last word.

    The file fills what is missing; it does not override what someone set on purpose.
    """
    monkeypatch.setenv("NTFY_TOKEN", "from_the_shell")
    (tmp_path / ".env").write_text("NTFY_TOKEN=from_the_file\n", encoding="utf-8")
    assert load_dotenv(tmp_path) == ()
    assert os.environ["NTFY_TOKEN"] == "from_the_shell"


def test_no_dotenv_is_not_an_error(tmp_path: Path) -> None:
    """Most installations have none. It means there was nothing to add."""
    assert load_dotenv(tmp_path) == ()


def test_comments_blank_lines_quotes_and_export_are_handled(tmp_path: Path) -> None:
    """The shapes a person actually writes, including one copied from a shell profile."""
    parsed = parse_dotenv(
        "\n".join(
            [
                "# a comment",
                "",
                "NTFY_SERVER=http://desk:8080",
                'NTFY_TOPIC="lacc-tesis"',
                "export NTFY_TOKEN='tk_secret'",
            ]
        )
    )
    assert parsed == {
        "NTFY_SERVER": "http://desk:8080",
        "NTFY_TOPIC": "lacc-tesis",
        "NTFY_TOKEN": "tk_secret",
    }


def test_a_malformed_line_costs_one_variable_not_the_run(tmp_path: Path) -> None:
    """The file exists to supply credentials; failing everything over a stray line is worse.

    The variable that did not arrive announces itself clearly when it is looked up.
    """
    parsed = parse_dotenv("this line has no equals sign\nNTFY_TOPIC=lacc\n")
    assert parsed == {"NTFY_TOPIC": "lacc"}


def test_a_dotenv_cannot_smuggle_in_a_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_environment: None
) -> None:
    """The load-bearing half: no environment may widen what LACC contacts.

    `.env` supplies secrets. Where documents go is `engine_host` in a file the user wrote,
    and an inherited variable redirecting them is the failure ADR-027 exists to prevent
    (ADR-030).
    """
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    (tmp_path / ".env").write_text(
        "OLLAMA_HOST=http://somewhere-else:11434\nengine_host=http://elsewhere:11434\n",
        encoding="utf-8",
    )
    load_dotenv(tmp_path)
    assert os.environ["OLLAMA_HOST"] == "http://somewhere-else:11434"

    config = Config(workspace_root=tmp_path)
    assert config.engine_host == ""
    assert config.remote_engine == ""
    with pytest.raises(ProviderError):
        resolve_engine_host(config.engine_host, network_access=True)
