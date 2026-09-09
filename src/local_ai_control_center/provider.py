"""Providers: the boundary between LACC and whatever produces model output.

`Provider` is an abstract port with a single operation (ADR-005). The core depends
on this abstraction, never on a concrete engine. `MockProvider` implements it
deterministically and offline, so every later phase can be built and tested with no
engine installed.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

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


_NOT_LOOPBACK = (
    "OLLAMA_HOST points at {host}, which is not this machine. LACC talks to an engine "
    "over loopback only: that is inter-process communication, while a non-loopback host "
    "is real network access, and sending your documents to another machine is not "
    "something LACC does because an environment variable said so. Running a model on "
    "another machine you own is a direction the roadmap records, and it needs its own "
    "decision record - authentication, authorization, where the audit trail lives - "
    "before it exists. Until then, unset OLLAMA_HOST or point it at 127.0.0.1."
)


def _is_loopback(hostname: str) -> bool:
    """Whether ``hostname`` names this machine, by literal address or by `localhost`."""
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def ollama_host() -> str:
    """The engine address, honoring OLLAMA_HOST, defaulting to loopback.

    Refuses a host that is not loopback rather than using it. PRINCIPLES treats
    loopback as inter-process communication and anything else as network access, which
    LACC does not do; without this check the promise is a comment, and an environment
    variable set by an installer, a script or a mistake would be enough to turn a local
    tool into one that sends private documents elsewhere, looking exactly like a normal
    run while it did.
    """
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if not host:
        return DEFAULT_OLLAMA_HOST
    if not host.startswith("http"):
        host = f"http://{host}"
    hostname = urllib.parse.urlparse(host).hostname
    if hostname is None or not _is_loopback(hostname):
        raise ProviderError(_NOT_LOOPBACK.format(host=host))
    return host


class OllamaProvider(Provider):
    """A provider backed by a local Ollama instance (ADR-013).

    Sends a prompt to Ollama's `/api/generate` with streaming off and returns the
    complete response. Talking to local Ollama over loopback is not network access
    in the sense the configuration guards. Failures are translated into clear,
    actionable messages rather than raised as raw errors.
    """

    def __init__(self, model: str, context_tokens: int | None = None) -> None:
        """Create the provider for a model name and, optionally, a context window.

        The window is given here rather than per prompt because it describes how the
        engine is set up for this run, not what is being asked of it. Ollama loads with
        a default window far smaller than most models support - 4096 against 32768 for
        qwen2.5:3b, measured - and silently drops whatever does not fit, so a window LACC
        did not ask for is a window LACC cannot enforce a ceiling against (ADR-019).
        """
        self._host = ollama_host()
        self._context_tokens = context_tokens
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
        url = f"{self._host}/api/generate"
        payload: dict[str, Any] = {"model": self._model, "prompt": prompt, "stream": False}
        if self._context_tokens is not None:
            payload["options"] = {"num_ctx": self._context_tokens}
        body = json.dumps(payload).encode("utf-8")
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
                f"Cannot reach Ollama at {self._host}. Is it running? "
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
