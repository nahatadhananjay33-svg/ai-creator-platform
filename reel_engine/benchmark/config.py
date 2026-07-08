"""Reel benchmark configuration (Phase C2)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ReelBenchmarkConfig:
    """One benchmark run: a fixed, deterministic workload for a renderer.

    The *workload* (timeline size, resolution, fps, profiles) is deterministic;
    wall-clock timings are not (that is the nature of a benchmark). Defaults to
    the hermetic ``mock`` renderer so the benchmark needs no FFmpeg.
    """

    renderer: str = "mock"
    n_scenes: int = 3
    scene_duration_s: float = 2.0
    width: int = 1080
    height: int = 1920
    fps: int = 30
    export_profiles: list[str] = field(
        default_factory=lambda: ["reel_9x16", "square_1x1", "landscape_16x9"]
    )
    repetitions: int = 3
    mock_max_dim: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
