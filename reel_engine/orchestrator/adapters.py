"""Pipeline stage adapters (Phase C3 walking skeleton).

Thin seams between the orchestrator and the existing engines. Each stage is a
tiny :class:`typing.Protocol` plus one engine-backed implementation:

- :class:`EngineVoiceStage` wraps :class:`voice_engine.VoiceEngine` (Kokoro by
  default, Chatterbox/mock by config) to turn text into a WAV.
- :class:`EngineAvatarStage` wraps ``avatar_engine.models.create_adapter``
  (MuseTalk by default, LatentSync/mock by config) to turn a reference +
  WAV into a talking-head video.

The protocols exist so the pipeline's regression tests can inject deterministic
fakes without importing a single model. No TTS or avatar logic is reimplemented
here — these adapters only translate the orchestrator's request/result shape to
each engine's own API and back.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from foundation.logging import get_logger

from reel_engine.orchestrator.config import AvatarStageConfig, VoiceStageConfig

logger = get_logger("reel_engine.orchestrator.adapters")


# --------------------------------------------------------------------- results
@dataclass(frozen=True)
class VoiceResult:
    """Outcome of the voice stage."""

    audio_path: Path
    sample_rate: int
    duration_s: float
    engine_id: str


@dataclass(frozen=True)
class AvatarResult:
    """Outcome of the avatar stage."""

    video_path: Path
    duration_s: float
    fps: float
    width: int
    height: int
    engine_id: str


# ------------------------------------------------------------------- protocols
class VoiceStage(Protocol):
    """Text -> speech WAV."""

    def synthesize(self, text: str, output_path: Path) -> VoiceResult: ...


class AvatarStage(Protocol):
    """(reference, speech WAV) -> talking-head video."""

    def generate(self, reference: Path, audio_path: Path,
                 output_path: Path) -> AvatarResult: ...


# ---------------------------------------------------------------- voice adapter
class EngineVoiceStage:
    """Voice stage backed by the production :class:`VoiceEngine` routing system."""

    def __init__(self, config: VoiceStageConfig) -> None:
        self.config = config

    def synthesize(self, text: str, output_path: Path) -> VoiceResult:
        # Imported lazily so the orchestrator package imports with no TTS deps.
        from voice_engine import VoiceEngine

        engine = VoiceEngine(overrides={"engine": {
            "default_model": self.config.model, "device": self.config.device}})
        logger.info("Synthesizing speech", extra={"context": {
            "model": self.config.model, "chars": len(text)}})
        result = engine.generate(
            text=text,
            language=self.config.language,
            speed=self.config.speed,
            model_id=self.config.model,
            output_path=output_path,
            use_cache=False,
        )
        return VoiceResult(
            audio_path=Path(result.audio_path),
            sample_rate=result.sample_rate,
            duration_s=result.audio_duration_s,
            engine_id=result.engine_id,
        )


# --------------------------------------------------------------- avatar adapter
class EngineAvatarStage:
    """Avatar stage backed by ``avatar_engine.models.create_adapter``.

    The reference asset is routed to the input the chosen adapter declares:
    image-driven models (MuseTalk, mock) receive it as ``source_image``,
    video-driven models (LatentSync) as ``driving_video`` — so one config field
    (``reference_face``) works across model families with no orchestrator branch.
    """

    def __init__(self, config: AvatarStageConfig) -> None:
        self.config = config

    def generate(self, reference: Path, audio_path: Path,
                 output_path: Path) -> AvatarResult:
        from avatar_engine.models.interface import GenerationRequest
        from avatar_engine.models.registry import create_adapter

        adapter = create_adapter(self.config.model, device=self.config.device)
        req_kwargs: dict[str, Path] = {"driving_audio": audio_path,
                                       "output_path": output_path}
        required = getattr(adapter, "REQUIRED_INPUTS", ("source_image", "driving_audio"))
        if "source_image" in required:
            req_kwargs["source_image"] = reference
        if "driving_video" in required:
            req_kwargs["driving_video"] = reference
        logger.info("Generating talking head", extra={"context": {
            "model": self.config.model, "reference": reference.name}})
        result = adapter.generate(GenerationRequest(**req_kwargs))
        return AvatarResult(
            video_path=Path(result.video_path),
            duration_s=result.duration_s,
            fps=result.fps,
            width=result.width,
            height=result.height,
            engine_id=result.engine_id,
        )
