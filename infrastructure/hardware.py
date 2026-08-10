"""What this machine has, and what that allows.

Sizing the context and the offload against real memory is what keeps a large
model from taking the process down on a small machine.
"""

import json
import logging
import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HardwareProfile:
    """snapshot of the machine's compute resources."""
    total_ram_gb: float = 0.0
    available_ram_gb: float = 0.0
    cpu_cores: int = 1
    gpu_name: str = ""
    # "nvidia" | "apple" | "none". Rust has always sent this and Python had
    # nowhere to put it, so it was dropped at the boundary -- and then the
    # CUDA-only fallback re-derived the answer wrongly. An Apple Silicon Mac
    # reports vram_gb 0.0 because its GPU has no *dedicated* memory, not
    # because it has no GPU. Without the vendor there is no way to tell those
    # two situations apart, and every consumer guessed.
    gpu_vendor: str = "none"
    vram_gb: float = 0.0
    # True when the GPU shares system RAM (Apple Silicon, most integrated
    # graphics). vram_gb is meaningless for these machines; what matters is
    # how much of total_ram_gb the GPU may borrow.
    unified_memory: bool = False
    has_cuda: bool = False
    tier: str = "low"  # low | medium | high


def _detect_ram() -> tuple[float, float]:
    """(total_gb, available_gb).

    Failing here is not cosmetic: 0.0 total pins the machine to the "low" tier
    for the life of the process, so the real exception is logged rather than a
    guess about its cause.
    """
    try:
        import psutil
        mem = psutil.virtual_memory()
        return round(mem.total / (1024 ** 3), 1), round(mem.available / (1024 ** 3), 1)
    except Exception as e:  # noqa: BLE001 - never let hardware probing kill startup
        logger.error(
            "ram detection failed (%s: %s); falling back to the low tier",
            type(e).__name__, e, exc_info=True,
        )
        return 0.0, 0.0


def _detect_cpu_cores() -> int:
    """return the number of physical cpu cores."""
    try:
        import psutil
        return psutil.cpu_count(logical=False) or os.cpu_count() or 1
    except ImportError:
        return os.cpu_count() or 1


def _detect_gpu() -> tuple[str, str, float, bool, bool]:
    """(gpu_name, gpu_vendor, vram_gb, has_cuda, unified_memory).

    FALLBACK ONLY -- the packaged app gets this natively from the Tauri shell.

    Must not import torch: it is bundled for embeddings, not inference, and
    whether torch sees CUDA says nothing about whether our llama.cpp build can
    offload. That question is engine_supports_gpu_offload().

    Every branch returns rather than raises. A detection path that can take
    down its caller turns "no GPU" into a crash.
    """
    # nvidia-smi is the cheapest reliable CUDA probe and needs no python deps.
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2, check=False,
        ).stdout.strip()
        if out:
            name, _, mem = out.splitlines()[0].partition(",")
            return name.strip(), "nvidia", round(float(mem) / 1024, 1), True, False
    except (OSError, ValueError, subprocess.SubprocessError):
        pass

    # Apple Silicon: no dedicated VRAM to report, so vram stays 0.0 and
    # `unified_memory` is what tells a caller the GPU borrows system RAM.
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "Apple Silicon", "apple", 0.0, False, True

    return "", "none", 0.0, False, False


def engine_supports_gpu_offload() -> bool:
    """Can the llama.cpp build we ship put layers on the GPU?

    A fact about the BINARY, not the machine, and the only thing that decides
    whether n_gpu_layers > 0 will work. A CUDA machine on a CPU-only wheel
    cannot offload; an Apple Silicon Mac on a Metal wheel can, while reporting
    0 GB of VRAM. Never infer this from the hardware.
    """
    try:
        from llama_cpp import llama_supports_gpu_offload
        return bool(llama_supports_gpu_offload())
    except (ImportError, AttributeError, OSError):
        # Older binding without the symbol, or llama.cpp not installed.
        # Assume no: claiming offload we cannot do fails the model load.
        return False


def _classify_tier(total_ram_gb: float, vram_gb: float) -> str:
    """classify a machine into a performance tier.

    tiers:
        low:    <12 gb ram and no usable gpu (<2 gb vram)
        medium: 12-24 gb ram or 2-8 gb vram
        high:   >24 gb ram or >8 gb vram
    """
    if vram_gb > 8 or total_ram_gb > 24:
        return "high"
    if vram_gb >= 2 or total_ram_gb >= 12:
        return "medium"
    return "low"


def _profile_from_env() -> HardwareProfile | None:
    """The profile the Tauri shell measured, or None if it did not.

    Preferring it keeps the packaged app from probing CUDA on startup, which is
    slow and can stall outright on a broken driver.
    """
    raw = os.environ.get("THINKSTACK_HW_PROFILE")
    if not raw:
        return None
    try:
        d = json.loads(raw)
        total = float(d.get("total_ram_gb", 0.0))
        vram = float(d.get("vram_gb", 0.0))
        vendor = str(d.get("gpu_vendor", "none")).lower()
        return HardwareProfile(
            total_ram_gb=total,
            available_ram_gb=float(d.get("available_ram_gb", 0.0)),
            cpu_cores=int(d.get("cpu_cores") or d.get("cpu_threads") or 1),
            gpu_name=str(d.get("gpu_name", "")),
            gpu_vendor=vendor,
            vram_gb=vram,
            # Rust may report it directly; infer from the vendor otherwise so
            # an older shell paired with a newer backend still behaves.
            unified_memory=bool(d.get("unified_memory", vendor == "apple")),
            has_cuda=bool(d.get("has_cuda", False)),
            tier=str(d.get("tier") or _classify_tier(total, vram)),
        )
    except (ValueError, TypeError) as e:
        logger.warning("could not parse THINKSTACK_HW_PROFILE, detecting locally: %s", e)
        return None


def profile_system() -> HardwareProfile:
    """The machine profile. Cached after the first call.

    Hardware does not change while the app runs, and probing on every question
    would slow every question. POST /api/system/diagnose clears the cache.
    """
    global _cached_profile
    if _cached_profile is not None:
        return _cached_profile

    from_env = _profile_from_env()
    if from_env is not None:
        logger.info(
            "hardware profile (from shell): %s tier - %.1f gb ram (%.1f free), "
            "%d cores, %s (%.1f gb vram)",
            from_env.tier, from_env.total_ram_gb, from_env.available_ram_gb,
            from_env.cpu_cores, from_env.gpu_name or "no gpu", from_env.vram_gb,
        )
        _cached_profile = from_env
        return from_env

    total_ram, avail_ram = _detect_ram()
    cores = _detect_cpu_cores()
    gpu_name, gpu_vendor, vram, has_cuda, unified = _detect_gpu()
    tier = _classify_tier(total_ram, vram)

    profile = HardwareProfile(
        total_ram_gb=total_ram,
        available_ram_gb=avail_ram,
        cpu_cores=cores,
        gpu_name=gpu_name,
        gpu_vendor=gpu_vendor,
        vram_gb=vram,
        unified_memory=unified,
        has_cuda=has_cuda,
        tier=tier,
    )

    logger.info(
        "hardware profile (detected): %s tier - %.1f gb ram (%.1f free), %d cores, %s (%.1f gb vram)",
        tier, total_ram, avail_ram, cores,
        gpu_name or "no gpu", vram,
    )

    _cached_profile = profile
    return profile


_cached_profile: HardwareProfile | None = None


def recommended_ctx_size(tier: str | None = None) -> int:
    """A context size the tier can hold: 2048, 4096 or 8192."""
    if tier is None:
        tier = profile_system().tier
    return {"low": 2048, "medium": 4096, "high": 8192}.get(tier, 2048)


def recommended_gpu_layers(vram_gb: float | None = None, model_size_gb: float = 1.0) -> int:
    """Layers to offload. 0 is CPU-only, -1 is all of them.

    A layer of a 1-3B model costs ~30-60 MB of VRAM; 0.5 GB is held back for
    the KV cache and driver overhead.
    """
    if vram_gb is None:
        vram_gb = profile_system().vram_gb

    if vram_gb < 1.5:
        return 0  # not enough vram for any useful offload

    usable_vram = vram_gb - 0.5  # headroom
    if model_size_gb <= usable_vram:
        return -1  # full offload fits

    # partial offload: estimate fraction of layers that fit
    # most gguf models have 24-32 layers; assume 32 for safety
    fraction = usable_vram / model_size_gb
    layers = int(fraction * 32)
    return max(0, min(layers, 32))


def max_safe_model_size_gb(
    available_ram_gb: float | None = None,
    vram_gb: float | None = None,
) -> float:
    """Largest model file this machine can load right now.

    3 GB is reserved for the OS, the embedding model, Python and the frontend.
    The model may sit in RAM, VRAM, or both.
    """
    if available_ram_gb is None or vram_gb is None:
        profile = profile_system()
        available_ram_gb = profile.available_ram_gb if available_ram_gb is None else available_ram_gb
        vram_gb = profile.vram_gb if vram_gb is None else vram_gb

    ram_budget = max(0, available_ram_gb - 3.0)
    # model can span ram + vram
    return round(ram_budget + vram_gb, 1)


def model_file_size_gb(model_path: Path) -> float:
    """Size of a GGUF in GB, or 0.0 when the file is missing."""
    try:
        return round(model_path.stat().st_size / (1024 ** 3), 2)
    except (OSError, FileNotFoundError):
        return 0.0
