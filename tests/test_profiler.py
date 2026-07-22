"""Tests for the profiler: fit formula, model parsing, and graceful detection."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from local_ai_control_center.profiler import (
    SystemProfile,
    _estimate_fits,
    profile_system,
)


def test_fit_formula_matches_the_arithmetic() -> None:
    """A model of P billion params at B bits weighs about P*B/8 GB."""
    fits = _estimate_fits(20.0)
    # An 8B model at 4-bit weighs 8 * 4 / 8 = 4.0 GB.
    eight_at_four = next(f for f in fits if f.parameters_b == 8 and f.quantization_bits == 4)
    assert eight_at_four.weight_gb == 4.0


def test_fit_covers_sizes_and_quantizations() -> None:
    """The table spans the fixed sizes and bit widths."""
    fits = _estimate_fits(16.0)
    assert {f.parameters_b for f in fits} == {1, 3, 8, 14, 32}
    assert {f.quantization_bits for f in fits} == {3, 4, 8}


def test_large_model_is_too_large_on_small_memory() -> None:
    """A 32B model at 8-bit does not fit a modest machine."""
    fits = _estimate_fits(16.0)
    big = next(f for f in fits if f.parameters_b == 32 and f.quantization_bits == 8)
    assert big.status == "too_large"


def test_small_model_fits_comfortably() -> None:
    """A 1B model fits easily with room to spare."""
    fits = _estimate_fits(16.0)
    small = next(f for f in fits if f.parameters_b == 1 and f.quantization_bits == 4)
    assert small.status == "fits"


def _fake_response(payload: dict[str, object], status: int = 200) -> object:
    """A stand-in for the object urlopen returns, usable as a context manager."""

    class _Resp:
        def __init__(self) -> None:
            self.status = status

        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    return _Resp()


def test_engine_absent_when_probe_fails() -> None:
    """A connection failure reports the engine as absent, without raising."""
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        profile = profile_system()
    assert profile.engine_present is False
    assert profile.installed_models == ()


def test_engine_present_parses_models() -> None:
    """A successful probe parses installed models with size and quantization."""
    payload = {
        "models": [
            {
                "name": "qwen2.5:3b",
                "size": 2 * 1024**3,
                "details": {"quantization_level": "Q4_K_M"},
            }
        ]
    }
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        profile = profile_system()
    assert profile.engine_present is True
    assert len(profile.installed_models) == 1
    model = profile.installed_models[0]
    assert model.name == "qwen2.5:3b"
    assert model.size_gb == 2.0
    assert model.quantization == "Q4_K_M"


def test_absent_engine_note_suggests_a_pull() -> None:
    """When no engine is found, a note suggests how to get one, without acting."""
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        profile = profile_system()
    assert any("ollama pull" in note for note in profile.notes)


def test_notes_warn_about_swapping_and_real_time_check() -> None:
    """The notes cover exceeding memory and how to verify free memory."""
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        profile = profile_system()
    joined = " ".join(profile.notes)
    assert "swapping" in joined
    assert "real time" in joined


def test_profile_reports_hardware_facts() -> None:
    """The profile includes architecture, OS, memory, disk, and uptime."""
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        profile = profile_system()
    assert profile.architecture != ""
    assert profile.os_name != ""
    assert profile.total_memory_gb > 0
    assert profile.free_disk_gb > 0
    assert profile.uptime_hours >= 0


def test_profile_is_frozen() -> None:
    """A profile cannot be mutated after creation."""
    profile = SystemProfile(engine_present=False)
    with pytest.raises(ValidationError):
        profile.engine_present = True  # type: ignore[misc]


def test_acceleration_note_is_honest_about_unusable_accelerators() -> None:
    """The acceleration note warns an accelerator may exist but be unusable."""
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        profile = profile_system()
    assert any("may not be usable" in note for note in profile.notes)
