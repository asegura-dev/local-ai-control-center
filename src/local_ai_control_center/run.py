"""Run identity: a unique, human-readable identifier for one execution.

Each execution gets a ``run_id`` of the form ``YYYYMMDDThhmmssZ-xxxx`` (a UTC
timestamp plus a short random suffix, ADR-002). The timestamp makes audit logs
readable and time-ordered; the random suffix keeps two runs that start in the
same second from colliding. Run identity is separate from configuration because
the two answer different questions and this one grows toward the audit system.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

_SUFFIX_ALPHABET = "0123456789abcdef"


def new_run_id() -> str:
    """Return a fresh run identifier.

    The format is ``YYYYMMDDThhmmssZ-xxxx``: a UTC timestamp to the second,
    followed by four random hex characters for uniqueness within the same second.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = "".join(secrets.choice(_SUFFIX_ALPHABET) for _ in range(4))
    return f"{timestamp}-{suffix}"
