"""Tests for the provider port and the deterministic mock implementation."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from local_ai_control_center.provider import (
    Completion,
    MockProvider,
    OllamaProvider,
    Provider,
    ProviderError,
    ollama_host,
    resolve_engine_host,
)


def test_mock_is_a_provider() -> None:
    """MockProvider satisfies the Provider port."""
    assert isinstance(MockProvider(), Provider)


def test_provider_cannot_be_instantiated() -> None:
    """The abstract port cannot be used directly."""
    with pytest.raises(TypeError):
        Provider()  # type: ignore[abstract]


def test_completion_carries_the_producing_provider() -> None:
    """A completion records which provider produced it."""
    completion = MockProvider().complete("hello")
    assert isinstance(completion, Completion)
    assert completion.provider == "mock"


def test_derived_response_is_deterministic() -> None:
    """The same prompt always yields the same derived completion."""
    provider = MockProvider()
    first = provider.complete("same prompt")
    second = provider.complete("same prompt")
    assert first.text == second.text


def test_derived_responses_differ_between_prompts() -> None:
    """Different prompts yield different derived completions."""
    provider = MockProvider()
    assert provider.complete("one").text != provider.complete("two").text


def test_derived_response_is_stable_across_instances() -> None:
    """Determinism holds across separate provider instances."""
    assert MockProvider().complete("stable").text == MockProvider().complete("stable").text


def test_scripted_response_is_returned() -> None:
    """A scripted prompt returns exactly the scripted answer."""
    provider = MockProvider({"question": "scripted answer"})
    assert provider.complete("question").text == "scripted answer"


def test_unscripted_prompt_falls_back_to_derived() -> None:
    """A prompt without a script still gets a deterministic answer."""
    provider = MockProvider({"scripted": "yes"})
    text = provider.complete("not scripted").text
    assert text
    assert text != "yes"


def test_scripted_empty_string_is_respected() -> None:
    """An empty scripted answer is used, not treated as missing."""
    provider = MockProvider({"prompt": ""})
    assert provider.complete("prompt").text == ""


def test_scripts_are_copied_not_shared() -> None:
    """Mutating the caller's mapping does not change provider behavior."""
    scripts = {"prompt": "original"}
    provider = MockProvider(scripts)
    scripts["prompt"] = "changed"
    assert provider.complete("prompt").text == "original"


def test_completion_is_frozen() -> None:
    """A completion cannot be mutated after creation."""
    completion = MockProvider().complete("x")
    with pytest.raises(ValidationError):
        completion.text = "tampered"  # type: ignore[misc]


def test_ollama_is_a_provider() -> None:
    """OllamaProvider satisfies the Provider port."""
    assert isinstance(OllamaProvider("qwen2.5:3b"), Provider)


def test_ollama_requires_a_model() -> None:
    """Constructing without a model is a clear configuration error."""
    with pytest.raises(ProviderError) as excinfo:
        OllamaProvider("")
    assert "No model configured" in str(excinfo.value)


def test_ollama_name_includes_the_model() -> None:
    """Completions are attributed to the specific model."""
    assert OllamaProvider("qwen2.5:3b").name == "ollama:qwen2.5:3b"


def _fake_generate_response(text: str) -> object:
    """A stand-in for urlopen's return, usable as a context manager."""
    import json

    class _Resp:
        def read(self) -> bytes:
            return json.dumps({"response": text, "done": True}).encode("utf-8")

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    return _Resp()


def test_ollama_returns_the_completion_text() -> None:
    """A successful generation returns the model's response text."""
    from unittest.mock import patch

    provider = OllamaProvider("qwen2.5:3b")
    with patch("urllib.request.urlopen", return_value=_fake_generate_response("hello there")):
        completion = provider.complete("hi")
    assert completion.text == "hello there"
    assert completion.provider == "ollama:qwen2.5:3b"


def test_ollama_translates_connection_failure() -> None:
    """A refused connection becomes an actionable message, not a raw error."""
    import urllib.error
    from unittest.mock import patch

    provider = OllamaProvider("qwen2.5:3b")
    with (
        patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")),
        pytest.raises(ProviderError) as excinfo,
    ):
        provider.complete("hi")
    assert "Cannot reach Ollama" in str(excinfo.value)


def test_ollama_translates_missing_model() -> None:
    """A 404 becomes a message telling the user to pull the model."""
    import urllib.error
    from unittest.mock import patch

    provider = OllamaProvider("nope:1b")
    error = urllib.error.HTTPError(url="http://x", code=404, msg="not found", hdrs=None, fp=None)
    with (
        patch("urllib.request.urlopen", side_effect=error),
        pytest.raises(ProviderError) as excinfo,
    ):
        provider.complete("hi")
    message = str(excinfo.value)
    assert "not installed" in message
    assert "ollama pull nope:1b" in message


def test_engine_address_defaults_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """With nothing configured, the engine is on this machine."""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert ollama_host() == "http://127.0.0.1:11434"


def test_engine_address_accepts_loopback_forms(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loopback by literal address or by name is inter-process communication, not network."""
    for value in ("127.0.0.1:11434", "http://127.0.0.1:11434", "localhost", "http://[::1]:11434"):
        monkeypatch.setenv("OLLAMA_HOST", value)
        assert ollama_host()


def test_engine_address_refuses_a_host_that_is_not_this_machine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An environment variable must not be able to send documents to another machine.

    PRINCIPLES puts a non-loopback host out of scope. Without this the promise is a
    comment: a variable set by an installer, a script or a mistake would be enough.
    """
    for value in ("http://192.168.1.50:11434", "https://models.example.com", "example.com"):
        monkeypatch.setenv("OLLAMA_HOST", value)
        with pytest.raises(ProviderError) as excinfo:
            ollama_host()
        assert "not this machine" in str(excinfo.value)


def test_provider_refuses_to_be_built_for_a_remote_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal happens at construction, before a prompt could be sent anywhere."""
    monkeypatch.setenv("OLLAMA_HOST", "https://models.example.com")
    with pytest.raises(ProviderError):
        OllamaProvider("qwen2.5:3b")


def _captured_request_body(provider: OllamaProvider) -> dict[str, object]:
    """Run a completion against a stubbed engine and return the body that was sent."""
    from unittest.mock import patch

    sent: list[bytes] = []

    def _capture(request: object, **_: object) -> object:
        sent.append(request.data)  # type: ignore[attr-defined]
        return _fake_generate_response("ok")

    with patch("urllib.request.urlopen", side_effect=_capture):
        provider.complete("a prompt")
    return dict(json.loads(sent[0].decode("utf-8")))


def test_a_configured_window_is_asked_for() -> None:
    """LACC asks the engine for the window it will enforce a ceiling against.

    Ollama loads with its own default - far smaller than most models support - and
    silently drops what does not fit, so a window LACC did not request is one it cannot
    hold the engine to (ADR-019).
    """
    body = _captured_request_body(OllamaProvider("qwen2.5:3b", context_tokens=8192))
    assert body["options"] == {"num_ctx": 8192}


def test_no_window_is_asked_for_when_none_is_configured() -> None:
    """Unset means unset: LACC does not invent a window to send."""
    body = _captured_request_body(OllamaProvider("qwen2.5:3b"))
    assert "options" not in body


def _fake_response_with(payload: dict[str, object]) -> object:
    """A stand-in for urlopen's return carrying an arbitrary engine payload."""

    class _Resp:
        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    return _Resp()


def test_the_engines_own_counts_are_kept() -> None:
    """The estimate can only be checked against what the engine actually counted."""
    from unittest.mock import patch

    payload = {
        "response": "hola",
        "prompt_eval_count": 750,
        "eval_count": 42,
        "done_reason": "stop",
    }
    with patch("urllib.request.urlopen", return_value=_fake_response_with(payload)):
        completion = OllamaProvider("qwen2.5:3b").complete("hi")
    assert completion.prompt_tokens == 750
    assert completion.answer_tokens == 42
    assert completion.finish_reason == "stop"


def test_counts_the_engine_does_not_report_stay_unknown() -> None:
    """Unknown is recorded as unknown, never filled in with something plausible."""
    from unittest.mock import patch

    with patch("urllib.request.urlopen", return_value=_fake_response_with({"response": "hola"})):
        completion = OllamaProvider("qwen2.5:3b").complete("hi")
    assert completion.prompt_tokens is None
    assert completion.answer_tokens is None
    assert completion.finish_reason is None


def test_a_malformed_count_is_treated_as_unknown() -> None:
    """An engine is external: what it sends is checked, not trusted to be the right shape."""
    from unittest.mock import patch

    payload = {"response": "hola", "prompt_eval_count": "many", "eval_count": -1}
    with patch("urllib.request.urlopen", return_value=_fake_response_with(payload)):
        completion = OllamaProvider("qwen2.5:3b").complete("hi")
    assert completion.prompt_tokens is None
    assert completion.answer_tokens is None


def test_the_mock_reports_no_counts() -> None:
    """A provider that cannot measure says so rather than inventing numbers."""
    completion = MockProvider().complete("hi")
    assert completion.prompt_tokens is None
    assert completion.finish_reason is None


def test_an_unnamed_remote_engine_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Network access alone does not send documents anywhere; the host must be named."""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    with pytest.raises(ProviderError):
        resolve_engine_host("http://desk:11434", network_access=False)


def test_a_named_remote_engine_is_used_when_network_access_permits_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one way to reach another machine: written in the configuration, under the ceiling."""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert resolve_engine_host("http://desk:11434", network_access=True) == "http://desk:11434"


def test_a_configured_loopback_engine_needs_no_network_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Talking to a local engine is inter-process communication, not network access."""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert resolve_engine_host("127.0.0.1:11434", network_access=False) == "http://127.0.0.1:11434"


def test_the_environment_can_never_name_a_remote_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ADR-022 protection does not move: a variable cannot send documents away.

    Even with network access permitted, which is the case that would have widened it.
    """
    monkeypatch.setenv("OLLAMA_HOST", "https://models.example.com")
    with pytest.raises(ProviderError):
        resolve_engine_host("", network_access=True)


def test_the_configuration_wins_over_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """A file naming a stronger machine is deliberate; an ambient variable is not.

    Letting `OLLAMA_HOST=localhost` quietly override it would answer from a smaller model
    and say nothing about it.
    """
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    assert resolve_engine_host("http://desk:11434", network_access=True) == "http://desk:11434"


def test_nothing_configured_and_nothing_in_the_environment_stays_on_this_machine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default is unchanged: loopback, with no network access needed or granted."""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert resolve_engine_host("", network_access=True) == ollama_host()
