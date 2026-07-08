"""Caption Engine configuration schema (Phase C4).

Layered on :class:`foundation.config.ConfigLoader` like every other engine:
packaged ``defaults.yaml`` <- optional user file <- ``AICP__captions__*`` env
<- explicit overrides. The config selects the caption ``kind``, a base style
``preset``, an ``animation``, and a set of style overrides; the engine resolves
them into a concrete :class:`CaptionStyle` via ``dataclasses.replace``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from foundation.config import ConfigLoader
from reel_engine.interfaces.types import CaptionAnimation

DEFAULTS_PATH: Path = Path(__file__).resolve().parent / "defaults.yaml"

#: CaptionStyle fields whose YAML value is a list that must become an RGB tuple.
_COLOR_FIELDS = ("primary_color", "highlight_color", "outline_color",
                 "shadow_color", "box_color")


@dataclass(frozen=True)
class CaptionEngineConfig:
    """Complete, validated Caption Engine configuration."""

    kind: str = "sentence"
    preset: str = "classic"
    animation_kind: str = "none"
    animation_duration_s: float = 0.2
    #: Partial CaptionStyle overrides applied on top of ``preset``.
    style_overrides: dict = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "CaptionEngineConfig":
        c = mapping.get("captions", {})
        anim = c.get("animation", {}) or {}
        raw_style = c.get("style", {}) or {}
        overrides = {k: (tuple(v) if k in _COLOR_FIELDS else v)
                     for k, v in raw_style.items()}
        return cls(
            kind=c.get("kind", "sentence"),
            preset=c.get("preset", "classic"),
            animation_kind=anim.get("kind", "none"),
            animation_duration_s=anim.get("duration_s", 0.2),
            style_overrides=overrides,
        )

    def animation(self) -> CaptionAnimation:
        return CaptionAnimation(kind=self.animation_kind,
                                duration_s=self.animation_duration_s)


def load_caption_engine_config(
    config_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
    apply_env_vars: bool = True,
) -> CaptionEngineConfig:
    """Load the layered Caption Engine configuration."""
    loader = ConfigLoader(
        defaults_path=DEFAULTS_PATH,
        environment_path=config_path,
        apply_env_vars=apply_env_vars,
    )
    return CaptionEngineConfig.from_mapping(loader.load(overrides))
