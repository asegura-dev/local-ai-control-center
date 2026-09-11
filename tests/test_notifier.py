"""Tests for the notifier port and its ntfy adapter.

Every test injects the transport. Nothing here opens a socket, so the egress guard from
ADR-022 stays exactly as strict as it was while LACC gains the ability to reach out.
"""

from __future__ import annotations

import urllib.error
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from local_ai_control_center.adapters.ntfy import (
    NtfyNotifier,
    basic_authorization,
    notifier_from_config,
)
from local_ai_control_center.core.config import Config
from local_ai_control_center.ports.notifier import Notification, NotifierMisconfigured


class _Recorder:
    """A transport that records the call instead of making it."""

    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.url = ""
        self.body = b""
        self.headers: Mapping[str, str] = {}
        self.calls = 0

    def __call__(self, url: str, body: bytes, headers: Mapping[str, str], timeout: float) -> int:
        self.calls += 1
        self.url = url
        self.body = body
        self.headers = headers
        return self.status


def _config(tmp_path: Path, **kwargs: object) -> Config:
    return Config(workspace_root=tmp_path, **kwargs)  # type: ignore[arg-type]


def test_the_topic_becomes_the_path_of_the_named_server() -> None:
    """A notification goes to the server the user named, and nowhere else."""
    post = _Recorder()
    NtfyNotifier("https://ntfy.example/", "lacc", post=post).send(Notification(title="t", body="b"))
    assert post.url == "https://ntfy.example/lacc"


def test_a_token_travels_as_a_bearer_credential() -> None:
    """The token comes from the environment and is sent as authorization, not in the body."""
    post = _Recorder()
    NtfyNotifier("http://desk:8080", "lacc", token="tk_secret", post=post).send(
        Notification(title="t", body="b")
    )
    assert post.headers["Authorization"] == "Bearer tk_secret"
    assert b"tk_secret" not in post.body


def test_title_priority_and_tags_are_headers() -> None:
    """ntfy reads them from headers; the body stays the one line of message."""
    post = _Recorder()
    NtfyNotifier("http://desk", "lacc", priority=4, tags=("robot",), post=post).send(
        Notification(title="LACC: done", body="summarize_file completed", tags=("bell",))
    )
    assert post.headers["Title"] == "LACC: done"
    assert post.headers["Priority"] == "4"
    assert post.headers["Tags"] == "robot,bell"
    assert post.body == b"summarize_file completed"


def test_a_server_that_is_not_http_is_refused() -> None:
    """The address arrives from the environment; a scheme LACC will post to is checked."""
    with pytest.raises(NotifierMisconfigured):
        NtfyNotifier("file:///etc/passwd", "lacc", post=_Recorder())


def test_a_server_without_a_host_is_refused() -> None:
    """A bare string is not a destination."""
    with pytest.raises(NotifierMisconfigured):
        NtfyNotifier("ntfy.example", "lacc", post=_Recorder())


def test_an_empty_topic_is_refused() -> None:
    """Posting to the server root is not posting to a topic."""
    with pytest.raises(NotifierMisconfigured):
        NtfyNotifier("https://ntfy.example", "   ", post=_Recorder())


def test_a_refusing_server_is_reported_not_raised() -> None:
    """Delivery is best effort: an HTTP error is an answer, not an exception."""
    delivery = NtfyNotifier("http://desk", "lacc", post=_Recorder(status=403)).send(
        Notification(title="t", body="b")
    )
    assert delivery.delivered is False
    assert "403" in delivery.detail


def test_an_unreachable_server_is_reported_not_raised() -> None:
    """The case the whole design turns on: a run that worked is not failed by this."""

    def refuse(url: str, body: bytes, headers: Mapping[str, str], timeout: float) -> int:
        raise urllib.error.URLError("no route to host")

    delivery = NtfyNotifier("http://desk", "lacc", post=refuse).send(
        Notification(title="t", body="b")
    )
    assert delivery.delivered is False
    assert "no route" in delivery.detail


def test_a_long_body_is_cut_rather_than_rejected() -> None:
    """ntfy refuses oversized bodies; a notification is not worth failing over."""
    post = _Recorder()
    NtfyNotifier("http://desk", "lacc", post=post).send(Notification(title="t", body="x" * 10_000))
    assert len(post.body) < 4096


def test_basic_credentials_encode_as_a_header_value() -> None:
    """For a server behind basic auth rather than a token."""
    assert basic_authorization("user", "pass") == "Basic dXNlcjpwYXNz"


def test_nothing_is_built_while_notifications_are_off(tmp_path: Path) -> None:
    """Off by default, like every capability."""
    assert notifier_from_config(_config(tmp_path)) is None


def test_nothing_is_built_without_network_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`network_access` is the ceiling over the notifier, not a separate switch.

    Enabling notifications does not grant the network; the configuration removes, and a
    setting that could grant reach past the ceiling would invert that (ADR-027).
    """
    monkeypatch.setenv("NTFY_SERVER", "https://ntfy.example")
    monkeypatch.setenv("NTFY_TOPIC", "lacc")
    config = _config(tmp_path, network_access=False, notifier={"ntfy": {"enabled": True}})
    assert notifier_from_config(config) is None


def test_nothing_is_built_when_the_environment_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Enabled but unconfigured is not an error: the run still worked."""
    monkeypatch.delenv("NTFY_SERVER", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    config = _config(tmp_path, network_access=True, notifier={"ntfy": {"enabled": True}})
    assert notifier_from_config(config) is None


def test_the_configuration_names_the_variables_it_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The YAML holds the name of a variable; the value stays in the environment."""
    monkeypatch.setenv("MY_SERVER", "https://ntfy.example")
    monkeypatch.setenv("MY_TOPIC", "thesis")
    monkeypatch.setenv("MY_TOKEN", "tk_secret")
    config = _config(
        tmp_path,
        network_access=True,
        notifier={
            "ntfy": {
                "enabled": True,
                "server_url_env": "MY_SERVER",
                "topic_env": "MY_TOPIC",
                "token_env": "MY_TOKEN",
            }
        },
    )
    post = _Recorder()
    notifier = notifier_from_config(config, post=post)
    assert notifier is not None
    notifier.send(Notification(title="t", body="b"))
    assert post.url == "https://ntfy.example/thesis"
    assert post.headers["Authorization"] == "Bearer tk_secret"


def test_a_misconfigured_server_in_the_environment_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A wrong value is told to the user rather than silently ignored."""
    monkeypatch.setenv("NTFY_SERVER", "ftp://desk")
    monkeypatch.setenv("NTFY_TOPIC", "lacc")
    config = _config(tmp_path, network_access=True, notifier={"ntfy": {"enabled": True}})
    with pytest.raises(NotifierMisconfigured):
        notifier_from_config(config)


def test_a_title_outside_ascii_is_folded_rather_than_raised() -> None:
    """An HTTP header is latin-1, and a character outside it raises `UnicodeEncodeError`.

    That is a `ValueError`, not an `OSError`, so a handler catching network failures would
    let it through and take down a run that had already produced its answer. Best effort
    has to mean this case too.
    """
    post = _Recorder()
    NtfyNotifier("http://desk", "lacc", post=post).send(
        Notification(title="Revisi\u00f3n lista \U0001f4c4", body="b")
    )
    title = post.headers["Title"]
    assert title.isascii()
    assert "Revision lista" in title


def test_a_newline_never_reaches_a_header() -> None:
    """Two headers where one was intended is header injection; it does not get that far."""
    post = _Recorder()
    NtfyNotifier("http://desk", "lacc", post=post).send(
        Notification(title="done\r\nX-Injected: 1", body="b")
    )
    assert "\r" not in post.headers["Title"]
    assert "\n" not in post.headers["Title"]


def test_a_transport_that_raises_a_value_error_is_still_best_effort() -> None:
    """Whatever the encoding path throws, the run that already worked is not failed."""

    def raises(url: str, body: bytes, headers: Mapping[str, str], timeout: float) -> int:
        raise UnicodeEncodeError("ascii", "x", 0, 1, "not encodable")

    delivery = NtfyNotifier("http://desk", "lacc", post=raises).send(
        Notification(title="t", body="b")
    )
    assert delivery.delivered is False


def test_a_clipped_body_is_still_valid_utf8() -> None:
    """Cutting encoded bytes is the obvious way and it splits an accented character in half."""
    post = _Recorder()
    NtfyNotifier("http://desk", "lacc", post=post).send(
        Notification(title="t", body="\u00e1" * 5000)
    )
    assert post.body.decode("utf-8")


def test_the_topic_cannot_be_written_into_the_configuration(tmp_path: Path) -> None:
    """The configuration names variables; it has no field that could hold the topic itself.

    On a shared ntfy server the topic is the only thing protecting the channel, so a
    configuration that *could* hold it is a configuration that ends up committed with it.
    Refusing the field outright beats warning about it: a warning that prevents nothing is
    the guard that gets ignored.
    """
    with pytest.raises(ValidationError):
        _config(tmp_path, notifier={"ntfy": {"enabled": True, "topic": "my-real-topic"}})
