"""A provider that touches nothing outside this process.

The same prompt always yields the same completion, which is what lets the suite exercise
the whole cycle without an engine - and is why the suite never noticed the real engine
was sampling at 0.8 (ADR-033).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from local_ai_control_center.ports.provider import Completion, Provider


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

    def complete(self, prompt: str, temperature: float = 0.0) -> Completion:
        """Return the scripted answer for ``prompt``, or a derived one.

        ``temperature`` is accepted and ignored: this provider is already deterministic,
        which is precisely why the suite never noticed the engine was not.
        """
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
