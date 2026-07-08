"""Branding & Theme Engine (Phase C5) — Timeline-native branding.

Turns a theme + brand facts (creator/channel/website/handles/logo) into a
validated ``BrandingTrack`` that lives natively in the Timeline IR. The renderer
simply lowers branding tracks to overlays; logos/cards are never hardcoded in it.

Pipeline:  theme -> BrandingTrack -> Timeline -> renderer -> MP4

Public API:
- :class:`BrandingEngine` — the facade (theme + brand facts -> BrandingTrack)
- :class:`BrandingEngineConfig` / :func:`load_branding_engine_config` — configuration
- theme presets in :mod:`branding_engine.themes`
- the builder in :mod:`branding_engine.timeline`
- packaged assets in :mod:`branding_engine.assets`

The frozen branding IR types (Theme/BrandingTrack/Logo/Watermark/LowerThird/
Intro/Outro/BrandingElement) live in ``reel_engine.interfaces`` — the single
Timeline contract.
"""
from __future__ import annotations

from branding_engine.config.settings import (
    BrandingEngineConfig,
    load_branding_engine_config,
)
from branding_engine.engine import BrandingEngine
from branding_engine.themes import get_theme, theme_names
from branding_engine.timeline import build_branding_track

__version__ = "1.0.0"

__all__ = [
    "BrandingEngine",
    "BrandingEngineConfig",
    "load_branding_engine_config",
    "get_theme",
    "theme_names",
    "build_branding_track",
]
