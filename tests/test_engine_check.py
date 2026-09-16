"""Tests for telling one kind of unreachable engine from another, and the pre-flight check."""

from __future__ import annotations

import errno
import json
import socket
import urllib.error
from unittest.mock import patch

from local_ai_control_center.adapters.ollama import (
    check_engine,
    unreachable_message,
    why_unreachable,
)


def test_each_fault_is_named_separately() -> None:
    """A refusal and a timeout have different fixes, so they must not share a message.

    Collapsing them into "is it running?" sent someone to restart a service that was
    already running, and was the reason `lacc engine test` exists.
    """
    assert why_unreachable(urllib.error.URLError(ConnectionRefusedError(61, "no"))) == "refused"
    assert why_unreachable(TimeoutError("slow")) == "timed out"
    assert why_unreachable(urllib.error.URLError(socket.gaierror(-2, "no name"))) == "unknown host"
    assert why_unreachable(urllib.error.URLError(OSError(errno.EHOSTUNREACH, "away"))) == "no route"
    assert why_unreachable(urllib.error.URLError("something else")) == "unreachable"


def test_a_timeout_is_not_told_to_start_the_engine() -> None:
    """The fault we actually hit: Ollama was running and bound to loopback."""
    message = unreachable_message("http://10.0.0.1:11434", TimeoutError("slow"))
    assert "timed out" in message
    assert "OLLAMA_HOST=0.0.0.0" in message
    assert "ollama serve" not in message


def test_a_refusal_is_told_to_start_the_engine() -> None:
    message = unreachable_message(
        "http://127.0.0.1:11434", urllib.error.URLError(ConnectionRefusedError(61, "no"))
    )
    assert "ollama serve" in message


def _tags(*names: str) -> object:
    class _Resp:
        def read(self) -> bytes:
            return json.dumps({"models": [{"name": n} for n in names]}).encode("utf-8")

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    return _Resp()


def test_an_unreachable_engine_reports_the_fault_and_never_raises() -> None:
    """A check that fails by raising is a check you cannot script."""
    with patch("urllib.request.urlopen", side_effect=TimeoutError("slow")):
        check = check_engine("qwen2.5:3b", "http://10.0.0.1:11434")
    assert not check.reached and not check.ready
    assert "timed out" in check.detail


def test_an_engine_without_the_model_says_what_it_does_have() -> None:
    with patch("urllib.request.urlopen", return_value=_tags("llama3.1:8b", "qwen2.5:7b")):
        check = check_engine("qwen2.5:14b", "http://10.0.0.1:11434")
    assert check.reached and not check.model_installed and not check.ready
    assert check.models == ("llama3.1:8b", "qwen2.5:7b")
    assert "ollama pull qwen2.5:14b" in check.detail


def test_an_engine_that_answers_is_ready() -> None:
    generated = {"response": "ready", "done": True}

    class _Gen:
        def read(self) -> bytes:
            return json.dumps(generated).encode("utf-8")

        def __enter__(self) -> _Gen:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    with patch("urllib.request.urlopen", side_effect=[_tags("qwen2.5:3b"), _Gen()]):
        check = check_engine("qwen2.5:3b", "http://127.0.0.1:11434")
    assert check.reached and check.model_installed and check.answered and check.ready
    assert check.seconds is not None


def test_an_engine_that_lists_the_model_but_will_not_answer_is_not_ready() -> None:
    """Installed is not the same as usable - the model can fail to load."""
    with patch(
        "urllib.request.urlopen",
        side_effect=[_tags("qwen2.5:3b"), urllib.error.URLError(ConnectionRefusedError(61, "no"))],
    ):
        check = check_engine("qwen2.5:3b", "http://127.0.0.1:11434")
    assert check.model_installed and not check.ready
