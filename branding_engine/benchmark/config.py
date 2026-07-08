"""Branding benchmark configuration (Phase C5)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BrandingBenchmarkConfig:
    """One benchmark run: a fixed, deterministic branding workload.

    The workload (theme, brand facts, resolution) is deterministic; wall-clock
    timings are not. Defaults to the hermetic ``mock`` renderer so the benchmark
    needs no FFmpeg or GPU.
    """

    renderer: str = "mock"
    theme: str = "corporate"
    creator: str = "Creator Name"
    channel: str = "My Channel"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    scene_duration_s: float = 5.0
    n_scenes: int = 2
    export_profiles: list[str] = field(
        default_factory=lambda: ["reel_9x16", "square_1x1"]
    )
    repetitions: int = 3
    mock_max_dim: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
