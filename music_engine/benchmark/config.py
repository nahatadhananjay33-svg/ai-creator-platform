"""Music benchmark configuration (Phase C8)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MusicBenchmarkConfig:
    """One benchmark run: a fixed, deterministic music-mixing workload.

    The workload (reel length, soundtrack, sample rate) is deterministic;
    wall-clock timings are not. Defaults to the hermetic ``mock`` renderer so the
    benchmark needs no FFmpeg, GPU, model, or network.
    """

    renderer: str = "mock"
    soundtrack: str = "ambient"
    reel_duration_s: float = 24.0
    n_scenes: int = 4
    width: int = 1080
    height: int = 1920
    fps: int = 30
    sample_rate: int = 44_100
    export_profiles: list[str] = field(
        default_factory=lambda: ["reel_9x16", "square_1x1"]
    )
    repetitions: int = 3
    mock_max_dim: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
