"""The converter port: what LACC needs from anything that turns a document into text.

Shaped by two concrete implementations from the start rather than guessed from one
(ADR-016). The implementations live under `adapters` (ADR-029).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ConversionError(Exception):
    """Raised when a document cannot be turned into text.

    Carries a message already translated into something a person can act on, the same
    posture `ProviderError` and `ReadError` take: a failure at an external, volatile
    boundary is reported clearly, never surfaced as a library's own error.
    """


class Converter(ABC):
    """Abstract port for anything that extracts text from a document.

    Implementations declare which file suffixes they handle, so a source is matched to
    a converter by what it is rather than by the caller knowing which to pick.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier of the converter, for audit records and messages."""

    @property
    @abstractmethod
    def suffixes(self) -> frozenset[str]:
        """Lower-case file suffixes this converter handles, including the dot."""

    @abstractmethod
    def extract_text(self, path: Path) -> str:
        """Return the text of the document at ``path``.

        Raises :class:`ConversionError` when the document cannot be read, or when it
        holds no extractable text at all - an empty result is reported, never returned.
        """
