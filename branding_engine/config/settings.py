"""Branding Engine configuration schema (Phase C5).

Layered on :class:`foundation.config.ConfigLoader` like every other engine:
packaged ``defaults.yaml`` <- optional user file <- ``AICP__branding__*`` env
<- explicit overrides. The config selects a theme, the brand facts, a logo, a
set of theme overrides, which components appear, and per-component overrides;
the engine resolves them into a concrete :class:`Theme` + :class:`BrandingTrack`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from foundation.config import ConfigLoader

DEFAULTS_PATH: Path = Path(__file__).resolve().parent / "defaults.yaml"

#: Theme fields whose YAML value is a list that must become an RGB tuple.
_COLOR_FIELDS = ("primary_color", "secondary_color", "text_color", "background_color")


@dataclass(frozen=True)
class BrandingEngineConfig:
    """Complete, validated Branding Engine configuration."""

    theme: str = "classic"
    creator: str = "Creator Name"
    channel: str = "My Channel"
    website: str = "example.com"
    social: tuple = ("@mychannel",)
    logo: str | None = None
    #: Partial Theme overrides applied on top of the preset.
    theme_overrides: dict = field(default_factory=dict)
    #: Which components to include (intro/outro/logo/watermark/lower_third).
    components: dict = field(default_factory=dict)
    #: Per-component text/timing overrides.
    intro: dict = field(default_factory=dict)
    outro: dict = field(default_factory=dict)
    lower_third: dict = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "BrandingEngineConfig":
        b = mapping.get("branding", {}) or {}
        overrides: dict[str, Any] = {}
        for key in ("font_family", *_COLOR_FIELDS, "watermark_opacity",
                    "safe_margin_v", "safe_margin_h"):
            val = b.get(key)
            if val is not None:
                overrides[key] = tuple(val) if key in _COLOR_FIELDS else val
        social = b.get("social") or ()
        return cls(
            theme=b.get("theme", "classic"),
            creator=b.get("creator", ""),
            channel=b.get("channel", ""),
            website=b.get("website", ""),
            social=tuple(social),
            logo=b.get("logo"),
            theme_overrides=overrides,
            components=dict(b.get("components", {}) or {}),
            intro=dict(b.get("intro", {}) or {}),
            outro=dict(b.get("outro", {}) or {}),
            lower_third=dict(b.get("lower_third", {}) or {}),
        )

    def component_enabled(self, name: str, default: bool = True) -> bool:
        return bool(self.components.get(name, default))


def load_branding_engine_config(
    config_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
    apply_env_vars: bool = True,
) -> BrandingEngineConfig:
    """Load the layered Branding Engine configuration."""
    loader = ConfigLoader(
        defaults_path=DEFAULTS_PATH,
        environment_path=config_path,
        apply_env_vars=apply_env_vars,
    )
    return BrandingEngineConfig.from_mapping(loader.load(overrides))
