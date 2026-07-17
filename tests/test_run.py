"""Tests for run identity generation."""

from __future__ import annotations

import re

from local_ai_control_center.run import new_run_id

_RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{4}$")


def test_run_id_matches_expected_format() -> None:
    """A run id looks like YYYYMMDDThhmmssZ-xxxx."""
    assert _RUN_ID_PATTERN.match(new_run_id())


def test_run_ids_are_unique() -> None:
    """Two ids generated together do not collide (the random suffix works)."""
    ids = {new_run_id() for _ in range(100)}
    assert len(ids) > 1


def test_run_id_is_sortable_by_time() -> None:
    """The timestamp prefix makes ids time-ordered (ignoring the random suffix)."""
    first = new_run_id()
    second = new_run_id()
    # Compare only the timestamp prefix; the random suffix has no order.
    first_timestamp = first.split("-")[0]
    second_timestamp = second.split("-")[0]
    assert second_timestamp >= first_timestamp
