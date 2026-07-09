"""AI Prompt & Storyboard Engine benchmark configuration (Phase C10)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

#: A fixed prompt set (deterministic workload; MockProvider needs no key).
_PROMPTS = (
    "Why investing in real estate early is beneficial",
    "How compound interest builds wealth over time",
    "Three habits that improve your daily focus",
)


@dataclass
class ScriptBenchmarkConfig:
    """One benchmark run: a fixed, deterministic prompt->reel workload.

    Uses the MockProvider so the benchmark is hermetic and pure-CPU (no network,
    no API key, no model). Wall-clock timings are not deterministic; the workload
    is.
    """

    provider: str = "mock"
    template: str = "general"
    prompts: tuple = field(default_factory=lambda: _PROMPTS)
    width: int = 1080
    height: int = 1920
    fps: int = 30
    repetitions: int = 5

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["prompts"] = list(self.prompts)
        return d
