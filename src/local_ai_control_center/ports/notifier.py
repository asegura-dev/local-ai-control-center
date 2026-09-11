"""The notifier port: saying that a run finished, to a machine the user named.

A notification never carries document content, and delivery is best effort: a notifier
that cannot reach its server does not fail a run that already succeeded (ADR-027).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class NotifierMisconfigured(ValueError):
    """The notifier settings do not describe a destination LACC will post to."""


class Notification(BaseModel):
    """What LACC has to say about a run that finished.

    Frozen, and deliberately narrow: a title, a line of body, and tags. There is no field
    for content because there is no case where a notification should carry any (ADR-027).
    """

    model_config = ConfigDict(frozen=True)

    title: str
    body: str
    tags: tuple[str, ...] = ()


class Delivery(BaseModel):
    """What happened when a notification was sent."""

    model_config = ConfigDict(frozen=True)

    transport: str
    delivered: bool
    detail: str = ""


class Notifier(ABC):
    """Abstract port for anything that can tell a person a run has finished."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier of the transport, for audit records."""

    @abstractmethod
    def send(self, notification: Notification) -> Delivery:
        """Deliver ``notification``, reporting what happened rather than raising."""
