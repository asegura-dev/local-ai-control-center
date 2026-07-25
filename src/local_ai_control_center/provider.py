"""Providers: the boundary between LACC and whatever produces model output.

`Provider` is an abstract port with a single operation (ADR-005). The core depends
on this abstraction, never on a concrete engine. `MockProvider` implements it
deterministically and offline, so every later phase can be built and tested with no
engine installed.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict


class Completion(BaseModel):
    """The result of a provider call.

    Carries the producing provider's name alongside the text, so an audit record
    can attribute a result rather than only storing it.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    provider: str


class Provider(ABC):
    """Abstract port for anything that turns a prompt into a completion.

    Implementations are free to call a local engine, a remote service, or nothing
    at all. The core only knows this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier recorded on completions this provider produces."""

    @abstractmethod
    def complete(self, prompt: str) -> Completion:
        """Return a completion for ``prompt``."""


class MockProvider(Provider):
    """A deterministic provider that touches nothing outside this process.

    The same prompt always yields the same completion. Responses come from one of
    two paths: a scripted answer supplied by the caller, or a predictable answer
    derived from the prompt itself.
    """

    def __init__(self, responses: Mapping[str, str] | None = None) -> None:
        """Create the provider, optionally scripting prompt-to-response pairs."""
        self._responses = dict(responses or {})

    @property
    def name(self) -> str:
        """Identify completions produced by this provider."""
        return "mock"

    def complete(self, prompt: str) -> Completion:
        """Return the scripted answer for ``prompt``, or a derived one."""
        scripted = self._responses.get(prompt)
        text = scripted if scripted is not None else self._derive(prompt)
        return Completion(text=text, provider=self.name)

    @staticmethod
    def _derive(prompt: str) -> str:
        """Derive a stable, readable answer from the prompt.

        Deterministic by construction: the same prompt yields the same digest, so
        tests can assert on it without scripting every case.
        """
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        return f"mock completion for prompt {digest}"


DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
_GENERATE_TIMEOUT_SECONDS = 300


class ProviderError(Exception):
    """Raised when a real provider cannot produce a completion.

    Carries a message already translated into something a person can act on.
    """


def _ollama_host() -> str:
    """The engine address, honoring OLLAMA_HOST, defaulting to loopback."""
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if not host:
        return DEFAULT_OLLAMA_HOST
    if not host.startswith("http"):
        host = f"http://{host}"
    return host


class OllamaProvider(Provider):
    """A provider backed by a local Ollama instance (ADR-013).

    Sends a prompt to Ollama's `/api/generate` with streaming off and returns the
    complete response. Talking to local Ollama over loopback is not network access
    in the sense the configuration guards. Failures are translated into clear,
    actionable messages rather than raised as raw errors.
    """

    def __init__(self, model: str) -> None:
        """Create the provider for a given model name (from configuration)."""
        if not model:
            raise ProviderError(
                "No model configured. Name one in your config (see 'lacc profile' "
                "for installed models), for example: model: qwen2.5:3b"
            )
        self._model = model

    @property
    def name(self) -> str:
        """Identify completions produced by this provider."""
        return f"ollama:{self._model}"

    def complete(self, prompt: str) -> Completion:
        """Send the prompt to Ollama and return the complete response.

        Translates connection, model, and timeout failures into clear messages.
        """
        url = f"{_ollama_host()}/api/generate"
        body = json.dumps({"model": self._model, "prompt": prompt, "stream": False}).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(request, timeout=_GENERATE_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise self._translate_http_error(error) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise ProviderError(
                f"Cannot reach Ollama at {_ollama_host()}. Is it running? "
                "Start it with 'ollama serve', or check 'lacc profile'."
            ) from error
        except (ValueError, OSError) as error:
            raise ProviderError(f"Unexpected response from Ollama: {error}") from error

        text = payload.get("response", "")
        return Completion(text=text, provider=self.name)

    def _translate_http_error(self, error: urllib.error.HTTPError) -> ProviderError:
        """Turn an HTTP error from Ollama into an actionable message."""
        if error.code == 404:
            return ProviderError(
                f"Model '{self._model}' is not installed. Pull it with "
                f"'ollama pull {self._model}', or see 'lacc profile'."
            )
        return ProviderError(f"Ollama returned an error ({error.code}): {error.reason}")
