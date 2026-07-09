"""Scene planning benchmark configuration (Phase C7)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SceneBenchmarkConfig:
    """One benchmark run: a fixed, deterministic planning workload.

    The workload (script size, resolution) is deterministic; wall-clock timings
    are not. Planning is pure CPU and needs no FFmpeg, GPU, model, or network —
    the benchmark is fully hermetic.

    ``script_repeats`` scales the input: a fixed ~10-scene base script repeated N
    times, so throughput is measured on a realistically sized script.
    """

    script_repeats: int = 8
    width: int = 1080
    height: int = 1920
    fps: int = 30
    with_captions: bool = True
    repetitions: int = 5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
