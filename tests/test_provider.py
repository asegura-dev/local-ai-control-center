"""Tests for the provider port and the deterministic mock implementation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from local_ai_control_center.provider import (
    Completion,
    MockProvider,
    OllamaProvider,
    Provider,
    ProviderError,
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
