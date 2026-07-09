"""Editing benchmark configuration (Phase C11)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class EditBenchmarkConfig:
    """One benchmark run: a fixed, deterministic edit workload (MockProvider).

    Hermetic and pure-CPU — no renderer, ffmpeg, GPU, model, or network. Wall-clock
    timings are not deterministic; the workload (prompt, patch set) is.
    """

    prompt: str = "Why investing in real estate early is beneficial"
    template: str = "real_estate"
    n_patches: int = 8            # patches applied per case
    width: int = 1080
    height: int = 1920
    fps: int = 30
    repetitions: int = 5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
