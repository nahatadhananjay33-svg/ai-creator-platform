"""Scene Engine configuration schema (Phase C7).

Layered on :class:`foundation.config.ConfigLoader` like every other engine:
packaged ``defaults.yaml`` <- optional user file <- ``AICP__scene__*`` env
<- explicit overrides. Supplies the deterministic knobs the splitter, the timing
estimator, and the visual planner read (pace, scene caps, preferred mix, caption
defaults). Pure configuration — no field here can turn planning non-deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from foundation.config import ConfigLoader

DEFAULTS_PATH: Path = Path(__file__).resolve().parent / "defaults.yaml"


@dataclass(frozen=True)
class SceneEngineConfig:
    """Complete, validated Scene Planning Engine configuration."""

    # speech / timing
    words_per_minute: float = 150.0
    speech_min_s: float = 0.8
    speech_max_s: float = 30.0
    transition_s: float = 0.0
    # scene splitting
    max_scene_duration_s: float = 8.0
    min_scene_duration_s: float = 1.5
    max_words_per_scene: int = 30
    min_words_per_scene: int = 3
    explanation_min_words: int = 24
    # preferred beat durations
    preferred_cta_duration_s: float = 3.0
    preferred_outro_duration_s: float = 3.0
    # preferred visual mix
    preferred_avatar_pct: float = 0.6
    preferred_talking_head_pct: float = 0.5
    preferred_broll_pct: float = 0.35
    # preferred layouts
    default_asset_layout: str = "full_screen"
    pip_layout: str = "picture_in_picture"
    pip_scale: float = 0.30
    comparison_layout: str = "side_by_side"
    # captions
    caption_kind: str = "sentence"
    caption_preset: str = "clean"

    def __post_init__(self) -> None:
        if self.words_per_minute <= 0:
            raise ValueError(f"words_per_minute must be positive, got {self.words_per_minute}")
        if self.max_words_per_scene < 1:
            raise ValueError(f"max_words_per_scene must be >= 1, got {self.max_words_per_scene}")
        if self.max_scene_duration_s <= 0:
            raise ValueError(f"max_scene_duration_s must be positive, got {self.max_scene_duration_s}")
        if self.min_scene_duration_s < 0:
            raise ValueError(f"min_scene_duration_s must be >= 0, got {self.min_scene_duration_s}")

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "SceneEngineConfig":
        s = mapping.get("scene", {}) or {}
        return cls(
            words_per_minute=s.get("words_per_minute", 150.0),
            speech_min_s=s.get("speech_min_s", 0.8),
            speech_max_s=s.get("speech_max_s", 30.0),
            transition_s=s.get("transition_s", 0.0),
            max_scene_duration_s=s.get("max_scene_duration_s", 8.0),
            min_scene_duration_s=s.get("min_scene_duration_s", 1.5),
            max_words_per_scene=s.get("max_words_per_scene", 30),
            min_words_per_scene=s.get("min_words_per_scene", 3),
            explanation_min_words=s.get("explanation_min_words", 24),
            preferred_cta_duration_s=s.get("preferred_cta_duration_s", 3.0),
            preferred_outro_duration_s=s.get("preferred_outro_duration_s", 3.0),
            preferred_avatar_pct=s.get("preferred_avatar_pct", 0.6),
            preferred_talking_head_pct=s.get("preferred_talking_head_pct", 0.5),
            preferred_broll_pct=s.get("preferred_broll_pct", 0.35),
            default_asset_layout=s.get("default_asset_layout", "full_screen"),
            pip_layout=s.get("pip_layout", "picture_in_picture"),
            pip_scale=s.get("pip_scale", 0.30),
            comparison_layout=s.get("comparison_layout", "side_by_side"),
            caption_kind=s.get("caption_kind", "sentence"),
            caption_preset=s.get("caption_preset", "clean"),
        )


def load_scene_engine_config(
    config_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
    apply_env_vars: bool = True,
) -> SceneEngineConfig:
    """Load the layered Scene Planning Engine configuration."""
    loader = ConfigLoader(
        defaults_path=DEFAULTS_PATH,
        environment_path=config_path,
        apply_env_vars=apply_env_vars,
    )
    return SceneEngineConfig.from_mapping(loader.load(overrides))
