"""Workflow benchmark configuration (Phase C14)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkflowBenchmarkConfig:
    """A fixed, hermetic workload for the workflow benchmark (mock voice + renderer)."""

    prompt: str = "Why investing in real estate early is beneficial"
    template: str = "real_estate"
    provider: str = "mock"
    voice_model: str = "mock"
    renderer: str = "mock"
    profiles: tuple[str, ...] = ("reel_9x16", "square_1x1")
    rebuild_stage: str = "editing"          # the stage forced for the incremental measurement
    repetitions: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt, "template": self.template, "provider": self.provider,
            "voice_model": self.voice_model, "renderer": self.renderer,
            "profiles": list(self.profiles), "rebuild_stage": self.rebuild_stage,
            "repetitions": self.repetitions,
        }


#: The stage-execution timings surfaced individually in the text summary.
REPORTED_STAGES: tuple[str, ...] = (
    "storyboard", "voice", "media_intel", "editing", "timeline", "render", "export")
