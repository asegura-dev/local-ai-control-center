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

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
_PROBE_TIMEOUT_SECONDS = 0.5
_QUANTIZATION_BITS: tuple[int, ...] = (3, 4, 8)
_MODEL_SIZES_B: tuple[int, ...] = (1, 3, 8, 14, 32)
_MEMORY_RESERVED_GB = 4.0
"""Memory left for the OS and other work when judging what a model can use."""


class InstalledModel(BaseModel):
    """A model reported by the engine as installed locally."""

    model_config = ConfigDict(frozen=True)

    name: str
    size_gb: float
    quantization: str


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
    notes: tuple[str, ...] = Field(default_factory=tuple)


def _ollama_host() -> str:
    """The engine address, honoring OLLAMA_HOST, defaulting to loopback."""
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if not host:
        return DEFAULT_OLLAMA_HOST
    if not host.startswith("http"):
        host = f"http://{host}"
    return host


def _probe_installed_models() -> tuple[bool, tuple[InstalledModel, ...]]:
    """Probe the local engine for installed models.

    Returns (engine_present, models). Any connection failure, timeout, or bad
    response means the engine is treated as absent - never an exception.
    """
    url = f"{_ollama_host()}/api/tags"
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
        models.append(
            InstalledModel(
                name=entry.get("name", "unknown"),
                size_gb=round(size_bytes / 1024**3, 1),
                quantization=details.get("quantization_level", "unknown"),
            )
        )
    return True, tuple(models)


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
    engine_present, models = _probe_installed_models()

    total_memory_gb = round(psutil.virtual_memory().total / 1024**3, 1)
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
    if not engine_present:
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
        notes=tuple(notes),
    )
