"""Providers: the boundary between LACC and whatever produces model output.

`Provider` is an abstract port with a single operation (ADR-005). The core depends
on this abstraction, never on a concrete engine. `MockProvider` implements it
deterministically and offline, so every later phase can be built and tested with no
engine installed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from local_ai_control_center.core.config import is_loopback, normalized_host
from local_ai_control_center.ports.provider import Completion, Provider, ProviderError

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
_GENERATE_TIMEOUT_SECONDS = 300

_NOT_LOOPBACK = (
    "OLLAMA_HOST points at {host}, which is not this machine. LACC talks to an engine "
    "over loopback only: that is inter-process communication, while a non-loopback host "
    "is real network access, and sending your documents to another machine is not "
    "something LACC does because an environment variable said so. Running a model on "
    "another machine you own is a direction the roadmap records, and it needs its own "
    "decision record - authentication, authorization, where the audit trail lives - "
    "before it exists. Until then, unset OLLAMA_HOST or point it at 127.0.0.1."
)

_NOT_NAMED = (
    "The engine host {host} is not this machine, and network_access is off. A host that "
    "is not loopback is reached only when the configuration both permits network access "
    "and names it, so that no environment or installer can widen what LACC contacts. Set "
    "network_access: true and engine_host in your configuration if this is a machine you "
    "own on a network you control (ADR-027)."
)


def resolve_engine_host(configured: str, network_access: bool) -> str:
    """Decide which engine address to use, and refuse the ones that were never named.

    An environment variable may only ever point at this machine: that protection is from
    ADR-022 and it does not move. A host elsewhere comes from the configuration alone,
    and only when network access is permitted - so the escape hatch is a file the user
    wrote rather than a variable something else set (ADR-027).

    The configuration wins over the variable. A file naming a stronger machine is a
    deliberate choice, and an ambient `OLLAMA_HOST` quietly sending the work back to this
    laptop would be the wrong kind of surprise: the answer would come from a smaller model
    and nothing would say so.
    """
    named = configured.strip()
    if named:
        host = normalized_host(named)
        hostname = urllib.parse.urlparse(host).hostname
        if hostname is not None and is_loopback(hostname):
            return host
        if not network_access:
            raise ProviderError(_NOT_NAMED.format(host=host))
        return host

    from_env = os.environ.get("OLLAMA_HOST", "").strip()
    if from_env:
        host = normalized_host(from_env)
        hostname = urllib.parse.urlparse(host).hostname
        if hostname is None or not is_loopback(hostname):
            raise ProviderError(_NOT_LOOPBACK.format(host=host))
        return host

    return DEFAULT_OLLAMA_HOST


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
    if hostname is None or not is_loopback(hostname):
        raise ProviderError(_NOT_LOOPBACK.format(host=host))
    return host


def _as_count(value: object) -> int | None:
    """Return ``value`` as a token count, or ``None`` when the engine did not report one.

    An engine is an external system, so what it sends is checked rather than trusted to
    be the shape expected. A missing or malformed count is unknown, and unknown is
    recorded as unknown.
    """
    return value if isinstance(value, int) and value >= 0 else None


class OllamaProvider(Provider):
    """A provider backed by a local Ollama instance (ADR-013).

    Sends a prompt to Ollama's `/api/generate` with streaming off and returns the
    complete response. Talking to local Ollama over loopback is not network access
    in the sense the configuration guards. Failures are translated into clear,
    actionable messages rather than raised as raw errors.
    """

    def __init__(
        self, model: str, context_tokens: int | None = None, host: str | None = None
    ) -> None:
        """Create the provider for a model name and, optionally, a context window.

        The window is given here rather than per prompt because it describes how the
        engine is set up for this run, not what is being asked of it. Ollama loads with
        a default window far smaller than most models support - 4096 against 32768 for
        qwen2.5:3b, measured - and silently drops whatever does not fit, so a window LACC
        did not ask for is a window LACC cannot enforce a ceiling against (ADR-019).
        """
        self._host = host if host is not None else ollama_host()
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

    def complete(self, prompt: str, temperature: float = 0.0) -> Completion:
        """Send the prompt to Ollama and return the complete response.

        Translates connection, model, and timeout failures into clear messages.

        The temperature is always sent. Leaving it out let the engine apply its own default
        - 0.8, measured - which samples rather than taking the most likely token, and made
        the audit's completion hashes impossible to reproduce (ADR-033).
        """
        url = f"{self._host}/api/generate"
        payload: dict[str, Any] = {"model": self._model, "prompt": prompt, "stream": False}
        options: dict[str, Any] = {"temperature": temperature}
        if self._context_tokens is not None:
            options["num_ctx"] = self._context_tokens
        payload["options"] = options
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

        return Completion(
            text=payload.get("response", ""),
            provider=self.name,
            prompt_tokens=_as_count(payload.get("prompt_eval_count")),
            answer_tokens=_as_count(payload.get("eval_count")),
            finish_reason=payload.get("done_reason") or None,
        )

    def _translate_http_error(self, error: urllib.error.HTTPError) -> ProviderError:
        """Turn an HTTP error from Ollama into an actionable message."""
        if error.code == 404:
            return ProviderError(
                f"Model '{self._model}' is not installed. Pull it with "
                f"'ollama pull {self._model}', or see 'lacc profile'."
            )
        return ProviderError(f"Ollama returned an error ({error.code}): {error.reason}")
