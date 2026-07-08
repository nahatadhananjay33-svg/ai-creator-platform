"""Visual Asset Engine configuration schema (Phase C6).

Layered on :class:`foundation.config.ConfigLoader` like every other engine:
packaged ``defaults.yaml`` <- optional user file <- ``AICP__assets__*`` env
<- explicit overrides. Supplies the defaults the builder falls back to when an
:class:`AssetSpec` leaves a field unset (layout, animation, duration, opacity,
safe margins, PIP size).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from foundation.config import ConfigLoader

DEFAULTS_PATH: Path = Path(__file__).resolve().parent / "defaults.yaml"


@dataclass(frozen=True)
class AssetEngineConfig:
    """Complete, validated Visual Asset Engine configuration."""

    default_layout: str = "full_screen"
    default_duration_s: float = 3.0
    overlay_opacity: float = 1.0
    safe_margin_v: float = 0.06
    safe_margin_h: float = 0.05
    pip_scale: float = 0.30
    pip_corner: str = "bottom_right"
    pip_margin: float = 0.05
    animation_in: str = "fade_in"
    animation_out: str = "fade_out"
    animation_duration_s: float = 0.4
    transition: str = "cut"

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "AssetEngineConfig":
        a = mapping.get("assets", {}) or {}
        pip = a.get("picture_in_picture", {}) or {}
        anim = a.get("animation", {}) or {}
        return cls(
            default_layout=a.get("default_layout", "full_screen"),
            default_duration_s=a.get("default_duration_s", 3.0),
            overlay_opacity=a.get("overlay_opacity", 1.0),
            safe_margin_v=a.get("safe_margin_v", 0.06),
            safe_margin_h=a.get("safe_margin_h", 0.05),
            pip_scale=pip.get("scale", 0.30),
            pip_corner=pip.get("corner", "bottom_right"),
            pip_margin=pip.get("margin", 0.05),
            animation_in=anim.get("kind_in", "fade_in"),
            animation_out=anim.get("kind_out", "fade_out"),
            animation_duration_s=anim.get("duration_s", 0.4),
            transition=a.get("transition", "cut"),
        )


def load_asset_engine_config(
    config_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
    apply_env_vars: bool = True,
) -> AssetEngineConfig:
    """Load the layered Visual Asset Engine configuration."""
    loader = ConfigLoader(
        defaults_path=DEFAULTS_PATH,
        environment_path=config_path,
        apply_env_vars=apply_env_vars,
    )
    return AssetEngineConfig.from_mapping(loader.load(overrides))
