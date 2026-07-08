"""Branding Engine facade (Phase C5).

The high-level, reusable API: turn a theme + brand facts into a validated,
Timeline-native :class:`BrandingTrack`. It wires two pieces —

    theme resolution  →  builder

— and nothing else. It generates *data* (a branding track); rendering is a
separate concern (the renderer lowers the track to overlays).

Everything is configuration-driven and deterministic: no ASR, no models, no I/O
beyond resolving the logo path, so ``generate`` is reproducible and hermetic.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from foundation.logging import get_logger
from reel_engine.interfaces.types import AssetRef, BrandingTrack, Theme

from branding_engine.config.settings import (
    BrandingEngineConfig,
    load_branding_engine_config,
)
from branding_engine.themes.presets import get_theme
from branding_engine.timeline.builder import build_branding_track

logger = get_logger("branding_engine")


class BrandingEngine:
    """Theme + brand facts -> a validated, styled BrandingTrack."""

    def __init__(self, config: BrandingEngineConfig | None = None) -> None:
        self.config = config or load_branding_engine_config()

    def resolve_theme(self, name: str | None = None, overrides: dict | None = None) -> Theme:
        """A concrete theme = preset base + config overrides + call overrides."""
        base = get_theme(name or self.config.theme)
        merged = {**self.config.theme_overrides, **(overrides or {})}
        return dataclasses.replace(base, **merged) if merged else base

    def generate(
        self,
        *,
        reel_duration_s: float | None = None,
        theme: Theme | str | None = None,
        theme_overrides: dict | None = None,
        creator: str | None = None,
        channel: str | None = None,
        website: str | None = None,
        handles: tuple | None = None,
        logo_path: Path | str | None = None,
        track_id: str = "branding",
    ) -> BrandingTrack:
        """Produce a branding track from the theme + brand facts.

        Component inclusion and per-component text/timing come from config
        (``components``/``intro``/``outro``/``lower_third``); anything passed
        explicitly wins. ``theme`` may be a preset name or a concrete Theme.
        """
        cfg = self.config
        if isinstance(theme, Theme):
            resolved_theme = theme
        else:
            resolved_theme = self.resolve_theme(theme, theme_overrides)

        logo_src = None
        chosen_logo = logo_path if logo_path is not None else cfg.logo
        if chosen_logo:
            logo_src = AssetRef(kind="file", uri=str(chosen_logo))

        handles = tuple(handles) if handles is not None else tuple(cfg.social)

        track = build_branding_track(
            resolved_theme,
            creator=creator if creator is not None else cfg.creator,
            channel=channel if channel is not None else cfg.channel,
            website=website if website is not None else cfg.website,
            handles=handles,
            logo_source=logo_src,
            reel_duration_s=reel_duration_s,
            include_logo=cfg.component_enabled("logo"),
            include_watermark=cfg.component_enabled("watermark"),
            include_intro=cfg.component_enabled("intro"),
            include_outro=cfg.component_enabled("outro"),
            include_lower_third=cfg.component_enabled("lower_third"),
            intro_title=cfg.intro.get("title"),
            intro_subtitle=cfg.intro.get("subtitle"),
            intro_duration_s=cfg.intro.get("duration_s"),
            outro_title=cfg.outro.get("title"),
            outro_subtitle=cfg.outro.get("subtitle"),
            outro_duration_s=cfg.outro.get("duration_s"),
            lower_third_title=cfg.lower_third.get("title"),
            lower_third_subtitle=cfg.lower_third.get("subtitle"),
            lower_third_start_s=cfg.lower_third.get("start_s", 1.0),
            lower_third_duration_s=cfg.lower_third.get("duration_s", 3.0),
            track_id=track_id,
        )
        logger.info("Branding generated", extra={"context": {
            "theme": resolved_theme.name,
            "intro": track.intro is not None, "outro": track.outro is not None,
            "logo": track.logo is not None, "watermark": track.watermark is not None,
            "lower_thirds": len(track.lower_thirds)}})
        return track
