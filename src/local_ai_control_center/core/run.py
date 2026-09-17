"""Run identity: a unique, human-readable identifier for one execution.

Each execution gets a ``run_id`` of the form ``YYYYMMDDThhmmssZ-xxxx`` (a UTC
timestamp plus a short random suffix, ADR-002). The timestamp makes audit logs
readable and time-ordered; the random suffix keeps two runs that start in the
same second from colliding. Run identity is separate from configuration because
the two answer different questions and this one grows toward the audit system.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

_SUFFIX_ALPHABET = "0123456789abcdef"


def new_run_id() -> str:
    """Return a fresh run identifier.

    The format is ``YYYYMMDDThhmmssZ-xxxx``: a UTC timestamp to the second,
    followed by four random hex characters for uniqueness within the same second.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = "".join(secrets.choice(_SUFFIX_ALPHABET) for _ in range(4))
    return f"{timestamp}-{suffix}"


Stage = Literal["dividing", "asking", "checking"]
"""The parts of a run long enough that somebody is waiting through them."""


class Progress(BaseModel):
    """Where a run has got to, as data rather than as a sentence.

    A run that reads a document in seventeen passes takes twenty minutes and, until this
    existed, said nothing between starting and finishing. A terminal can render this as a
    line and an interface can render it as a bar; neither is decided here, which is the
    point - the core describes, and whoever is watching presents (ADR-046).
    """

    model_config = ConfigDict(frozen=True)

    stage: Stage
    done: int = 0
    total: int = 0
    detail: str = ""

    @property
    def fraction(self) -> float:
        """How much of this stage is finished, between zero and one.

        Zero when the total is unknown, which is honest: a caller drawing a bar from this
        gets an empty one rather than a wrong one.
        """
        return self.done / self.total if self.total > 0 else 0.0


ProgressFn = Callable[[Progress], None]
"""What a caller passes in to be told how far along a run is.

Optional everywhere. A run that nobody is watching must behave identically to one that is,
so this is never consulted for anything but reporting.
"""
