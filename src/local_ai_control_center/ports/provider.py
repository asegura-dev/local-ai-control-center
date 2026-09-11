"""The provider port: what LACC needs from anything that completes a prompt.

Mirrors the converter and notifier ports. The abstract class and the contract that
crosses it live here; every engine that satisfies it lives under `adapters` (ADR-029).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class Completion(BaseModel):
    """The result of a provider call.

    Carries the producing provider's name alongside the text, so an audit record
    can attribute a result rather than only storing it.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    provider: str
    prompt_tokens: int | None = None
    """Tokens the engine counted in the prompt, when it says. The only way LACC's own
    estimate can be checked against reality (ADR-020)."""

    answer_tokens: int | None = None
    """Tokens the engine produced, when it says."""

    finish_reason: str | None = None
    """Why generation stopped, when the engine says. An answer that stopped because it
    ran out of room ends mid-thought and looks like an answer."""


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
    def complete(self, prompt: str, temperature: float = 0.0) -> Completion:
        """Return a completion for ``prompt``.

        ``temperature`` is per request because it is a property of the task, not of the
        engine: a skill copying words out of a document needs a different setting from one
        rewriting prose, and the skill is what knows which it is (ADR-033).
        """


class ProviderError(Exception):
    """Raised when a real provider cannot produce a completion.

    Carries a message already translated into something a person can act on.
    """
