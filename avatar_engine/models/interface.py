"""Avatar generation interface types.

Mirrors ``voice_engine.interfaces``: a request/result pair plus an abstract
engine. Every avatar model — reenactment, talking head, or lip-sync — is
driven through the same interface so the benchmark and future production
pipelines stay adapter-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from foundation.model_manager import ModelSpec


@dataclass(frozen=True)
class GenerationRequest:
    """One avatar generation job.

    Which inputs are required depends on the adapter's task:
    - audio-driven models need ``source_image`` + ``driving_audio``
    - reenactment models need ``source_image`` + ``driving_video``
    - lip-sync models need ``driving_video`` (template) + ``driving_audio``
    """

    source_image: Path | None = None
    driving_audio: Path | None = None
    driving_video: Path | None = None
    output_path: Path | None = None
    scenario_id: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """Outcome of one generation, self-reported by the adapter."""

    video_path: Path
    engine_id: str
    generation_time_s: float
    duration_s: float
    fps: float
    width: int
    height: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def real_time_factor(self) -> float | None:
        """Generation seconds per second of output video (lower is better)."""
        if self.duration_s <= 0:
            return None
        return self.generation_time_s / self.duration_s


class AvatarGenerator(ABC):
    """Abstract avatar generation engine."""

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Platform-unique model id (matches the research catalog)."""

    @property
    @abstractmethod
    def spec(self) -> ModelSpec:
        """Static model metadata (single source of truth)."""

    @abstractmethod
    def is_available(self) -> bool:
        """True when the adapter's dependencies are importable here."""

    @abstractmethod
    def load(self) -> None:
        """Load weights (lazy; idempotent)."""

    @abstractmethod
    def unload(self) -> None:
        """Release model memory."""

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Run one generation job and return the produced video."""
