"""Providers: the boundary between LACC and whatever produces model output.

`Provider` is an abstract port with a single operation (ADR-005). The core depends
on this abstraction, never on a concrete engine. `MockProvider` implements it
deterministically and offline, so every later phase can be built and tested with no
engine installed.
"""

from __future__ import annotations

import hashlib
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
