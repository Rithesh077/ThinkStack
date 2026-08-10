"""Which GGUF answers a given task, on this machine, right now.

Every dependency is INJECTED -- registry, manifest, budget, external finder --
for two reasons. It makes routing testable against fabricated machines with no
hardware or llama.cpp present, and it stops an import cycle: ollama_client
already reaches into domain.model_manager, so reaching back up into
infrastructure.hardware would close the loop.

Resolution order, strongest claim first::

    registry, user-assigned      the user chose this, in Bench
    registry, manifest-assigned  a release put it there
    bundled.json                 what this build ships
    TASK_MODEL_MAP / .env        deprecated; warns when explicitly set
    base model                   the floor -- always tried last

A candidate must both EXIST and FIT the memory budget. The first that does both
wins; anything that exists but does not fit is remembered, so the caller can
explain the downgrade rather than silently producing worse results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

logger = logging.getLogger(__name__)

# a function that, given a wanted filename, returns a loadable path for the same
# weights somewhere else on this machine (LM Studio, a previous download), or
# None. Injected so routing can be tested without touching a filesystem.
ExternalFinder = Callable[[str], Optional[Path]]


@dataclass(frozen=True)
class Candidate:
    """one model considered for a task, and where the claim came from."""

    path: Path
    source: str          # registry-user | registry-manifest | bundled | legacy | base
    entry_id: str | None = None
    size_gb: float = 0.0


@dataclass(frozen=True)
class Resolution:
    """The outcome of routing one task.

    Carries the REASON, not just the path. A downgrade the interface cannot
    explain looks to the user like the app is simply worse, so the reasoning
    has to be data rather than a log line.
    """

    path: Path | None
    entry_id: str | None = None
    source: str = "none"
    reason: str = ""
    ollama_tag: str | None = None
    # set when a model was skipped purely because it did not fit. this is the
    # difference between "you have no analysis model" and "your analysis model
    # is too big for the memory free right now", which need different fixes.
    downgraded_from: str | None = None

    @property
    def resolved(self) -> bool:
        return self.path is not None or self.ollama_tag is not None

    def as_dict(self) -> dict:
        return {
            "path": str(self.path) if self.path else None,
            "entry_id": self.entry_id,
            "source": self.source,
            "reason": self.reason,
            "ollama_tag": self.ollama_tag,
            "downgraded_from": self.downgraded_from,
        }


def _fits(size_gb: float, budget_gb: float) -> bool:
    """Whether `size_gb` fits `budget_gb`.

    A budget of 0 means "could not measure", and is treated as NO constraint.
    Refusing to load on an unknown budget turns a failed measurement into a
    broken app; attempting it lets llama.cpp fail properly instead.

    Callers holding a MachineCapability should pass `fits_fn` to `resolve` so
    the answer comes from `capability.plan_for_size` rather than being derived
    twice. This is the fallback for callers holding only a number.
    """
    if budget_gb <= 0:
        return True
    return size_gb <= budget_gb


def _size_of(path: Path, declared: float) -> float:
    """Size in GB: measured when the file is readable, else as declared.

    NOT `hardware.model_file_size_gb`, which rounds to 2dp. This is compared
    against a memory budget, and rounding a comparison input is how a model
    that does not fit gets approved -- at 2dp anything under ~5 MB reads as
    0.0 GB and passes any budget. Round at display time, never here.

    The declared size can be stale if a user swapped the file, so it is only
    the fallback.
    """
    try:
        return path.stat().st_size / (1024 ** 3)
    except OSError:
        return declared


def collect_candidates(
    task: str,
    *,
    registry,
    manifest,
    models_dir: Path,
    external_finder: ExternalFinder | None = None,
    legacy_defaults: Sequence[str] = (),
) -> list[Candidate]:
    """Every model claiming `task`, strongest claim first.

    Checks existence but NOT the budget. Keeping them separate is what lets a
    caller tell "nothing is set up for this task" apart from "what is set up
    does not fit right now" -- different problems with different remedies.
    """
    out: list[Candidate] = []
    seen: set[str] = set()

    def add(path: Path, source: str, entry_id: str | None, size: float) -> None:
        key = str(path)
        if key in seen:
            return
        seen.add(key)
        out.append(Candidate(path=path, source=source, entry_id=entry_id,
                             size_gb=_size_of(path, size)))

    # 1 + 2. the registry, already ordered user-assigned first by `for_task`
    for entry in registry.for_task(task):
        if not entry.exists():
            continue
        add(Path(entry.path),
            "registry-user" if entry.user_assigned else "registry-manifest",
            entry.id, entry.size_gb)

    # 3. what this build bundles for the task
    for filename in manifest.files_for(task):
        p = Path(models_dir) / filename
        if p.is_file():
            bundled = manifest.get_by_file(filename)
            add(p, "bundled", bundled.id if bundled else None,
                bundled.size_gb if bundled else 0.0)

    # 4. the deprecated hardcoded defaults. still honoured so a tester's
    #    gitignored .env override keeps working -- we cannot see who has one.
    for filename in legacy_defaults:
        p = Path(models_dir) / filename
        if p.is_file():
            add(p, "legacy", None, 0.0)
        elif external_finder is not None:
            # the user may hold these exact weights under another runtime's
            # naming; using those beats degrading to the base model.
            found = external_finder(filename)
            if found is not None:
                add(found, "legacy", None, 0.0)

    return out


def resolve(
    task: str,
    *,
    registry,
    manifest,
    models_dir: Path,
    budget_gb: float = 0.0,
    external_finder: ExternalFinder | None = None,
    legacy_defaults: Sequence[str] = (),
    base_model: Path | None = None,
    ollama_lookup: Callable[[str], Optional[str]] | None = None,
    plan_for_size: Callable[[float], object] | None = None,
) -> Resolution:
    """Pick the model for `task`. Never raises.

    `plan_for_size` should be `MachineCapability.plan_for_size`: it decides
    whether a model fits AND supplies the sentence explaining why not, so the
    router acts on the same answer Bench displays.

    Nothing available falls through to the base model; no base model resolves
    to nothing, which the caller reports rather than crashes on.
    """
    candidates = collect_candidates(
        task,
        registry=registry,
        manifest=manifest,
        models_dir=models_dir,
        external_finder=external_finder,
        legacy_defaults=legacy_defaults,
    )

    too_big: Candidate | None = None
    too_big_why = ""
    for c in candidates:
        # ONE authority for the decision: the budget. `plan_for_size` supplies
        # the SENTENCE only.
        #
        # Letting capability.plan_for_size decide instead looked tidier and was
        # wrong: it reads the live machine, so it silently overrode the budget
        # its caller had computed -- and re-created the two-disagreeing-budgets
        # problem this refactor exists to remove. It also made routing
        # untestable, because a stubbed budget no longer affected the outcome.
        fits = _fits(c.size_gb, budget_gb)
        why = f"needs {c.size_gb:.1f} GB but only {budget_gb:.1f} GB is free"
        if not fits and plan_for_size is not None:
            plan = plan_for_size(c.size_gb)
            why = str(getattr(plan, "reason", "")) or why

        if fits:
            return Resolution(
                path=c.path,
                entry_id=c.entry_id,
                source=c.source,
                reason=f"{c.path.name} ({c.size_gb:.1f} GB)",
            )
        if too_big is None:
            too_big, too_big_why = c, why

    # Nothing loadable from disk. Ollama may still be able to serve these
    # weights over http even though llama.cpp cannot open its blob store.
    if ollama_lookup is not None:
        tag = ollama_lookup(task)
        if tag:
            return Resolution(
                path=None, ollama_tag=tag, source="ollama",
                reason=f"served by Ollama as {tag}",
            )

    # The floor. Always tried last, and deliberately not budget-checked: if the
    # bundled baseline does not fit, there is nothing left to fall back TO, and
    # refusing to try guarantees failure where attempting might succeed.
    if base_model is not None and Path(base_model).is_file():
        if too_big is not None:
            logger.warning(
                "task %s: %s %s; using %s",
                task, too_big.path.name, too_big_why, Path(base_model).name,
            )
            return Resolution(
                path=Path(base_model), source="base",
                entry_id=None,
                # the sentence comes from capability.plan_for_size when the
                # caller supplied it, so Bench and Diagnose cannot disagree
                # about why the same model was skipped.
                reason=(f"{too_big.path.name} {too_big_why}, "
                        f"so {Path(base_model).name} is being used"),
                downgraded_from=too_big.path.name,
            )
        return Resolution(
            path=Path(base_model), source="base",
            reason=f"no model is assigned to {task.replace('_', ' ')}, using the bundled model",
        )

    return Resolution(
        path=None, source="none",
        reason=f"no model is available for {task.replace('_', ' ')}",
        downgraded_from=too_big.path.name if too_big else None,
    )
