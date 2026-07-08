"""End-to-end pipeline configuration schema (Phase C3 walking skeleton).

Layered on :class:`foundation.config.ConfigLoader` exactly like the Reels and
Voice engines: packaged ``defaults.yaml`` <- optional user file <- ``AICP__..``
env vars <- explicit overrides. Selecting the voice model, avatar model,
resolution, fps, renderer, or export set is a configuration change, never a code
change.

The ``render``/``export`` sections deliberately reuse the Reels Engine
:class:`RenderConfig`/:class:`ExportConfig` dataclasses so there is a single
source of truth for codec/resolution settings, and :meth:`PipelineConfig.reel_config`
hands them straight to the renderer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from foundation.config import ConfigLoader
from reel_engine.config.settings import ExportConfig, ReelEngineConfig, RenderConfig

#: Packaged defaults + the demo reference face shipped with the orchestrator.
DEFAULTS_PATH: Path = Path(__file__).resolve().parent / "defaults.yaml"
ASSETS_DIR: Path = Path(__file__).resolve().parent / "assets"
DEMO_FACE_PATH: Path = ASSETS_DIR / "reference_face.png"
DEMO_SCRIPT_PATH: Path = ASSETS_DIR / "script.txt"


@dataclass(frozen=True)
class VoiceStageConfig:
    """Voice Engine selection for the pipeline's first stage."""

    model: str = "kokoro"       # "kokoro" (default) | "chatterbox" | "mock"
    language: str = "en"
    speed: float = 1.0
    device: str = "auto"


@dataclass(frozen=True)
class AvatarStageConfig:
    """Avatar Engine selection for the pipeline's second stage."""

    model: str = "musetalk"     # "musetalk" (default) | "latentsync" | "mock"
    device: str = "auto"


@dataclass(frozen=True)
class PipelineConfig:
    """Complete, validated end-to-end pipeline configuration."""

    voice: VoiceStageConfig = field(default_factory=VoiceStageConfig)
    avatar: AvatarStageConfig = field(default_factory=AvatarStageConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    reference_face: str | None = None
    output_dir: str | None = None

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "PipelineConfig":
        return cls(
            voice=ConfigLoader.bind(mapping.get("voice", {}), VoiceStageConfig),
            avatar=ConfigLoader.bind(mapping.get("avatar", {}), AvatarStageConfig),
            render=ConfigLoader.bind(mapping.get("render", {}), RenderConfig),
            export=ConfigLoader.bind(mapping.get("export", {}), ExportConfig),
            reference_face=mapping.get("reference_face"),
            output_dir=mapping.get("output_dir"),
        )

    def reel_config(self) -> ReelEngineConfig:
        """The Reels Engine configuration the renderer consumes (shared schema)."""
        return ReelEngineConfig(render=self.render, export=self.export,
                                output_dir=self.output_dir)

    def resolved_reference(self) -> Path:
        """Reference face/video path, falling back to the packaged demo face."""
        return Path(self.reference_face) if self.reference_face else DEMO_FACE_PATH

    def resolved_output_dir(self) -> Path:
        """Directory finished reels land in (defaults to orchestrator/output)."""
        if self.output_dir:
            return Path(self.output_dir)
        return Path(__file__).resolve().parent / "output"


def load_pipeline_config(
    config_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
    apply_env_vars: bool = True,
) -> PipelineConfig:
    """Load the layered end-to-end pipeline configuration."""
    loader = ConfigLoader(
        defaults_path=DEFAULTS_PATH,
        environment_path=config_path,
        apply_env_vars=apply_env_vars,
    )
    return PipelineConfig.from_mapping(loader.load(overrides))
