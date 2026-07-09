"""Music & Audio Mixing Engine configuration schema (Phase C8).

Layered on :class:`foundation.config.ConfigLoader` like every other engine:
packaged ``defaults.yaml`` <- optional user file <- ``AICP__music__*`` env
<- explicit overrides. Supplies the deterministic mixing knobs the planner and
builder read (music level, ducking, fades, loop, default soundtrack). Pure
configuration — no field here can turn mixing non-deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from foundation.config import ConfigLoader

DEFAULTS_PATH: Path = Path(__file__).resolve().parent / "defaults.yaml"


@dataclass(frozen=True)
class MusicEngineConfig:
    """Complete, validated Music & Audio Mixing Engine configuration."""

    # levels
    volume: float = 0.18
    track_gain: float = 1.0
    default_soundtrack: str = "ambient"
    # ducking
    ducking_enabled: bool = True
    ducking_level: float = 0.35
    ducking_attack_s: float = 0.25
    ducking_release_s: float = 0.60
    ducking_pad_s: float = 0.15
    # fades
    fade_in_s: float = 1.5
    fade_out_s: float = 2.0
    fade_curve: str = "linear"
    # loop
    loop_enabled: bool = True
    loop_crossfade_s: float = 0.5

    def __post_init__(self) -> None:
        if not (0.0 <= self.volume <= 1.0):
            raise ValueError(f"music.volume must be in [0, 1], got {self.volume}")
        if self.track_gain < 0:
            raise ValueError(f"music.track_gain must be non-negative, got {self.track_gain}")
        if not (0.0 <= self.ducking_level <= 1.0):
            raise ValueError(f"music.ducking.level must be in [0, 1], got {self.ducking_level}")
        for name in ("fade_in_s", "fade_out_s", "loop_crossfade_s",
                     "ducking_attack_s", "ducking_release_s", "ducking_pad_s"):
            if getattr(self, name) < 0:
                raise ValueError(f"music.{name} must be non-negative, got {getattr(self, name)}")

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "MusicEngineConfig":
        m = mapping.get("music", {}) or {}
        duck = m.get("ducking", {}) or {}
        fade = m.get("fade", {}) or {}
        loop = m.get("loop", {}) or {}
        return cls(
            volume=m.get("volume", 0.18),
            track_gain=m.get("track_gain", 1.0),
            default_soundtrack=m.get("default_soundtrack", "ambient"),
            ducking_enabled=duck.get("enabled", True),
            ducking_level=duck.get("level", 0.35),
            ducking_attack_s=duck.get("attack_s", 0.25),
            ducking_release_s=duck.get("release_s", 0.60),
            ducking_pad_s=duck.get("pad_s", 0.15),
            fade_in_s=fade.get("fade_in_s", 1.5),
            fade_out_s=fade.get("fade_out_s", 2.0),
            fade_curve=fade.get("curve", "linear"),
            loop_enabled=loop.get("enabled", True),
            loop_crossfade_s=loop.get("crossfade_s", 0.5),
        )


def load_music_engine_config(
    config_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
    apply_env_vars: bool = True,
) -> MusicEngineConfig:
    """Load the layered Music & Audio Mixing Engine configuration."""
    loader = ConfigLoader(
        defaults_path=DEFAULTS_PATH,
        environment_path=config_path,
        apply_env_vars=apply_env_vars,
    )
    return MusicEngineConfig.from_mapping(loader.load(overrides))
