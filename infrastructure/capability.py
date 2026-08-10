"""What this machine can actually do.

ONE place that turns hardware facts into decisions. Anything asking "can I run
this model", "how big a context", "how many tokens may I ask for" comes here
and derives nothing itself.

    Rust (diagnosis.rs)   FACTS about the machine
    llama.cpp             ONE fact about the binary: can it offload at all?
    this module           every DECISION derived from those facts
    callers               ask; never derive

Decisions live here because they are policy, and policy has to be testable
against machines nobody owns -- every test fabricates a profile and asserts the
decision, on any OS, with no GPU present.

This module answers questions and never acts. No downloads, no loading, no disk
changes, no consent: those belong above it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from infrastructure.hardware import HardwareProfile

# Context windows by tier. Bigger is better but costs memory: the KV cache
# grows with the window, and on a small machine an oversized context is what
# turns a working model into an OOM at load.
CTX_BY_TIER = {"low": 2048, "medium": 4096, "high": 8192}

# A summary does not get better past roughly a thousand tokens, so the reply
# budget is capped. The floor keeps a summary plus a few key points possible
# even on the smallest window.
OUTPUT_CEILING = 1024
OUTPUT_FLOOR = 256

# Rough English ratio. A tokenizer is not a divider, so the margin below
# absorbs the difference plus the chat template's own tokens.
CHARS_PER_TOKEN = 4
PROMPT_SAFETY_MARGIN = 0.85

# A research paper's body text, in characters. Used only to decide whether the
# single-pass path is plausible; the real decision is made per-document by the
# caller comparing its own length against `input_chars`.
TYPICAL_PAPER_CHARS = 12000

# Leave room for the KV cache and the runtime alongside the weights themselves.
MODEL_MEMORY_HEADROOM_GB = 1.0


@dataclass(frozen=True)
class ModelPlan:
    """How to run one model on this machine, or why we cannot.

    Frozen because it is a decision, not a setting. A caller that wants a
    different plan asks for a different plan; it does not mutate this one.
    """

    fits: bool
    reason: str            # human sentence; empty when it fits
    n_ctx: int             # context window to load the model with
    n_gpu_layers: int      # 0 = CPU only; -1 = all layers on the GPU
    output_tokens: int     # safe max_tokens for a reply
    input_chars: int       # prompt characters that fit alongside that reply
    needs_map_reduce: bool  # a typical paper will not fit in one pass


class MachineCapability:
    """Answers every hardware-derived question, from facts SUPPLIED to it.

    Nothing here may look anything up. `engine_offload` is a fact about the
    llama.cpp binary and `accelerable_device` about the graphics drivers, so
    both are injected -- otherwise a fabricated profile produces advice about
    the machine running the test rather than the machine described, which is
    the guess this class exists to remove.

    Both were once inferred from the hardware, and both went wrong: Apple
    Silicon reports no CUDA and 0 GB of VRAM, so `has_cuda && vram >= 2` pinned
    every Mac to CPU no matter what its engine supported.
    """

    def __init__(self, profile: HardwareProfile, engine_offload: bool = False,
                 accelerable_device: str | None = None) -> None:
        self.profile = profile
        self.engine_offload = engine_offload
        # label of the device acceleration could use, or None. See above.
        self.accelerable_device = accelerable_device

    # ---------------------------------------------------------------- facts

    @property
    def tier(self) -> str:
        return self.profile.tier or "low"

    @property
    def usable_gpu_memory_gb(self) -> float:
        """Memory the GPU may use for weights, in GB.

        Unified-memory machines report 0 GB of VRAM because there is no
        separate pool -- the GPU borrows system RAM. Reading that 0 as "no GPU"
        is the mistake that pinned every Mac to CPU.

        Half of total RAM, deliberately conservative: the OS, the app and the
        embedding model share that pool.
        """
        if not self.engine_offload:
            return 0.0
        if self.profile.unified_memory:
            return max(0.0, self.profile.total_ram_gb * 0.5)
        return max(0.0, self.profile.vram_gb)

    # ------------------------------------------------------------ decisions

    def context_size(self) -> int:
        """Context window for this machine."""
        return CTX_BY_TIER.get(self.tier, CTX_BY_TIER["low"])

    def output_tokens(self, ctx: int | None = None) -> int:
        """Tokens of REPLY this machine can afford to ask for.

        A quarter of the window, clamped. Asking 1024 of a 2048 window spends
        half the context on the answer and leaves the paper competing for the
        rest, which is how summarization stopped fitting its own request.
        """
        ctx = ctx or self.context_size()
        return max(OUTPUT_FLOOR, min(OUTPUT_CEILING, ctx // 4))

    def input_chars(self, ctx: int | None = None, output_tokens: int | None = None) -> int:
        """Prompt characters that fit alongside the reply.

        The window holds BOTH. This is the arithmetic nothing owned before.
        """
        ctx = ctx or self.context_size()
        out = output_tokens if output_tokens is not None else self.output_tokens(ctx)
        room_tokens = max(0, ctx - out)
        return int(room_tokens * CHARS_PER_TOKEN * PROMPT_SAFETY_MARGIN)

    def gpu_layers(self, model_size_gb: float) -> int:
        """How many layers to put on the GPU. 0 = CPU, -1 = all of them.

        Returns 0 whenever the engine cannot offload, whatever the hardware
        says. Claiming an offload the binary cannot perform does not degrade
        gracefully -- the model load raises.
        """
        if not self.engine_offload:
            return 0
        usable = self.usable_gpu_memory_gb - MODEL_MEMORY_HEADROOM_GB
        if usable <= 0:
            return 0
        if model_size_gb <= usable:
            return -1  # everything fits; let llama.cpp put it all on the GPU
        # Partial offload, proportional to what fits. Most GGUF models in this
        # size class have 24-32 layers; 32 is the safe assumption.
        return max(0, min(32, int((usable / model_size_gb) * 32)))

    # ----------------------------------------------------------- the answer

    def plan_for_size(self, model_size_gb: float) -> ModelPlan:
        """Everything needed to run a model of this size -- or why we cannot.

        Sized by NUMBER, not by path, because the important callers do not have
        a file yet: "can this machine run this 4 GB model?" has to be
        answerable before anything is downloaded.
        """
        ctx = self.context_size()
        out = self.output_tokens(ctx)
        chars = self.input_chars(ctx, out)

        # Weights must fit in memory alongside everything else running.
        budget = self.profile.available_ram_gb or self.profile.total_ram_gb
        needed = model_size_gb + MODEL_MEMORY_HEADROOM_GB
        fits = budget <= 0 or needed <= budget

        reason = ""
        if not fits:
            reason = (
                f"needs about {needed:.1f} GB but only {budget:.1f} GB is free"
            )

        return ModelPlan(
            fits=fits,
            reason=reason,
            n_ctx=ctx,
            n_gpu_layers=self.gpu_layers(model_size_gb),
            output_tokens=out,
            input_chars=chars,
            needs_map_reduce=chars < TYPICAL_PAPER_CHARS,
        )

    def plan_for_file(self, path: Path) -> ModelPlan:
        """plan_for_size for a model already on disk. Sugar, nothing more."""
        try:
            size_gb = path.stat().st_size / (1024 ** 3)
        except OSError:
            return ModelPlan(
                fits=False, reason=f"cannot read {path.name}", n_ctx=self.context_size(),
                n_gpu_layers=0, output_tokens=OUTPUT_FLOOR, input_chars=0,
                needs_map_reduce=True,
            )
        return self.plan_for_size(size_gb)

    def can_run(self, model_size_gb: float) -> bool:
        return self.plan_for_size(model_size_gb).fits

    # ----------------------------------------------------------- for the UI

    def report(self) -> dict:
        """Facts, decisions and advice, for the Diagnose screen.

        Returns DATA, not formatted text: the frontend owns layout, and the
        same structure can later feed the model picker when Diagnose and
        "Add better models" are merged.
        """
        p = self.profile
        ctx = self.context_size()
        out = self.output_tokens(ctx)
        return {
            "machine": {
                "tier": self.tier,
                "total_ram_gb": p.total_ram_gb,
                "available_ram_gb": p.available_ram_gb,
                "cpu_cores": p.cpu_cores,
                "gpu_name": p.gpu_name,
                "gpu_vendor": p.gpu_vendor,
                "vram_gb": p.vram_gb,
                "unified_memory": p.unified_memory,
            },
            "engine": {
                "gpu_offload_supported": self.engine_offload,
                "usable_gpu_memory_gb": round(self.usable_gpu_memory_gb, 1),
            },
            "limits": {
                "context_size": ctx,
                "output_tokens": out,
                "input_chars": self.input_chars(ctx, out),
                "long_papers_need_multiple_passes": self.input_chars(ctx, out)
                < TYPICAL_PAPER_CHARS,
            },
            "advice": self.advice(),
        }

    def advice(self) -> list[str]:
        """Plain sentences a researcher can act on. No jargon, no scolding."""
        out: list[str] = []
        p = self.profile

        if self.input_chars() < TYPICAL_PAPER_CHARS:
            out.append(
                "Long papers are summarized in several passes on this machine, "
                "which is slower. A larger model with a bigger context would "
                "read them in one go."
            )
        if p.unified_memory and not self.engine_offload:
            out.append(
                "This Mac has a GPU the app is not using: the installed "
                "inference engine was built without Metal support, so "
                "everything runs on the CPU."
            )
        # Two independent detectors answer "is there a GPU here", and they
        # disagree. `vram_gb` comes from nvidia-smi, which exists only where
        # NVIDIA's proprietary driver is installed; `accelerable_device` comes
        # from Vulkan, which reaches AMD, Intel and open NVIDIA drivers too.
        #
        # Gating on vram_gb meant an AMD, Intel or Mesa/NVK machine reported
        # 0.0 GB and this sentence never printed -- while the Bench card beside
        # it offered them the graphics download anyway. The offer appeared with
        # nothing explaining why anyone would want it, on exactly the machines
        # the Vulkan work was done to reach.
        #
        # So ask the detector that can actually see them, and keep vram_gb only
        # as the fallback for a machine where Vulkan told us nothing but
        # nvidia-smi found a card.
        usable = self.accelerable_device
        has_gpu = bool(usable) or p.vram_gb >= 2
        if not p.unified_memory and has_gpu and not self.engine_offload:
            # The original wording -- "the installed inference engine is a
            # CPU-only build and cannot use it" -- was accurate and useless. It
            # named an internal component, gave no reason, and offered nothing,
            # so a tester with an RTX 4050 read it as a defect rather than as a
            # deliberate trade.
            #
            # It must not promise what we cannot deliver, and must not state a
            # size: the real figure is measured by acceleration.plan() and shown
            # where the button is. Whether the offer is real is a question about
            # Vulkan, not about the vendor -- an earlier draft gated it on
            # gpu_vendor == "nvidia", correct while the plan was CUDA and wrong
            # the moment it became Vulkan.
            if usable:
                out.append(
                    f"{usable} is not being used yet. ThinkStack ships with "
                    "processor-only inference to keep the download small; "
                    "graphics support can be added below."
                )
            else:
                out.append(
                    f"{p.gpu_name or 'Your graphics card'} was found, but no "
                    "graphics driver ThinkStack can use is installed, so "
                    "analysis runs on the processor."
                )
        if p.available_ram_gb and p.available_ram_gb < 2:
            out.append(
                f"Only {p.available_ram_gb:.1f} GB of memory is free. Closing "
                "other applications will make analysis noticeably faster."
            )
        if not out:
            out.append("This machine can run the bundled models comfortably.")
        return out


def _detect_accelerable_device() -> str | None:
    """the device acceleration could use on THIS machine, or None.

    Called only by `for_this_machine`, which is the one function here allowed
    to touch real hardware. Everything else receives the answer.
    """
    try:
        from infrastructure import vulkan
        device = vulkan.best_device()
        return device.label if device else None
    except Exception:  # noqa: BLE001 - advice must never be the thing that fails
        return None


def for_this_machine() -> MachineCapability:
    """The capability of the machine we are running on.

    Convenience for callers that just want the answer. Tests construct
    MachineCapability directly with a fabricated profile instead.
    """
    from infrastructure.hardware import engine_supports_gpu_offload, profile_system

    return MachineCapability(
        profile_system(),
        engine_supports_gpu_offload(),
        _detect_accelerable_device(),
    )
