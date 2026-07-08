"""Caption benchmark configuration (Phase C4)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

#: A fixed, representative script so the workload is deterministic.
DEFAULT_TEXT = (
    "Welcome to the AI Creator Platform. Captions are now a native timeline "
    "track. They stay in sync with the audio, and export cleanly to SRT and "
    "WebVTT. Enjoy building with them."
)


@dataclass
class CaptionBenchmarkConfig:
    """One benchmark run: a fixed, deterministic caption workload.

    The workload (script, duration, caption kind/style, resolution) is
    deterministic; wall-clock timings are not. Defaults to the hermetic ``mock``
    renderer so the benchmark needs no FFmpeg or GPU.
    """

    renderer: str = "mock"
    text: str = DEFAULT_TEXT
    duration_s: float = 10.0
    kind: str = "karaoke"
    preset: str = "tiktok"
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
