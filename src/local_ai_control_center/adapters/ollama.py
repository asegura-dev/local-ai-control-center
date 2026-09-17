"""Providers: the boundary between LACC and whatever produces model output.

`Provider` is an abstract port with a single operation (ADR-005). The core depends
on this abstraction, never on a concrete engine. `MockProvider` implements it
deterministically and offline, so every later phase can be built and tested with no
engine installed.
"""

from __future__ import annotations

import errno
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.budget import answer_reserve
from local_ai_control_center.core.config import is_loopback, normalized_host
from local_ai_control_center.ports.provider import Completion, Provider, ProviderError

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
_SLOWEST_TOKENS_PER_SECOND = 3
"""The slowest generation this project has measured, rounded down.

A 32B model that did not fit the card produced 2.7 tokens per second against 29 for one
that did. A timeout has to survive that case or it refuses correct work on the hardware
most likely to need patience (ADR-046).
"""

_MINIMUM_GENERATE_TIMEOUT = 300
"""Floor, for windows small enough that the derivation would be shorter than a model load."""


def generation_timeout(context_tokens: int | None) -> int:
    """How long one generation may legitimately take, from the window it was given.

    The window bounds the answer through `answer_reserve`; the slowest measured rate turns
    that bound into a time. A fixed number is unrelated to the work asked for and was wrong
    in both directions: 300 seconds refused passes that were still being generated at 252,
    and reported them as an engine that could not be reached (ADR-046).

    A hung engine therefore costs this long before it is given up on. That is the price of
    not abandoning work that is merely slow.
    """
    if context_tokens is None:
        return _MINIMUM_GENERATE_TIMEOUT
    return max(
        _MINIMUM_GENERATE_TIMEOUT, answer_reserve(context_tokens) // _SLOWEST_TOKENS_PER_SECOND
    )


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

    def complete(
        self,
        prompt: str,
        temperature: float = 0.0,
        schema: dict[str, Any] | None = None,
    ) -> Completion:
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
        if schema is not None:
            # The engine constrains decoding to this, so the shape stops being a request
            # and becomes something the model cannot emit its way around (ADR-052).
            payload["format"] = schema
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )

        try:
            limit = generation_timeout(self._context_tokens)
            with urllib.request.urlopen(request, timeout=limit) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise self._translate_http_error(error) from error
        except (urllib.error.URLError, TimeoutError) as error:
            # A timeout here is not the timeout `check_engine` sees. This one follows a
            # prompt the engine is still working on; that one follows a question about
            # which models exist. Reporting both as "cannot reach" is what made a busy
            # engine look like an unreachable one (ADR-046).
            if why_unreachable(error) == "timed out":
                raise ProviderError(
                    f"Ollama at {self._host} did not answer within {limit}s. The prompt was "
                    f"about {len(prompt) // 3:,} tokens; a large pass on a busy engine can "
                    "take longer. Nothing was lost - the request simply was not waited for. "
                    "If the engine is idle and this repeats, the network is worth checking."
                ) from error
            raise ProviderError(unreachable_message(self._host, error)) from error
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


def why_unreachable(error: BaseException) -> str:
    """Name the way an engine could not be reached, as a short key.

    Refused and timed out are different faults with different fixes, and the guides say so:
    a refusal means nothing is listening, a timeout means something is between you and it -
    a firewall, or an engine bound to loopback on a machine you are reaching over a network.
    Collapsing them into "is it running?" sends a person to restart a service that is
    already running, which is what happened.
    """
    reason = getattr(error, "reason", error)
    if isinstance(error, TimeoutError) or isinstance(reason, TimeoutError):
        return "timed out"
    if isinstance(reason, ConnectionRefusedError):
        return "refused"
    if isinstance(reason, socket.gaierror):
        return "unknown host"
    if isinstance(reason, OSError) and reason.errno in (
        errno.EHOSTUNREACH,
        errno.ENETUNREACH,
    ):
        return "no route"
    return "unreachable"


_ADVICE = {
    "refused": (
        "Nothing is listening there. Ollama is not running, or is on another port. "
        "Start it with 'ollama serve'."
    ),
    "timed out": (
        "Something answered for the address but not for the port: a firewall, or an "
        "engine bound to loopback on a machine you are reaching over a network. On the "
        "engine machine, set OLLAMA_HOST=0.0.0.0:11434 and allow the port."
    ),
    "unknown host": "The address does not resolve. Check the host name in engine_host.",
    "no route": "No route to that address. Check the network, or Tailscale if you use it.",
    "unreachable": "Check that the engine is running and that the address is right.",
}


def unreachable_message(host: str, error: BaseException) -> str:
    """A message that says which fault it was, and what fixes that one."""
    fault = why_unreachable(error)
    return f"Cannot reach Ollama at {host}: {fault}. {_ADVICE[fault]}"


_PROBE_TIMEOUT = 8
"""Seconds to wait when only asking the engine what it holds."""


class EngineCheck(BaseModel):
    """What a pre-flight check of the engine found, step by step.

    Each step is separate because each fails for its own reason and is fixed its own way.
    A single "it works / it does not" would be the message this replaces.
    """

    model_config = ConfigDict(frozen=True)

    host: str
    reached: bool = False
    detail: str = ""
    models: tuple[str, ...] = ()
    wanted_model: str = ""
    model_installed: bool = False
    answered: bool = False
    seconds: float | None = None

    @property
    def ready(self) -> bool:
        """Whether a run would get an answer."""
        return self.answered


def check_engine(model: str, host: str, context_tokens: int | None = None) -> EngineCheck:
    """Ask the engine the questions a run is about to assume the answers to.

    Reaching it, listing what it holds, finding the configured model among them, and
    getting one token out of it. Never raises: the point is to report a fault, and a check
    that fails by raising is a check you cannot script.
    """
    url = f"{host}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=_PROBE_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as error:
        return EngineCheck(host=host, detail=unreachable_message(host, error), wanted_model=model)
    except (ValueError, OSError) as error:
        return EngineCheck(host=host, detail=f"Unexpected response: {error}", wanted_model=model)

    names = tuple(entry.get("name", "") for entry in payload.get("models", []))
    installed = model in names
    if not installed:
        return EngineCheck(
            host=host,
            reached=True,
            models=names,
            wanted_model=model,
            detail=f"'{model}' is not installed there. Pull it with 'ollama pull {model}'.",
        )

    started = time.monotonic()
    try:
        OllamaProvider(model, context_tokens, host).complete("Reply with the word ready.", 0.0)
    except ProviderError as error:
        return EngineCheck(
            host=host,
            reached=True,
            models=names,
            wanted_model=model,
            model_installed=True,
            detail=str(error),
        )
    return EngineCheck(
        host=host,
        reached=True,
        models=names,
        wanted_model=model,
        model_installed=True,
        answered=True,
        seconds=round(time.monotonic() - started, 1),
        detail="The engine answered.",
    )
