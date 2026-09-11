"""Profiler: detect and report what the machine offers, without acting.

Reads and reports only (ADR-012): whether Ollama is present, which models are
installed, the hardware, and rough capacity guidance computed by formula. It never
pulls a model, runs inference, or writes anything. Probing the local engine on
loopback is not network access in the sense `network_access` guards.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import time
import urllib.error
import urllib.request

import psutil
from pydantic import BaseModel, ConfigDict, Field

from local_ai_control_center.adapters.ollama import ollama_host
from local_ai_control_center.ports.provider import ProviderError

_PROBE_TIMEOUT_SECONDS = 0.5
_QUANTIZATION_BITS: tuple[int, ...] = (3, 4, 8)
_MODEL_SIZES_B: tuple[int, ...] = (1, 3, 8, 14, 32)
_WINDOW_SIZES: tuple[int, ...] = (4096, 8192, 16384, 32768)
"""Window sizes the cost report walks through. A range, not a recommendation."""

_CACHE_BYTES_PER_ELEMENT = 2
"""Bytes per cached value, assuming a sixteen-bit cache. Quantizing it costs less."""

_RUNTIME_ALLOWANCE = 1.5
"""How much more than the attention cache a window is assumed to cost.

An allowance, not a calibration. Growth of about 1.4 times the computed cache was
observed once, on one model, one engine version and one machine (ADR-021); rounding away
from that observation rather than fitting to it is the point. It errs toward reporting
less headroom than the machine has, which is the direction where being wrong is cheap.
"""

_MEMORY_RESERVED_GB = 4.0
"""Memory left for the OS and other work when judging what a model can use."""


class InstalledModel(BaseModel):
    """A model reported by the engine as installed locally."""

    model_config = ConfigDict(frozen=True)

    name: str
    size_gb: float
    quantization: str
    cache_bytes_per_token: int | None = None
    """What one token of context window costs in the attention cache, or ``None`` when
    the model does not publish enough of its shape to say (ADR-021)."""

    context_tokens: int | None = None
    """The largest window the model supports, or ``None`` when the engine did not say.

    Not the window it will run with: Ollama loads with its own smaller default unless
    asked for more, which is why the report says both (ADR-019).
    """


class ModelFit(BaseModel):
    """How a model of a given size and quantization fits in memory.

    A rough estimate from the weight formula, not a promise. `status` is one of
    "fits", "tight", or "too_large".
    """

    model_config = ConfigDict(frozen=True)

    parameters_b: int
    quantization_bits: int
    weight_gb: float
    status: str


class WindowCost(BaseModel):
    """What one context window size would cost for one model, by formula.

    An approximation with stated assumptions (ADR-021), not a promise, and never a
    recommendation: it says what a size costs, not which size to choose.
    """

    model_config = ConfigDict(frozen=True)

    model: str
    window_tokens: int
    cache_gb: float
    total_gb: float
    status: str


class SystemProfile(BaseModel):
    """A frozen report of what the machine offers. Data, not a recommendation."""

    model_config = ConfigDict(frozen=True)

    engine_present: bool
    installed_models: tuple[InstalledModel, ...] = ()
    architecture: str = ""
    processor: str = ""
    os_name: str = ""
    cpu_count: int | None = None
    total_memory_gb: float = 0.0
    free_disk_gb: float = 0.0
    uptime_hours: float = 0.0
    fits: tuple[ModelFit, ...] = ()
    window_costs: tuple[WindowCost, ...] = ()
    available_memory_gb: float = 0.0
    notes: tuple[str, ...] = Field(default_factory=tuple)


def _probe_installed_models() -> tuple[bool, tuple[InstalledModel, ...]]:
    """Probe the local engine for installed models.

    Returns (engine_present, models). Any connection failure, timeout, or bad
    response means the engine is treated as absent - never an exception. A refused
    engine address is not swallowed the same way: `ollama_host` raises rather than
    letting the probe reach a machine that is not this one, and the caller turns that
    into a note instead of a silent "no engine".
    """
    url = f"{ollama_host()}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=_PROBE_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                return False, ()
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return False, ()

    models = []
    for entry in payload.get("models", []):
        details = entry.get("details", {})
        size_bytes = entry.get("size", 0)
        name = entry.get("name", "unknown")
        window, per_token = _probe_model_shape(name)
        models.append(
            InstalledModel(
                name=name,
                size_gb=round(size_bytes / 1024**3, 1),
                quantization=details.get("quantization_level", "unknown"),
                context_tokens=window,
                cache_bytes_per_token=per_token,
            )
        )
    return True, tuple(models)


def _probe_model_shape(model: str) -> tuple[int | None, int | None]:
    """Ask the engine what ``model`` supports and what a token of window costs it.

    Reads and does not act (ADR-012): asking what a model is does not load it. Any
    failure means the numbers are unknown, and unknown is reported as unknown rather
    than filled in with something plausible.
    """
    request = urllib.request.Request(
        f"{ollama_host()}/api/show",
        data=json.dumps({"model": model}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_PROBE_TIMEOUT_SECONDS * 4) as response:
            info = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None, None
    model_info = info.get("model_info", {})
    window = None
    for key, value in model_info.items():
        if key.endswith("context_length") and isinstance(value, int):
            window = value
            break
    return window, _cache_bytes_per_token(model_info)


def _cache_bytes_per_token(model_info: dict[str, object]) -> int | None:
    """Bytes the attention cache holds per token, from the model's own metadata.

    Two caches, one for keys and one for values, across every layer, for every attention
    head that has one, at the width of a head. Keys are matched by suffix because the
    metadata is prefixed per architecture, and hardcoding one family is the narrowness
    this avoids. Missing metadata yields ``None``: unknown is a usable answer, a guessed
    one is not (ADR-021).
    """

    def value(suffix: str) -> int | None:
        for key, found in model_info.items():
            if key.endswith(suffix) and isinstance(found, int) and found > 0:
                return found
        return None

    layers = value(".block_count")
    kv_heads = value(".attention.head_count_kv")
    head_width = value(".attention.key_length")
    if head_width is None:
        embedding, heads = value(".embedding_length"), value(".attention.head_count")
        head_width = embedding // heads if embedding and heads else None
    if not (layers and kv_heads and head_width):
        return None
    return 2 * layers * kv_heads * head_width * _CACHE_BYTES_PER_ELEMENT


def _estimate_window_costs(
    model: InstalledModel, per_token: int, free_memory_gb: float
) -> tuple[WindowCost, ...]:
    """What each window size would cost for ``model``, against the memory free now."""
    costs = []
    for window in _WINDOW_SIZES:
        if model.context_tokens is not None and window > model.context_tokens:
            continue
        cache_gb = per_token * window / 1024**3
        total = round(model.size_gb + cache_gb * _RUNTIME_ALLOWANCE, 1)
        if total > free_memory_gb:
            status = "too_large"
        elif total > free_memory_gb * 0.85:
            status = "tight"
        else:
            status = "fits"
        costs.append(
            WindowCost(
                model=model.name,
                window_tokens=window,
                cache_gb=round(cache_gb, 2),
                total_gb=total,
                status=status,
            )
        )
    return tuple(costs)


def _estimate_fits(total_memory_gb: float) -> tuple[ModelFit, ...]:
    """Estimate how common model sizes fit, by the weight formula.

    A model of P billion parameters at B bits weighs about P * B / 8 gigabytes.
    Compared against memory left after reserving some for the system. Orientation,
    not a promise: "fits" if it sits under the usable budget, "tight" if near it,
    "too_large" if over.
    """
    usable = max(total_memory_gb - _MEMORY_RESERVED_GB, 0.0)
    fits = []
    for params in _MODEL_SIZES_B:
        for bits in _QUANTIZATION_BITS:
            weight = round(params * bits / 8, 1)
            if weight > usable:
                status = "too_large"
            elif weight > usable * 0.85:
                status = "tight"
            else:
                status = "fits"
            fits.append(
                ModelFit(
                    parameters_b=params,
                    quantization_bits=bits,
                    weight_gb=weight,
                    status=status,
                )
            )
    return tuple(fits)


def _processor_name() -> str:
    """The processor name if the platform gives a useful one, else empty.

    `platform.processor()` often returns the architecture again or nothing; in that
    case we report nothing rather than something misleading.
    """
    name = platform.processor().strip()
    if not name or name.lower() == platform.machine().lower():
        return ""
    return name


def _acceleration_note() -> str:
    """An honest note about accelerators the engine may not use."""
    return (
        "GPU/NPU acceleration is not detected and may not be usable even if present. "
        "On Snapdragon, for example, a GPU (Adreno) and NPU exist but Ollama runs on "
        "CPU. Check how your engine reports it runs rather than assuming."
    )


def _free_memory_hint() -> str:
    """OS-specific hint for checking free memory in real time."""
    system = platform.system()
    if system == "Windows":
        return "Check free memory in real time with Task Manager (Ctrl+Shift+Esc)."
    if system == "Darwin":
        return "Check free memory in real time with Activity Monitor."
    return "Check free memory in real time with your system monitor (e.g. `free -h`)."


def profile_system() -> SystemProfile:
    """Detect and report what the machine offers. No side effects."""
    engine_note = ""
    try:
        engine_present, models = _probe_installed_models()
    except ProviderError as error:
        engine_present, models = False, ()
        engine_note = str(error)

    memory = psutil.virtual_memory()
    total_memory_gb = round(memory.total / 1024**3, 1)
    available_memory_gb = round(memory.available / 1024**3, 1)
    window_costs = tuple(
        cost
        for model in models
        if model.cache_bytes_per_token
        for cost in _estimate_window_costs(model, model.cache_bytes_per_token, available_memory_gb)
    )
    free_disk_gb = round(shutil.disk_usage(os.path.expanduser("~")).free / 1024**3, 1)
    uptime_hours = round((time.time() - psutil.boot_time()) / 3600, 1)

    notes = [
        "Capacity is an estimate from total memory; ensure enough is actually free.",
        "Exceeding available memory does not crash but forces swapping to disk, "
        "which makes a model run very slowly - 'fits' assumes the memory is free.",
        _free_memory_hint(),
        _acceleration_note(),
    ]
    if uptime_hours >= 72:
        notes.append(
            f"Up {uptime_hours} hours: a restart can free fragmented memory and "
            "improve model performance."
        )
    if any(model.context_tokens for model in models):
        notes.append(
            "A model's window above is the largest it supports, not the one it will run "
            "with: Ollama loads with its own smaller default - 4096 tokens, measured - "
            "and silently drops whatever does not fit. Set `context_tokens` in your "
            "configuration and LACC asks for that window and refuses a prompt too large "
            "for it. A larger window costs memory."
        )
    if engine_note:
        notes.append(engine_note)
    elif not engine_present:
        notes.append(
            "No local engine detected. If you use Ollama, start it, then pull a "
            "model, for example: ollama pull llama3.2"
        )

    return SystemProfile(
        engine_present=engine_present,
        installed_models=models,
        architecture=platform.machine(),
        processor=_processor_name(),
        os_name=f"{platform.system()} {platform.release()}".strip(),
        cpu_count=os.cpu_count(),
        total_memory_gb=total_memory_gb,
        free_disk_gb=free_disk_gb,
        uptime_hours=uptime_hours,
        fits=_estimate_fits(total_memory_gb),
        window_costs=window_costs,
        available_memory_gb=available_memory_gb,
        notes=tuple(notes),
    )
