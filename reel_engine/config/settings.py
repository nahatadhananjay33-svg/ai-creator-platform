"""Reels Engine configuration schema (Phase C2).

Layered on :class:`foundation.config.ConfigLoader` exactly like the Voice
Engine: packaged ``defaults.yaml`` <- optional user file <- ``AICP__section__key``
env vars <- explicit overrides. Switching the render backend, resolution, or
export set is a configuration change, never a code change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from foundation.config import ConfigLoader

DEFAULTS_PATH: Path = Path(__file__).resolve().parent / "defaults.yaml"


@dataclass(frozen=True)
class RenderConfig:
    """Master-render settings (resolution, timing, codecs, text)."""

    width: int = 1080
    height: int = 1920
    fps: int = 30
    codec: str = "libx264"
    pix_fmt: str = "yuv420p"
    bitrate: str = "6M"
    audio_codec: str = "aac"
    audio_sample_rate: int = 44100
    renderer: str = "ffmpeg"
    font_size: int = 96
    text_color: str = "#FFFFFF"
    mock_max_dim: int = 160


@dataclass(frozen=True)
class ExportConfig:
    """Which platform/aspect profiles to emit from the master."""

    profiles: list[str] = field(
        default_factory=lambda: ["reel_9x16", "square_1x1", "landscape_16x9"]
    )


@dataclass(frozen=True)
class ReelEngineConfig:
    """Complete, validated Reels Engine configuration."""

    render: RenderConfig = field(default_factory=RenderConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    output_dir: str | None = None

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "ReelEngineConfig":
        return cls(
            render=ConfigLoader.bind(mapping.get("render", {}), RenderConfig),
            export=ConfigLoader.bind(mapping.get("export", {}), ExportConfig),
            output_dir=mapping.get("output_dir"),
        )


def load_reel_engine_config(
    config_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
    apply_env_vars: bool = True,
) -> ReelEngineConfig:
    """Load the layered Reels Engine configuration."""
    loader = ConfigLoader(
        defaults_path=DEFAULTS_PATH,
        environment_path=config_path,
        apply_env_vars=apply_env_vars,
    )
    return ReelEngineConfig.from_mapping(loader.load(overrides))
