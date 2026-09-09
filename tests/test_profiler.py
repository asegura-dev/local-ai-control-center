"""Tests for the profiler: fit formula, model parsing, and graceful detection."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from local_ai_control_center.profiler import (
    InstalledModel,
    SystemProfile,
    _cache_bytes_per_token,
    _estimate_fits,
    _estimate_window_costs,
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


_QWEN_SHAPE = {
    "general.architecture": "qwen2",
    "qwen2.block_count": 36,
    "qwen2.attention.head_count": 16,
    "qwen2.attention.head_count_kv": 2,
    "qwen2.embedding_length": 2048,
}


def test_cache_cost_comes_from_the_models_own_numbers() -> None:
    """Two caches, every layer, every kv head, at the width of a head, at 16 bits."""
    # 2 * 36 layers * 2 kv heads * (2048 / 16) head width * 2 bytes = 36864.
    assert _cache_bytes_per_token(_QWEN_SHAPE) == 36864


def test_cache_cost_is_found_whatever_the_architecture_is_called() -> None:
    """Keys are matched by suffix: hardcoding one model family is the narrowness to avoid."""
    other = {key.replace("qwen2.", "llama."): value for key, value in _QWEN_SHAPE.items()}
    assert _cache_bytes_per_token(other) == 36864


def test_an_explicit_head_width_is_preferred_over_dividing() -> None:
    """When a model publishes its head width, that is used rather than inferred."""
    shape = dict(_QWEN_SHAPE) | {"qwen2.attention.key_length": 64}
    assert _cache_bytes_per_token(shape) == 2 * 36 * 2 * 64 * 2


def test_a_model_that_does_not_publish_its_shape_costs_unknown() -> None:
    """Unknown is a usable answer; a guessed one is not."""
    assert _cache_bytes_per_token({"general.architecture": "mystery"}) is None
    assert _cache_bytes_per_token(dict(_QWEN_SHAPE) | {"qwen2.block_count": 0}) is None


def _model(context_tokens: int | None = 32768) -> InstalledModel:
    return InstalledModel(
        name="qwen2.5:3b",
        size_gb=1.8,
        quantization="Q4_K_M",
        context_tokens=context_tokens,
        cache_bytes_per_token=36864,
    )


def test_window_cost_grows_with_the_window() -> None:
    """Twice the window is twice the cache, which is the whole shape of the trade."""
    costs = {c.window_tokens: c for c in _estimate_window_costs(_model(), 36864, 16.0)}
    assert costs[8192].cache_gb == round(costs[4096].cache_gb * 2, 2)
    assert costs[32768].total_gb > costs[4096].total_gb


def test_window_cost_is_marked_against_the_memory_free_now() -> None:
    """The same window fits on a machine with room and does not on one without."""
    roomy = {c.window_tokens: c for c in _estimate_window_costs(_model(), 36864, 16.0)}
    cramped = {c.window_tokens: c for c in _estimate_window_costs(_model(), 36864, 2.0)}
    assert roomy[32768].status == "fits"
    assert cramped[32768].status == "too_large"


def test_windows_beyond_what_the_model_supports_are_not_offered() -> None:
    """Reporting the cost of a window the model cannot take would be noise."""
    windows = {c.window_tokens for c in _estimate_window_costs(_model(8192), 36864, 16.0)}
    assert windows == {4096, 8192}


def test_the_report_includes_the_weights_not_only_the_cache() -> None:
    """What matters is what the machine has to hold, not what the cache alone costs."""
    cost = next(c for c in _estimate_window_costs(_model(), 36864, 16.0) if c.window_tokens == 4096)
    assert cost.total_gb > 1.8
    assert cost.cache_gb < cost.total_gb
